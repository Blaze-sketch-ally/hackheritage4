"""API routes for the STUDENT side of Workshop discovery and applying.

Every route is guarded by require_student() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. `student_id` is always current_user.id.

Mirrors app.api.student_opportunities' apply/withdraw shape, over the
standalone `industry_workshops` / `industry_workshop_applications` tables
(024_industry_workshops.sql / 056_workshop_applications.sql) rather than
the unified `applications` table -- Workshops are not part of that model.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_workshop import StudentWorkshop, StudentWorkshopListResponse
from app.schemas.workshop_application import (
    WorkshopApplicationListResponse,
    WorkshopApplicationResponse,
    WorkshopApplyRequest,
)
from app.services import notification_producer, student_workshop_service

router = APIRouter(prefix="/student", tags=["student-workshops"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="This workshop is not available."
    )


def _application_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="We couldn't find that application."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


def _own_name(client: Client, student_id: str) -> str | None:
    """Best-effort: the caller's own full_name, for the industry-facing
    notification body. Always allowed by RLS (a user may always read
    their own profiles row) -- never used to read anyone else's."""
    try:
        response = (
            client.table("profiles")
            .select("full_name")
            .eq("id", student_id)
            .maybe_single()
            .execute()
        )
        row = response.data if response is not None else None
        return row.get("full_name") if row else None
    except Exception:  # noqa: BLE001 -- notification enrichment only
        return None


@router.get("/workshops", response_model=StudentWorkshopListResponse)
def list_workshops(
    search: str | None = Query(default=None, max_length=200),
    current_user: CurrentUser = Depends(require_student),
) -> StudentWorkshopListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_workshop_service.list_workshops(client, current_user.id, search=search)
    except Exception as exc:
        raise _server_error("load workshops") from exc
    return StudentWorkshopListResponse(workshops=[StudentWorkshop(**row) for row in rows])


@router.get("/workshops/{workshop_id}", response_model=StudentWorkshop)
def get_workshop(
    workshop_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> StudentWorkshop:
    client = build_user_client(current_user.access_token)
    try:
        row = student_workshop_service.get_workshop(client, current_user.id, str(workshop_id))
    except Exception as exc:
        raise _server_error("load this workshop") from exc
    if row is None:
        raise _not_found()
    return StudentWorkshop(**row)


@router.post(
    "/workshops/{workshop_id}/applications",
    response_model=WorkshopApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_workshop(
    workshop_id: UUID,
    _body: WorkshopApplyRequest,
    current_user: CurrentUser = Depends(require_student),
) -> WorkshopApplicationResponse:
    client = build_user_client(current_user.access_token)

    try:
        workshop = student_workshop_service.get_workshop(
            client, current_user.id, str(workshop_id)
        )
    except Exception as exc:
        raise _server_error("load this workshop") from exc
    if workshop is None:
        raise _not_found()

    try:
        row = student_workshop_service.apply_to_workshop(
            client, current_user.id, str(workshop_id)
        )
    except student_workshop_service.DuplicateApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this workshop.",
        ) from exc
    except student_workshop_service.WorkshopNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workshop is no longer accepting applications.",
        ) from exc
    except Exception as exc:
        raise _server_error("submit your application") from exc

    # Best-effort: let the owning Industry account know a student applied.
    # Never turns a successful application submission into an error.
    notification_producer.emit_new_application(
        industry_id=row["industry_id"],
        kind="WORKSHOP",
        related_entity_id=row["workshop_id"],
        opportunity_title=workshop.get("title"),
        student_name=_own_name(client, current_user.id),
    )

    return WorkshopApplicationResponse(**row)


@router.get("/workshop-applications", response_model=WorkshopApplicationListResponse)
def list_my_applications(
    current_user: CurrentUser = Depends(require_student),
) -> WorkshopApplicationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_workshop_service.list_my_applications(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your applications") from exc
    return WorkshopApplicationListResponse(
        applications=[WorkshopApplicationResponse(**row) for row in rows]
    )


@router.post(
    "/workshop-applications/{application_id}/withdraw",
    response_model=WorkshopApplicationResponse,
)
def withdraw_application(
    application_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> WorkshopApplicationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_workshop_service.withdraw_application(
            client, current_user.id, str(application_id)
        )
    except student_workshop_service.ApplicationNotWithdrawableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("withdraw this application") from exc
    if row is None:
        raise _application_not_found()

    notification_producer.emit_application_withdrawn(
        industry_id=row["industry_id"],
        kind="WORKSHOP",
        related_entity_id=row["workshop_id"],
        opportunity_title=(row.get("workshop") or {}).get("title"),
        student_name=_own_name(client, current_user.id),
    )

    return WorkshopApplicationResponse(**row)
