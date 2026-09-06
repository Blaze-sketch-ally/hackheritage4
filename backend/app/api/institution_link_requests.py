"""API routes for the student <-> institution linking workflow -- a
bilateral relationship between a STUDENT account (initiator) and an
INSTITUTION account (approver). Same split rationale as
industry_collaborations.py: kept separate from institution.py (which only
holds the institution's own profile/overview) because this table has two
different actors with two different role guards, exactly like
industry_collaborations.py is separate from industry.py.

Every route uses build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. `student_id` is always current_user.id for
student-side routes; `institution_id` is always current_user.id for
institution-side routes. Neither is ever taken from the request body.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_institution, require_student
from app.core.security import build_user_client
from app.schemas.institution_link import (
    InstitutionLinkRequest,
    InstitutionResolution,
    LinkRequestCreate,
    LinkRequestListResponse,
    LinkRequestStatus,
)
from app.services import institution_link_service

router = APIRouter(prefix="/institution-links", tags=["institution-links"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link request not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


# ============================================================
# Resolution (student-side create form)
# ============================================================


@router.get("/resolve", response_model=InstitutionResolution)
def resolve_institution(
    identifier: str = Query(min_length=1),
    current_user: CurrentUser = Depends(require_student),
) -> InstitutionResolution:
    client = build_user_client(current_user.access_token)
    try:
        row = institution_link_service.resolve_institution(client, identifier)
    except Exception as exc:
        raise _server_error("look up that institution") from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Institution account found with that username.",
        )
    return InstitutionResolution(**row)


# ============================================================
# Student side
# ============================================================


@router.get("/mine", response_model=LinkRequestListResponse)
def list_my_requests(
    current_user: CurrentUser = Depends(require_student),
) -> LinkRequestListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = institution_link_service.list_my_requests(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your institution link requests") from exc
    return LinkRequestListResponse(requests=rows)


@router.post("", response_model=InstitutionLinkRequest, status_code=status.HTTP_201_CREATED)
def create_request(
    body: LinkRequestCreate,
    current_user: CurrentUser = Depends(require_student),
) -> InstitutionLinkRequest:
    client = build_user_client(current_user.access_token)
    try:
        row = institution_link_service.create_request(client, current_user.id, body.institution_id)
    except institution_link_service.AlreadyLinkedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except institution_link_service.InvalidInstitutionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("submit your institution link request") from exc
    return InstitutionLinkRequest(**row)


@router.post("/{request_id}/cancel", response_model=InstitutionLinkRequest)
def cancel_request(
    request_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> InstitutionLinkRequest:
    client = build_user_client(current_user.access_token)
    try:
        row = institution_link_service.cancel_own_request(client, current_user.id, str(request_id))
    except institution_link_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a pending request can be cancelled.",
        ) from exc
    except Exception as exc:
        raise _server_error("cancel the request") from exc
    if row is None:
        raise _not_found()
    return InstitutionLinkRequest(**row)


# ============================================================
# Institution side
# ============================================================


@router.get("/incoming", response_model=LinkRequestListResponse)
def list_incoming(
    status_filter: LinkRequestStatus | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_institution),
) -> LinkRequestListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = institution_link_service.list_incoming(client, current_user.id, status=status_filter)
    except Exception as exc:
        raise _server_error("load your institution link requests") from exc
    return LinkRequestListResponse(requests=rows)


@router.post("/{request_id}/approve", response_model=InstitutionLinkRequest)
def approve_request(
    request_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionLinkRequest:
    client = build_user_client(current_user.access_token)
    try:
        row = institution_link_service.approve_request(client, current_user.id, str(request_id))
    except institution_link_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a pending request can be approved.",
        ) from exc
    except Exception as exc:
        raise _server_error("approve the request") from exc
    if row is None:
        raise _not_found()
    return InstitutionLinkRequest(**row)


@router.post("/{request_id}/reject", response_model=InstitutionLinkRequest)
def reject_request(
    request_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionLinkRequest:
    client = build_user_client(current_user.access_token)
    try:
        row = institution_link_service.reject_request(client, current_user.id, str(request_id))
    except institution_link_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a pending request can be rejected.",
        ) from exc
    except Exception as exc:
        raise _server_error("reject the request") from exc
    if row is None:
        raise _not_found()
    return InstitutionLinkRequest(**row)


@router.post("/{request_id}/unlink", response_model=InstitutionLinkRequest)
def unlink_request(
    request_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionLinkRequest:
    client = build_user_client(current_user.access_token)
    try:
        row = institution_link_service.unlink_request(client, current_user.id, str(request_id))
    except institution_link_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an approved (linked) request can be unlinked.",
        ) from exc
    except Exception as exc:
        raise _server_error("unlink the student") from exc
    if row is None:
        raise _not_found()
    return InstitutionLinkRequest(**row)
