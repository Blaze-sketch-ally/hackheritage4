"""Pydantic schemas for the Institution Dashboard overview
(backend/app/api/institution.py, GET /api/v1/institution/overview).

Every metric here is computed live, through a user-scoped RLS client
(build_user_client), never service_role. Student-level metrics
(student_metrics, department_metrics, student_insights) are scoped by
`student_profiles.institution_id = auth.uid()` -- see
database/migrations/037_institution_tenancy.sql -- and are honestly zero
for an institution with no linked students; nothing here is fabricated to
fill the page.

`platform_wide=True` on a field marks a metric the schema cannot scope to
one institution today (jobs/internships/workshops have no
institution-ownership relationship -- they belong to the posting Industry
account, visible to every authenticated user once PUBLISHED). Those
fields must never be presented as "your institution's" data.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# database/migrations/037_institution_tenancy.sql: institution_profiles_phone_format
_PHONE_PATTERN = r"^[0-9+\-\s()]{7,20}$"


class InstitutionProfileFields(BaseModel):
    """The editable institution-profile fields, shared by the update
    request and the response. Every field is optional: an INSTITUTION
    account has a `profiles` row from signup but no `institution_profiles`
    row until the first save (same lazy-row pattern as
    industry_profiles/student_profiles)."""

    institution_name: str | None = Field(default=None, max_length=200)
    institution_type: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=200)
    website_url: str | None = Field(default=None, max_length=2048)
    contact_phone: str | None = Field(default=None, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data: object) -> object:
        """Same as IndustryProfileFields' own validator: trim strings and
        treat "" / whitespace-only as NULL before field validation runs."""
        if not isinstance(data, dict):
            return data
        cleaned: dict = {}
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip() or None
            cleaned[key] = value
        return cleaned

    @field_validator("contact_phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(_PHONE_PATTERN, value) is None:
            raise ValueError(
                "Enter a valid phone number: 7-20 characters using digits, spaces, "
                "and + - ( ) only."
            )
        return value


class InstitutionProfileUpdate(InstitutionProfileFields):
    """PUT /api/v1/institution/profile body. `extra="forbid"` structurally
    rejects an attempt to smuggle `id` or anything else into the payload
    -- ownership is always the authenticated caller."""

    model_config = ConfigDict(extra="forbid")


class InstitutionProfileResponse(InstitutionProfileFields):
    """GET / PUT response. `created_at`/`updated_at` are None only in the
    no-row-yet window (a GET before the first save)."""

    id: str
    created_at: str | None = None
    updated_at: str | None = None


class StudentMetrics(BaseModel):
    """Counts among students LINKED to this institution
    (student_profiles.institution_id = caller). Students who exist on the
    platform but are not linked are invisible here by design -- RLS
    enforces this, not application-layer filtering."""

    total_linked_students: int
    placed: int
    unplaced_active: int
    not_participating: int
    # None when total_linked_students == 0 -- never a fabricated 0%.
    placement_percentage: float | None


class DepartmentMetric(BaseModel):
    """One real `departments` row (database/migrations/
    040_institution_departments.sql) among this institution's linked
    students, grouped by `student_profiles.department_id` -- NOT the
    free-text `student_profiles.department` string. A student with no
    department_id is grouped under the synthetic "Unassigned" label
    (`department_id` is then None)."""

    department: str
    department_id: str | None
    total_students: int
    placed_students: int
    placement_percentage: float | None


class RecentOpportunity(BaseModel):
    """A recently PUBLISHED job/internship -- platform-wide content, not
    owned by this institution. `applicants_from_your_institution` IS
    institution-specific: it counts only this institution's own linked
    students among the applicants, which the institution-scoped
    applications RLS policy makes honestly computable."""

    id: str
    title: str
    opportunity_type: str  # "INTERNSHIP" | "JOB"
    company_name: str | None
    posted_at: str | None
    applicants_from_your_institution: int


class OpportunitiesOverview(BaseModel):
    active_jobs: int
    active_internships: int
    recent: list[RecentOpportunity]
    platform_wide: bool = True


class IndustryOverview(BaseModel):
    """Company-directory data (industry_profiles is broadly readable to
    every authenticated user -- see 017_industry_profiles.sql). Not
    scoped to this institution's own relationships; see `collaborations`
    for the part of Industry activity that genuinely is."""

    total_industry_partners: int
    recent_postings_count: int
    platform_wide: bool = True


class CollaborationsOverview(BaseModel):
    """This IS institution-specific -- these are collaboration proposals
    addressed to this institution account
    (industry_collaborations.recipient_id = caller), not platform-wide."""

    pending: int
    active: int
    total: int


class UpcomingEvent(BaseModel):
    """Merges (Phase 10, 045_institution_events.sql) the institution's own
    upcoming organized events with platform-wide PUBLISHED Industry
    workshops -- `platform_wide` distinguishes which is which per row.
    See the Institution Events module (institution_event_service.py) for
    the full event workspace this is a compact preview of."""

    id: str
    title: str
    event_type: str  # "WORKSHOP" for a platform-wide row, or the
    # institution's own event_type (SEMINAR/GUEST_LECTURE/...) otherwise.
    start_date: str | None
    organizer: str | None
    platform_wide: bool = True


class SkillCount(BaseModel):
    skill_name: str
    student_count: int


class StudentInsights(BaseModel):
    students_with_no_applications: int
    students_actively_applying: int
    top_skills: list[SkillCount]
    assessments_completed: int
    # None when assessments_completed == 0.
    average_assessment_percentage: float | None


class InstitutionOverviewResponse(BaseModel):
    generated_at: str
    institution_name: str | None
    student_metrics: StudentMetrics
    department_metrics: list[DepartmentMetric]
    opportunities: OpportunitiesOverview
    industry: IndustryOverview
    collaborations: CollaborationsOverview
    upcoming_events: list[UpcomingEvent]
    student_insights: StudentInsights
    # Always present, always shown in the UI -- explains why
    # "eligible students" is absent (no eligibility data model exists)
    # and that student/placement metrics only cover linked students.
    tenancy_note: str
    eligibility_note: str
