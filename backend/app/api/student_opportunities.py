"""API routes for the STUDENT side of opportunity discovery and applying.

Every route is guarded by require_student() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. `student_id` is always current_user.id, never
read from a request body or query parameter.

This is a read adapter over the existing `internships` / `jobs` tables and
a thin writer over the existing `applications` table (020_applications.sql
unchanged): no `opportunities` table, no `opportunity_id` column, no new
status enum. The Industry recruitment pipeline is untouched.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_opportunity import (
    ApplyRequest,
    OpportunityMatchResponse,
    SourceType,
    StudentApplicationListResponse,
    StudentApplicationResponse,
    StudentOpportunityDetail,
    StudentOpportunityListResponse,
    StudentOpportunitySummary,
)
from app.services import student_opportunity_service

router = APIRouter(prefix="/student", tags=["student-opportunities"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="This opportunity is not available."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/opportunities", response_model=StudentOpportunityListResponse)
def list_opportunities(
    source_type: SourceType | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    current_user: CurrentUser = Depends(require_student),
) -> StudentOpportunityListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_opportunity_service.list_opportunities(
            client, current_user.id, source_type=source_type, search=search
        )
    except Exception as exc:
        raise _server_error("load opportunities") from exc
    return StudentOpportunityListResponse(
        opportunities=[StudentOpportunitySummary(**row) for row in rows]
    )


@router.get("/opportunities/{opportunity_id}", response_model=StudentOpportunityDetail)
def get_opportunity(
    opportunity_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> StudentOpportunityDetail:
    client = build_user_client(current_user.access_token)
    try:
        row = student_opportunity_service.get_opportunity(
            client, current_user.id, opportunity_id
        )
    except student_opportunity_service.InvalidOpportunityIdError as exc:
        raise _not_found() from exc
    except Exception as exc:
        raise _server_error("load this opportunity") from exc
    if row is None:
        raise _not_found()
    return StudentOpportunityDetail(**row)


@router.get("/opportunities/{opportunity_id}/match", response_model=OpportunityMatchResponse)
def get_opportunity_match(
    opportunity_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> OpportunityMatchResponse:
    """The caller's own advisory skill fit against one opportunity.
    Deterministic, no LLM, nothing stored. Isolated from Apply -- a
    failure here never blocks applying."""
    client = build_user_client(current_user.access_token)

    try:
        opportunity = student_opportunity_service.get_opportunity(
            client, current_user.id, opportunity_id
        )
    except student_opportunity_service.InvalidOpportunityIdError as exc:
        raise _not_found() from exc
    except Exception as exc:
        raise _server_error("load this opportunity") from exc
    if opportunity is None:
        raise _not_found()

    try:
        result = student_opportunity_service.compute_opportunity_match(
            client, current_user.id, opportunity_id
        )
    except Exception as exc:
        raise _server_error("calculate your match") from exc
    return OpportunityMatchResponse(**result)


@router.post(
    "/opportunities/{opportunity_id}/applications",
    response_model=StudentApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_opportunity(
    opportunity_id: str,
    body: ApplyRequest,
    current_user: CurrentUser = Depends(require_student),
) -> StudentApplicationResponse:
    client = build_user_client(current_user.access_token)

    # Verify the posting is visible/published FIRST (RLS-respecting read),
    # exactly like app.api.assessments.create_attempt -- so a bad id is a
    # clean 404 rather than a smuggled insert attempt.
    try:
        opportunity = student_opportunity_service.get_opportunity(
            client, current_user.id, opportunity_id
        )
    except student_opportunity_service.InvalidOpportunityIdError as exc:
        raise _not_found() from exc
    except Exception as exc:
        raise _server_error("load this opportunity") from exc
    if opportunity is None:
        raise _not_found()

    try:
        row = student_opportunity_service.apply_to_opportunity(
            client, current_user.id, opportunity_id, body.cover_note
        )
    except student_opportunity_service.DuplicateApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this opportunity.",
        ) from exc
    except student_opportunity_service.OpportunityNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This opportunity is no longer accepting applications.",
        ) from exc
    except student_opportunity_service.InvalidOpportunityIdError as exc:
        raise _not_found() from exc
    except Exception as exc:
        raise _server_error("submit your application") from exc
    return StudentApplicationResponse(**row)


@router.get("/applications", response_model=StudentApplicationListResponse)
def list_my_applications(
    current_user: CurrentUser = Depends(require_student),
) -> StudentApplicationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_opportunity_service.list_my_applications(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your applications") from exc
    return StudentApplicationListResponse(
        applications=[StudentApplicationResponse(**row) for row in rows]
    )
