"""Canonical Faculty mentor-capability contracts for Phase F4.2.

Deliberately separate from app.schemas.faculty_permissions
(AssessmentCapability) -- mentorship and assessment authority are two
independent trust axes (039_faculty_mentor_permissions.sql's own header
comment). There is exactly one mentorship capability, so unlike
AssessmentCapability this has no enum of capability names -- a Faculty
member either holds `faculty_mentor` or does not.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class MentorPermissionStatus(str, Enum):
    GRANTED = "GRANTED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class MyMentorCapabilityResponse(BaseModel):
    """Data-minimised, self-only representation for Faculty UI controls."""

    role: str
    can_mentor: bool


# ---- Admin-facing contracts (admin_*_mentor_* RPCs in
# 039_faculty_mentor_permissions.sql) -- carry grant metadata an ordinary
# Faculty member never sees. Never reuse these on a Faculty-facing route.


class FacultyMentorPermissionAdminResponse(BaseModel):
    """One Faculty member's mentor-capability grant, as seen by an ADMIN."""

    permission_id: str
    status: MentorPermissionStatus
    granted_by: str | None = None
    status_changed_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FacultyWithMentorPermissionResponse(BaseModel):
    """One Faculty member and their mentor-capability grant, if any."""

    faculty_id: str
    email: str
    username: str | None = None
    full_name: str | None = None
    permission: FacultyMentorPermissionAdminResponse | None = None


class AdminFacultyMentorPermissionListResponse(BaseModel):
    faculty: list[FacultyWithMentorPermissionResponse]


class AdminSetMentorPermissionStatusRequest(BaseModel):
    """PATCH /admin/faculty/mentor-permissions/{permission_id}/status."""

    model_config = ConfigDict(extra="forbid")

    status: MentorPermissionStatus
