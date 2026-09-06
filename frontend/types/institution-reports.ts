// Mirrors backend/app/schemas/institution_reports.py
// (GET /api/v1/institution/reports).
//
// PHASE 11. NOT a second Analytics module -- every report reshapes the
// output of an EXISTING institution service (see the backend module's
// own docstring for exactly which one backs which report). No new data
// model, no re-derived "placed"/"selected"/"company"/"department"
// definition.

export const REPORT_TYPES = [
  "PLACEMENT",
  "INTERNSHIP",
  "STUDENT",
  "DEPARTMENT",
  "INDUSTRY",
  "EVENTS",
  "COLLABORATION",
] as const;
export type ReportType = (typeof REPORT_TYPES)[number];

export const REPORT_TYPE_LABELS: Record<ReportType, string> = {
  PLACEMENT: "Placement Report",
  INTERNSHIP: "Internship Report",
  STUDENT: "Student Report",
  DEPARTMENT: "Department Report",
  INDUSTRY: "Industry / Company Report",
  EVENTS: "Events Report",
  COLLABORATION: "Collaboration Report",
};

export const REPORT_TYPE_DESCRIPTIONS: Record<ReportType, string> = {
  PLACEMENT: "Placement summary, department breakdown, company breakdown and application status.",
  INTERNSHIP: "Internship opportunities, applications, companies, stipend and department distribution.",
  STUDENT: "Institution-scoped student roster with placement and internship status.",
  DEPARTMENT: "Per-department students, average CGPA, placement and internship participation.",
  INDUSTRY: "Company relationships, recruitment/internship activity, connections and collaborations.",
  EVENTS: "Institution-organized events and published industry workshops.",
  COLLABORATION: "Collaboration proposals with your institution, by status.",
};

export interface CategoryCountRow {
  label: string;
  count: number;
}

export interface ReportFilters {
  department_id: string | null;
  batch: number | null;
  company_id: string | null;
  status: string | null;
  event_type: string | null;
  collaboration_status: string | null;
  date_from: string | null;
  date_to: string | null;
}

// ---- Placement ----

export interface PlacementReportSummary {
  total_students: number;
  students_with_applications: number;
  students_selected: number;
  placement_rate: number | null;
  companies_involved: number;
  active_placement_drives: number;
}

export interface PlacementReportDepartmentRow {
  department_id: string;
  department: string;
  student_count: number;
  placed_count: number;
  placement_rate: number | null;
}

export interface PlacementReportCompanyRow {
  company_name: string;
  applicants: number;
  selected_offers: number;
  unique_students_placed: number;
  selection_rate: number | null;
}

export interface PlacementReport {
  summary: PlacementReportSummary;
  department_breakdown: PlacementReportDepartmentRow[];
  company_breakdown: PlacementReportCompanyRow[];
  status_breakdown: CategoryCountRow[];
  note: string;
}

// ---- Internship ----

export interface InternshipReportKpis {
  curated_internships: number;
  active_internships: number;
  companies: number;
  applicants: number;
  selected_students: number;
  active_participants: number;
  completed_internships: number;
  participation_unknown: number;
}

export interface InternshipReportDepartmentRow {
  department_id: string;
  department: string;
  student_count: number;
  participants: number;
  participation_rate: number | null;
  selected_count: number;
  completed_count: number;
}

export interface InternshipReportCompanyRow {
  company_name: string;
  opportunities: number;
  applicants: number;
  selected: number;
  completed: number;
}

export interface InternshipReportStipendRow {
  currency: string;
  internship_count: number;
  average_stipend: number;
  min_stipend: number;
  max_stipend: number;
}

export interface InternshipReport {
  kpis: InternshipReportKpis;
  department_breakdown: InternshipReportDepartmentRow[];
  company_breakdown: InternshipReportCompanyRow[];
  mode_distribution: CategoryCountRow[];
  status_breakdown: CategoryCountRow[];
  stipend_by_currency: InternshipReportStipendRow[];
  note: string;
}

// ---- Student ----

export interface StudentReportRow {
  full_name: string | null;
  username: string | null;
  department: string;
  batch: number | null;
  cgpa: number | null;
  placement_status: string;
  internship_status: string;
  top_skills: string[];
}

export interface StudentReport {
  students: StudentReportRow[];
  total: number;
  page: number;
  page_size: number;
  summary: Record<string, number>;
  note: string;
}

// ---- Department ----

export interface DepartmentReportRow {
  id: string;
  name: string;
  code: string | null;
  student_count: number;
  average_cgpa: number | null;
  placed_count: number;
  placement_rate: number | null;
  internship_selected_count: number;
  applications_total: number;
}

export interface DepartmentReport {
  departments: DepartmentReportRow[];
  note: string;
}

// ---- Industry / Company ----

export interface CompanyReportRow {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  relationship_type: string | null;
  relationship_status: string | null;
  has_explicit_relationship: boolean;
  jobs_opportunities: number;
  jobs_selected_students: number;
  internship_opportunities: number;
  internship_selected: number;
  placement_drives_count: number;
  students_selected: number;
  connections_count: number;
  events_count: number;
  collaborations_count: number;
  last_activity_at: string | null;
}

export interface CompanyReportMetrics {
  total_partners: number;
  active_partners: number;
  recruiting_partners: number;
  internship_partners: number;
  placement_drives_total: number;
  students_selected_total: number;
  internship_students_total: number;
}

export interface CompanyReport {
  companies: CompanyReportRow[];
  metrics: CompanyReportMetrics;
  note: string;
}

// ---- Events ----

export interface EventReportRow {
  id: string;
  source: string;
  title: string;
  event_type: string;
  status: string;
  company_name: string | null;
  start_at: string | null;
  end_at: string | null;
  target_department_names: string[];
  target_batches: number[];
  platform_wide: boolean;
}

export interface EventsReport {
  events: EventReportRow[];
  total_events: number;
  upcoming_events: number;
  completed_events: number;
  registration_note: string;
}

// ---- Collaboration ----

export interface CollaborationReportRow {
  id: string;
  title: string;
  company_name: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface CollaborationReport {
  collaborations: CollaborationReportRow[];
  status_breakdown: CategoryCountRow[];
  note: string;
}

// ---- envelope ----

export interface InstitutionReportResponse {
  report_type: ReportType;
  institution_name: string | null;
  generated_at: string;
  filters_applied: ReportFilters;

  placement?: PlacementReport | null;
  internship?: InternshipReport | null;
  student?: StudentReport | null;
  department?: DepartmentReport | null;
  industry?: CompanyReport | null;
  events?: EventsReport | null;
  collaboration?: CollaborationReport | null;
}
