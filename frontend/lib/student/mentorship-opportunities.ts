import { api } from "@/lib/api";
import type {
  StudentMentorshipOpportunityDetail,
  StudentMentorshipOpportunityListResponse,
  StudentMentorshipOpportunityWorkMode,
} from "@/types/student-mentorship-opportunity";

/**
 * Talks to the Student Mentorship Discovery API
 * (backend/app/api/student_mentorship_opportunities.py,
 * /api/v1/student/mentorship-opportunities). The only place the frontend
 * builds these requests -- components call these functions, never
 * `api.*` directly.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * student's own Supabase access token. No `student_id` is ever sent --
 * these are read-only list/detail endpoints with no per-student state.
 *
 * A student-facing "mentorship opportunity" is one PUBLISHED industry
 * mentorship posting. There is no request endpoint because there is no
 * request/pairing table in the canonical schema;
 * `detail.requests_available` is always false and the UI shows a
 * truthful "requests aren't available yet" state.
 */

export function listMentorshipOpportunities(params?: {
  workMode?: StudentMentorshipOpportunityWorkMode;
  search?: string;
}): Promise<StudentMentorshipOpportunityListResponse> {
  const query = new URLSearchParams();
  if (params?.workMode) query.set("work_mode", params.workMode);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/student/mentorship-opportunities${qs ? `?${qs}` : ""}`);
}

export function getMentorshipOpportunity(
  mentorshipId: string,
): Promise<StudentMentorshipOpportunityDetail> {
  return api.get(`/api/v1/student/mentorship-opportunities/${encodeURIComponent(mentorshipId)}`);
}
