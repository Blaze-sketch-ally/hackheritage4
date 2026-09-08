"""Pydantic schemas for the Institution-Curated Internships module
(backend/app/api/institution.py, /institution/internships...,
database/migrations/046_institution_internships.sql).

Replaces the old Phase 7 "directory" (every currently-PUBLISHED
internship platform-wide, plus any internship one of the institution's
own students happened to apply to) with an EXPLICIT curation model: the
Institution browses AVAILABLE (published, not-yet-curated) internships
and explicitly selects/adds the ones it wants -- only those appear in the
default (curated) list. There is no `institution_internship_applications`
table -- application/selection data is still read live from the EXISTING
`applications` table (020_applications.sql), scoped to whichever
internships this institution has curated. "Selected" (a student) still
means exactly what it has meant since 037_institution_tenancy.sql: an
application row with opportunity_type = 'INTERNSHIP' and
status = 'SELECTED'. `institution_internships.status` (ACTIVE/INACTIVE) is
a completely different concept -- whether the INSTITUTION itself curated
this internship -- and is never rendered or computed as if it were a
student's application status.

Honesty boundaries enforced here, not just documented:
  - Stipend is the existing flat `internships.stipend_amount` /
    `stipend_currency` columns -- there is no separate disbursement
    ledger anywhere in this schema, so none is exposed here.
  - `participation_estimate` (NOT_STARTED / ACTIVE / COMPLETED / UNKNOWN)
    is a best-effort ESTIMATE derived from `internships.start_date` +
    `duration_months` for a SELECTED application -- never a tracked
    attendance/completion fact (no such table exists).
  - No structured eligibility model exists for internships -- only the
    free-text `eligibility_criteria` column is ever surfaced; no
    per-student eligibility verdict is computed.
"""

from pydantic import BaseModel

# ---- shared ----


class StatusCount(BaseModel):
    status: str
    count: int


class ParticipationBreakdown(BaseModel):
    """Counts of SELECTED internship applications by estimated
    participation stage -- see the module docstring. `unknown` is never
    dropped or guessed into another bucket."""

    not_started: int
    active: int
    completed: int
    unknown: int


# ---- curated directory ----


class InstitutionInternshipRow(BaseModel):
    id: str
    title: str
    company_name: str | None
    industry_id: str
    work_mode: str | None
    duration_months: int | None
    stipend_amount: float | None
    stipend_currency: str | None
    application_deadline: str | None
    start_date: str | None
    status: str
    """The underlying internship POSTING's own lifecycle status
    (DRAFT/PUBLISHED/CLOSED/ARCHIVED) -- never confused with
    `association_status` below."""

    association_id: str
    association_status: str
    """ACTIVE ("currently curated by this institution") or INACTIVE
    ("removed by this institution") -- the institution's OWN selection
    state, completely independent of the posting's own status and of any
    student's application status."""
    added_at: str | None

    applicants_from_institution: int
    selected_from_institution: int


class InstitutionInternshipListResponse(BaseModel):
    internships: list[InstitutionInternshipRow]
    mode_options: list[str]
    status_options: list[str]


# ---- available directory (not yet curated) ----


class AvailableInternshipRow(BaseModel):
    """A real, currently-PUBLISHED internship this institution has NOT
    yet curated -- the ONLY source `POST /internships/{id}/select` may
    reference. Never a free-text or fabricated posting."""

    id: str
    title: str
    company_name: str | None
    industry_id: str
    work_mode: str | None
    duration_months: int | None
    stipend_amount: float | None
    stipend_currency: str | None
    application_deadline: str | None
    start_date: str | None
    status: str


class AvailableInternshipListResponse(BaseModel):
    internships: list[AvailableInternshipRow]
    mode_options: list[str]


# ---- select / remove ----


class InternshipAssociationResponse(BaseModel):
    id: str
    internship_id: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None


# ---- detail ----


class InstitutionInternshipApplicant(BaseModel):
    application_id: str
    student_id: str
    full_name: str | None
    username: str | None
    department: str
    cgpa: float | None
    status: str
    applied_at: str | None
    # Only meaningful when status == 'SELECTED'; null otherwise.
    participation_estimate: str | None
    interview: dict | None = None


class InstitutionInternshipDetail(BaseModel):
    id: str
    title: str
    description: str | None
    company_name: str | None
    industry_id: str
    location: str | None
    work_mode: str | None
    duration_months: int | None
    stipend_amount: float | None
    stipend_currency: str | None
    eligibility_criteria: str | None
    application_deadline: str | None
    start_date: str | None
    status: str

    association_id: str
    association_status: str
    added_at: str | None

    applicants_from_institution: int
    selected_from_institution: int
    participation: ParticipationBreakdown
    status_distribution: list[StatusCount]
    applicants: list[InstitutionInternshipApplicant]

    eligibility_note: str
    participation_note: str
    privacy_note: str


# ---- overview / KPIs / analytics ----


class InternshipKpis(BaseModel):
    curated_internships: int
    """Total internships this institution has ACTIVELY curated."""
    active_internships: int
    """Curated AND the underlying posting is still PUBLISHED."""
    companies: int
    """Distinct companies represented among curated internships."""
    applicants: int
    selected_students: int
    active_participants: int
    completed_internships: int
    participation_unknown: int


class DepartmentInternshipBreakdown(BaseModel):
    id: str
    name: str
    student_count: int
    participants: int
    participation_rate: float | None
    selected_count: int
    completed_count: int


class CompanyInternshipBreakdown(BaseModel):
    company_name: str
    opportunities: int
    applicants: int
    selected: int
    completed: int


class ModeCount(BaseModel):
    mode: str
    count: int


class StipendCurrencyStats(BaseModel):
    currency: str
    internship_count: int
    average_stipend: float
    min_stipend: float
    max_stipend: float


class StipendStats(BaseModel):
    available: bool
    note: str
    by_currency: list[StipendCurrencyStats]


class InstitutionInternshipOverviewResponse(BaseModel):
    kpis: InternshipKpis
    departments: list[DepartmentInternshipBreakdown]
    companies: list[CompanyInternshipBreakdown]
    mode_distribution: list[ModeCount]
    # Internship POSTING status (DRAFT/PUBLISHED/CLOSED/ARCHIVED) among
    # every internship this institution has curated -- not application status.
    status_distribution: list[StatusCount]
    # Application-lifecycle activity (APPLIED/SHORTLISTED/.../SELECTED/...)
    # among the institution's own students' applications to curated internships.
    application_status_distribution: list[StatusCount]
    stipend: StipendStats

    tenancy_note: str
    eligibility_note: str
    participation_note: str
    curation_note: str
