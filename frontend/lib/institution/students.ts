import { api } from "@/lib/api";
import type { StudentDetail, StudentListParams, StudentListResponse } from "@/types/institution-student";

/**
 * Talks to the Institution Student Directory API
 * (backend/app/api/institution.py — /api/v1/institution/students). Same
 * request pattern as lib/institution/dashboard.ts: the frontend never
 * sends an institution id and never re-scopes what it renders — every
 * filter/sort/pagination param is forwarded as-is, and the backend
 * derives institution identity from the caller's token.
 */
export function getInstitutionStudents(params: StudentListParams = {}): Promise<StudentListResponse> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const qs = query.toString();
  return api.get(`/api/v1/institution/students${qs ? `?${qs}` : ""}`);
}

export function getInstitutionStudent(studentId: string): Promise<StudentDetail> {
  return api.get(`/api/v1/institution/students/${studentId}`);
}
