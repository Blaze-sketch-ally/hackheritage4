import { api } from "@/lib/api";
import { LIVE_LINK_STATUSES, type InstitutionLinkRequest } from "@/types/institution-link";
import type { StudentInstitutionResponse } from "@/types/student-institution";

/** Talks to backend/app/api/student_institution.py, GET /api/v1/student/institution. */
export function getMyInstitutionWorkspace(): Promise<StudentInstitutionResponse> {
  return api.get("/api/v1/student/institution");
}

// ---- Canonical display state (shared by the Dashboard card and any ----
// ---- other Student surface that needs "what is my institution link?") ----

export type StudentInstitutionLinkState =
  | { kind: "NOT_CONNECTED" }
  | { kind: "PENDING"; institutionName: string | null }
  | { kind: "REJECTED"; institutionName: string | null }
  | { kind: "VERIFIED"; workspace: StudentInstitutionResponse }
  /** institution_link_requests already says APPROVED, but
   * GET /student/institution still reports linked: false. This happens
   * when the DB trigger that sets student_profiles.institution_id on
   * approval (apply_link_request_status_change, migration 038) finds no
   * student_profiles row for this student yet -- that table is created
   * lazily, only once a student saves their Student Profile, so its
   * UPDATE silently affects zero rows. Surfaced honestly (we DO know the
   * request was approved) instead of falsely reporting "not connected". */
  | { kind: "VERIFIED_AWAITING_SYNC"; institutionName: string | null };

/**
 * Reconciles the two existing Student<->Institution data sources into one
 * display state, so no component re-derives this logic on its own:
 *   - GET /student/institution (student_profiles.institution_id) -- the
 *     richer, fully-populated view (KPIs, curated placement drives/
 *     internships/events).
 *   - institution_link_requests (GET /institution-links/mine) -- the
 *     request lifecycle itself (PENDING/APPROVED/REJECTED/...), which
 *     InstitutionLinkCard already reads directly.
 * These are normally in lockstep, but see VERIFIED_AWAITING_SYNC above for
 * the one known case where they can disagree.
 */
export function resolveStudentInstitutionLinkState(
  workspace: StudentInstitutionResponse,
  requests: InstitutionLinkRequest[],
): StudentInstitutionLinkState {
  if (workspace.linked) return { kind: "VERIFIED", workspace };

  const live = requests.find((r) => LIVE_LINK_STATUSES.includes(r.status));
  if (live?.status === "APPROVED") {
    return { kind: "VERIFIED_AWAITING_SYNC", institutionName: live.institution_name };
  }
  if (live?.status === "PENDING") {
    return { kind: "PENDING", institutionName: live.institution_name };
  }

  const mostRecent = requests[0]; // GET /institution-links/mine is newest-updated first
  if (mostRecent?.status === "REJECTED") {
    return { kind: "REJECTED", institutionName: mostRecent.institution_name };
  }

  return { kind: "NOT_CONNECTED" };
}
