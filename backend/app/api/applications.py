"""API routes for the Industry side of applications.

Every route is guarded by require_industry() and every read/write to
`applications` goes through build_user_client(current_user.access_token)
-- never get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. The owning Industry account is always
current_user.id; `industry_id` is never read from the request.

The one service-role touch in this module is a BEST-EFFORT side effect:
after a status change succeeds, `notification_producer` writes the
student a `student_notifications` row (that table has no insert policy, so
only the service role can). It runs on an already-authorized
require_industry() request, swallows its own errors, and never affects the
response -- see app.services.notification_producer.

Industry can list its applications, read one, and move one along the
recruitment status pipeline. It cannot change an application's student,
opportunity, or owner (there is no field for it here, and the database
triggers block it regardless). Student-facing "apply" / "withdraw" flows
are NOT part of this module.
"""

import contextlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.application import (
    ApplicationListResponse,
    ApplicationMatchResponse,
    ApplicationResponse,
    ApplicationStatus,
    ApplicationStatusUpdate,
    ApplicationSummaryResponse,
    OpportunityType,
)
from app.services import application_service, match_service, notification_producer

router = APIRouter(prefix="/applications", tags=["applications"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=ApplicationListResponse)
def list_applications(
    status_filter: ApplicationStatus | None = Query(default=None, alias="status"),
    opportunity_type: OpportunityType | None = Query(default=None),
    internship_id: UUID | None = Query(default=None),
    job_id: UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(require_industry),
) -> ApplicationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = application_service.list_applications(
            client,
            current_user.id,
            status=status_filter,
            opportunity_type=opportunity_type,
            internship_id=str(internship_id) if internship_id else None,
            job_id=str(job_id) if job_id else None,
        )
    except Exception as exc:
        raise _server_error("load applications") from exc
    return ApplicationListResponse(applications=rows)


@router.get("/summary", response_model=ApplicationSummaryResponse)
def get_applications_summary(
    current_user: CurrentUser = Depends(require_industry),
) -> ApplicationSummaryResponse:
    """Per-status counts of the caller's own applications -- the
    recruitment funnel's data source. Declared before /{application_id}
    so the literal path wins the match."""
    client = build_user_client(current_user.access_token)
    try:
        summary = application_service.get_status_summary(client, current_user.id)
    except Exception as exc:
        raise _server_error("load the recruitment summary") from exc
    return ApplicationSummaryResponse(**summary)


@router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(
    application_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ApplicationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = application_service.get_application(client, current_user.id, str(application_id))
    except Exception as exc:
        raise _server_error("load the application") from exc
    if row is None:
        raise _not_found()
    return ApplicationResponse(**row)


@router.get("/{application_id}/match", response_model=ApplicationMatchResponse)
def get_application_match(
    application_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ApplicationMatchResponse:
    """A deterministic, advisory skill-fit summary for one owned
    application: score 0-100, matched / needs-improvement / missing skills,
    coverage, and a recommendation band. No LLM. Never changes the
    application's status. The candidate skill data comes from the
    ownership-checked public.application_skill_match RPC (021).
    """
    client = build_user_client(current_user.access_token)

    try:
        application = application_service.get_application(
            client, current_user.id, str(application_id)
        )
    except Exception as exc:
        raise _server_error("load the application") from exc
    if application is None:
        raise _not_found()

    try:
        rows = application_service.get_skill_match_rows(client, str(application_id))
    except Exception as exc:
        raise _server_error("calculate the match") from exc

    result = match_service.compute_match(str(application_id), rows)

    # Best-effort cache of the server-computed score onto applications.match_score
    # (Phase 8 left the column read-only). Only when the posting actually has
    # requirements -- a "0" for a posting with no required skills would be
    # misleading. A write failure never fails the response.
    if result["required_count"] > 0:
        with contextlib.suppress(Exception):
            application_service.set_match_score(
                client, current_user.id, str(application_id), result["score"]
            )

    return ApplicationMatchResponse(**result)


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
def update_application_status(
    application_id: UUID,
    body: ApplicationStatusUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> ApplicationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = application_service.update_status(
            client, current_user.id, str(application_id), body.status
        )
    except application_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An application at '{exc.current}' can't be moved to '{exc.target}'.",
        ) from exc
    except Exception as exc:
        raise _server_error("update the application") from exc
    if row is None:
        raise _not_found()

    # Best-effort: let the student know their application moved. The
    # producer writes with the service role (student_notifications has no
    # insert policy) and swallows its own errors -- a failed notification
    # never turns a successful status change into an error.
    notification_producer.emit_application_status_change(
        student_id=row["student_id"],
        application_id=str(application_id),
        new_status=row["status"],
        opportunity_title=(row.get("opportunity") or {}).get("title"),
    )

    return ApplicationResponse(**row)
