import { api } from "@/lib/api";
import type {
  FacultyStudentMentorship,
  FacultyStudentMentorshipListResponse,
  MentorshipStatus,
} from "@/types/faculty-mentorship";

/**
 * Thin, 1:1 wrappers over the Student-side mentorship endpoints
 * (backend/app/api/student_mentorships.py). No capability concept on
 * this side -- faculty_mentor only gates the Faculty participant.
 */

export function listMyMentorships(): Promise<FacultyStudentMentorshipListResponse> {
  return api.get("/api/v1/student/mentorships");
}

export function requestMentorship(facultyId: string, focusArea?: string | null): Promise<FacultyStudentMentorship> {
  return api.post("/api/v1/student/mentorships", { target_id: facultyId, focus_area: focusArea || null });
}

export function updateMentorshipStatus(
  mentorshipId: string,
  status: Extract<MentorshipStatus, "ACCEPTED" | "DECLINED" | "WITHDRAWN" | "ACTIVE" | "COMPLETED" | "ENDED">,
): Promise<FacultyStudentMentorship> {
  return api.patch(`/api/v1/student/mentorships/${mentorshipId}/status`, { status });
}
