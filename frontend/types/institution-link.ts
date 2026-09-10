// Mirrors backend/app/schemas/institution_link.py -- the bilateral
// student <-> institution linking workflow
// (database/migrations/038_institution_link_requests.sql).

export type LinkRequestStatus = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED" | "REMOVED";

export interface InstitutionLinkRequest {
  id: string;
  student_id: string;
  institution_id: string;
  status: LinkRequestStatus;
  created_at: string | null;
  updated_at: string | null;
  /** Resolved server-side. Populated on institution-side reads only. */
  student_name: string | null;
  student_username: string | null;
  /** Resolved server-side. Populated on student-side reads only. */
  institution_name: string | null;
}

export interface InstitutionResolution {
  id: string;
  full_name: string | null;
}

/** A request counts as "live" if it still occupies the student's one
 * active slot (institution_link_requests_one_live_per_student_idx). */
export const LIVE_LINK_STATUSES: LinkRequestStatus[] = ["PENDING", "APPROVED"];
