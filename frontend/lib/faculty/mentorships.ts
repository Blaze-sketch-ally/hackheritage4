import { api } from "@/lib/api";
import type {
  FacultyStudentMentorship,
  FacultyStudentMentorshipListResponse,
  MenteeProfileBundle,
  MentorshipNote,
  MentorshipStatus,
} from "@/types/faculty-mentorship";

/**
 * Thin, 1:1 wrappers over the Faculty-side mentorship endpoints
 * (backend/app/api/faculty_mentorships.py). Every call goes through
 * apiFetch (lib/api.ts), which attaches the caller's own Supabase
 * session; require_faculty()/require_mentor_capability() + RLS are the
 * real enforcement, this module performs no authorization of its own.
 */

export function listMyMentorships(): Promise<FacultyStudentMentorshipListResponse> {
  return api.get("/api/v1/faculty/mentorships");
}

export function requestMentorship(studentId: string, focusArea?: string | null): Promise<FacultyStudentMentorship> {
  return api.post("/api/v1/faculty/mentorships", { target_id: studentId, focus_area: focusArea || null });
}

export function getMentorship(mentorshipId: string): Promise<FacultyStudentMentorship> {
  return api.get(`/api/v1/faculty/mentorships/${mentorshipId}`);
}

export function updateMentorshipStatus(
  mentorshipId: string,
  status: Extract<MentorshipStatus, "ACCEPTED" | "DECLINED" | "WITHDRAWN" | "ACTIVE" | "COMPLETED" | "ENDED">,
): Promise<FacultyStudentMentorship> {
  return api.patch(`/api/v1/faculty/mentorships/${mentorshipId}/status`, { status });
}

export function getMenteeProfile(mentorshipId: string): Promise<MenteeProfileBundle> {
  return api.get(`/api/v1/faculty/mentorships/${mentorshipId}/student`);
}

export function getMentorshipNote(mentorshipId: string): Promise<MentorshipNote | null> {
  return api.get(`/api/v1/faculty/mentorships/${mentorshipId}/notes`);
}

export function saveMentorshipNote(mentorshipId: string, note: string): Promise<MentorshipNote> {
  return api.put(`/api/v1/faculty/mentorships/${mentorshipId}/notes`, { note });
}
