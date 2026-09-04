/**
 * Mirrors backend/app/schemas/internship_completion.py -- field-for-field,
 * same nullability.
 *
 * Phase 7: internship completion + certificate
 * (database/migrations/039_workspace_submissions_completion.sql --
 * internship_completions, internship_certificates,
 * public.verify_internship_certificate). "Requirements met" is always
 * computed live on the backend from program_assignments.is_required +
 * is_published and workspace_submissions (an ACCEPTED attempt) -- the
 * frontend never recomputes it, only displays what the API returns.
 */

export type CompletionOutcome = "PASS" | "FAIL";

export interface OutstandingRequirement {
  kind: "ASSIGNMENT";
  id: string;
  title: string;
}

export interface CertificateSkill {
  skill_id: string;
  skill_name: string;
}

/** The frozen public snapshot, plus the record's own immutable fields --
 * never a live join. Captured once, at issuance. */
export interface CertificateInfo {
  certificate_number: string;
  student_name: string | null;
  company_name: string | null;
  internship_title: string | null;
  issued_at: string | null;
  skills: CertificateSkill[];
  revoked: boolean;
}

export interface CompletionSummary {
  workspace_id: string;
  required_count: number;
  completed_count: number;
  requirements_met: boolean;
  outstanding: OutstandingRequirement[];
  industry_verified: boolean;
  result: CompletionOutcome | null;
  verified_at: string | null;
  certificate: CertificateInfo | null;
}

/** POST .../completion/verify body. `industry_id` / `outcome` /
 * `certificate_number` are never sent -- every one is server-derived. */
export interface VerifyCompletionInput {
  summary?: string | null;
}

/** GET /api/v1/certificates/verify/{number} -- exactly the safe public
 * fields; no email, no UUIDs, no submission/stipend data. */
export interface PublicCertificate {
  certificate_number: string;
  student_name: string | null;
  company_name: string | null;
  title: string | null;
  issued_at: string | null;
  status: "VALID" | "REVOKED";
}
