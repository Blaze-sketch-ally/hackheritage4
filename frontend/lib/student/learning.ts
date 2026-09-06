import { api } from "@/lib/api";
import type {
  LearningDifficulty,
  LearningProgressStatus,
  LearningRecommendationListResponse,
  LearningResourceDetail,
  LearningResourceListResponse,
  LearningResourceType,
  ProgressUpdateResponse,
  StudentLearningProgressListResponse,
} from "@/types/student-learning";

/**
 * Talks to OUR Student Learning API (backend/app/api/student_learning.py,
 * /api/v1/student/learning). The only place the frontend builds these
 * requests -- components call these functions, never `api.*` directly.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * student's own Supabase access token. No `student_id` is ever sent --
 * the backend derives it from the token (require_student ->
 * current_user.id). The progress request body carries ONLY `status`;
 * timestamps and any score/verification concept are server-owned (there
 * is no verification concept on this path at all).
 */

/** Server-side filters supported by GET /resources: `skill_id` (uuid),
 * `difficulty`, `resource_type`. Anything not passed is omitted. */
export function listLearningResources(params?: {
  skillId?: string;
  difficulty?: LearningDifficulty;
  resourceType?: LearningResourceType;
}): Promise<LearningResourceListResponse> {
  const query = new URLSearchParams();
  if (params?.skillId) query.set("skill_id", params.skillId);
  if (params?.difficulty) query.set("difficulty", params.difficulty);
  if (params?.resourceType) query.set("resource_type", params.resourceType);
  const qs = query.toString();
  return api.get(`/api/v1/student/learning/resources${qs ? `?${qs}` : ""}`);
}

export function getLearningResource(resourceId: string): Promise<LearningResourceDetail> {
  return api.get(`/api/v1/student/learning/resources/${encodeURIComponent(resourceId)}`);
}

/** The authenticated student's own learning history only -- SAVED /
 * IN_PROGRESS / COMPLETED rows, each with its resource embedded. */
export function listMyLearningProgress(): Promise<StudentLearningProgressListResponse> {
  return api.get("/api/v1/student/learning/progress");
}

/** Learning resources mapped to the authenticated student's OWN canonical
 * Skill Gap skills (backend GET /api/v1/student/learning/recommended).
 *
 * Sends NO body, NO query params -- specifically no `student_id` and no
 * skill id. The backend computes the student's gap itself (via
 * `skill_gap_service`, exactly as GET /skill-gap does) and maps its
 * recommendation skills to resources; the client only asks for "my"
 * recommendations. `mode` on the response says whether the gap came from
 * a saved target role ("JOB_ROLE") or the personal analysis
 * ("PERSONAL"). */
export function getRecommendedLearningResources(): Promise<LearningRecommendationListResponse> {
  return api.get("/api/v1/student/learning/recommended");
}

/** Create or move the caller's own progress on one resource. The path
 * identifies the resource; the token identifies the student; the body is
 * ONLY `{ status }`. Never sends student_id / started_at / completed_at /
 * created_at / updated_at / score / verification -- all server-owned. */
export function setLearningProgress(
  resourceId: string,
  status: LearningProgressStatus,
): Promise<ProgressUpdateResponse> {
  return api.post(
    `/api/v1/student/learning/resources/${encodeURIComponent(resourceId)}/progress`,
    { status },
  );
}
