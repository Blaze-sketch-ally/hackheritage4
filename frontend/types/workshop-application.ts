// Mirrors `industry_workshop_applications`
// (database/migrations/056_workshop_applications.sql) and
// backend/app/schemas/workshop_application.py. Keep all three in sync.
//
// Applicant identity: name/institution/department/graduation year/skills
// are resolved server-side via public.workshop_applicant_profiles (056) --
// never a raw student_id shown as the primary identity. Same fallback
// convention as types/application.ts's `applicantDisplayName`.

export const WORKSHOP_APPLICATION_STATUSES = [
  "APPLIED",
  "ACCEPTED",
  "REJECTED",
  "WITHDRAWN",
  "COMPLETED",
] as const;
export type WorkshopApplicationStatus = (typeof WORKSHOP_APPLICATION_STATUSES)[number];

export const WORKSHOP_APPLICATION_STATUS_LABELS: Record<WorkshopApplicationStatus, string> = {
  APPLIED: "Applied",
  ACCEPTED: "Accepted",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
  COMPLETED: "Completed",
};

/** The statuses an Industry account can move a Workshop application to.
 * Mirrors backend `IndustrySettableWorkshopStatus`. */
export const INDUSTRY_SETTABLE_WORKSHOP_STATUSES = ["ACCEPTED", "REJECTED", "COMPLETED"] as const;
export type IndustrySettableWorkshopStatus = (typeof INDUSTRY_SETTABLE_WORKSHOP_STATUSES)[number];

/** Valid Industry-driven transitions. Mirrors
 * industry_workshop_application_service._STATUS_TRANSITIONS. */
export const WORKSHOP_APPLICATION_TRANSITIONS: Record<
  WorkshopApplicationStatus,
  IndustrySettableWorkshopStatus[]
> = {
  APPLIED: ["ACCEPTED", "REJECTED"],
  ACCEPTED: ["COMPLETED", "REJECTED"],
  REJECTED: [],
  WITHDRAWN: [],
  COMPLETED: [],
};

export const WORKSHOP_TRANSITION_LABELS: Record<IndustrySettableWorkshopStatus, string> = {
  ACCEPTED: "Accept",
  REJECTED: "Reject",
  COMPLETED: "Mark completed",
};

export interface WorkshopApplicationOpportunity {
  id: string;
  title: string;
  status: string;
}

export interface WorkshopApplication {
  id: string;
  student_id: string;
  student_name?: string | null;
  institution_name?: string | null;
  department?: string | null;
  graduation_year?: number | null;
  skills?: string[] | null;
  industry_id: string;
  workshop_id: string;
  status: WorkshopApplicationStatus;
  applied_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  workshop: WorkshopApplicationOpportunity | null;
}

export interface WorkshopApplicationListResponse {
  applications: WorkshopApplication[];
}

/** A short, privacy-safe label for an applicant, built only from the id. */
export function workshopApplicantRef(studentId: string): string {
  return `Applicant ${studentId.slice(0, 8)}`;
}

export function workshopApplicantDisplayName(application: {
  student_id: string;
  student_name?: string | null;
}): string {
  const name = application.student_name?.trim();
  return name ? name : workshopApplicantRef(application.student_id);
}
