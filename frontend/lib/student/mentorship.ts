import { api } from "@/lib/api";
import type {
  StudentMentorshipDetail,
  StudentMentorshipListResponse,
  StudentMentorshipWorkMode,
} from "@/types/student-mentorship";

/**
 * Talks to OUR Student Mentorship API
 * (backend/app/api/student_mentorship.py, /api/v1/student/mentorship).
 * The only place the frontend builds these requests -- components call
 * these functions, never `api.*` directly.
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

export function listMentorships(params?: {
  workMode?: StudentMentorshipWorkMode;
  search?: string;
}): Promise<StudentMentorshipListResponse> {
  const query = new URLSearchParams();
  if (params?.workMode) query.set("work_mode", params.workMode);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/student/mentorship${qs ? `?${qs}` : ""}`);
}

export function getMentorship(mentorshipId: string): Promise<StudentMentorshipDetail> {
  return api.get(`/api/v1/student/mentorship/${encodeURIComponent(mentorshipId)}`);
}
