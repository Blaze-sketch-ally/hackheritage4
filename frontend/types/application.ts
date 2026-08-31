/**
 * Mirrors backend/app/schemas/application.py exactly -- field-for-field,
 * same nullability (Phase 1M).
 */

import type { Opportunity, OpportunityMatchSkill } from "@/types/opportunity";

export type ApplicationStatus = "APPLIED" | "SHORTLISTED" | "INTERVIEW" | "SELECTED" | "REJECTED";

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  "APPLIED",
  "SHORTLISTED",
  "INTERVIEW",
  "SELECTED",
  "REJECTED",
];

/** Mirrors `ApplicationResponse`. `opportunity` is embedded on the
 * student's own applications list so the frontend never needs a second
 * round-trip per row -- absent (undefined) on other response shapes. */
export interface Application {
  id: string;
  opportunity_id: string;
  student_id: string;
  status: ApplicationStatus;
  cover_note: string | null;
  created_at: string;
  updated_at: string;
  opportunity?: Opportunity | null;
}

/** Mirrors `ApplicantResponse` -- the industry-facing view. Never
 * contains answer keys, raw assessment answers, or any field beyond what
 * recruitment review needs. */
export interface Applicant {
  id: string;
  student_id: string;
  student_name: string | null;
  status: ApplicationStatus;
  cover_note: string | null;
  overall_match_score: string;
  created_at: string;
  updated_at: string;
}

/** Mirrors `ApplicantDetailResponse` (Phase 1N) -- everything Applicant
 * has, plus the full per-skill breakdown. Used by the industry
 * "Applicant" detail page only; the applicant list/table above stays on
 * the leaner `Applicant` shape. */
export interface ApplicantDetail extends Applicant {
  skills: OpportunityMatchSkill[];
}
