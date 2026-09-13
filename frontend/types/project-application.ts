// Mirrors `industry_project_applications`
// (database/migrations/057_project_applications.sql) and
// backend/app/schemas/project_application.py. Keep all three in sync.
//
// Projects intentionally skip the Internship/Job interview workflow:
// Apply -> Shortlist -> Select -> Active -> Completed.

export const PROJECT_APPLICATION_STATUSES = [
  "APPLIED",
  "SHORTLISTED",
  "SELECTED",
  "ACTIVE",
  "REJECTED",
  "WITHDRAWN",
  "COMPLETED",
] as const;
export type ProjectApplicationStatus = (typeof PROJECT_APPLICATION_STATUSES)[number];

export const PROJECT_APPLICATION_STATUS_LABELS: Record<ProjectApplicationStatus, string> = {
  APPLIED: "Applied",
  SHORTLISTED: "Shortlisted",
  SELECTED: "Selected",
  ACTIVE: "Active",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
  COMPLETED: "Completed",
};

export const INDUSTRY_SETTABLE_PROJECT_STATUSES = [
  "SHORTLISTED",
  "SELECTED",
  "ACTIVE",
  "REJECTED",
  "COMPLETED",
] as const;
export type IndustrySettableProjectStatus = (typeof INDUSTRY_SETTABLE_PROJECT_STATUSES)[number];

/** Valid Industry-driven transitions. Mirrors
 * industry_project_application_service._STATUS_TRANSITIONS. A strong
 * candidate can be Selected directly from Applied, without a Shortlist
 * step. */
export const PROJECT_APPLICATION_TRANSITIONS: Record<
  ProjectApplicationStatus,
  IndustrySettableProjectStatus[]
> = {
  APPLIED: ["SHORTLISTED", "SELECTED", "REJECTED"],
  SHORTLISTED: ["SELECTED", "REJECTED"],
  SELECTED: ["ACTIVE"],
  ACTIVE: ["COMPLETED"],
  REJECTED: [],
  WITHDRAWN: [],
  COMPLETED: [],
};

export const PROJECT_TRANSITION_LABELS: Record<IndustrySettableProjectStatus, string> = {
  SHORTLISTED: "Shortlist",
  SELECTED: "Select",
  ACTIVE: "Mark active",
  REJECTED: "Reject",
  COMPLETED: "Mark completed",
};

export interface ProjectApplicationOpportunity {
  id: string;
  title: string;
  status: string;
}

export interface ProjectApplication {
  id: string;
  student_id: string;
  student_name?: string | null;
  institution_name?: string | null;
  department?: string | null;
  graduation_year?: number | null;
  skills?: string[] | null;
  industry_id: string;
  project_id: string;
  status: ProjectApplicationStatus;
  applied_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  project: ProjectApplicationOpportunity | null;
}

export interface ProjectApplicationListResponse {
  applications: ProjectApplication[];
}

export function projectApplicantRef(studentId: string): string {
  return `Applicant ${studentId.slice(0, 8)}`;
}

export function projectApplicantDisplayName(application: {
  student_id: string;
  student_name?: string | null;
}): string {
  const name = application.student_name?.trim();
  return name ? name : projectApplicantRef(application.student_id);
}
