/**
 * Mirrors backend/app/schemas/internship_program.py -- field-for-field,
 * same nullability.
 *
 * Phase 4: an industry account authors exactly one internship_program per
 * internship posting (database/migrations/037_internship_program.sql) --
 * metadata, ordered modules, module items, and required/optional program
 * skills -- and publishes it. The student-facing preview (Phase 3)
 * consumes the PUBLISHED result unchanged.
 */

export type ProgramStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
export type SkillRequirement = "REQUIRED" | "OPTIONAL";
export type ModuleItemType = "VIDEO" | "PDF" | "LINK" | "TEXT";

export const MODULE_ITEM_TYPES: ModuleItemType[] = ["VIDEO", "PDF", "LINK", "TEXT"];

// database/migrations/037_internship_program.sql -- program_assignments
export type AssignmentType = "ASSIGNMENT" | "QUIZ" | "PROJECT";
export type SubmissionKind = "LINK" | "REPO" | "FILE" | "TEXT" | "MIXED";
export type SubmissionStatus =
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "REVISION_REQUESTED"
  | "ACCEPTED"
  | "REJECTED";

export const ASSIGNMENT_TYPES: AssignmentType[] = ["ASSIGNMENT", "QUIZ", "PROJECT"];
export const SUBMISSION_KINDS: SubmissionKind[] = ["LINK", "REPO", "FILE", "TEXT", "MIXED"];

export const ASSIGNMENT_TYPE_LABEL: Record<AssignmentType, string> = {
  ASSIGNMENT: "Assignment",
  QUIZ: "Quiz",
  PROJECT: "Project",
};

export const SUBMISSION_KIND_LABEL: Record<SubmissionKind, string> = {
  LINK: "A link (repo or live URL)",
  REPO: "A code repository",
  FILE: "A file / attachment link",
  TEXT: "A written response",
  MIXED: "Repo + live URL + file + notes",
};

export interface ProgramInternshipRef {
  id: string;
  title: string;
  status: string;
}

export interface ProgramMeta {
  id: string;
  internship_id: string;
  title: string;
  summary: string | null;
  estimated_weeks: number | null;
  status: ProgramStatus;
  published_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProgramModuleItem {
  id: string;
  module_id: string;
  title: string;
  item_type: string;
  content_url: string | null;
  content_text: string | null;
  order_index: number;
  is_published: boolean;
}

export interface ProgramAssignment {
  id: string;
  module_id: string;
  program_id: string;
  title: string;
  description: string | null;
  instructions: string | null;
  assignment_type: string;
  is_required: boolean;
  is_published: boolean;
  order_index: number;
  due_offset_days: number | null;
  submission_kind: string;
  repo_required: boolean;
  live_url_expected: boolean;
  max_score: number | null;
  linked_skill_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProgramModule {
  id: string;
  title: string;
  description: string | null;
  order_index: number;
  is_published: boolean;
  items: ProgramModuleItem[];
  assignments: ProgramAssignment[];
}

export interface ProgramSkill {
  skill_id: string;
  skill_name: string;
  requirement: SkillRequirement;
}

export interface AvailableSkill {
  skill_id: string;
  skill_name: string;
  required_level: string | null;
  importance: string | null;
}

export interface InternshipProgramBundle {
  internship: ProgramInternshipRef;
  program: ProgramMeta | null;
  modules: ProgramModule[];
  skills: ProgramSkill[];
  available_skills: AvailableSkill[];
}

export interface ProgramMetaInput {
  title?: string;
  summary?: string | null;
  estimated_weeks?: number | null;
}

export interface ModuleInput {
  title?: string;
  description?: string | null;
  is_published?: boolean;
}

export interface ModuleItemInput {
  title?: string;
  item_type?: ModuleItemType;
  content_url?: string | null;
  content_text?: string | null;
  is_published?: boolean;
}

export interface AssignmentInput {
  title?: string;
  description?: string | null;
  instructions?: string | null;
  assignment_type?: AssignmentType;
  is_required?: boolean;
  is_published?: boolean;
  due_offset_days?: number | null;
  submission_kind?: SubmissionKind;
  repo_required?: boolean;
  live_url_expected?: boolean;
  max_score?: number | null;
  linked_skill_id?: string | null;
}

// submission_reviews.verdict CHECK (migration 039). UNDER_REVIEW is a
// submission_status only -- never a verdict.
export type ReviewVerdict = "ACCEPTED" | "REVISION_REQUESTED" | "REJECTED";

export const REVIEW_VERDICTS: ReviewVerdict[] = [
  "ACCEPTED",
  "REVISION_REQUESTED",
  "REJECTED",
];

export const REVIEW_VERDICT_LABEL: Record<ReviewVerdict, string> = {
  ACCEPTED: "Accept",
  REVISION_REQUESTED: "Request revision",
  REJECTED: "Reject",
};

/** One submission_reviews row as the INDUSTRY sees it (append-only -- a
 * correction is a new row, newest first). `reviewer_id` is the reviewing
 * industry account; the student never receives it. */
export interface SubmissionReview {
  id: string;
  verdict: string;
  feedback: string | null;
  score: number | null;
  reviewer_id: string | null;
  created_at: string | null;
}

/**
 * The industry submission view
 * (backend/app/api/internship_programs.py -- GET .../program/submissions).
 * Phase 6 adds `reviews` / `latest_review` per attempt and the review
 * endpoints.
 */
export interface IndustrySubmission {
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
  reviews: SubmissionReview[];
  latest_review: SubmissionReview | null;
}

export interface IndustrySubmissionListItem extends IndustrySubmission {
  student_name: string | null;
  assignment_title: string | null;
  module_title: string | null;
  attempt_count: number;
}

export interface IndustrySubmissionList {
  submissions: IndustrySubmissionListItem[];
}

export interface IndustrySubmissionDetail {
  submission: IndustrySubmission;
  student_name: string | null;
  assignment_title: string | null;
  module_title: string | null;
  assignment_max_score: number | null;
  attempts: IndustrySubmission[];
}

/** POST .../submissions/{id}/review body. `reviewer_id` is never sent --
 * the backend forces it to the authenticated industry account. */
export interface ReviewSubmissionInput {
  verdict: ReviewVerdict;
  feedback?: string | null;
  score?: number | null;
}
