"""Pydantic schemas for the cross-module Industry Participant view --
one normalized read composed from the four existing, already
ownership-scoped applicant sources (`applications` for INTERNSHIP/JOB,
`industry_project_applications`, `industry_workshop_applications`,
`industry_training_applications`). No new table: this is a read-only
aggregation, computed server-side by app.services.industry_participant_service
from the same list_applications()/list_applications() functions each
opportunity-centric Applicants view already calls.

Lets an Industry account answer "what has this student applied to across
ALL of my postings?" (the student-centric view) without a new data model.
"""

from typing import Literal

from pydantic import BaseModel

ParticipantOpportunityType = Literal["INTERNSHIP", "JOB", "PROJECT", "WORKSHOP", "TRAINING"]


class ParticipantRecord(BaseModel):
    """One student's participation in one of the caller's own postings.
    `id` is the underlying application/registration row id (from whichever
    of the four source tables this record came from) -- never a synthetic
    id. `opportunity_href` is computed server-side, the single source of
    truth for where this record's opportunity detail lives (a specific
    application for INTERNSHIP/JOB, or that posting's Applicants view for
    PROJECT/WORKSHOP/TRAINING, which have no per-application detail
    route) -- the frontend never re-derives it."""

    id: str
    student_id: str
    student_name: str | None = None
    institution_name: str | None = None
    department: str | None = None
    graduation_year: int | None = None
    skills: list[str] | None = None
    opportunity_type: ParticipantOpportunityType
    opportunity_id: str
    opportunity_title: str
    opportunity_href: str
    status: str
    applied_at: str | None = None


class ParticipantListResponse(BaseModel):
    records: list[ParticipantRecord]
