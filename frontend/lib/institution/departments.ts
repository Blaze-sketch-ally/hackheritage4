import { api } from "@/lib/api";
import type {
  DepartmentDetail,
  DepartmentFields,
  DepartmentListResponse,
  DepartmentUpdateFields,
} from "@/types/institution-department";
import type { StudentDetail } from "@/types/institution-student";

/**
 * Talks to the Institution Departments API
 * (backend/app/api/institution.py — /api/v1/institution/departments...).
 * Same request pattern as lib/institution/{dashboard,students}.ts: the
 * frontend never sends an institution id, and the backend derives
 * ownership from the caller's token.
 */

export function getInstitutionDepartments(): Promise<DepartmentListResponse> {
  return api.get("/api/v1/institution/departments");
}

export function getInstitutionDepartment(departmentId: string): Promise<DepartmentDetail> {
  return api.get(`/api/v1/institution/departments/${departmentId}`);
}

export function createInstitutionDepartment(fields: DepartmentFields): Promise<DepartmentDetail> {
  return api.post("/api/v1/institution/departments", fields);
}

export function updateInstitutionDepartment(
  departmentId: string,
  fields: DepartmentUpdateFields,
): Promise<DepartmentDetail> {
  return api.put(`/api/v1/institution/departments/${departmentId}`, fields);
}

/** `departmentId: null` clears the student's department assignment. */
export function assignStudentDepartment(
  studentId: string,
  departmentId: string | null,
): Promise<StudentDetail> {
  return api.patch(`/api/v1/institution/students/${studentId}/department`, { department_id: departmentId });
}
