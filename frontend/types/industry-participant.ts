// Mirrors backend/app/schemas/industry_participant.py -- the cross-module
// Industry Participant view, composed server-side from the four existing
// Applicants sources (no new table). See that module's docstring.

import {
  TRAINING_APPLICATION_STATUS_LABELS,
  type TrainingApplicationStatus,
} from "@/types/training-application";
import {
  WORKSHOP_APPLICATION_STATUS_LABELS,
  type WorkshopApplicationStatus,
} from "@/types/workshop-application";

export const PARTICIPANT_OPPORTUNITY_TYPES = [
  "INTERNSHIP",
  "JOB",
  "PROJECT",
  "WORKSHOP",
  "TRAINING",
] as const;
export type ParticipantOpportunityType = (typeof PARTICIPANT_OPPORTUNITY_TYPES)[number];

export const PARTICIPANT_OPPORTUNITY_TYPE_LABELS: Record<ParticipantOpportunityType, string> = {
  INTERNSHIP: "Internship",
  JOB: "Job",
  PROJECT: "Project",
  WORKSHOP: "Workshop",
  TRAINING: "Training",
};

// Fallback labels for Job/Internship/Project statuses, which never use
// "ACCEPTED" so there's no ambiguity. Workshop/Training use "ACCEPTED" but
// mean "Enrolled" -- handled per-module in participantStatusLabel() below
// via each module's own *_APPLICATION_STATUS_LABELS, never invented here.
const _GENERIC_STATUS_LABELS: Record<string, string> = {
  APPLIED: "Applied",
  UNDER_REVIEW: "Under review",
  SHORTLISTED: "Shortlisted",
  INTERVIEW_SCHEDULED: "Interview",
  SELECTED: "Selected",
  ACTIVE: "Active",
  COMPLETED: "Completed",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
};

export interface ParticipantRecord {
  id: string;
  student_id: string;
  student_name: string | null;
  institution_name: string | null;
  department: string | null;
  graduation_year: number | null;
  skills: string[] | null;
  opportunity_type: ParticipantOpportunityType;
  opportunity_id: string;
  opportunity_title: string;
  opportunity_href: string;
  status: string;
  applied_at: string | null;
}

export interface ParticipantListResponse {
  records: ParticipantRecord[];
}

export function participantRef(studentId: string): string {
  return `Applicant ${studentId.slice(0, 8)}`;
}

export function participantDisplayName(record: { student_id: string; student_name: string | null }): string {
  const name = record.student_name?.trim();
  return name ? name : participantRef(record.student_id);
}

/** The human-readable status label for one participant record, using
 * each module's own existing label map for WORKSHOP/TRAINING (where
 * "ACCEPTED" means "Enrolled") and a shared fallback for the rest --
 * never a raw enum value. */
export function participantStatusLabel(record: ParticipantRecord): string {
  if (record.opportunity_type === "WORKSHOP") {
    return WORKSHOP_APPLICATION_STATUS_LABELS[record.status as WorkshopApplicationStatus] ?? record.status;
  }
  if (record.opportunity_type === "TRAINING") {
    return TRAINING_APPLICATION_STATUS_LABELS[record.status as TrainingApplicationStatus] ?? record.status;
  }
  return _GENERIC_STATUS_LABELS[record.status] ?? record.status;
}
