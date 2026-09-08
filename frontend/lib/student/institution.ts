import { api } from "@/lib/api";
import type { StudentInstitutionResponse } from "@/types/student-institution";

/** Talks to backend/app/api/student_institution.py, GET /api/v1/student/institution. */
export function getMyInstitutionWorkspace(): Promise<StudentInstitutionResponse> {
  return api.get("/api/v1/student/institution");
}
