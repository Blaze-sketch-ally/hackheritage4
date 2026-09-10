"""Pydantic schemas for the FACULTY side of in-app notifications.

Field names and constraints match
database/migrations/066_faculty_notifications.sql (`faculty_notifications`)
exactly -- mirrors app.schemas.student_notification's own shape and
reasoning. Validation here mirrors that migration's CHECK constraints so
a bad value comes back as a friendly 422 instead of a raw database
error -- the database stays authoritative.

There is deliberately no create/write schema exposed to Faculty: the
migration has NO insert policy, so notifications are only ever written
by trusted system-context code (service role, via
app.services.faculty_notification_producer). The only mutation a Faculty
member can make is toggling `read_at` on their own row, and the request
body for that carries nothing -- the path identifies the notification
and the token identifies the recipient.
"""

from typing import Literal

from pydantic import BaseModel

# faculty_notifications.type CHECK -- 066, widened by 068 (+
# 'RECONCILIATION_RESOLVED', an evaluator-facing notice that a
# reconciliation decision was recorded for a question they evaluated --
# see 068's own header for the exact, narrow information it carries).
# Only types with a real, single-recipient event source are included
# (see 066's own header and the Faculty Notification System audit report).
NotificationType = Literal[
    "EVALUATION_ASSIGNED",
    "EVALUATION_REVOKED",
    "REVIEW_DECISION",
    "MENTORSHIP",
    "RECONCILIATION_RESOLVED",
]

# faculty_notifications.related_entity_type CHECK -- 066.
RelatedEntityType = Literal["QUESTION", "EVALUATION", "MENTORSHIP"]


class FacultyNotification(BaseModel):
    """One `faculty_notifications` row, the recipient's own. `is_read` is
    derived from `read_at` for the frontend's convenience; no internal
    column beyond these is exposed."""

    id: str
    type: str
    title: str
    body: str
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    is_read: bool
    read_at: str | None = None
    created_at: str | None = None


class FacultyNotificationListResponse(BaseModel):
    notifications: list[FacultyNotification]
    unread_count: int


class MarkAllReadResponse(BaseModel):
    updated: int
