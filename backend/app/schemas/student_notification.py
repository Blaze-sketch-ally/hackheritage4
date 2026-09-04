"""Pydantic schemas for the STUDENT side of in-app notifications.

Field names and constraints match
database/migrations/035_student_notifications.sql (`student_notifications`)
exactly. Validation here mirrors that migration's CHECK constraints so a
bad value comes back as a friendly 422 instead of a raw database error --
the database stays authoritative.

There is deliberately no create/write schema exposed to students: the
migration has NO insert policy, so notifications are only ever written by
trusted system-context code (service role). The only mutation a student
can make is toggling `read_at` on their own row, and the request body for
that carries nothing -- the path identifies the notification and the
token identifies the recipient.
"""

from typing import Literal

from pydantic import BaseModel

# student_notifications.type CHECK -- 035, widened by migration 039
# (+ 'INTERNSHIP').
NotificationType = Literal[
    "APPLICATION_STATUS",
    "INTERVIEW",
    "ASSESSMENT",
    "LEARNING",
    "MENTORSHIP",
    "EVENT",
    "SYSTEM",
    "INTERNSHIP",
]

# student_notifications.related_entity_type CHECK -- 035, widened by
# migration 039 (+ 'INTERNSHIP_WORKSPACE').
RelatedEntityType = Literal[
    "APPLICATION",
    "INTERVIEW",
    "ASSESSMENT",
    "LEARNING_RESOURCE",
    "MENTORSHIP",
    "EVENT",
    "INTERNSHIP_WORKSPACE",
]


class StudentNotification(BaseModel):
    """One `student_notifications` row, the recipient's own. `is_read` is
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


class StudentNotificationListResponse(BaseModel):
    notifications: list[StudentNotification]
    unread_count: int


class MarkAllReadResponse(BaseModel):
    updated: int
