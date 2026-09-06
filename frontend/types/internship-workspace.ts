/**
 * Mirrors backend/app/schemas/internship_workspace.py -- field-for-field,
 * same nullability.
 *
 * The Internship Workspace is the student's post-selection internship
 * offer + training container (database/migrations/038_internship_workspace.sql).
 * There is one workspace per SELECTED internship application, for
 * REMOTE/HYBRID postings only. The student can accept or decline a
 * PENDING_ACCEPTANCE workspace and, once ACCEPTED, choose which OPTIONAL
 * program skills to focus on. Program authoring, assignments, submissions,
 * completion and the certificate are later phases.
 */

export type WorkspaceStatus =
  | "PENDING_ACCEPTANCE"
  | "ACCEPTED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "DECLINED"
  | "RESCINDED";

export const WORKSPACE_STATUSES: WorkspaceStatus[] = [
  "PENDING_ACCEPTANCE",
  "ACCEPTED",
  "IN_PROGRESS",
  "COMPLETED",
  "DECLINED",
  "RESCINDED",
];

/** Friendly label -- the backend value is never changed, only presented. */
export const WORKSPACE_STATUS_LABEL: Record<WorkspaceStatus, string> = {
  PENDING_ACCEPTANCE: "Pending Acceptance",
  ACCEPTED: "Accepted",
  IN_PROGRESS: "In Progress",
  COMPLETED: "Completed",
  DECLINED: "Declined",
  RESCINDED: "Rescinded",
};

export interface WorkspaceInternshipRef {
  id: string;
  title: string | null;
  description: string | null;
  work_mode: string | null;
  /** DRAFT / PUBLISHED / CLOSED / ARCHIVED -- context only, NOT an access
   * gate. The workspace stays readable regardless of this value. */
  status: string | null;
}

export interface InternshipWorkspaceSummary {
  id: string;
  application_id: string;
  internship_id: string;
  student_id: string;
  industry_id: string;
  work_mode: string;
  workspace_status: WorkspaceStatus;
  accepted_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  declined_at: string | null;
  decline_reason: string | null;
  rescinded_at: string | null;
  rescind_reason: string | null;
  created_at: string | null;
  updated_at: string | null;
  internship: WorkspaceInternshipRef | null;
}

export type ModuleItemType = "VIDEO" | "PDF" | "LINK" | "TEXT";

export interface WorkspaceProgramModuleItem {
  id: string;
  title: string;
  item_type: string;
  content_url: string | null;
  content_text: string | null;
  order_index: number;
}

export interface WorkspaceProgramModule {
  id: string;
  title: string;
  description: string | null;
  order_index: number;
  items: WorkspaceProgramModuleItem[];
}

export interface WorkspaceProgramSkill {
  skill_id: string;
  skill_name: string;
  requirement: "REQUIRED" | "OPTIONAL";
}

export interface WorkspaceProgramPreview {
  id: string;
  title: string;
  summary: string | null;
  status: string;
  modules: WorkspaceProgramModule[];
  skills: WorkspaceProgramSkill[];
}

export interface InternshipWorkspaceDetail extends InternshipWorkspaceSummary {
  program: WorkspaceProgramPreview | null;
  /** OPTIONAL program skill_ids the student has currently selected.
   * REQUIRED skills are always in scope and are never listed here. */
  selected_skill_ids: string[];
}

// ---- Phase 5: assignments + the student's own submissions ----

export type SubmissionStatus =
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "REVISION_REQUESTED"
  | "ACCEPTED"
  | "REJECTED";

/** The industry's review of ONE of the student's own attempts, as the
 * student sees it. NO reviewer identity -- the student never learns who
 * reviewed. `reviewed_at` is the review row's timestamp. */
export interface StudentSubmissionReview {
  verdict: string;
  feedback: string | null;
  score: number | null;
  reviewed_at: string | null;
}

/** One of the student's OWN submission attempts, with the industry's
 * review of it (Phase 6 -- append-only history, newest first). The
 * submission's own content is immutable once written. */
export interface WorkspaceSubmission {
  id: string;
  workspace_id: string;
  assignment_id: string;
  attempt_number: number;
  submission_status: string;
  repo_url: string | null;
  live_url: string | null;
  attachment_url: string | null;
  notes: string | null;
  submitted_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  reviews: StudentSubmissionReview[];
  latest_review: StudentSubmissionReview | null;
}

export interface WorkspaceAssignmentBase {
  id: string;
  module_id: string;
  program_id: string;
  title: string;
  description: string | null;
  instructions: string | null;
  assignment_type: string;
  is_required: boolean;
  order_index: number;
  due_offset_days: number | null;
  submission_kind: string;
  repo_required: boolean;
  live_url_expected: boolean;
  max_score: number | null;
  linked_skill_id: string | null;
}

export interface WorkspaceAssignmentSummary extends WorkspaceAssignmentBase {
  module_title: string | null;
  module_order_index: number;
  attempt_count: number;
  latest_submission: WorkspaceSubmission | null;
  can_submit: boolean;
  submit_blocked_reason: string | null;
}

export interface WorkspaceAssignmentList {
  assignments: WorkspaceAssignmentSummary[];
}

export interface WorkspaceAssignmentModuleRef {
  id: string;
  title: string | null;
}

export interface WorkspaceAssignmentDetail {
  assignment: WorkspaceAssignmentBase;
  module: WorkspaceAssignmentModuleRef;
  submissions: WorkspaceSubmission[];
  attempt_count: number;
  can_submit: boolean;
  submit_blocked_reason: string | null;
}

export interface CreateSubmissionInput {
  repo_url?: string | null;
  live_url?: string | null;
  attachment_url?: string | null;
  notes?: string | null;
}
