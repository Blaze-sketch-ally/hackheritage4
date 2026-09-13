// Mirrors `industry_training_applications`
// (database/migrations/059_training_applications.sql) and
// backend/app/schemas/training_application.py. Keep all three in sync.
//
// "ACCEPTED" is the DB value; the UI label is "Enrolled" -- no separate
// ACTIVE status exists in the database for this friendlier wording.

export const TRAINING_APPLICATION_STATUSES = [
  "APPLIED",
  "ACCEPTED",
  "REJECTED",
  "WITHDRAWN",
  "COMPLETED",
] as const;
export type TrainingApplicationStatus = (typeof TRAINING_APPLICATION_STATUSES)[number];

export const TRAINING_APPLICATION_STATUS_LABELS: Record<TrainingApplicationStatus, string> = {
  APPLIED: "Registered",
  ACCEPTED: "Enrolled",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
  COMPLETED: "Completed",
};

export const INDUSTRY_SETTABLE_TRAINING_STATUSES = ["ACCEPTED", "REJECTED", "COMPLETED"] as const;
export type IndustrySettableTrainingStatus = (typeof INDUSTRY_SETTABLE_TRAINING_STATUSES)[number];

/** Valid Industry-driven transitions. Mirrors
 * industry_training_application_service._STATUS_TRANSITIONS. */
export const TRAINING_APPLICATION_TRANSITIONS: Record<
  TrainingApplicationStatus,
  IndustrySettableTrainingStatus[]
> = {
  APPLIED: ["ACCEPTED", "REJECTED"],
  ACCEPTED: ["COMPLETED", "REJECTED"],
  REJECTED: [],
  WITHDRAWN: [],
  COMPLETED: [],
};

export const TRAINING_TRANSITION_LABELS: Record<IndustrySettableTrainingStatus, string> = {
  ACCEPTED: "Enroll",
  REJECTED: "Reject",
  COMPLETED: "Mark completed",
};

export interface TrainingApplicationOpportunity {
  id: string;
  title: string;
  status: string;
}

export interface TrainingApplication {
  id: string;
  student_id: string;
  student_name?: string | null;
  institution_name?: string | null;
  department?: string | null;
  graduation_year?: number | null;
  skills?: string[] | null;
  industry_id: string;
  training_id: string;
  status: TrainingApplicationStatus;
  applied_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  training: TrainingApplicationOpportunity | null;
}

export interface TrainingApplicationListResponse {
  applications: TrainingApplication[];
}

export function trainingApplicantRef(studentId: string): string {
  return `Applicant ${studentId.slice(0, 8)}`;
}

export function trainingApplicantDisplayName(application: {
  student_id: string;
  student_name?: string | null;
}): string {
  const name = application.student_name?.trim();
  return name ? name : trainingApplicantRef(application.student_id);
}
