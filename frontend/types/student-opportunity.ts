/**
 * Mirrors backend/app/schemas/student_opportunity.py -- field-for-field,
 * same nullability.
 *
 * IMPORTANT: this is a read adapter over the live `internships` / `jobs`
 * tables (database/migrations/018, 019). There is no `opportunities`
 * table and no `opportunity_id` column on `applications`. The
 * student-facing opportunity `id` is a prefixed string --
 * `internship_<uuid>` / `job_<uuid>` -- so the backend can always resolve
 * which source table a given opportunity maps to.
 *
 * Application `status` is one of the seven live `applications.status`
 * values (020_applications.sql) -- never a reduced set. The Industry
 * recruitment pipeline is the sole writer of it.
 */

import type { InterviewMode, InterviewStatus } from "@/types/interview";

export type SourceType = "INTERNSHIP" | "JOB";

/** Browse-list sort keys — a fixed whitelist mirroring backend
 * `OpportunitySort` (schemas/student_opportunity.py). `newest` is the
 * default and is never serialized to the URL or the API. */
export type OpportunitySort = "newest" | "deadline";

/** All seven live values -- see database/migrations/020_applications.sql. */
export type StudentApplicationStatus =
  | "APPLIED"
  | "UNDER_REVIEW"
  | "SHORTLISTED"
  | "INTERVIEW_SCHEDULED"
  | "SELECTED"
  | "REJECTED"
  | "WITHDRAWN";

export const STUDENT_APPLICATION_STATUSES: StudentApplicationStatus[] = [
  "APPLIED",
  "UNDER_REVIEW",
  "SHORTLISTED",
  "INTERVIEW_SCHEDULED",
  "SELECTED",
  "REJECTED",
  "WITHDRAWN",
];

/** Active candidate stages a student may still withdraw from. Mirrors the
 * backend `WITHDRAWABLE_STATUSES` (student_opportunity_service.py).
 * SELECTED (offer in hand), REJECTED (terminal) and WITHDRAWN (already
 * withdrawn) are not withdrawable — the backend returns 409 for those. */
export const WITHDRAWABLE_APPLICATION_STATUSES: readonly StudentApplicationStatus[] = [
  "APPLIED",
  "UNDER_REVIEW",
  "SHORTLISTED",
  "INTERVIEW_SCHEDULED",
];

export function canWithdrawApplication(status: StudentApplicationStatus): boolean {
  return WITHDRAWABLE_APPLICATION_STATUSES.includes(status);
}

export interface OpportunityIndustry {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;
}

export interface OpportunitySkill {
  skill_id: string;
  skill_name: string;
  category_name: string | null;
  required_level: string;
  importance: string;
}

export interface StudentOpportunitySummary {
  id: string;
  source_type: SourceType;
  title: string;
  description: string;
  location: string | null;
  work_mode: string | null;
  status: string;
  industry: OpportunityIndustry | null;
  application_deadline: string | null;
  created_at: string | null;
  has_applied: boolean;
}

export interface StudentOpportunityDetail extends StudentOpportunitySummary {
  eligibility_criteria: string | null;
  openings: number | null;
  // internship-only
  duration_months: number | null;
  stipend_amount: number | null;
  stipend_currency: string | null;
  start_date: string | null;
  // job-only
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  experience_min_years: number | null;
  skills: OpportunitySkill[];
}

export interface StudentApplicationOpportunity {
  id: string;
  source_type: SourceType;
  title: string | null;
  industry: OpportunityIndustry | null;
  location: string | null;
  /** ONSITE / REMOTE / HYBRID / null (null once the posting is no longer
   * PUBLISHED). Drives the Applications-page workspace CTA for a SELECTED
   * internship: only REMOTE/HYBRID get an Internship Workspace. */
  work_mode: string | null;
}

/** The student's own LIVE (SCHEDULED) interview for an application.
 * Mirrors backend `StudentApplicationInterview`
 * (backend/app/schemas/student_opportunity.py), stitched on server-side
 * from the `public.student_interviews` RPC. `notes` is Industry-private
 * and is never included. `null` on `StudentApplication.interview` when the
 * application has no live interview (INTERVIEW_SCHEDULED can exist without
 * one — a manual status move, or a cancelled/completed interview). */
export interface StudentApplicationInterview {
  id: string;
  application_id: string;
  /** ISO-8601 UTC instant. Render in the viewer's locale. */
  scheduled_at: string;
  duration_minutes: number;
  mode: InterviewMode;
  location: string | null;
  status: InterviewStatus;
}

export interface StudentApplication {
  id: string;
  student_id: string;
  opportunity_type: SourceType;
  internship_id: string | null;
  job_id: string | null;
  status: StudentApplicationStatus;
  cover_note: string | null;
  match_score: number | null;
  applied_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  opportunity: StudentApplicationOpportunity | null;
  interview: StudentApplicationInterview | null;
}

export type SkillMatchStatus = "MATCHED" | "NEEDS_IMPROVEMENT" | "MISSING";
export type MatchRecommendation = "STRONG" | "GOOD" | "PARTIAL" | "LOW";

export interface MatchSkill {
  skill_id: string;
  skill_name: string;
  required_level: string;
  importance: string;
  candidate_has: boolean;
  candidate_level: string | null;
  candidate_verified: boolean;
  status: SkillMatchStatus;
}

export interface OpportunityMatch {
  opportunity_id: string;
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

/** Friendly label for every one of the seven statuses -- the backend
 * value is never changed, only presented. */
export const STATUS_LABEL: Record<StudentApplicationStatus, string> = {
  APPLIED: "Applied",
  UNDER_REVIEW: "Under Review",
  SHORTLISTED: "Shortlisted",
  INTERVIEW_SCHEDULED: "Interview Scheduled",
  SELECTED: "Selected",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
};
