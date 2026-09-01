// Mirrors the `industry_collaborations` table
// (database/migrations/026_industry_collaborations.sql) and
// backend/app/schemas/industry_collaboration.py. Keep all three in sync.
//
// This is NOT a posting entity like IndustryProject/IndustryTraining/
// IndustryWorkshop/IndustryMentorship — it is a bilateral academia-
// industry collaboration proposal/relationship between an INDUSTRY
// account (initiator) and a FACULTY or INSTITUTION account (recipient),
// with its own lifecycle:
// DRAFT -> SENT -> ACCEPTED/REJECTED -> ACTIVE -> COMPLETED/CANCELLED.
//
// Named `industry-collaboration` (not `collaboration`/`collaborations`)
// to avoid colliding with the still-unimplemented, ambiguous generic
// stubs and with 009_collaboration.sql's own broader, unimplemented
// scope — both untouched.

export const COLLABORATION_STATUSES = [
  "DRAFT",
  "SENT",
  "ACCEPTED",
  "REJECTED",
  "ACTIVE",
  "COMPLETED",
  "CANCELLED",
] as const;
export type CollaborationStatus = (typeof COLLABORATION_STATUSES)[number];

export const COLLABORATION_STATUS_LABELS: Record<CollaborationStatus, string> = {
  DRAFT: "Draft",
  SENT: "Sent",
  ACCEPTED: "Accepted",
  REJECTED: "Rejected",
  ACTIVE: "Active",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export const RECIPIENT_TYPES = ["FACULTY", "INSTITUTION"] as const;
export type RecipientType = (typeof RECIPIENT_TYPES)[number];

export const RECIPIENT_TYPE_LABELS: Record<RecipientType, string> = {
  FACULTY: "Faculty",
  INSTITUTION: "Institution",
};

export interface IndustryCollaboration {
  id: string;
  industry_id: string;
  recipient_id: string;
  recipient_type: RecipientType;
  title: string;
  description: string;
  status: CollaborationStatus;
  created_at: string | null;
  updated_at: string | null;
  /** Display identity of each party, resolved server-side (migration 029 —
   * `collaboration_counterparty_names()`). `industry_name` is the
   * initiator's company name; `recipient_name` is the Faculty/Institution
   * account's name. Either may be null (migration not yet applied, or no
   * name on file) — fall back to the recipient-type label. */
  industry_name?: string | null;
  recipient_name?: string | null;
}

/** POST body. Always created as DRAFT — no `status`, no `industry_id`,
 * no `recipient_type` (derived server-side from `recipient_id`'s real
 * role). `recipient_id` is normally obtained via the recipient resolver
 * first. */
export interface CollaborationCreate {
  title: string;
  description: string;
  recipient_id: string;
}

/** PUT body — partial, DRAFT-only. `recipient_id` is never editable. */
export interface CollaborationUpdate {
  title?: string;
  description?: string;
}

/** Minimal recipient lookup result — id/role/full_name only, never
 * email/phone/other profile fields. */
export interface RecipientResolution {
  id: string;
  role: RecipientType;
  full_name: string | null;
}
