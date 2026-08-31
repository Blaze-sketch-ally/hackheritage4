"""Pydantic schemas for the Application API (Phase 1M).

Mirrors the `applications` table in
database/migrations/024_opportunities_and_applications.sql exactly.

No endpoint or service logic lives here -- schemas only.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.opportunity import OpportunityMatchSkillResponse, OpportunityResponse


class ApplicationStatus(str, Enum):
    APPLIED = "APPLIED"
    SHORTLISTED = "SHORTLISTED"
    INTERVIEW = "INTERVIEW"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class ApplicationCreateRequest(BaseModel):
    """The opportunity is identified by the URL path
    (POST /opportunities/{id}/applications), never the body -- student_id
    and status are never client-supplied (student_id is derived from the
    authenticated caller; status always starts APPLIED, enforced by the
    DB's own INSERT policy, not merely this schema)."""

    model_config = ConfigDict(extra="forbid")

    cover_note: str | None = None


class ApplicationResponse(BaseModel):
    """Mirrors `applications`. Returned for a student's own applications
    list -- includes the opportunity's own summary so the frontend never
    needs a second round-trip per row."""

    id: UUID
    opportunity_id: UUID
    student_id: UUID
    status: ApplicationStatus
    cover_note: str | None
    created_at: datetime
    updated_at: datetime
    opportunity: OpportunityResponse | None = None


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationResponse]


class ApplicationStatusUpdateRequest(BaseModel):
    """The ONLY field an industry owner may ever change on an existing
    application -- opportunity_id/student_id/cover_note have no field
    here at all (matches how the DB trigger,
    prevent_unauthorized_application_change, independently blocks
    changing them regardless of what a raw REST call might attempt)."""

    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus


class ApplicantResponse(BaseModel):
    """One applicant row for the industry-facing applicant list -- an
    application plus its own current match score, computed fresh (never
    stored), so a reviewer sees the same explainable score a student
    would see for themselves. Never includes answer keys, raw assessment
    answers, or any other student's data -- only what's necessary for
    recruitment review."""

    id: UUID
    student_id: UUID
    student_name: str | None
    status: ApplicationStatus
    cover_note: str | None
    overall_match_score: Decimal
    created_at: datetime
    updated_at: datetime


class ApplicantListResponse(BaseModel):
    opportunity_id: UUID
    applicants: list[ApplicantResponse]


class ApplicantDetailResponse(ApplicantResponse):
    """One applicant, industry-facing, with the full per-skill breakdown
    -- everything ApplicantResponse has, plus `skills` (Phase 1N:
    GET /opportunities/{id}/applicants/{application_id}). The list
    endpoint above deliberately omits this breakdown to stay lean; this
    detail endpoint is the one place it's exposed, computed by the exact
    same unmodified Phase 1L `compute_alignment()` call
    list_opportunity_applicants already makes -- not a second algorithm,
    just keeping a result the list endpoint already discards."""

    skills: list[OpportunityMatchSkillResponse]
