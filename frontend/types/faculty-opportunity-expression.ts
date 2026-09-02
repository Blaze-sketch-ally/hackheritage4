import type { OpportunitySource } from "@/types/faculty-opportunity";
import type { FacultyEngagement } from "@/types/faculty-engagement";

/** Mirrors backend/app/schemas/faculty_opportunity_expression.py exactly.
 * Deliberately NOT called "application" -- see the approved F3.4
 * architecture: "application" already means the STUDENT-only
 * opportunities/applications model in this codebase. */
export const EOI_STATUSES = [
  "DRAFT",
  "SUBMITTED",
  "UNDER_REVIEW",
  "ACCEPTED",
  "REJECTED",
  "WITHDRAWN",
] as const;
export type EoiStatus = (typeof EOI_STATUSES)[number];

export const EOI_STATUS_LABELS: Record<EoiStatus, string> = {
  DRAFT: "Draft",
  SUBMITTED: "Submitted",
  UNDER_REVIEW: "Under review",
  ACCEPTED: "Accepted",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
};

export interface FacultyOpportunityExpression {
  id: string;
  source: OpportunitySource;
  opportunity_id: string;
  opportunity_title: string | null;
  faculty_id: string;
  status: EoiStatus;
  message: string | null;
  reviewed_by: string | null;
  reviewer_note: string | null;
  created_at: string | null;
  updated_at: string | null;
  /** Populated only once this EOI is ACCEPTED (Phase F4.1). */
  engagement: FacultyEngagement | null;
}

export interface FacultyOpportunityExpressionListResponse {
  expressions: FacultyOpportunityExpression[];
}
