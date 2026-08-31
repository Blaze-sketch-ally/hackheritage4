"""Pydantic schemas for the Opportunity API (Phase 1M).

Mirrors database/migrations/024_opportunities_and_applications.sql
exactly -- no invented columns, no invented enum values. Single unified
opportunity domain: JOB and INTERNSHIP share every schema here, per the
Phase 1M product decision -- there are no separate JobResponse/
InternshipResponse types (app/schemas/job.py and internship.py stay
untouched, empty stubs).

Decimal fields (required_level, weight, and every match-related field)
serialize as JSON STRINGS, exactly like every other Decimal field in this
project (see schemas/assessment.py's own docstring) -- never parse them
into a JS number client-side.

No endpoint, service, or matching logic lives here -- schemas only.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.career_role import AlignmentStatus

# ============================================================
# Enums -- exact mirrors of the CHECK constraints in
# 024_opportunities_and_applications.sql
# ============================================================


class OpportunityType(str, Enum):
    JOB = "JOB"
    INTERNSHIP = "INTERNSHIP"


class OpportunityStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"


# ============================================================
# opportunities
# ============================================================


class OpportunityResponse(BaseModel):
    """Mirrors `opportunities`."""

    id: UUID
    industry_id: UUID
    title: str
    description: str | None
    opportunity_type: OpportunityType
    location: str | None
    status: OpportunityStatus
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OpportunityListResponse(BaseModel):
    opportunities: list[OpportunityResponse]


class OpportunityCreateRequest(BaseModel):
    """Always creates a fresh DRAFT -- status/published_at/industry_id are
    never client-supplied (industry_id is derived from the authenticated
    caller; status/published_at are owned entirely by the DB trigger, see
    the migration's own header comment)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    opportunity_type: OpportunityType
    location: str | None = None


class OpportunityUpdateRequest(BaseModel):
    """Partial update of basic metadata only. Every field optional.
    status changes go through the dedicated publish/close endpoints, not
    here -- this model has no status field at all, so a client cannot
    even attempt to smuggle one in (extra="forbid" rejects it outright).
    opportunity_type IS accepted here (still editable while DRAFT) -- the
    DB trigger, not this schema, enforces that it becomes locked once
    PUBLISHED and the whole row becomes immutable once CLOSED; this
    schema does not need to duplicate that state-dependent logic."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    opportunity_type: OpportunityType | None = None
    location: str | None = None


# ============================================================
# opportunity_skill_requirements
# ============================================================


class OpportunityRequirementInput(BaseModel):
    """One requirement row for PUT /opportunities/{id}/requirements --
    same shape and same bounds as career_role_skill_requirements'
    equivalent CHECK constraints
    (022_career_roles_skill_gap.sql). Validated here at the API boundary
    (422 on violation) rather than only relying on the DB's own CHECK
    constraint -- the DB constraint remains the real, structural
    guarantee (defense in depth, same principle as every other
    RLS-is-the-boundary rule in this project), but rejecting an
    obviously-invalid value immediately, before any database round-trip,
    gives a far clearer error than a generic conflict/500 surfaced from a
    deep constraint violation."""

    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    required_level: Decimal = Field(ge=0, le=100)
    weight: Decimal = Field(default=Decimal("1.0"), ge=0)


class OpportunityRequirementsReplaceRequest(BaseModel):
    """Full replacement of an opportunity's requirement set -- same
    replace-the-whole-set contract as Phase 1K's
    BlueprintUpsertRequest."""

    model_config = ConfigDict(extra="forbid")

    requirements: list[OpportunityRequirementInput]


class OpportunityRequirementResponse(BaseModel):
    """Mirrors `opportunity_skill_requirements`, with the skill's display
    name resolved via the embedded FK -- same pattern as
    career_role_service.get_career_role_requirements()."""

    skill_id: UUID
    skill_name: str
    required_level: Decimal
    weight: Decimal


class OpportunityRequirementsResponse(BaseModel):
    opportunity_id: UUID
    requirements: list[OpportunityRequirementResponse]


# ============================================================
# Matching (Phase 1L alignment engine, reused unchanged)
# ============================================================


class OpportunityMatchSkillResponse(BaseModel):
    """Mirrors app.services.skill_alignment_service.SkillAlignmentResult
    field for field -- identical shape to Phase 1L's SkillGapSkillResponse,
    reused rather than redefined (see app/api/opportunities.py)."""

    skill_id: UUID
    skill_name: str
    required_level: Decimal
    student_score: Decimal
    gap: Decimal
    weight: Decimal
    status: AlignmentStatus


class OpportunityMatchResponse(BaseModel):
    """The authenticated student's own derived match against one
    opportunity -- never constructed with another student's data. Always
    computed fresh from CURRENT requirements and CURRENT assessment
    evidence (see the migration's own "historical integrity" note) --
    never a stored, application-time snapshot."""

    opportunity: OpportunityResponse
    overall_score: Decimal
    skills: list[OpportunityMatchSkillResponse]
