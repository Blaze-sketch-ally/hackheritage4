"""API routes for Industry workshop management.

Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. The workshop owner is always current_user.id;
`industry_id` is never read from the request. Lifecycle changes go
through the dedicated publish/close/archive endpoints, not PUT.

Student-facing workshop discovery/registration is NOT part of this module
(Phase 10C scope -- see database/migrations/024_industry_workshops.sql).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.industry_workshop import (
    WorkshopCreate,
    WorkshopListResponse,
    WorkshopResponse,
    WorkshopStatus,
    WorkshopUpdate,
)
from app.schemas.workshop_application import (
    WorkshopApplicationListResponse,
    WorkshopApplicationResponse,
    WorkshopApplicationStatus,
    WorkshopApplicationStatusUpdate,
)
from app.services import (
    industry_workshop_application_service,
    industry_workshop_service,
    notification_producer,
)

router = APIRouter(prefix="/workshops", tags=["industry-workshops"])


def _application_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Workshop application not found."
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workshop not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=WorkshopListResponse)
def list_workshops(
    status_filter: WorkshopStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_industry),
) -> WorkshopListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_workshop_service.list_workshops(
            client, current_user.id, status=status_filter, search=search
        )
    except Exception as exc:
        raise _server_error("load your workshops") from exc
    return WorkshopListResponse(workshops=rows)


@router.post("", response_model=WorkshopResponse, status_code=status.HTTP_201_CREATED)
def create_workshop(
    body: WorkshopCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> WorkshopResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json")
    try:
        row = industry_workshop_service.create_workshop(client, current_user.id, payload)
    except Exception as exc:
        raise _server_error("create the workshop") from exc
    return WorkshopResponse(**row)


@router.get("/{workshop_id}", response_model=WorkshopResponse)
def get_workshop(
    workshop_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> WorkshopResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_workshop_service.get_workshop(client, current_user.id, str(workshop_id))
    except Exception as exc:
        raise _server_error("load the workshop") from exc
    if row is None:
        raise _not_found()
    return WorkshopResponse(**row)


@router.put("/{workshop_id}", response_model=WorkshopResponse)
def update_workshop(
    workshop_id: UUID,
    body: WorkshopUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> WorkshopResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json", exclude_unset=True)
    try:
        row = industry_workshop_service.update_workshop(
            client, current_user.id, str(workshop_id), payload
        )
    except Exception as exc:
        raise _server_error("save the workshop") from exc
    if row is None:
        raise _not_found()
    return WorkshopResponse(**row)


@router.post("/{workshop_id}/publish", response_model=WorkshopResponse)
def publish_workshop(
    workshop_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> WorkshopResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_workshop_service.publish_workshop(client, current_user.id, str(workshop_id))
    except industry_workshop_service.PublishValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This workshop isn't ready to publish. Add: " + ", ".join(exc.missing) + ".",
        ) from exc
    except industry_workshop_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft or closed workshop can be published.",
        ) from exc
    except Exception as exc:
        raise _server_error("publish the workshop") from exc
    if row is None:
        raise _not_found()
    return WorkshopResponse(**row)


@router.post("/{workshop_id}/close", response_model=WorkshopResponse)
def close_workshop(
    workshop_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> WorkshopResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_workshop_service.close_workshop(client, current_user.id, str(workshop_id))
    except industry_workshop_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a published workshop can be closed.",
        ) from exc
    except Exception as exc:
        raise _server_error("close the workshop") from exc
    if row is None:
        raise _not_found()
    return WorkshopResponse(**row)


@router.post("/{workshop_id}/archive", response_model=WorkshopResponse)
def archive_workshop(
    workshop_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> WorkshopResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_workshop_service.archive_workshop(client, current_user.id, str(workshop_id))
    except industry_workshop_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workshop is already archived.",
        ) from exc
    except Exception as exc:
        raise _server_error("archive the workshop") from exc
    if row is None:
        raise _not_found()
    return WorkshopResponse(**row)


# ============================================================
# Applicants (industry_workshop_applications, 056_workshop_applications.sql)
# ============================================================


@router.get("/{workshop_id}/applications", response_model=WorkshopApplicationListResponse)
def list_workshop_applications(
    workshop_id: UUID,
    status_filter: WorkshopApplicationStatus | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_industry),
) -> WorkshopApplicationListResponse:
    """Students who applied to one of the caller's own workshops. Human-
    readable applicant info (name/institution/department/year/skills) is
    attached server-side -- never a raw student_id."""
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_workshop_application_service.list_applications(
            client, current_user.id, status=status_filter, workshop_id=str(workshop_id)
        )
    except Exception as exc:
        raise _server_error("load applicants") from exc
    return WorkshopApplicationListResponse(applications=rows)


@router.patch(
    "/applications/{application_id}/status", response_model=WorkshopApplicationResponse
)
def update_workshop_application_status(
    application_id: UUID,
    body: WorkshopApplicationStatusUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> WorkshopApplicationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_workshop_application_service.update_status(
            client, current_user.id, str(application_id), body.status
        )
    except industry_workshop_application_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An application at '{exc.current}' can't be moved to '{exc.target}'.",
        ) from exc
    except Exception as exc:
        raise _server_error("update the application") from exc
    if row is None:
        raise _application_not_found()

    notification_producer.emit_workshop_status_change(
        student_id=row["student_id"],
        workshop_id=row["workshop_id"],
        new_status=row["status"],
        workshop_title=(row.get("workshop") or {}).get("title"),
    )

    return WorkshopApplicationResponse(**row)
