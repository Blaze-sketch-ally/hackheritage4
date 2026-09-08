// Mirrors backend/app/schemas/institution_student.py -- the Institution
// Student Directory (GET /institution/students,
// GET /institution/students/{id}).
//
// `placement_status` reuses the EXACT same three-bucket definition as
// the Institution Dashboard: PLACED (>=1 SELECTED application), APPLYING
// (>=1 application, none SELECTED), NOT_PARTICIPATING (no applications).
// The Dashboard and this Directory must never disagree about what
// "placed" means -- see the backend service's own docstring.

export type PlacementStatus = "PLACED" | "APPLYING" | "NOT_PARTICIPATING";
export type InternshipStatus = "SELECTED" | "APPLYING" | "NONE";

export const PLACEMENT_STATUS_LABELS: Record<PlacementStatus, string> = {
  PLACED: "Placed",
  APPLYING: "Unplaced",
  NOT_PARTICIPATING: "No Applications",
};

export const INTERNSHIP_STATUS_LABELS: Record<InternshipStatus, string> = {
  SELECTED: "Selected",
  APPLYING: "Applying",
  NONE: "None",
};

export interface StudentSummary {
  id: string;
  full_name: string | null;
  username: string | null;
  avatar_url: string | null;
  link_request_id: string | null;
  /** null means "Unassigned" -- see types/institution-department.ts.
   * `department` is the resolved display name ("Unassigned" when
   * department_id is null), not free text anymore. */
  department_id: string | null;
  department: string;
  batch: number | null;
  cgpa: number | null;
  percentage: number | null;
  placement_status: PlacementStatus;
  internship_status: InternshipStatus;
  top_skills: string[];
  profile_completion: number;
}

/** One of the institution's real departments (id + name) -- includes
 * inactive ones too, so a student historically assigned to a
 * since-deactivated department can still be filtered for. "Unassigned"
 * is not listed here -- it's a fixed, well-known filter value
 * (UNASSIGNED_DEPARTMENT_FILTER below), not a real department row. */
export interface DepartmentOption {
  id: string;
  name: string;
}

export const UNASSIGNED_DEPARTMENT_FILTER = "unassigned";

export interface StudentListFilters {
  departments: DepartmentOption[];
  batches: number[];
}

/** Roster-wide counts (before search/filter/pagination) -- the same
 * `_placement_buckets` computation as the Institution Dashboard, so
 * these summary cards can never disagree with the Dashboard's own KPIs
 * for the same institution. */
export interface StudentListSummary {
  total_students: number;
  placed: number;
  unplaced: number;
  no_applications: number;
  internship_selected: number;
}

export interface StudentListResponse {
  students: StudentSummary[];
  total: number;
  page: number;
  page_size: number;
  filters: StudentListFilters;
  summary: StudentListSummary;
}

export interface StudentSkillSummary {
  skill_name: string;
  proficiency_level: string;
  is_verified: boolean;
}

export interface StudentProjectSummary {
  id: string;
  title: string;
  description: string | null;
  project_url: string | null;
  repo_url: string | null;
  is_ongoing: boolean;
  skills: string[];
}

export interface StudentCertificationSummary {
  id: string;
  name: string;
  issuing_organization: string | null;
  issue_date: string | null;
  credential_url: string | null;
}

export interface StudentAchievementSummary {
  id: string;
  title: string;
  description: string | null;
  achievement_date: string | null;
  issuing_organization: string | null;
}

export interface StudentApplicationSummary {
  id: string;
  opportunity_type: "INTERNSHIP" | "JOB";
  opportunity_title: string | null;
  company_name: string | null;
  status: string;
  applied_at: string | null;
}

export interface StudentAssessmentSummary {
  assessment_title: string | null;
  skill_name: string | null;
  status: string;
  percentage: number | null;
  submitted_at: string | null;
}

export interface StudentInterviewSummary {
  id: string;
  opportunity_title: string | null;
  scheduled_at: string;
  mode: string;
  status: string;
}

export interface StudentDetail {
  id: string;
  full_name: string | null;
  username: string | null;
  avatar_url: string | null;
  link_request_id: string | null;

  department_id: string | null;
  department: string;
  /** The student's own free-text student_profiles.department value --
   * informational only, shown to help decide which real department to
   * assign; never the authoritative value. */
  self_reported_department: string | null;
  batch: number | null;
  degree: string | null;
  cgpa: number | null;
  percentage: number | null;
  profile_completion: number;

  skills: StudentSkillSummary[];

  projects: StudentProjectSummary[];
  certifications: StudentCertificationSummary[];
  achievements: StudentAchievementSummary[];

  applications: StudentApplicationSummary[];
  placement_status: PlacementStatus;
  internship_status: InternshipStatus;

  assessments_completed: number;
  average_assessment_percentage: number | null;
  assessments: StudentAssessmentSummary[];

  interviews: StudentInterviewSummary[];

  notes: string[];
}

export interface StudentListParams {
  search?: string;
  department?: string;
  batch?: number;
  cgpa_min?: number;
  cgpa_max?: number;
  placement_status?: PlacementStatus;
  internship_status?: InternshipStatus;
  skill?: string;
  sort_by?: "name" | "cgpa" | "department" | "placement_status";
  sort_dir?: "asc" | "desc";
  page?: number;
  page_size?: number;
}
