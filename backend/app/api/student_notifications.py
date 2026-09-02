"""API routes for the STUDENT side of in-app notifications.

Every route is guarded by require_student() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. The recipient is ALWAYS current_user.id; no
`student_id` / `recipient_id` / `user_id` is ever read from a request
body, query, or path.

There is deliberately NO create endpoint. `student_notifications` has no
insert policy (035_student_notifications.sql), so notifications are only
ever written by trusted system-context code. The only mutation a student
can make here is toggling their own read state.

This is storage + consumption only: no existing feature is wired to emit
notifications in this phase. Producer integration is deferred.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_notification import (
    MarkAllReadResponse,
    StudentNotification,
    StudentNotificationListResponse,
)
from app.services import student_notification_service

router = APIRouter(prefix="/student", tags=["student-notifications"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="This notification is not available."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/notifications", response_model=StudentNotificationListResponse)
def list_notifications(
    unread: bool = Query(default=False, description="Return only unread notifications."),
    limit: int = Query(
        default=student_notification_service.DEFAULT_LIMIT,
        ge=1,
        le=student_notification_service.MAX_LIMIT,
    ),
    current_user: CurrentUser = Depends(require_student),
) -> StudentNotificationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_notification_service.list_notifications(
            client, current_user.id, unread_only=unread, limit=limit
        )
        count = student_notification_service.unread_count(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your notifications") from exc
    return StudentNotificationListResponse(
        notifications=[StudentNotification(**row) for row in rows], unread_count=count
    )


@router.get("/notifications/{notification_id}", response_model=StudentNotification)
def get_notification(
    notification_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> StudentNotification:
    client = build_user_client(current_user.access_token)
    try:
        row = student_notification_service.get_notification(
            client, current_user.id, str(notification_id)
        )
    except Exception as exc:
        raise _server_error("load this notification") from exc
    if row is None:
        raise _not_found()
    return StudentNotification(**row)


@router.patch("/notifications/{notification_id}/read", response_model=StudentNotification)
def mark_notification_read(
    notification_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> StudentNotification:
    """Mark one of the caller's own notifications read. Empty body -- the
    path identifies the notification, the token identifies the recipient.
    Idempotent."""
    client = build_user_client(current_user.access_token)
    try:
        row = student_notification_service.set_read(
            client, current_user.id, str(notification_id), read=True
        )
    except Exception as exc:
        raise _server_error("update this notification") from exc
    if row is None:
        raise _not_found()
    return StudentNotification(**row)


@router.patch("/notifications/{notification_id}/unread", response_model=StudentNotification)
def mark_notification_unread(
    notification_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> StudentNotification:
    """Mark one of the caller's own notifications unread again. Empty body.
    Idempotent."""
    client = build_user_client(current_user.access_token)
    try:
        row = student_notification_service.set_read(
            client, current_user.id, str(notification_id), read=False
        )
    except Exception as exc:
        raise _server_error("update this notification") from exc
    if row is None:
        raise _not_found()
    return StudentNotification(**row)


@router.post("/notifications/read-all", response_model=MarkAllReadResponse)
def mark_all_notifications_read(
    current_user: CurrentUser = Depends(require_student),
) -> MarkAllReadResponse:
    client = build_user_client(current_user.access_token)
    try:
        updated = student_notification_service.mark_all_read(client, current_user.id)
    except Exception as exc:
        raise _server_error("update your notifications") from exc
    return MarkAllReadResponse(updated=updated)
