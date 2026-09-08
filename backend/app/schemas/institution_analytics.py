"""Pydantic schemas for Institution Analytics
(backend/app/api/institution.py, GET /api/v1/institution/analytics).

PHASE 6 -- a dedicated analytics workspace, not a second dashboard and not
a second calculation engine. Every metric here reuses the SAME
authoritative computation already established by earlier phases:

  - "placed" is still exactly `_placement_buckets` (an application with
    status = 'SELECTED') from institution_service.py -- imported, never
    redefined. See institution_analytics_service.py's own docstring for
    the full list of what is reused vs newly computed.
  - `departments` in this response is the literal output of
    institution_department_service.list_departments -- the same rows
    /institution/departments renders, so the two pages can never disagree.
  - `placements.drives` reuses institution_placement_service.list_drives.
  - `placements` (participating/placed/total_selected_offers/placement_rate/
    department_breakdown) reuses institution_placement_service.get_placement_overview.

Honesty boundaries (Part 34/35 of the phase task -- "mark unavailable
rather than inventing a data model"):
  - No AI predictions, scores, or "critical" labels anywhere in this
    module. `skill_gaps` uses two small, DOCUMENTED, constant thresholds
    (see institution_analytics_service._SKILL_GAP_MIN_DEMAND /
    _SKILL_GAP_LOW_COVERAGE_PCT) -- never an opaque score.
  - `skill_gaps.available=False` with an explanatory note when no
    currently-PUBLISHED job declares any required skill (job_skills /
    019_jobs.sql) -- the comparison is skipped, not faked.
  - `assessments` never reports a pass_rate -- no pass/fail threshold
    exists anywhere in the schema (004_assessments.sql only stores raw
    score/percentage).
  - `trends.has_sufficient_data=False` (empty `months`) when the
    institution has no application history at all.
"""

from pydantic import BaseModel

# ---- shared small shapes ----


class StatusCount(BaseModel):
    status: str
    count: int


class AnalyticsFilters(BaseModel):
    """Query parameters actually applied when this response was computed
    -- echoed back so the frontend can show "Filtered by: CSE, Batch 2026"
    next to numbers that respect them. See `filter_scope_note` on the
    top-level response for exactly which sections these narrow."""

    department_id: str | None = None
    batch: int | None = None
    date_from: str | None = None
    date_to: str | None = None


class DepartmentFilterOption(BaseModel):
    id: str
    name: str


class AnalyticsFilterOptions(BaseModel):
    """Available choices for the filter controls -- the same department
    list/batch list the Student Directory already exposes
    (institution_student_service.list_students' own `filters` block),
    not a second derivation."""

    departments: list[DepartmentFilterOption]
    batches: list[int]


# ---- overview ----


class AnalyticsOverview(BaseModel):
    """Institution-wide core KPIs (Part 6). Scoped by the active filters
    (department_id/batch/date range) when present -- unfiltered, this is
    the same total/placed/unplaced/placement_rate the Dashboard shows."""

    total_students: int
    placed_students: int
    unplaced_students: int
    # None when total_students == 0 -- never a fabricated 0%.
    placement_rate: float | None
    students_with_applications: int
    students_without_applications: int
    # Unique students with at least one INTERNSHIP-type application.
    internship_participants: int
    active_placement_drives: int
    completed_placement_drives: int


# ---- departments (Part 7/8 -- literally institution_department_service.list_departments) ----


class DepartmentAnalytics(BaseModel):
    id: str
    name: str
    code: str | None
    is_active: bool
    student_count: int
    placed_count: int
    unplaced_count: int
    no_applications_count: int
    placement_rate: float | None
    internship_selected_count: int


# ---- placement drives (Part 9) ----


class DriveAnalyticsRow(BaseModel):
    id: str
    title: str
    company_name: str | None
    status: str
    eligible_count: int
    applied_count: int
    selected_count: int
    # selected_count / applied_count. None (shown as N/A) when
    # applied_count == 0 -- never a divide-by-zero fabrication.
    selection_rate: float | None


class DepartmentPlacementBreakdown(BaseModel):
    department: str
    placed_count: int


