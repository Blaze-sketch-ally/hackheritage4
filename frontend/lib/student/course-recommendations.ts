import { api } from "@/lib/api";
import type { CourseRecommendationResponse } from "@/types/course-recommendation";

/**
 * Talks to the live Course Recommendation API
 * (backend/app/api/ai.py::get_course_recommendations, POST
 * /api/v1/ai/course-recommendations). Only place in the frontend that
 * constructs this request -- components call this function, never
 * `api.post` directly. Every call goes through lib/api.ts's
 * apiFetch(), which attaches the student's own Supabase access token;
 * no student_id is ever sent -- the backend derives it from the token.
 *
 * Always returns 200 with a fully-shaped response, even when the
 * external course provider and/or the YouTube provider are
 * unconfigured/unavailable -- check `meta.external_discovery_status`
 * / `meta.youtube_status` to know what degraded, never assume every
 * section is populated.
 */
export function getCourseRecommendations(): Promise<CourseRecommendationResponse> {
  return api.post("/api/v1/ai/course-recommendations");
}
