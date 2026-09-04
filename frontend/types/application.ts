// Mirrors the Industry-facing shape of `applications`
// (database/migrations/020_applications.sql) and
// backend/app/schemas/application.py. Keep all three in sync.
//
// Applicant identity: `profiles` RLS still gives Industry no direct read
// access to an applicant's `profiles` / `student_profiles` row — that is
// unchanged. `student_name` is resolved server-side (backend
// application_service, via the public.application_applicant_names RPC,
// database/migrations/036_application_applicant_names.sql) scoped to the
// same ownership predicate as the applications RLS policy itself, so it
// only ever carries `profiles.full_name` — no email, avatar, or other
// profile data. It can be null (lookup failure, or the student never set
// a full_name) — always fall back to `applicantRef`/`applicantDisplayName`
// rather than assuming it's present.

export const APPLICATION_STATUSES = [
  "APPLIED",
  "UNDER_REVIEW",
  "SHORTLISTED",
  "INTERVIEW_SCHEDULED",
  "SELECTED",
  "REJECTED",
  "WITHDRAWN",
] as const;
export type ApplicationStatus = (typeof APPLICATION_STATUSES)[number];

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  APPLIED: "Applied",
  UNDER_REVIEW: "Under review",
  SHORTLISTED: "Shortlisted",
  INTERVIEW_SCHEDULED: "Interview scheduled",
  SELECTED: "Selected",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
};

export const OPPORTUNITY_TYPES = ["INTERNSHIP", "JOB"] as const;
export type OpportunityType = (typeof OPPORTUNITY_TYPES)[number];

export const OPPORTUNITY_TYPE_LABELS: Record<OpportunityType, string> = {
  INTERNSHIP: "Internship",
  JOB: "Job",
};

/** The statuses an Industry account can move an application to. Mirrors
 * backend `IndustrySettableStatus` — WITHDRAWN and APPLIED are excluded. */
export const INDUSTRY_SETTABLE_STATUSES = [
  "UNDER_REVIEW",
  "SHORTLISTED",
  "INTERVIEW_SCHEDULED",
  "SELECTED",
  "REJECTED",
] as const;
export type IndustrySettableStatus = (typeof INDUSTRY_SETTABLE_STATUSES)[number];

/** Valid Industry-driven transitions. Mirrors
 * application_service._STATUS_TRANSITIONS — used to only offer valid
 * actions in the UI (the backend still re-checks, so stale tabs get a
 * clean 409). */
export const APPLICATION_TRANSITIONS: Record<ApplicationStatus, IndustrySettableStatus[]> = {
  APPLIED: ["UNDER_REVIEW", "SHORTLISTED", "REJECTED"],
  UNDER_REVIEW: ["SHORTLISTED", "REJECTED"],
  SHORTLISTED: ["INTERVIEW_SCHEDULED", "REJECTED"],
  INTERVIEW_SCHEDULED: ["SELECTED", "REJECTED"],
  SELECTED: [],
  REJECTED: [],
  WITHDRAWN: [],
};

export const TRANSITION_LABELS: Record<IndustrySettableStatus, string> = {
  UNDER_REVIEW: "Move to review",
  SHORTLISTED: "Shortlist",
  INTERVIEW_SCHEDULED: "Schedule interview",
  SELECTED: "Mark selected",
  REJECTED: "Reject",
};

export interface ApplicationOpportunity {
  id: string;
  title: string;
  /** The posting's own lifecycle status (DRAFT/PUBLISHED/CLOSED/ARCHIVED). */
  status: string;
}

export interface Application {
  id: string;
  student_id: string;
  /** The applicant's display name (profiles.full_name), resolved
   * server-side. Null/undefined when resolution failed or the student has
   * no full_name — use `applicantDisplayName` rather than reading this
   * directly. */
  student_name?: string | null;
  industry_id: string;
  opportunity_type: OpportunityType;
  internship_id: string | null;
  job_id: string | null;
  status: ApplicationStatus;
  cover_note: string | null;
  /** Best-effort cache of the deterministic Skill Match score (Phase 9),
   * 0–100. Null until GET /api/v1/applications/{id}/match has run for it. */
  match_score: number | null;
  applied_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  opportunity: ApplicationOpportunity | null;
}

/** GET /api/v1/applications/summary — drives the recruitment funnel. */
export interface ApplicationSummary {
  counts: Record<ApplicationStatus, number>;
  total: number;
}

/** The forward recruitment pipeline, in order — the funnel's stages. */
export const RECRUITMENT_PIPELINE: ApplicationStatus[] = [
  "APPLIED",
  "UNDER_REVIEW",
  "SHORTLISTED",
  "INTERVIEW_SCHEDULED",
  "SELECTED",
];

/** Statuses that leave the pipeline — shown separately from the funnel. */
export const RECRUITMENT_EXITS: ApplicationStatus[] = ["REJECTED", "WITHDRAWN"];

/** A short, privacy-safe label for an applicant, built only from the id —
 * the fallback used when no resolved name is available (RPC failure, or
 * the student never set a full_name). */
export function applicantRef(studentId: string): string {
  return `Applicant ${studentId.slice(0, 8)}`;
}

/** The applicant's real name when the backend resolved one, else the same
 * `applicantRef` truncated-id fallback every recruitment view already
 * used. Prefer this over `applicantRef` wherever an application's
 * applicant is displayed. */
export function applicantDisplayName(application: {
  student_id: string;
  student_name?: string | null;
}): string {
  const name = application.student_name?.trim();
  return name ? name : applicantRef(application.student_id);
}

// ===========================================================================
// Skill Match (Phase 9) — GET /api/v1/applications/{id}/match
// Deterministic and advisory. No LLM. The backend is the sole source of the
// score; the frontend never recomputes it. Mirrors
// backend/app/schemas/application.py ApplicationMatchResponse / MatchSkill.
// ===========================================================================

export const MATCH_SKILL_STATUSES = ["MATCHED", "NEEDS_IMPROVEMENT", "MISSING"] as const;
export type MatchSkillStatus = (typeof MATCH_SKILL_STATUSES)[number];

export const MATCH_SKILL_STATUS_LABELS: Record<MatchSkillStatus, string> = {
  MATCHED: "Matched",
  NEEDS_IMPROVEMENT: "Needs improvement",
  MISSING: "Missing",
};

export const MATCH_RECOMMENDATIONS = ["STRONG", "GOOD", "PARTIAL", "LOW"] as const;
export type MatchRecommendation = (typeof MATCH_RECOMMENDATIONS)[number];

export const MATCH_RECOMMENDATION_LABELS: Record<MatchRecommendation, string> = {
  STRONG: "Strong match",
  GOOD: "Good match",
  PARTIAL: "Partial match",
  LOW: "Low match",
};

export interface MatchSkill {
  skill_id: string;
  skill_name: string;
  required_level: string;
  importance: string;
  candidate_has: boolean;
  candidate_level: string | null;
  candidate_verified: boolean;
  status: MatchSkillStatus;
}

export interface ApplicationMatch {
  application_id: string;
  score: number;
  recommendation: MatchRecommendation;
  skill_coverage: string;
  required_count: number;
  matched_count: number;
  needs_improvement_count: number;
  missing_count: number;
  matched_skills: MatchSkill[];
  needs_improvement_skills: MatchSkill[];
  missing_skills: MatchSkill[];
}
