import { api } from "@/lib/api";

/**
 * Thin, 1:1 wrappers over the ADMIN-only Faculty mentor-capability
 * endpoints (backend/app/api/admin_faculty.py's mentor-permission
 * routes, Phase F4.2) and the read-only mentorship-oversight endpoint
 * (backend/app/api/admin_mentorships.py). Same shape as
 * lib/admin/faculty-permissions.ts -- require_admin() + each admin_*
 * RPC's own is_admin() check are the real enforcement.
 */

export type MentorPermissionStatus = "GRANTED" | "SUSPENDED" | "REVOKED";

export interface FacultyMentorPermissionAdmin {
  permission_id: string;
  status: MentorPermissionStatus;
  granted_by: string | null;
  status_changed_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface FacultyWithMentorPermission {
  faculty_id: string;
  email: string;
  username: string | null;
  full_name: string | null;
  permission: FacultyMentorPermissionAdmin | null;
}

export interface AdminFacultyMentorPermissionListResponse {
  faculty: FacultyWithMentorPermission[];
}

export function listFacultyMentorPermissions(): Promise<AdminFacultyMentorPermissionListResponse> {
  return api.get("/api/v1/admin/faculty/mentor-permissions");
}

export function grantMentorCapability(facultyId: string): Promise<FacultyMentorPermissionAdmin> {
  return api.post(`/api/v1/admin/faculty/${facultyId}/mentor-permission`);
}

export function setMentorPermissionStatus(
  permissionId: string,
  status: MentorPermissionStatus,
): Promise<FacultyMentorPermissionAdmin> {
  return api.patch(`/api/v1/admin/faculty/mentor-permissions/${permissionId}/status`, { status });
}

export interface AdminMentorship {
  id: string;
  faculty_id: string;
  student_id: string;
  status: string;
  requested_by: string;
  start_date: string | null;
  end_date: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AdminMentorshipListResponse {
  mentorships: AdminMentorship[];
}

export function listAllMentorships(): Promise<AdminMentorshipListResponse> {
  return api.get("/api/v1/admin/mentorships");
}
