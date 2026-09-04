"""Pydantic schemas for the Industry side of applications
(database/migrations/020_applications.sql -- the unified internship + job
application table).

An application row is created by a STUDENT applying to a published
internship/job. Industry's involvement is read + a single mutable field:
`status`. Everything else on the row is immutable to Industry, enforced
by the `prevent_application_identity_change` trigger and by only ever
sending `{"status": ...}` from the service.

Student identity: `profiles` RLS still only permits a user to read their
own row (001_profiles.sql) -- that is unchanged. `student_name` is
resolved server-side through `public.application_applicant_names`
(036_application_applicant_names.sql), a SECURITY DEFINER function scoped
to the exact same "Industry can view applications to their own postings"
predicate as the applications table's own RLS SELECT policy, so it can
never name a student for an application the caller doesn't already own.
It returns only `profiles.full_name` -- no email, avatar, or any other
profile data. When name resolution fails (or the student has no
full_name), `student_name` is None and the frontend falls back to a
truncated `student_id` reference.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

# database/migrations/020_applications.sql -- applications.status CHECK
ApplicationStatus = Literal[
    "APPLIED",
    "UNDER_REVIEW",
    "SHORTLISTED",
    "INTERVIEW_SCHEDULED",
    "SELECTED",
    "REJECTED",
    "WITHDRAWN",
]
OpportunityType = Literal["INTERNSHIP", "JOB"]

APPLICATION_STATUSES: tuple[str, ...] = (
    "APPLIED",
    "UNDER_REVIEW",
    "SHORTLISTED",
    "INTERVIEW_SCHEDULED",
    "SELECTED",
    "REJECTED",
    "WITHDRAWN",
)

# The status values an INDUSTRY account is allowed to set. WITHDRAWN is
# deliberately absent -- that transition belongs to the student, and the
# `prevent_student_status_override` trigger is the mirror of this rule on
# the database side. APPLIED is absent -- it is the initial state only.
IndustrySettableStatus = Literal[
    "UNDER_REVIEW",
    "SHORTLISTED",
    "INTERVIEW_SCHEDULED",
    "SELECTED",
    "REJECTED",
]


class ApplicationOpportunity(BaseModel):
    """The internship or job an application was submitted to, resolved
    through the caller's own postings (Industry owns these rows, so RLS
    permits the join). `status` here is the *posting's* lifecycle status
    (DRAFT/PUBLISHED/CLOSED/ARCHIVED), not the application's."""

    id: str
    title: str
    status: str


class ApplicationResponse(BaseModel):
    id: str
    student_id: str
    # Resolved via public.application_applicant_names -- see module
    # docstring. None if resolution fails or the student has no full_name.
    student_name: str | None = None
    industry_id: str
    opportunity_type: str
    internship_id: str | None = None
    job_id: str | None = None
    status: str
    cover_note: str | None = None
    # Populated later by the AI matching service (Phase 8) -- not written here.
    match_score: float | None = None
    applied_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    opportunity: ApplicationOpportunity | None = None


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationResponse]


class ApplicationSummaryResponse(BaseModel):
    """Per-status counts of the caller's own applications, for the
    recruitment funnel. `counts` carries every status (0 when none)."""

    counts: dict[str, int]
    total: int


SkillMatchStatus = Literal["MATCHED", "NEEDS_IMPROVEMENT", "MISSING"]
MatchRecommendation = Literal["STRONG", "GOOD", "PARTIAL", "LOW"]


class MatchSkill(BaseModel):
    """One required skill of the posting, with how the applicant covers it.
    Only skills the caller's own posting requires ever appear here."""

    skill_id: str
    skill_name: str
    required_level: str
    importance: str
    candidate_has: bool
    candidate_level: str | None = None
    candidate_verified: bool = False
    status: SkillMatchStatus


class ApplicationMatchResponse(BaseModel):
    """Advisory only. A deterministic, reproducible skill-fit summary for
    one application. Never connected to status transitions. No LLM, no
    stored explanation -- the structured result is authoritative."""

    application_id: str
    score: int  # 0-100
    recommendation: MatchRecommendation
    skill_coverage: str  # e.g. "8 / 10"
    required_count: int
    matched_count: int
    needs_improvement_count: int
    missing_count: int
    matched_skills: list[MatchSkill]
    needs_improvement_skills: list[MatchSkill]
    missing_skills: list[MatchSkill]


class ApplicationStatusUpdate(BaseModel):
    """PATCH /api/v1/applications/{id}/status body.

    `status` is a restricted Literal, so an out-of-range value, WITHDRAWN,
    APPLIED, or a smuggled `student_id` / `industry_id` / `internship_id`
    all fail validation with a 422 before any handler runs
    (`extra="forbid"`).
    """

    model_config = ConfigDict(extra="forbid")

    status: IndustrySettableStatus
