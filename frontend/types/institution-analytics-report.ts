// Mirrors backend/app/schemas/institution_analytics.py
// (InstitutionAnalyticsResponse, GET /api/v1/institution/analytics).
//
// This is the Institution ANALYTICS workspace's response shape -- distinct
// from types/institution-analytics.ts (the Dashboard's InstitutionOverview).
// Every number here reuses the same authoritative calculations the
// Dashboard/Departments/Placements pages already use -- see the backend
// service's own docstring for exactly what is reused vs newly computed.

export interface AnalyticsFilters {
  department_id: string | null;
  batch: number | null;
  date_from: string | null;
  date_to: string | null;
}

export interface DepartmentFilterOption {
  id: string;
  name: string;
}

export interface AnalyticsFilterOptions {
  departments: DepartmentFilterOption[];
  batches: number[];
}

export interface AnalyticsOverview {
  total_students: number;
  placed_students: number;
  unplaced_students: number;
  placement_rate: number | null;
  students_with_applications: number;
  students_without_applications: number;
  internship_participants: number;
  active_placement_drives: number;
  completed_placement_drives: number;
}

export interface DepartmentAnalytics {
  id: string;
  name: string;
  code: string | null;
  is_active: boolean;
  student_count: number;
  placed_count: number;
  unplaced_count: number;
  no_applications_count: number;
  placement_rate: number | null;
  internship_selected_count: number;
}

export interface DriveAnalyticsRow {
  id: string;
  title: string;
  company_name: string | null;
  status: string;
  eligible_count: number;
  applied_count: number;
  selected_count: number;
  selection_rate: number | null;
}

export interface DepartmentPlacementBreakdown {
  department: string;
  placed_count: number;
}

export interface PlacementAnalytics {
  total_drives: number;
  active_drives: number;
  completed_drives: number;
  cancelled_drives: number;
  draft_drives: number;
  participating_students: number;
  placed_students: number;
  total_selected_offers: number;
  placement_rate: number | null;
  average_applicants_per_drive: number | null;
  department_breakdown: DepartmentPlacementBreakdown[];
  drives: DriveAnalyticsRow[];
}

export interface CompanyHiring {
  company_name: string;
  postings_count: number;
  applicants: number;
  selected_offers: number;
  unique_students_placed: number;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface ApplicationAnalytics {
  total_applications: number;
  students_with_applications: number;
  students_without_applications: number;
  applications_per_applying_student: number | null;
  status_distribution: StatusCount[];
}

export interface SkillCoverage {
  skill_name: string;
  student_count: number;
  coverage_percentage: number | null;
}

export interface SkillAnalytics {
  total_students_considered: number;
  top_skills: SkillCoverage[];
}

export interface SkillGapItem {
  skill_name: string;
  student_coverage_count: number;
  student_coverage_percentage: number | null;
  job_demand_count: number;
  high_demand: boolean;
  low_coverage: boolean;
}

export interface SkillGapAnalytics {
  available: boolean;
  note: string;
  items: SkillGapItem[];
}

export interface InternshipAnalytics {
  available: boolean;
  note: string;
  participants: number;
  applications_total: number;
  participation_rate: number | null;
  status_distribution: StatusCount[];
}

export interface AssessmentAnalytics {
  students_assessed: number;
  total_attempts: number;
  average_score: number | null;
}

export interface InterviewAnalytics {
  total: number;
  students_interviewed: number;
  scheduled: number;
  completed: number;
  cancelled: number;
  upcoming: number;
}

export interface TrendPoint {
  /** "YYYY-MM" */
  period: string;
  applications: number;
  selections: number;
  internship_applications: number;
}

export interface TrendAnalytics {
  has_sufficient_data: boolean;
  months: TrendPoint[];
  historical_note: string;
}

export interface InstitutionAnalyticsReport {
  generated_at: string;
  institution_name: string | null;
  filters_applied: AnalyticsFilters;
  filter_options: AnalyticsFilterOptions;

  overview: AnalyticsOverview;
  departments: DepartmentAnalytics[];
  placements: PlacementAnalytics;
  companies: CompanyHiring[];
  applications: ApplicationAnalytics;
  skills: SkillAnalytics;
  skill_gaps: SkillGapAnalytics;
  internships: InternshipAnalytics;
  assessments: AssessmentAnalytics;
  interviews: InterviewAnalytics;
  trends: TrendAnalytics;

  tenancy_note: string;
  eligibility_note: string;
  filter_scope_note: string;
}

/** Real applications.status values (database/migrations/020_applications.sql)
 * -- mirrors types/application.ts's own label map, duplicated here only as
 * plain labels (no import cycle risk) since this module is analytics-only. */
export const APPLICATION_STATUS_LABELS: Record<string, string> = {
  APPLIED: "Applied",
  UNDER_REVIEW: "Under Review",
  SHORTLISTED: "Shortlisted",
  INTERVIEW_SCHEDULED: "Interview Scheduled",
  SELECTED: "Selected",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
};

export const ANALYTICS_METRIC_DEFINITIONS = {
  overview: "Core counts among students linked to your institution, respecting the active filters.",
  departments:
    "The exact same per-department rows shown on the Departments page -- always institution-wide, never filtered by this page's own department selector.",
  placements:
    "Placement-drive coordination summary -- always institution-wide. Reuses the same placed/selected definitions as the Placement Drives page.",
  companies:
    "Every company your institution's students have applied to (directly or through a coordinated drive), always institution-wide.",
  applications: "Application volume and status distribution among the students in scope.",
  skills: "How many students in scope have each skill on file, and what share of the scope that represents.",
  skillGaps:
    "Compares your students' skill coverage against how many currently-PUBLISHED jobs (platform-wide) require each skill.",
  internships: "Internship application participation among the students in scope.",
  assessments: "Assessment attempts and average score among the students in scope. No pass/fail threshold exists in this schema.",
  interviews: "Interview records for the students in scope, excluding any industry-private notes.",
  trends: "Monthly application activity over the last 6 months, by submission date.",
} as const;
