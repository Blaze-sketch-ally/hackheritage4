"""Read-only Faculty opportunity discovery (Phase F3.2, corrected in the
approved F3.4 architecture review).

CORRECTION: this originally modeled `category` (PROJECT/TRAINING/WORKSHOP/
MENTORSHIP) over the four Industry->STUDENT posting tables
(028-031_industry_*.sql). The architecture review established those four
tables are explicitly Student-facing by documented product intent (their
own migration headers say so), even though RLS technically permits any
authenticated read -- treating them as Faculty-facing was a semantic
error. This module now models `source` (INDUSTRY/INSTITUTION) over the
two tables built specifically for Faculty participation:
industry_faculty_opportunities and institution_faculty_opportunities
(037_faculty_opportunities_and_expressions.sql).

`source` is API response metadata only -- it identifies which physical
table a row came from so the frontend/caller knows which downstream
endpoint (express-interest, etc.) to use. It is never a polymorphic
database foreign key: each opportunity's `id` is a real primary key in
exactly one physical table, and the backend already knows which table
before building this response.
"""

from typing import Literal

from pydantic import BaseModel

OpportunitySource = Literal["INDUSTRY", "INSTITUTION"]

OPPORTUNITY_SOURCES: tuple[str, ...] = ("INDUSTRY", "INSTITUTION")


class FacultyOpportunity(BaseModel):
    """One published Faculty opportunity, normalized across both source
    tables into a single display shape."""

    id: str
    source: OpportunitySource
    owner_id: str
    # Best-effort display enrichment (see faculty_opportunity_service's
    # own docstring for why this is INDUSTRY-only) -- None for
    # INSTITUTION sources and for an INDUSTRY owner with no saved company
    # profile yet.
    owner_name: str | None = None
    title: str
    description: str | None = None
    location: str | None = None
    work_mode: str | None = None
    capacity: int | None = None
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    start_date: str | None = None
    status: Literal["PUBLISHED"] = "PUBLISHED"
    created_at: str | None = None
    updated_at: str | None = None


class FacultyOpportunityListResponse(BaseModel):
    opportunities: list[FacultyOpportunity]