class PlacementAnalytics(BaseModel):
    total_drives: int
    active_drives: int
    completed_drives: int
    cancelled_drives: int
    draft_drives: int
    # Unique institution students who applied to any drive-linked job.
    participating_students: int
    # Unique institution students SELECTED for any drive-linked job.
    placed_students: int
    # Count of SELECTED applications across drive-linked jobs -- can
    # exceed placed_students only if a student holds multiple selected
    # offers across different drives. Never conflated with it.
    total_selected_offers: int
    placement_rate: float | None
    # None when there are no drives at all.
    average_applicants_per_drive: float | None
    department_breakdown: list[DepartmentPlacementBreakdown]
    drives: list[DriveAnalyticsRow]


# ---- companies (Part 10) ----


class CompanyHiring(BaseModel):
    """One company your institution's students have engaged with, across
    EVERY application (job or internship) -- not limited to
    drive-coordinated postings, since a student can apply directly. This
    is analytics only: no company CRM/profile data is added or exposed
    here beyond the name already visible via industry_profiles."""

    company_name: str
    postings_count: int
    applicants: int
    selected_offers: int
    unique_students_placed: int


# ---- applications (Part 11) ----


class ApplicationAnalytics(BaseModel):
    total_applications: int
    students_with_applications: int
    students_without_applications: int
    # total_applications / students_with_applications. None when
    # students_with_applications == 0.
    applications_per_applying_student: float | None
    status_distribution: list[StatusCount]


# ---- skills (Part 12/13) ----


class SkillCoverage(BaseModel):
    skill_name: str
    student_count: int
    # student_count / total students considered. None when there are no
    # students in scope.
    coverage_percentage: float | None


class SkillAnalytics(BaseModel):
    total_students_considered: int
    top_skills: list[SkillCoverage]


# ---- skill gaps (Part 14/15) ----


class SkillGapItem(BaseModel):
    skill_name: str
    student_coverage_count: int
    student_coverage_percentage: float | None
    # Number of currently-PUBLISHED jobs (platform-wide) that require
    # this skill (job_skills, 019_jobs.sql).
    job_demand_count: int
    # Descriptive flags from small documented constant thresholds --
    # never an opaque AI score. See institution_analytics_service.py.
    high_demand: bool
    low_coverage: bool


class SkillGapAnalytics(BaseModel):
    available: bool
    note: str
    items: list[SkillGapItem]


# ---- internships (Part 16) ----


class InternshipAnalytics(BaseModel):
    available: bool
    note: str
    participants: int
    applications_total: int
    # participants / total students considered. None when 0 students.
    participation_rate: float | None
    status_distribution: list[StatusCount]


# ---- assessments (Part 17) ----


class AssessmentAnalytics(BaseModel):
    students_assessed: int
    total_attempts: int
    # None when total_attempts == 0. No pass_rate is reported -- see the
    # module docstring.
    average_score: float | None


# ---- interviews (Part 18) ----


class InterviewAnalytics(BaseModel):
    total: int
    students_interviewed: int
    scheduled: int
    completed: int
    cancelled: int
    upcoming: int


# ---- trends (Part 19) ----


class TrendPoint(BaseModel):
    """'YYYY-MM'. Every count here is by record CREATION date
    (applications.applied_at) -- the schema records no
    status-change timestamp, so this cannot and does not claim to show
    WHEN a student was selected, only when they applied. See
    `historical_note`."""

    period: str
    applications: int
    selections: int
    internship_applications: int


class TrendAnalytics(BaseModel):
    has_sufficient_data: bool
    months: list[TrendPoint]
    historical_note: str


# ---- top-level response ----


class InstitutionAnalyticsResponse(BaseModel):
    generated_at: str
    institution_name: str | None
    filters_applied: AnalyticsFilters
    filter_options: AnalyticsFilterOptions

    overview: AnalyticsOverview
    departments: list[DepartmentAnalytics]
    placements: PlacementAnalytics
    companies: list[CompanyHiring]
    applications: ApplicationAnalytics
    skills: SkillAnalytics
    skill_gaps: SkillGapAnalytics
    internships: InternshipAnalytics
    assessments: AssessmentAnalytics
    interviews: InterviewAnalytics
    trends: TrendAnalytics

    tenancy_note: str
    eligibility_note: str
    # Explains that department_id/batch/date filters narrow the
    # student/application-level sections (overview, applications, skills,
    # skill coverage, internships, assessments, interviews, trends) but
    # NOT the departments table, placement-drive list, or company
    # breakdown -- those are themselves the full breakdown views a filter
    # would otherwise just be re-deriving.
    filter_scope_note: str
