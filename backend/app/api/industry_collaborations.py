"""API routes for Industry collaborations -- a bilateral academia-industry
collaboration proposal/relationship between an INDUSTRY account
(initiator) and a FACULTY or INSTITUTION account (recipient).

Every route uses build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. `industry_id` is always current_user.id for
industry-side routes; `recipient_id` is always current_user.id for
recipient-side routes. Neither is ever read from the request body.

This is NOT a posting entity like industry_projects/industry_trainings/
industry_workshops/industry_mentorship_opportunities -- there is no
publish/close/archive here, only the send/accept/reject/activate/complete/
cancel lifecycle approved for Phase 10E.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    CurrentUser,
    require_collaboration_party,
    require_collaboration_recipient,
    require_industry,
)
from app.core.security import build_user_client
from app.schemas.industry_collaboration import (
    CollaborationCreate,
    CollaborationListResponse,
    CollaborationStatus,
    CollaborationUpdate,
    IndustryCollaboration,
    RecipientResolution,
)
from app.services import industry_collaboration_service

router = APIRouter(prefix="/collaborations", tags=["industry-collaborations"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaboration not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


# ============================================================
# Recipient resolution (industry-side, used by the create form)
# ============================================================


@router.get("/recipients/resolve", response_model=RecipientResolution)
def resolve_recipient(
    identifier: str = Query(min_length=1),
    current_user: CurrentUser = Depends(require_industry),
) -> RecipientResolution:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_collaboration_service.resolve_recipient(client, identifier)
    except Exception as exc:
        raise _server_error("look up that recipient") from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Faculty or Institution account found with that username.",
        )
    return RecipientResolution(**row)


# ============================================================
# Industry side
# ============================================================


@router.get("", response_model=CollaborationListResponse)
def list_collaborations(
    status_filter: CollaborationStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_industry),
) -> CollaborationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_collaboration_service.list_collaborations(
            client, current_user.id, status=status_filter, search=search
        )
    except Exception as exc:
        raise _server_error("load your collaborations") from exc
    return CollaborationListResponse(collaborations=rows)


@router.post("", response_model=IndustryCollaboration, status_code=status.HTTP_201_CREATED)
def create_collaboration(
    body: CollaborationCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryCollaboration:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json")
    try:
        row = industry_collaboration_service.create_collaboration(client, current_user.id, payload)
    except industry_collaboration_service.InvalidRecipientError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("create the collaboration") from exc
    return IndustryCollaboration(**row)


@router.put("/{collaboration_id}", response_model=IndustryCollaboration)
def update_collaboration(
    collaboration_id: UUID,
    body: CollaborationUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryCollaboration:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json", exclude_unset=True)
    try:
        row = industry_collaboration_service.update_collaboration(
            client, current_user.id, str(collaboration_id), payload
        )
    except industry_collaboration_service.NotDraftError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft collaboration can be edited.",
        ) from exc
    except Exception as exc:
        raise _server_error("save the collaboration") from exc
    if row is None:
        raise _not_found()
    return IndustryCollaboration(**row)


@router.post("/{collaboration_id}/send", response_model=IndustryCollaboration)
def send_collaboration(
    collaboration_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryCollaboration:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_collaboration_service.send_collaboration(
            client, current_user.id, str(collaboration_id)
        )
    except industry_collaboration_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft collaboration can be sent.",
        ) from exc
    except Exception as exc:
        raise _server_error("send the collaboration") from exc
    if row is None:
        raise _not_found()
    return IndustryCollaboration(**row)


@router.post("/{collaboration_id}/activate", response_model=IndustryCollaboration)
def activate_collaboration(
    collaboration_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryCollaboration:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_collaboration_service.activate_collaboration(
            client, current_user.id, str(collaboration_id)
        )
    except industry_collaboration_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an accepted collaboration can be activated.",
        ) from exc
    except Exception as exc:
        raise _server_error("activate the collaboration") from exc
    if row is None:
        raise _not_found()
    return IndustryCollaboration(**row)


@router.post("/{collaboration_id}/complete", response_model=IndustryCollaboration)
def complete_collaboration(
    collaboration_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryCollaboration:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_collaboration_service.complete_collaboration(
            client, current_user.id, str(collaboration_id)
        )
    except industry_collaboration_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an active collaboration can be completed.",
        ) from exc
    except Exception as exc:
        raise _server_error("complete the collaboration") from exc
    if row is None:
        raise _not_found()
    return IndustryCollaboration(**row)


@router.post("/{collaboration_id}/cancel", response_model=IndustryCollaboration)
def cancel_collaboration(
    collaboration_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryCollaboration:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_collaboration_service.cancel_collaboration(
            client, current_user.id, str(collaboration_id)
        )
    except industry_collaboration_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This collaboration can no longer be cancelled.",
        ) from exc
    except Exception as exc:
        raise _server_error("cancel the collaboration") from exc
    if row is None:
        raise _not_found()
    return IndustryCollaboration(**row)


# ============================================================
# Recipient side
# ============================================================


@router.get("/incoming", response_model=CollaborationListResponse)
def list_incoming_collaborations(
    status_filter: CollaborationStatus | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_collaboration_recipient),
) -> CollaborationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_collaboration_service.list_incoming_collaborations(
            client, current_user.id, status=status_filter
        )
    except Exception as exc:
        raise _server_error("load your incoming collaborations") from exc
    return CollaborationListResponse(collaborations=rows)


@router.post("/{collaboration_id}/accept", response_model=IndustryCollaboration)
def accept_collaboration(
    collaboration_id: UUID,
    current_user: CurrentUser = Depends(require_collaboration_recipient),
) -> IndustryCollaboration:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_collaboration_service.accept_collaboration(
            client, current_user.id, str(collaboration_id)
        )
    except industry_collaboration_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a sent proposal can be accepted.",
        ) from exc
    except Exception as exc:
        raise _server_error("accept the collaboration") from exc
    if row is None:
        raise _not_found()
    return IndustryCollaboration(**row)


@router.post("/{collaboration_id}/reject", response_model=IndustryCollaboration)
def reject_collaboration(
    collaboration_id: UUID,
    current_user: CurrentUser = Depends(require_collaboration_recipient),
) -> IndustryCollaboration:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_collaboration_service.reject_collaboration(
            client, current_user.id, str(collaboration_id)
        )
    except industry_collaboration_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a sent proposal can be rejected.",
        ) from exc
    except Exception as exc:
        raise _server_error("reject the collaboration") from exc
    if row is None:
        raise _not_found()
    return IndustryCollaboration(**row)


# ============================================================
# Shared detail (either party)
# ============================================================


@router.get("/{collaboration_id}", response_model=IndustryCollaboration)
def get_collaboration(
    collaboration_id: UUID,
    current_user: CurrentUser = Depends(require_collaboration_party),
) -> IndustryCollaboration:
    client = build_user_client(current_user.access_token)
    try:
        if current_user.role == "INDUSTRY":
            row = industry_collaboration_service.get_own_collaboration(
                client, current_user.id, str(collaboration_id)
            )
        else:
            row = industry_collaboration_service.get_incoming_collaboration(
                client, current_user.id, str(collaboration_id)
            )
    except Exception as exc:
        raise _server_error("load the collaboration") from exc
    if row is None:
        raise _not_found()
    return IndustryCollaboration(**row)
