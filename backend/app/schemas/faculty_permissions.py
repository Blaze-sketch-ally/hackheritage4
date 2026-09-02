"""Canonical Faculty assessment capability contracts for Phase F2."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AssessmentCapability(str, Enum):
    AUTHOR = "assessment_author"
    REVIEWER = "assessment_reviewer"
    EVALUATOR = "assessment_evaluator"
    MODERATOR = "assessment_moderator"
    LEAD = "assessment_lead"


class PermissionStatus(str, Enum):
    GRANTED = "GRANTED"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class MyFacultyCapabilitiesResponse(BaseModel):
    """Data-minimised, self-only representation for Faculty UI controls."""

    role: str
    capabilities: list[AssessmentCapability]


# ---- Admin-facing contracts (035_admin_faculty_permission_management.sql) ----
#
# Unlike MyFacultyCapabilitiesResponse, these DO carry grant metadata
# (granted_by, status_changed_by, expires_at) -- an ADMIN managing
# permissions is exactly the audience that metadata exists for. Never
# reuse these response models on a Faculty-facing route.


class FacultyPermissionAdminResponse(BaseModel):
    """One (Faculty, capability) grant row, as seen by an ADMIN."""

    permission_id: str
    capability: AssessmentCapability
    status: PermissionStatus
    granted_by: str | None = None
    status_changed_by: str | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FacultyWithPermissionsResponse(BaseModel):
    """One Faculty member and every capability grant they currently have
    (possibly none, for a Faculty member nothing has been granted to
    yet)."""

    faculty_id: str
    email: str
    username: str | None = None
    full_name: str | None = None
    permissions: list[FacultyPermissionAdminResponse]


class AdminFacultyListResponse(BaseModel):
    faculty: list[FacultyWithPermissionsResponse]


class AdminGrantCapabilityRequest(BaseModel):
    """POST /admin/faculty/{faculty_id}/assessment-permissions.
    `extra=\"forbid\"` (via model_config below) so granted_by can never be
    smuggled in from the client -- it is always the authenticated admin,
    derived server-side by the admin_grant_assessment_capability() RPC
    from auth.uid()."""

    model_config = {"extra": "forbid"}

    capability: AssessmentCapability
    expires_at: datetime | None = Field(default=None)


class AdminSetPermissionStatusRequest(BaseModel):
    """PATCH /admin/faculty/assessment-permissions/{permission_id}/status."""

    model_config = {"extra": "forbid"}

    status: PermissionStatus
