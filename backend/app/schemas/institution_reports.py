"""Pydantic schemas for the Institution Reports module
(backend/app/api/institution.py, GET /api/v1/institution/reports).

PHASE 11. This is NOT a second Analytics module and NOT a new data
model -- every report reshapes the output of an EXISTING institution
service (institution_analytics_service, institution_internship_service,
institution_student_service, institution_department_service,
institution_industry_service, institution_industry_connection_service,
institution_event_service, industry_collaboration_service). See
institution_reports_service.py's own docstring for exactly which
function backs which report, so this module never recomputes a
definition ("placed", "selected", "company", "department") that already
has one authoritative implementation.

No new database table exists or is needed. No CSV/PDF library exists
anywhere in this repository (confirmed by a full-repo audit before this
phase started) -- export is therefore not implemented server-side; the
frontend generates CSV client-side from this same JSON response (a
handful of lines of plain string-joining, no dependency) and offers a
browser Print for a formatted copy. See the module's own report for the
full audit findings.
"""

from typing import Literal

from pydantic import BaseModel

ReportType = Literal[
    "PLACEMENT", "INTERNSHIP", "STUDENT", "DEPARTMENT", "INDUSTRY", "EVENTS", "COLLABORATION"
]

REPORT_TYPES: tuple[str, ...] = (
    "PLACEMENT",
    "INTERNSHIP",
    "STUDENT",
    "DEPARTMENT",
    "INDUSTRY",
    "EVENTS",
    "COLLABORATION",
)


class CategoryCountRow(BaseModel):
    """Generic (label, count) row -- reused for every breakdown in this
    module (application status, internship status, event mode, event
    status, collaboration status, ...) rather than a differently-named
    model per breakdown for what is structurally the same shape."""

    label: str
    count: int


class ReportFilters(BaseModel):
    """Echoes back exactly which filters were actually applied -- not
    every report honours every filter (Step 5: "do not expose a filter
    the backend cannot apply accurately"); see each report's own `note`
    for which of these it respects."""

    department_id: str | None = None
    batch: int | None = None
    company_id: str | None = None
    status: str | None = None
    event_type: str | None = None
    collaboration_status: str | None = None
    date_from: str | None = None
    date_to: str | None = None


# ============================================================
# Placement Report -- backed entirely by institution_analytics_service.
# compute_institution_analytics (Phase 6), which already supports
# department_id/batch/date_from/date_to filters. No new calculation.
# ============================================================


class PlacementReportSummary(BaseModel):
    total_students: int
    students_with_applications: int
    students_selected: int
    placement_rate: float | None
    companies_involved: int
    active_placement_drives: int


class PlacementReportDepartmentRow(BaseModel):
    department_id: str
    department: str
    student_count: int
    placed_count: int
    placement_rate: float | None


class PlacementReportCompanyRow(BaseModel):
    company_name: str
    applicants: int
    selected_offers: int
    unique_students_placed: int
    # selected_offers / applicants -- None when applicants == 0.
    selection_rate: float | None


class PlacementReport(BaseModel):
    summary: PlacementReportSummary
    department_breakdown: list[PlacementReportDepartmentRow]
    company_breakdown: list[PlacementReportCompanyRow]
    status_breakdown: list[CategoryCountRow]
    note: str


# ============================================================
# Internship Report -- backed entirely by institution_internship_service.
# compute_internship_overview (Phase 7). Institution-wide only: that
# service does not support department/batch/date filtering, and
# partially filtering only the breakdown tables (not the KPIs) would
# produce inconsistent numbers -- so this report deliberately ignores
# department_id/batch/date filters rather than half-applying them.
# ============================================================


class InternshipReportKpis(BaseModel):
    """Mirrors institution_internship_service.compute_internship_overview's
    `kpis` exactly -- scoped to this institution's CURATED internships
    only, never every platform internship."""

    curated_internships: int
    active_internships: int
    companies: int
    applicants: int
    selected_students: int
    active_participants: int
    completed_internships: int
    participation_unknown: int


class InternshipReportDepartmentRow(BaseModel):
    department_id: str
    department: str
    student_count: int
    participants: int
    participation_rate: float | None
    selected_count: int
    completed_count: int


class InternshipReportCompanyRow(BaseModel):
    company_name: str
    opportunities: int
    applicants: int
    selected: int
    completed: int


