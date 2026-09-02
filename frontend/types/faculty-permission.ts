import type { AssessmentCapability } from "@/lib/faculty/capabilities";

export type PermissionStatus = "GRANTED" | "SUSPENDED" | "EXPIRED" | "REVOKED";

/** One (Faculty, capability) grant row, as seen by an ADMIN -- carries
 * grant metadata that GET /faculty/me/assessment-capabilities never
 * exposes to the Faculty member themselves. */
export interface FacultyPermissionAdmin {
  permission_id: string;
  capability: AssessmentCapability;
  status: PermissionStatus;
  granted_by: string | null;
  status_changed_by: string | null;
  expires_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface FacultyWithPermissions {
  faculty_id: string;
  email: string;
  username: string | null;
  full_name: string | null;
  permissions: FacultyPermissionAdmin[];
}

export interface AdminFacultyListResponse {
  faculty: FacultyWithPermissions[];
}
