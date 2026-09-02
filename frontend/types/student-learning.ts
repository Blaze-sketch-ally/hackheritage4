/**
 * Mirrors backend/app/schemas/student_learning.py -- field-for-field,
 * same nullability (Phase 6B).
 *
 * Backed by database/migrations/033_learning_resources.sql:
 * `learning_resources` (curated catalog), `learning_resource_skills`
 * (resource -> canonical `skills` mapping), `student_learning_progress`
 * (the caller's own SAVED / IN_PROGRESS / COMPLETED relationship).
 *
 * Learning progress is NOT skill evidence: there is no score, percentage,
 * certificate, verification, or skill-proficiency field here, because the
 * backend has none. Completing a resource never touches `student_skills`
 * and never verifies a skill.
 *
 * `student_id` never appears -- every request derives identity from the
 * authenticated token (require_student -> current_user.id).
 */

export type LearningResourceType = "COURSE" | "ARTICLE" | "VIDEO" | "OTHER";
export type LearningDifficulty = "Beginner" | "Intermediate" | "Advanced" | "Expert";
export type LearningProgressStatus = "SAVED" | "IN_PROGRESS" | "COMPLETED";

export const LEARNING_PROGRESS_STATUSES: LearningProgressStatus[] = [
  "SAVED",
  "IN_PROGRESS",
  "COMPLETED",
];
export const LEARNING_RESOURCE_TYPES: LearningResourceType[] = [
  "COURSE",
  "ARTICLE",
  "VIDEO",
  "OTHER",
];
export const LEARNING_DIFFICULTIES: LearningDifficulty[] = [
  "Beginner",
  "Intermediate",
  "Advanced",
  "Expert",
];

/** One skill a resource helps with, resolved to its catalog name. */
export interface LearningResourceSkill {
  skill_id: string;
  skill_name: string;
  target_level: string | null;
}

/** The authenticated student's own progress on one resource, embedded on
 * a resource response. Always the caller's own (RLS + explicit filter). */
export interface StudentLearningProgress {
  status: LearningProgressStatus;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
}

/** One catalogued learning resource (list item and detail share this
 * shape). `resource_type`/`difficulty` are kept as `string` for forward
 * compatibility -- render via the label maps below. */
export interface LearningResource {
  id: string;
  title: string;
  description: string | null;
  url: string;
  provider: string | null;
  resource_type: string;
  difficulty: string | null;
  estimated_minutes: number | null;
  skills: LearningResourceSkill[];
  progress: StudentLearningProgress | null;
}

export type LearningResourceDetail = LearningResource;

export interface LearningResourceListResponse {
  resources: LearningResource[];
}

/** The resource a progress row points at, on the "My Learning" list.
 * `null` when the resource has since been deactivated -- the progress row
 * (the student's history) still exists. */
export interface LearningProgressResourceRef {
  id: string;
  title: string;
  url: string;
  provider: string | null;
  resource_type: string;
  difficulty: string | null;
}

/** One row of the authenticated student's own learning history. */
export interface StudentLearningResource {
  resource_id: string;
  status: LearningProgressStatus;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  resource: LearningProgressResourceRef | null;
}

export interface StudentLearningProgressListResponse {
  progress: StudentLearningResource[];
}

export interface ProgressUpdateResponse {
  resource_id: string;
  status: LearningProgressStatus;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// ---- Skill Gap -> Learning recommendations (Phase 6D) ----

/** Mirrors backend `MatchedGapSkill`. One canonical Skill Gap skill a
 * recommended resource is mapped to. `reason` is the Skill Gap engine's
 * own server-authored text -- shown verbatim, never rewritten here.
 * `priority` is HIGH / MEDIUM / LOW, used only for grouping/ordering. */
export interface LearningRecommendationMatchedSkill {
  skill_id: string;
  skill_name: string;
  reason: string;
  priority: string;
}

/** Mirrors backend `LearningRecommendation`. One resource plus every
 * current Skill Gap skill it covers (a resource is listed once even when
 * it matches several gap skills). */
export interface LearningRecommendation {
  resource: LearningResource;
  matched_skills: LearningRecommendationMatchedSkill[];
}

/** Mirrors backend `LearningRecommendationListResponse`. `mode` mirrors
 * GET /api/v1/skill-gap -- "JOB_ROLE" when the student has a saved target
 * role, "PERSONAL" otherwise. */
export interface LearningRecommendationListResponse {
  mode: "JOB_ROLE" | "PERSONAL";
  recommendations: LearningRecommendation[];
}

// ---- display helpers ----

export const PROGRESS_LABEL: Record<LearningProgressStatus, string> = {
  SAVED: "Saved",
  IN_PROGRESS: "In progress",
  COMPLETED: "Completed",
};

export const RESOURCE_TYPE_LABEL: Record<string, string> = {
  COURSE: "Course",
  ARTICLE: "Article",
  VIDEO: "Video",
  OTHER: "Resource",
};

export function resourceTypeLabel(value: string): string {
  return RESOURCE_TYPE_LABEL[value] ?? value;
}
