"""Pydantic schemas for the STUDENT side of opportunity discovery and
applications.

This is a thin, read-only *adapter* over the two real posting tables --
`internships` (database/migrations/018_internships.sql) and `jobs`
(019_jobs.sql). There is no `opportunities` table in this architecture and
none is introduced: the student-facing "opportunity" is just a normalized
view of one internship OR one job.

The student-facing identifier is a prefixed string --
``internship_<uuid>`` / ``job_<uuid>`` -- so the adapter can always
resolve which source table (and therefore which of
`applications.internship_id` / `applications.job_id`) a given opportunity
maps to, without assuming the raw internship/job UUIDs never collide.

An application row is still the existing `applications` row
(020_applications.sql) unchanged: `student_id` from the authenticated
caller, `industry_id` from the BEFORE-INSERT trigger, `opportunity_type` +
`internship_id`/`job_id` derived here, `status` defaulting to APPLIED.
The student never supplies any of those -- the only field they control is
`cover_note`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Mirrors applications.opportunity_type / the INTERNSHIP-xor-JOB split.
SourceType = Literal["INTERNSHIP", "JOB"]

# database/migrations/020_applications.sql -- applications.status CHECK.
# The student frontend renders all seven; the values are never redefined.
StudentApplicationStatus = Literal[
    "APPLIED",
    "UNDER_REVIEW",
    "SHORTLISTED",
    "INTERVIEW_SCHEDULED",
    "SELECTED",
    "REJECTED",
    "WITHDRAWN",
]


class OpportunityIndustry(BaseModel):
    """Company display info for a posting, read from `industry_profiles`
    (RLS: "Authenticated users can view industry profiles"). `company_name`
    can be null -- an Industry account can post before filling in its
    company profile -- and no `profiles` column (full_name, email, ...) is
    ever exposed here; there is no RLS path to it for a student."""

    id: str
    company_name: str | None = None
    industry_sector: str | None = None
    logo_url: str | None = None


class OpportunitySkill(BaseModel):
    skill_id: str
    skill_name: str
    category_name: str | None = None
    required_level: str
    importance: str


class StudentOpportunitySummary(BaseModel):
    """One published internship/job, normalized for the browse list."""

    id: str
    source_type: SourceType
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None
    status: str  # the posting's lifecycle status -- always PUBLISHED in the list
    industry: OpportunityIndustry | None = None
    application_deadline: str | None = None
    created_at: str | None = None
    has_applied: bool = False


class StudentOpportunityDetail(StudentOpportunitySummary):
    """One published internship/job, normalized for the detail page --
    every field either table can supply, plus the required-skill list.
    Fields the other source type doesn't have are simply null."""

    eligibility_criteria: str | None = None
    openings: int | None = None

    # internship-only
    duration_months: int | None = None
    stipend_amount: float | None = None
    stipend_currency: str | None = None
    start_date: str | None = None

    # job-only
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    experience_min_years: float | None = None

    skills: list[OpportunitySkill] = Field(default_factory=list)


class StudentOpportunityListResponse(BaseModel):
    opportunities: list[StudentOpportunitySummary]


class ApplyRequest(BaseModel):
    """POST /api/v1/student/opportunities/{id}/applications body.

    `cover_note` is the ONLY field a student may send. `extra="forbid"`
    structurally rejects any attempt to smuggle in `student_id`,
    `industry_id`, `status`, `match_score`, `internship_id`, `job_id`, or
    `opportunity_type` -- every one of those is derived server-side.
    """

    model_config = ConfigDict(extra="forbid")

    cover_note: str | None = Field(default=None, max_length=5_000)


class StudentApplicationOpportunity(BaseModel):
    """The posting an application points at, embedded on the student's own
    application list so "My Applications" needs no second round-trip. Can
    be partially null if the posting is no longer PUBLISHED (a student has
    no RLS path to a CLOSED/ARCHIVED posting)."""

    id: str
    source_type: SourceType
    title: str | None = None
    industry: OpportunityIndustry | None = None
    location: str | None = None


class StudentApplicationResponse(BaseModel):
    """A row from the existing `applications` table, student's own only.
    Same columns as the Industry response, minus nothing -- the student
    already owns every field here."""

    id: str
    student_id: str
    opportunity_type: str
    internship_id: str | None = None
    job_id: str | None = None
    status: str
    cover_note: str | None = None
    match_score: float | None = None
    applied_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    opportunity: StudentApplicationOpportunity | None = None


class StudentApplicationListResponse(BaseModel):
    applications: list[StudentApplicationResponse]


# ---- match (advisory, deterministic, reuses app.services.match_service) ----

SkillMatchStatus = Literal["MATCHED", "NEEDS_IMPROVEMENT", "MISSING"]
MatchRecommendation = Literal["STRONG", "GOOD", "PARTIAL", "LOW"]


class MatchSkill(BaseModel):
    skill_id: str
    skill_name: str
    required_level: str
    importance: str
    candidate_has: bool
    candidate_level: str | None = None
    candidate_verified: bool = False
    status: SkillMatchStatus


class OpportunityMatchResponse(BaseModel):
    """The authenticated student's own advisory skill fit against one
    opportunity. Computed fresh on every call by
    app.services.match_service.compute_match (the same deterministic
    engine the Industry applicant-match endpoint uses) -- no LLM, nothing
    stored, never coupled to an application row or its status."""

    opportunity_id: str
    score: int  # 0-100
    recommendation: MatchRecommendation
    skill_coverage: str
    required_count: int
    matched_count: int
    needs_improvement_count: int
    missing_count: int
    matched_skills: list[MatchSkill]
    needs_improvement_skills: list[MatchSkill]
    missing_skills: list[MatchSkill]
