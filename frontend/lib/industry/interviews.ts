import { api } from "@/lib/api";
import type {
  Interview,
  InterviewCreate,
  InterviewStatus,
  InterviewUpdate,
} from "@/types/interview";

/**
 * Talks to the Industry interview API
 * (backend/app/api/interviews.py, /api/v1/interviews). The only place the
 * frontend builds these requests — components call these functions, never
 * `api.*` directly. Ownership is never sent: the backend derives the
 * owning Industry account (and the interview's student) from the caller's
 * token and the referenced application.
 */

export function getInterviews(params?: {
  status?: InterviewStatus | "";
  application_id?: string;
  upcoming?: boolean;
}): Promise<{ interviews: Interview[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.application_id) query.set("application_id", params.application_id);
  if (params?.upcoming) query.set("upcoming", "true");
  const qs = query.toString();
  return api.get(`/api/v1/interviews${qs ? `?${qs}` : ""}`);
}

export function getInterview(id: string): Promise<Interview> {
  return api.get(`/api/v1/interviews/${id}`);
}

/** Schedules an interview for one of the caller's SHORTLISTED /
 * INTERVIEW_SCHEDULED applications. The backend re-validates eligibility,
 * future time, and slot conflicts (422 / 409). */
export function scheduleInterview(data: InterviewCreate): Promise<Interview> {
  return api.post("/api/v1/interviews", data);
}

/** Reschedule / edit a still-SCHEDULED interview. */
export function rescheduleInterview(id: string, data: InterviewUpdate): Promise<Interview> {
  return api.patch(`/api/v1/interviews/${id}`, data);
}

export function completeInterview(id: string): Promise<Interview> {
  return api.post(`/api/v1/interviews/${id}/complete`);
}

export function cancelInterview(id: string): Promise<Interview> {
  return api.post(`/api/v1/interviews/${id}/cancel`);
}
