"""API routes for Industry internship management.

Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. The internship owner is always current_user.id;
`industry_id` is never read from the request. Lifecycle changes go
through the dedicated publish/close/archive endpoints, not PUT.

Student-facing internship discovery is NOT part of this module.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.internship import (
    InternshipCreate,
    InternshipListResponse,
    InternshipResponse,
    InternshipStatus,
    InternshipUpdate,
)
from app.services import internship_service

router = APIRouter(prefix="/internships", tags=["internships"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=InternshipListResponse)
def list_internships(
    status_filter: InternshipStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = internship_service.list_internships(
            client, current_user.id, status=status_filter, search=search
        )
    except Exception as exc:
        raise _server_error("load your internships") from exc
    return InternshipListResponse(internships=rows)


@router.post("", response_model=InternshipResponse, status_code=status.HTTP_201_CREATED)
def create_internship(
    body: InternshipCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json")
    skills = payload.pop("skills")
    try:
        row = internship_service.create_internship(client, current_user.id, payload, skills)
    except internship_service.InvalidSkillError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="One or more selected skills are no longer available.",
        ) from exc
    except Exception as exc:
        raise _server_error("create the internship") from exc
    return InternshipResponse(**row)


@router.get("/{internship_id}", response_model=InternshipResponse)
def get_internship(
    internship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = internship_service.get_internship(client, current_user.id, str(internship_id))
    except Exception as exc:
        raise _server_error("load the internship") from exc
    if row is None:
        raise _not_found()
    return InternshipResponse(**row)


@router.put("/{internship_id}", response_model=InternshipResponse)
def update_internship(
    internship_id: UUID,
    body: InternshipUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json", exclude_unset=True)
    skills = payload.pop("skills", None)
    try:
        row = internship_service.update_internship(
            client, current_user.id, str(internship_id), payload, skills
        )
    except internship_service.InvalidSkillError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="One or more selected skills are no longer available.",
        ) from exc
    except Exception as exc:
        raise _server_error("save the internship") from exc
    if row is None:
        raise _not_found()
    return InternshipResponse(**row)


@router.post("/{internship_id}/publish", response_model=InternshipResponse)
def publish_internship(
    internship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = internship_service.publish_internship(client, current_user.id, str(internship_id))
    except internship_service.PublishValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This internship isn't ready to publish. Add: " + ", ".join(exc.missing) + ".",
        ) from exc
    except internship_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft or closed internship can be published.",
        ) from exc
    except Exception as exc:
        raise _server_error("publish the internship") from exc
    if row is None:
        raise _not_found()
    return InternshipResponse(**row)


@router.post("/{internship_id}/close", response_model=InternshipResponse)
def close_internship(
    internship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = internship_service.close_internship(client, current_user.id, str(internship_id))
    except internship_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a published internship can be closed.",
        ) from exc
    except Exception as exc:
        raise _server_error("close the internship") from exc
    if row is None:
        raise _not_found()
    return InternshipResponse(**row)


@router.post("/{internship_id}/archive", response_model=InternshipResponse)
def archive_internship(
    internship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = internship_service.archive_internship(client, current_user.id, str(internship_id))
    except internship_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This internship is already archived.",
        ) from exc
    except Exception as exc:
        raise _server_error("archive the internship") from exc
    if row is None:
        raise _not_found()
    return InternshipResponse(**row)
