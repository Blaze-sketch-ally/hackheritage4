"""Pydantic schemas for Industry interview scheduling
(database/migrations/030_industry_interviews.sql -- the `interviews`
table). Keep field names/constraints in sync with that migration and with
frontend/types/interview.ts.

An interview always hangs off an existing `applications` row (020). Its
`industry_id` and `student_id` are NEVER accepted from the client -- they
are copied server-side (by a database trigger) from the referenced
application, which already carries the authoritative, immutable
student <-> industry <-> posting relationship. `status` is never accepted
from the client either -- it only changes through the explicit lifecycle
endpoints. `extra="forbid"` on the write models is what structurally
rejects an attempt to smuggle any of these in.

Applicant identity: exactly like application responses, an interview
response carries the candidate only as `student_id` (a uuid). The schema
gives Industry no path to an applicant's name/email/profile, and this
module adds none.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# database/migrations/030_industry_interviews.sql -- interviews.mode CHECK
InterviewMode = Literal["ONLINE", "PHONE", "ONSITE"]
# database/migrations/030_industry_interviews.sql -- interviews.status CHECK
InterviewStatus = Literal["SCHEDULED", "COMPLETED", "CANCELLED"]

INTERVIEW_MODES: tuple[str, ...] = ("ONLINE", "PHONE", "ONSITE")
INTERVIEW_STATUSES: tuple[str, ...] = ("SCHEDULED", "COMPLETED", "CANCELLED")


class InterviewCreate(BaseModel):
    """POST /api/v1/interviews. Always created as SCHEDULED -- there is no
    `status` field here, and no `industry_id`/`student_id` (derived
    server-side from `application_id`). The application must be one the
    caller owns and must be at the SHORTLISTED or INTERVIEW_SCHEDULED
    stage -- enforced by the service and by a database trigger."""

    model_config = ConfigDict(extra="forbid")

    application_id: str
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=5, le=480)
    mode: InterviewMode
    location: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=10_000)


class InterviewUpdate(BaseModel):
    """PATCH /api/v1/interviews/{id} -- reschedule and/or edit details.
    Partial: only the fields actually sent are changed. Permitted only
    while the interview is still SCHEDULED (the service rejects it once
    COMPLETED/CANCELLED). `application_id` is immutable and cannot be
    changed here; `status` changes only through /complete and /cancel."""

    model_config = ConfigDict(extra="forbid")

    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    mode: InterviewMode | None = None
    location: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=10_000)


class InterviewOpportunity(BaseModel):
    """The internship/job the underlying application was submitted to.
    `status` here is the posting's lifecycle status
    (DRAFT/PUBLISHED/CLOSED/ARCHIVED), not the interview's."""

    id: str
    title: str
    status: str


class InterviewResponse(BaseModel):
    id: str
    application_id: str
    industry_id: str
    student_id: str
    scheduled_at: str
    duration_minutes: int
    mode: str
    location: str | None = None
    notes: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    # The posting the underlying application was submitted to, resolved
    # through the caller's own postings (RLS permits the join). Mirrors
    # ApplicationResponse.opportunity. Null if the posting embed was
    # unavailable.
    opportunity: InterviewOpportunity | None = None
    opportunity_type: str | None = None


class InterviewListResponse(BaseModel):
    interviews: list[InterviewResponse]