class InternshipReportStipendRow(BaseModel):
    currency: str
    internship_count: int
    average_stipend: float
    min_stipend: float
    max_stipend: float


class InternshipReport(BaseModel):
    kpis: InternshipReportKpis
    department_breakdown: list[InternshipReportDepartmentRow]
    company_breakdown: list[InternshipReportCompanyRow]
    mode_distribution: list[CategoryCountRow]
    status_breakdown: list[CategoryCountRow]
    stipend_by_currency: list[InternshipReportStipendRow]
    note: str


# ============================================================
# Student Report -- backed entirely by institution_student_service.
# list_students (Phase 3). Same privacy boundary: no email/phone.
# ============================================================


class StudentReportRow(BaseModel):
    full_name: str | None
    username: str | None
    department: str
    batch: int | None
    cgpa: float | None
    placement_status: str
    internship_status: str
    top_skills: list[str]


class StudentReport(BaseModel):
    students: list[StudentReportRow]
    total: int
    page: int
    page_size: int
    summary: dict
    note: str


# ============================================================
# Department Report -- backed by institution_department_service.
# list_departments (Phase 4) plus one new, honestly-derived aggregate
# (average CGPA) computed directly from student_profiles.cgpa -- no
# average-CGPA metric exists anywhere else in this project to compete
# with, so this is additive, not a redefinition of anything.
# ============================================================


class DepartmentReportRow(BaseModel):
    id: str
    name: str
    code: str | None
    student_count: int
    # None when no student in the department has a recorded CGPA.
    average_cgpa: float | None
    placed_count: int
    placement_rate: float | None
    internship_selected_count: int
    applications_total: int


class DepartmentReport(BaseModel):
    departments: list[DepartmentReportRow]
    note: str


# ============================================================
# Industry / Company Report -- backed by institution_industry_service
# (Phase 8, company activity + explicit relationships),
# institution_industry_connection_service (Phase 9, connection counts),
# institution_event_service (Phase 10, event counts), and
# industry_collaboration_service (existing, collaboration counts) --
# each fetched ONCE and grouped by industry_id, never per-company (no N+1).
# ============================================================


class CompanyReportRow(BaseModel):
    id: str
    company_name: str | None
    industry_sector: str | None
    relationship_type: str | None
    relationship_status: str | None
    has_explicit_relationship: bool
    jobs_opportunities: int
    jobs_selected_students: int
    internship_opportunities: int
    internship_selected: int
    placement_drives_count: int
    students_selected: int
    connections_count: int
    events_count: int
    collaborations_count: int
    last_activity_at: str | None


class CompanyReportMetrics(BaseModel):
    total_partners: int
    active_partners: int
    recruiting_partners: int
    internship_partners: int
    placement_drives_total: int
    students_selected_total: int
    internship_students_total: int


class CompanyReport(BaseModel):
    companies: list[CompanyReportRow]
    metrics: CompanyReportMetrics
    note: str


# ============================================================
# Events Report -- backed entirely by institution_event_service
# (Phase 10). No registration/attendance field exists anywhere.
# ============================================================


class EventReportRow(BaseModel):
    id: str
    source: str
    title: str
    event_type: str
    status: str
    company_name: str | None
    start_at: str | None
    end_at: str | None
    target_department_names: list[str]
    target_batches: list[int]
    platform_wide: bool


class EventsReport(BaseModel):
    events: list[EventReportRow]
    total_events: int
    upcoming_events: int
    completed_events: int
    registration_note: str


# ============================================================
# Collaboration Report -- backed entirely by the EXISTING
# industry_collaboration_service.list_incoming_collaborations
# (industry_collaborations, 026). Lifecycle untouched.
# ============================================================


class CollaborationReportRow(BaseModel):
    id: str
    title: str
    company_name: str | None
    status: str
    created_at: str | None
    updated_at: str | None


class CollaborationReport(BaseModel):
    collaborations: list[CollaborationReportRow]
    status_breakdown: list[CategoryCountRow]
    note: str


# ============================================================
# top-level envelope
# ============================================================


class InstitutionReportResponse(BaseModel):
    report_type: ReportType
    institution_name: str | None
    generated_at: str
    filters_applied: ReportFilters

    placement: PlacementReport | None = None
    internship: InternshipReport | None = None
    student: StudentReport | None = None
    department: DepartmentReport | None = None
    industry: CompanyReport | None = None
    events: EventsReport | None = None
    collaboration: CollaborationReport | None = None
