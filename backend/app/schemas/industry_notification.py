"""Pydantic schemas for the INDUSTRY side of in-app notifications.

Field names and constraints match
database/migrations/055_industry_notifications.sql (`industry_notifications`)
exactly -- the Industry mirror of
backend/app/schemas/student_notification.py. There is deliberately no
create/write schema exposed to Industry: the migration has NO insert
policy, so notifications are only ever written by trusted system-context
code (service role, via app.services.notification_producer). The only
mutation an Industry account can make is toggling `read_at` on their own
row.
"""

from typing import Literal

from pydantic import BaseModel

# industry_notifications.type CHECK -- 055
NotificationType = Literal["NEW_APPLICATION", "WITHDRAWAL", "SYSTEM"]

# industry_notifications.related_entity_type CHECK -- 055. Always points
# at the POSTING (or, for INTERNSHIP/JOB, the application row -- Industry
# already has a per-application detail route) the event concerns.
RelatedEntityType = Literal[
    "INTERNSHIP_APPLICATION",
    "JOB_APPLICATION",
    "PROJECT_APPLICATION",
    "WORKSHOP_APPLICATION",
]


class IndustryNotification(BaseModel):
    """One `industry_notifications` row, the recipient's own. `is_read` is
    derived from `read_at`."""

    id: str
    type: str
    title: str
    body: str
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    is_read: bool
    read_at: str | None = None
    created_at: str | None = None


class IndustryNotificationListResponse(BaseModel):
    notifications: list[IndustryNotification]
    unread_count: int


class MarkAllReadResponse(BaseModel):
    updated: int
