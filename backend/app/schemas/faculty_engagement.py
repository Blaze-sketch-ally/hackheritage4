"""Pydantic schemas for Faculty engagements (`faculty_engagements`,
038_faculty_engagements.sql) -- the relationship created once an
Industry/Institution accepts a Faculty expression of interest.

Deliberately distinct from FacultyOpportunityExpressionResponse (the EOI
itself) -- an Engagement is a separate historical record, never an EOI,
opportunity, industry_collaboration, or mentorship relationship.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EngagementSource = Literal["INDUSTRY_EOI", "INSTITUTION_EOI"]
EngagementStatus = Literal["PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"]


class FacultyEngagementResponse(BaseModel):
    id: str
    source_kind: EngagementSource
    industry_eoi_id: str | None = None
    institution_eoi_id: str | None = None
    faculty_id: str
    organization_id: str
    status: EngagementStatus
    start_date: str | None = None
    end_date: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class FacultyEngagementListResponse(BaseModel):
    engagements: list[FacultyEngagementResponse]


class UpdateEngagementStatusRequest(BaseModel):
    """PATCH .../engagements/{id}/status body, used by the owning
    Industry/Institution. `status` must be one of the transitions the
    database trigger actually permits (PLANNED->ACTIVE/CANCELLED,
    ACTIVE->COMPLETED/CANCELLED) -- anything else is rejected at the
    database layer regardless of what reaches this schema. Faculty/
    organization identity is never accepted here -- immutable, derived
    at creation only."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ACTIVE", "COMPLETED", "CANCELLED"]
    notes: str | None = Field(default=None, max_length=5_000)
    start_date: str | None = None
    end_date: str | None = None
