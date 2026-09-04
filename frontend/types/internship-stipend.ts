/**
 * Mirrors backend/app/schemas/internship_stipend.py -- field-for-field,
 * same nullability.
 *
 * Phase 8: internship stipend RECORD-KEEPING
 * (database/migrations/039_workspace_submissions_completion.sql --
 * stipend_disbursements). There is no payment gateway, no bank/UPI
 * integration, and no real money movement anywhere in this app --
 * "RELEASED" means the industry recorded that a disbursement happened,
 * never that this portal performed one. Independent of completion /
 * certificate (Phase 7): a workspace can be PASS-completed with a
 * stipend still PENDING, or vice versa.
 */

// stipend_disbursements.disbursement_status CHECK (039).
export type StipendStatus = "PENDING" | "APPROVED" | "RELEASED" | "CANCELLED";

export interface Stipend {
  id: string;
  workspace_id: string;
  amount: number;
  currency: string;
  disbursement_status: StipendStatus;
  reference: string | null;
  notes: string | null;
  released_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** Always 200s for an owned workspace -- `stipend` is null until the
 * industry configures one. That is an honest, normal state, not an error. */
export interface StipendSummary {
  workspace_id: string;
  stipend: Stipend | null;
}

/** `disbursement_status` / `released_by` are never sent -- always
 * server-derived. */
export interface CreateStipendInput {
  amount: number;
  currency?: string;
  reference?: string | null;
  notes?: string | null;
}

/** Only accepted by the backend while the record is PENDING. */
export interface UpdateStipendInput {
  amount?: number;
  currency?: string;
  reference?: string | null;
  notes?: string | null;
}
