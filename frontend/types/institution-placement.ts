// Mirrors backend/app/schemas/institution_placement.py -- the
// Institution Placement Drive Management module (database/migrations/
// 041_institution_placement_drives.sql).
//
// A placement drive coordinates an EXISTING job/application/interview
// pipeline -- it never introduces a second "placement" concept. "Placed"
// still means exactly what it means everywhere else in this app: an
// application with status = 'SELECTED'.

export type DriveStatus = "DRAFT" | "OPEN" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
export type DriveMode = "ONSITE" | "REMOTE" | "HYBRID";

export const DRIVE_STATUSES: DriveStatus[] = ["DRAFT", "OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"];

export const DRIVE_STATUS_LABELS: Record<DriveStatus, string> = {
  DRAFT: "Draft",
  OPEN: "Open",
  IN_PROGRESS: "In Progress",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

/** Same transition map as institution_placement_service._VALID_TRANSITIONS
 * -- kept here only to drive which buttons are shown, never trusted as
 * the actual authorization: the backend re-validates every transition. */
export const DRIVE_STATUS_TRANSITIONS: Record<DriveStatus, DriveStatus[]> = {
  DRAFT: ["OPEN", "CANCELLED"],
  OPEN: ["IN_PROGRESS", "CANCELLED"],
  IN_PROGRESS: ["COMPLETED", "CANCELLED"],
  COMPLETED: [],
  CANCELLED: [],
};

export interface AvailableJobOption {
  id: string;
  title: string;
  company_name: string | null;
  work_mode: string | null;
  employment_type: string | null;
  location: string | null;
  application_deadline: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
}

export interface PlacementDriveSummary {
  id: string;
  job_id: string;
  job_title: string | null;
  company_name: string | null;
  location: string | null;
  work_mode: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  // The underlying job's CURRENT status -- may no longer be PUBLISHED for
  // a historical drive (institution_visible_job_details).
  job_status: string | null;

  title: string;
  status: DriveStatus;
  application_deadline: string | null;
  drive_date: string | null;
  mode: DriveMode | null;
  venue: string | null;

  eligible_department_ids: string[];
  eligible_department_names: string[];
  eligible_batches: number[];
  minimum_cgpa: number | null;
  eligible_skill_ids: string[];
  eligible_skill_names: string[];

  eligible_count: number;
  applied_count: number;
  selected_count: number;

  created_at: string | null;
  updated_at: string | null;
}

export interface PlacementDriveDetail extends PlacementDriveSummary {
  description: string | null;
  instructions: string | null;
  job_description: string | null;
}

export interface PlacementDriveListResponse {
  drives: PlacementDriveSummary[];
}

export interface PlacementDriveFields {
  job_id: string;
  title: string;
  description?: string | null;
  application_deadline?: string | null;
  drive_date?: string | null;
  mode?: DriveMode | null;
  venue?: string | null;
  instructions?: string | null;
  eligible_department_ids?: string[];
  eligible_batches?: number[];
  minimum_cgpa?: number | null;
  eligible_skill_ids?: string[];
}

export type PlacementDriveUpdateFields = Partial<Omit<PlacementDriveFields, "job_id">>;

export interface EligibleStudent {
  id: string;
  full_name: string | null;
  username: string | null;
  avatar_url: string | null;
  department: string;
  batch: number | null;
  cgpa: number | null;
  is_eligible: boolean;
  reasons: string[];
  // null when this student has not applied to the drive's job at all.
  application_status: string | null;
}

export interface DriveStudentsResponse {
  students: EligibleStudent[];
  eligible_count: number;
  applied_count: number;
}

export interface DriveApplicantInterview {
  scheduled_at: string;
  mode: string;
  status: string;
}

export interface DriveApplicant {
  application_id: string;
  student_id: string;
  full_name: string | null;
  username: string | null;
  department: string;
  cgpa: number | null;
  status: string;
  applied_at: string | null;
  interview: DriveApplicantInterview | null;
}

export interface DriveApplicantsResponse {
  applicants: DriveApplicant[];
}

export interface DepartmentPlacementBreakdown {
  department: string;
  placed_count: number;
}

export interface CompanyPlacementBreakdown {
  company_name: string;
  selected_count: number;
}

export interface PlacementOverviewResponse {
  active_drives: number;
  completed_drives: number;
  participating_students: number;
  placed_students: number;
  total_selected_offers: number;
  placement_rate: number | null;
  department_breakdown: DepartmentPlacementBreakdown[];
  company_breakdown: CompanyPlacementBreakdown[];
}

export interface PlacementDriveListParams {
  search?: string;
  status?: DriveStatus;
}
