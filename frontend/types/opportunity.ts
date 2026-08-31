/**
 * Mirrors backend/app/schemas/opportunity.py exactly -- field-for-field,
 * same nullability (Phase 1M). Single unified opportunity domain: JOB and
 * INTERNSHIP share every type here -- there is no separate Job/
 * Internship interface anywhere in this file.
 *
 * IMPORTANT: required_level/weight/student_score/gap/overall_score are
 * all Pydantic Decimal fields, which this API serializes as JSON
 * STRINGS (same convention as types/assessment.ts and
 * types/career-role.ts) -- never parse these into a JS number to do
 * arithmetic client-side; the backend is the sole source of these
 * values.
 */

import type { AlignmentStatus } from "@/types/career-role";

export type OpportunityType = "JOB" | "INTERNSHIP";
export type OpportunityStatus = "DRAFT" | "PUBLISHED" | "CLOSED";

/** Mirrors `OpportunityResponse` / the `opportunities` table. */
export interface Opportunity {
  id: string;
  industry_id: string;
  title: string;
  description: string | null;
  opportunity_type: OpportunityType;
  location: string | null;
  status: OpportunityStatus;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunityCreateInput {
  title: string;
  description?: string | null;
  opportunity_type: OpportunityType;
  location?: string | null;
}

/** Mirrors `OpportunityUpdateRequest` -- every field optional, partial
 * update. No `status` field exists here at all -- use the dedicated
 * publish/close calls instead. */
export interface OpportunityUpdateInput {
  title?: string;
  description?: string | null;
  opportunity_type?: OpportunityType;
  location?: string | null;
}

/** Mirrors `OpportunityRequirementInput`. */
export interface OpportunityRequirementInput {
  skill_id: string;
  required_level: string;
  weight: string;
}

/** Mirrors `OpportunityRequirementResponse`. */
export interface OpportunityRequirement {
  skill_id: string;
  skill_name: string;
  required_level: string;
  weight: string;
}

/** Mirrors `OpportunityMatchSkillResponse` -- identical shape to
 * types/career-role.ts's SkillGapSkill (same backend AlignmentStatus
 * enum, same Phase 1L alignment engine, reused unchanged). */
export interface OpportunityMatchSkill {
  skill_id: string;
  skill_name: string;
  required_level: string;
  student_score: string;
  gap: string;
  weight: string;
  status: AlignmentStatus;
}

/** Mirrors `OpportunityMatchResponse` -- the authenticated student's own
 * derived match against one opportunity. Always a CURRENT, freshly
 * computed view -- never a stored, application-time snapshot (see
 * database/migrations/024_opportunities_and_applications.sql's own
 * header comment). */
export interface OpportunityMatch {
  opportunity: Opportunity;
  overall_score: string;
  skills: OpportunityMatchSkill[];
}
