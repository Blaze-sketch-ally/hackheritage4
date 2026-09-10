"""API routes for the FACULTY side of in-app notifications.

Mirrors app.api.student_notifications exactly. Every route is guarded by
require_faculty() and every read/write goes through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so Supabase RLS stays the real access-control boundary.
The recipient is ALWAYS current_user.id; no `faculty_id` / `recipient_id`
/ `user_id` is ever read from a request body, query, or path.

There is deliberately NO create endpoint. `faculty_notifications` has no
insert policy (066_faculty_notifications.sql), so notifications are only
ever written by trusted system-context code (see
app.services.faculty_notification_producer). The only mutation a Faculty
member can make here is toggling their own read state.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_faculty
from app.core.security import build_user_client
from app.schemas.faculty_notification import (
    FacultyNotification,
    FacultyNotificationListResponse,
    MarkAllReadResponse,
)
from app.services import faculty_notification_service

router = APIRouter(prefix="/faculty", tags=["faculty-notifications"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="This notification is not available."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/notifications", response_model=FacultyNotificationListResponse)
def list_notifications(
    unread: bool = Query(default=False, description="Return only unread notifications."),
    limit: int = Query(
        default=faculty_notification_service.DEFAULT_LIMIT,
        ge=1,
        le=faculty_notification_service.MAX_LIMIT,
    ),
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyNotificationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = faculty_notification_service.list_notifications(
            client, current_user.id, unread_only=unread, limit=limit
        )
        count = faculty_notification_service.unread_count(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your notifications") from exc
    return FacultyNotificationListResponse(
        notifications=[FacultyNotification(**row) for row in rows], unread_count=count
    )


@router.get("/notifications/unread-count")
def get_unread_count(
    current_user: CurrentUser = Depends(require_faculty),
) -> dict[str, int]:
    """A cheap, standalone count -- never fetches rows merely to count
    them. Kept as a plain dict response (no dedicated schema needed for
    one field) since it exists purely so the header bell doesn't need to
    request/parse a full notification list just to render a badge."""
    client = build_user_client(current_user.access_token)
    try:
        count = faculty_notification_service.unread_count(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your unread notification count") from exc
    return {"unread_count": count}


@router.get("/notifications/{notification_id}", response_model=FacultyNotification)
def get_notification(
    notification_id: UUID,
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyNotification:
    client = build_user_client(current_user.access_token)
    try:
        row = faculty_notification_service.get_notification(
            client, current_user.id, str(notification_id)
        )
    except Exception as exc:
        raise _server_error("load this notification") from exc
    if row is None:
        raise _not_found()
    return FacultyNotification(**row)


@router.patch("/notifications/{notification_id}/read", response_model=FacultyNotification)
def mark_notification_read(
    notification_id: UUID,
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyNotification:
    """Mark one of the caller's own notifications read. Empty body -- the
    path identifies the notification, the token identifies the recipient.
    Idempotent."""
    client = build_user_client(current_user.access_token)
    try:
        row = faculty_notification_service.set_read(
            client, current_user.id, str(notification_id), read=True
        )
    except Exception as exc:
        raise _server_error("update this notification") from exc
    if row is None:
        raise _not_found()
    return FacultyNotification(**row)


@router.patch("/notifications/{notification_id}/unread", response_model=FacultyNotification)
def mark_notification_unread(
    notification_id: UUID,
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyNotification:
    """Mark one of the caller's own notifications unread again. Empty body.
    Idempotent."""
    client = build_user_client(current_user.access_token)
    try:
        row = faculty_notification_service.set_read(
            client, current_user.id, str(notification_id), read=False
        )
    except Exception as exc:
        raise _server_error("update this notification") from exc
    if row is None:
        raise _not_found()
    return FacultyNotification(**row)


@router.post("/notifications/read-all", response_model=MarkAllReadResponse)
def mark_all_notifications_read(
    current_user: CurrentUser = Depends(require_faculty),
) -> MarkAllReadResponse:
    client = build_user_client(current_user.access_token)
    try:
        updated = faculty_notification_service.mark_all_read(client, current_user.id)
    except Exception as exc:
        raise _server_error("update your notifications") from exc
    return MarkAllReadResponse(updated=updated)
