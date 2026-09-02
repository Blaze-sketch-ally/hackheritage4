import { api } from "@/lib/api";
import type {
  StudentEventDetail,
  StudentEventListResponse,
  StudentEventWorkMode,
} from "@/types/student-event";

/**
 * Talks to OUR Student Events API (backend/app/api/student_events.py,
 * /api/v1/student/events). The only place the frontend builds these
 * requests -- components call these functions, never `api.*` directly.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * student's own Supabase access token. No `student_id` is ever sent --
 * these are read-only list/detail endpoints with no per-student state.
 *
 * A student-facing "event" is one PUBLISHED industry workshop. There is
 * no registration endpoint because there is no registration table in the
 * canonical schema; `detail.registration_available` is always false and
 * the UI shows a truthful "not available yet" state.
 */

export function listEvents(params?: {
  workMode?: StudentEventWorkMode;
  search?: string;
}): Promise<StudentEventListResponse> {
  const query = new URLSearchParams();
  if (params?.workMode) query.set("work_mode", params.workMode);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/student/events${qs ? `?${qs}` : ""}`);
}

export function getEvent(eventId: string): Promise<StudentEventDetail> {
  return api.get(`/api/v1/student/events/${encodeURIComponent(eventId)}`);
}
