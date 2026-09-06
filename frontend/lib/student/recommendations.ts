import { api } from "@/lib/api";
import type { StudentRecommendationsResponse } from "@/types/student-recommendation";

/**
 * Talks to OUR aggregate recommendation API
 * (backend/app/api/student_recommendations.py,
 * GET /api/v1/student/recommendations). The only place the frontend
 * builds this request -- components call this function, never `api.*`
 * directly.
 *
 * The recommendation CONTEXT (target role, skills, gap) is derived
 * entirely server-side from the authenticated token. This client sends
 * NO `student_id`, NO `skill_ids`, NO `target_job_role_id`, NO
 * `match_score` -- only an optional bounded `limit` that changes page
 * size, never whose recommendations come back.
 */
export function getRecommendations(params?: {
  limit?: number;
}): Promise<StudentRecommendationsResponse> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return api.get(`/api/v1/student/recommendations${qs ? `?${qs}` : ""}`);
}
