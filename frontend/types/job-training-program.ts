/**
 * Mirrors backend/app/schemas/job_training_program.py -- field-for-field,
 * same nullability. Also mirrors frontend/types/internship-program.ts,
 * which is the internship-side authoring analog.
 *
 * An industry account authors exactly one job_program per JOB posting
 * (database/migrations/052_job_training.sql) -- program metadata, ordered
 * modules, learning items, required/optional program skills, and gradable
 * assignments -- and publishes / unpublishes it. There is no submission /
 * review system for Job Training (unlike the internship program), so this
 * file carries no submission-review types.
 */

export type JobProgramStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
export type SkillRequirement = "REQUIRED" | "OPTIONAL";
export type JobProgramItemType = "VIDEO" | "PDF" | "LINK" | "TEXT";

export const JOB_PROGRAM_ITEM_TYPES: JobProgramItemType[] = ["VIDEO", "PDF", "LINK", "TEXT"];

export type AssignmentType = "ASSIGNMENT" | "QUIZ" | "PROJECT";
export type SubmissionKind = "LINK" | "REPO" | "FILE" | "TEXT" | "MIXED";

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

export interface ProgramJobRef {
  id: string;
  title: string;
  status: string;
}

export interface JobProgramMeta {
  id: string;
  job_id: string;
  title: string;
  summary: string | null;
  estimated_weeks: number | null;
  status: JobProgramStatus;
  published_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface JobProgramItemResponse {
  id: string;
  module_id: string;
  title: string;
  item_type: string;
  content_url: string | null;
  content_text: string | null;
  order_index: number;
  is_published: boolean;
}

export interface JobProgramAssignmentResponse {
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

export interface JobProgramModuleResponse {
  id: string;
  title: string;
  description: string | null;
  order_index: number;
  is_published: boolean;
  items: JobProgramItemResponse[];
  assignments: JobProgramAssignmentResponse[];
}

export interface JobProgramSkillResponse {
  skill_id: string;
  skill_name: string;
  requirement: SkillRequirement;
}

/** One of the job's recruitment skills (job_skills, 019), offered to the
 * authoring UI as a suggestion list. Not a hard limit -- a Job Training
 * program may train skills outside the screening set. */
export interface AvailableSkill {
  skill_id: string;
  skill_name: string;
  required_level: string | null;
  importance: string | null;
}

export interface JobProgramBundle {
  job: ProgramJobRef;
  program: JobProgramMeta | null;
  modules: JobProgramModuleResponse[];
  skills: JobProgramSkillResponse[];
  available_skills: AvailableSkill[];
}

export interface JobProgramMetaInput {
  title?: string;
  summary?: string | null;
  estimated_weeks?: number | null;
}

export interface JobProgramModuleInput {
  title?: string;
  description?: string | null;
  is_published?: boolean;
}

export interface JobProgramItemInput {
  title?: string;
  item_type?: JobProgramItemType;
  content_url?: string | null;
  content_text?: string | null;
  is_published?: boolean;
}

export interface JobAssignmentInput {
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
