"""Pydantic schemas for the student <-> institution linking workflow
(`institution_link_requests`, database/migrations/
038_institution_link_requests.sql).

Same shape as schemas/industry_collaboration.py: a bilateral relationship
between an initiator (STUDENT here) and an approver (INSTITUTION here),
with `status` never accepted from the client -- it only changes through
the explicit lifecycle endpoints, and `institution_id` is never accepted
directly either (a student resolves it by username first, mirroring
CollaborationCreate's `recipient_id` being obtained via
GET /collaborations/recipients/resolve).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LinkRequestStatus = Literal["PENDING", "APPROVED", "REJECTED", "CANCELLED", "REMOVED"]

LINK_REQUEST_STATUSES: tuple[str, ...] = (
    "PENDING",
    "APPROVED",
    "REJECTED",
    "CANCELLED",
    "REMOVED",
)


class InstitutionResolution(BaseModel):
    """GET /api/v1/institution-links/resolve response. Deliberately
    minimal -- id and full_name only, and only ever populated for an
    INSTITUTION-role match (see resolve_institution_by_username)."""

    id: str
    full_name: str | None = None


class LinkRequestCreate(BaseModel):
    """POST /api/v1/institution-links body. `institution_id` must be the
    id of an existing INSTITUTION profile, typically obtained via
    GET /institution-links/resolve first -- the database trigger rejects
    anything else."""

    model_config = ConfigDict(extra="forbid")

    institution_id: str = Field(min_length=1)


class InstitutionLinkRequest(BaseModel):
    id: str
    student_id: str
    institution_id: str
    status: LinkRequestStatus
    created_at: str | None = None
    updated_at: str | None = None
    # Resolved server-side -- see institution_link_request_student_names()
    # (institution-side reads) and institution_profiles' own broadly
    # readable name (student-side reads, resolved in the service layer
    # from the already-public institution_profiles.institution_name).
    # Never accepted from the client; not stored on this table.
    student_name: str | None = None
    student_username: str | None = None
    institution_name: str | None = None


class LinkRequestListResponse(BaseModel):
    requests: list[InstitutionLinkRequest]
