import { api } from "@/lib/api";
import type { AssessmentCapability } from "@/lib/faculty/capabilities";
import type {
  AdminFacultyListResponse,
  FacultyPermissionAdmin,
  PermissionStatus,
} from "@/types/faculty-permission";

/**
 * Thin, 1:1 wrappers over the ADMIN-only Faculty capability endpoints
 * (backend/app/api/admin_faculty.py, Phase F2's admin control surface) --
 * same shape as lib/faculty/question-bank.ts. Every call goes through
 * apiFetch (lib/api.ts), which attaches the caller's own Supabase
 * session; require_admin() + the admin_* RPCs' own is_admin() checks are
 * the real enforcement, this module holds no privileged credentials and
 * performs no authorization decisions of its own.
 */

export function listFacultyAssessmentPermissions(): Promise<AdminFacultyListResponse> {
  return api.get("/api/v1/admin/faculty/assessment-permissions");
}

export function grantAssessmentCapability(
  facultyId: string,
  capability: AssessmentCapability,
  expiresAt?: string | null,
): Promise<FacultyPermissionAdmin> {
  return api.post(`/api/v1/admin/faculty/${facultyId}/assessment-permissions`, {
    capability,
    expires_at: expiresAt || null,
  });
}

export function setAssessmentPermissionStatus(
  permissionId: string,
  status: PermissionStatus,
): Promise<FacultyPermissionAdmin> {
  return api.patch(`/api/v1/admin/faculty/assessment-permissions/${permissionId}/status`, {
    status,
  });
}
