"""API routes for the INDUSTRY side of in-app notifications.

Exact mirror of app.api.student_notifications, guarded by
require_industry() instead of require_student(). Every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role. The recipient is ALWAYS current_user.id.

There is deliberately NO create endpoint -- `industry_notifications` has
no insert policy (055_industry_notifications.sql); notifications are only
ever written by trusted system-context code
(app.services.notification_producer).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.industry_notification import (
    IndustryNotification,
    IndustryNotificationListResponse,
    MarkAllReadResponse,
)
from app.services import industry_notification_service

router = APIRouter(prefix="/industry", tags=["industry-notifications"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="This notification is not available."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/notifications", response_model=IndustryNotificationListResponse)
def list_notifications(
    unread: bool = Query(default=False, description="Return only unread notifications."),
    limit: int = Query(
        default=industry_notification_service.DEFAULT_LIMIT,
        ge=1,
        le=industry_notification_service.MAX_LIMIT,
    ),
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryNotificationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_notification_service.list_notifications(
            client, current_user.id, unread_only=unread, limit=limit
        )
        count = industry_notification_service.unread_count(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your notifications") from exc
    return IndustryNotificationListResponse(
        notifications=[IndustryNotification(**row) for row in rows], unread_count=count
    )


@router.get("/notifications/{notification_id}", response_model=IndustryNotification)
def get_notification(
    notification_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryNotification:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_notification_service.get_notification(
            client, current_user.id, str(notification_id)
        )
    except Exception as exc:
        raise _server_error("load this notification") from exc
    if row is None:
        raise _not_found()
    return IndustryNotification(**row)


@router.patch("/notifications/{notification_id}/read", response_model=IndustryNotification)
def mark_notification_read(
    notification_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryNotification:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_notification_service.set_read(
            client, current_user.id, str(notification_id), read=True
        )
    except Exception as exc:
        raise _server_error("update this notification") from exc
    if row is None:
        raise _not_found()
    return IndustryNotification(**row)


@router.patch("/notifications/{notification_id}/unread", response_model=IndustryNotification)
def mark_notification_unread(
    notification_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryNotification:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_notification_service.set_read(
            client, current_user.id, str(notification_id), read=False
        )
    except Exception as exc:
        raise _server_error("update this notification") from exc
    if row is None:
        raise _not_found()
    return IndustryNotification(**row)


@router.post("/notifications/read-all", response_model=MarkAllReadResponse)
def mark_all_notifications_read(
    current_user: CurrentUser = Depends(require_industry),
) -> MarkAllReadResponse:
    client = build_user_client(current_user.access_token)
    try:
        updated = industry_notification_service.mark_all_read(client, current_user.id)
    except Exception as exc:
        raise _server_error("update your notifications") from exc
    return MarkAllReadResponse(updated=updated)
