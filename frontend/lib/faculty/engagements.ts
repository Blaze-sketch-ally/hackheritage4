import { api } from "@/lib/api";
import type { FacultyEngagementListResponse } from "@/types/faculty-engagement";

/**
 * Thin wrapper over GET /api/v1/faculty/engagements (Phase F4.1).
 * Read-only -- Faculty has no lifecycle-mutating action on an engagement
 * in this phase.
 */
export function listMyEngagements(): Promise<FacultyEngagementListResponse> {
  return api.get("/api/v1/faculty/engagements");
}
