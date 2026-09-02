"""Pydantic schemas for Faculty expressions of interest ("EOI") --
`faculty_industry_opportunity_expressions` /
`faculty_institution_opportunity_expressions`
(037_faculty_opportunities_and_expressions.sql).

Deliberately NOT named "application" -- see the approved architecture
design: "application" already has a precise, hard-coded meaning in this
codebase (the STUDENT-only `applications` table, 024). This is a
structurally different, Faculty-initiated concept against a different
opportunity domain.

`source` (INDUSTRY/INSTITUTION) is API response metadata identifying
which underlying table an EOI or opportunity came from -- it is never a
polymorphic database foreign key; each EOI row's `opportunity_id` is a
real, single-target foreign key into exactly one physical table, and the
backend already knows which one before it ever builds a response.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OpportunitySource = Literal["INDUSTRY", "INSTITUTION"]
EoiStatus = Literal["DRAFT", "SUBMITTED", "UNDER_REVIEW", "ACCEPTED", "REJECTED", "WITHDRAWN"]


class ExpressInterestRequest(BaseModel):
    """POST .../express-interest body. Creates the EOI as DRAFT and
    immediately submits it in the same call -- a real DRAFT row is
    created and the DRAFT->SUBMITTED transition genuinely happens (the
    trigger/RLS rules both fire), this just spares the Faculty caller a
    separate "save draft" step for V1. `message` is optional -- Faculty
    may express interest with no note at all."""

    model_config = ConfigDict(extra="forbid")

    message: str | None = Field(default=None, max_length=5_000)


class FacultyOpportunityExpressionResponse(BaseModel):
    id: str
    source: OpportunitySource
    opportunity_id: str
    opportunity_title: str | None = None
    faculty_id: str
    status: EoiStatus
    message: str | None = None
    reviewed_by: str | None = None
    reviewer_note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class FacultyOpportunityExpressionListResponse(BaseModel):
    expressions: list[FacultyOpportunityExpressionResponse]


class ReviewExpressionRequest(BaseModel):
    """PATCH .../review body, used by the owning Industry/Institution.
    `status` must be one of the transitions the database trigger actually
    permits (SUBMITTED->UNDER_REVIEW, UNDER_REVIEW->ACCEPTED/REJECTED) --
    anything else is rejected at the database layer regardless of what
    reaches this schema. `reviewed_by` is never accepted here -- the
    database trigger derives it from auth.uid()."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["UNDER_REVIEW", "ACCEPTED", "REJECTED"]
    reviewer_note: str | None = Field(default=None, max_length=5_000)
