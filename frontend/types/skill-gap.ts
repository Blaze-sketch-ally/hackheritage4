/**
 * Mirrors backend/app/schemas/skill_gap.py exactly -- field-for-field,
 * same nullability. readiness_percentage/gap are plain Pydantic ints (not
 * Decimal), so -- unlike types/assessment.ts -- these come back as real
 * JSON numbers, not strings; still never recomputed client-side.
 */

import type { Difficulty } from "@/types/assessment";

export type Importance = "CORE" | "IMPORTANT" | "OPTIONAL";
export type RelationshipType = "PREREQUISITE" | "RELATED" | "NEXT_STEP" | "COMPLEMENTARY";
export type GapStatus = "MATCHED" | "NEEDS_IMPROVEMENT" | "MISSING";
export type VerificationStatus = "VERIFIED" | "UNVERIFIED";
export type Priority = "HIGH" | "MEDIUM" | "LOW";
export type AnalysisMode = "JOB_ROLE" | "PERSONAL";

/** Mirrors `JobRoleResponse`. Only ever populated from active roles. */
export interface JobRole {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Mirrors `TargetJobRoleResponse`. */
export interface TargetJobRole {
  id: string;
  job_role: JobRole;
  created_at: string;
  updated_at: string;
}

/** Mirrors `SkillGapItem`. current_level is the student's DECLARED level
 * (or null if the skill isn't in their active list) -- verification_status
 * is a separate signal for whether that declared level is
 * assessment-verified. Never derive one from the other client-side. */
export interface SkillGapItem {
  skill_id: string;
  skill_name: string;
  current_level: Difficulty | null;
  required_level: Difficulty;
  gap: number;
  status: GapStatus;
  verification_status: VerificationStatus;
  importance: Importance;
  priority: Priority;
  assessment_available: boolean;
  assessment_id: string | null;
}

/** Mirrors `SkillGapSummary`. */
export interface SkillGapSummary {
  matched: number;
  needs_improvement: number;
  missing: number;
  unverified: number;
}

/** Mirrors `Recommendation`. `reason` is server-authored from a small set
 * of fixed templates -- never LLM text, never rewritten client-side. */
export interface Recommendation {
  skill_id: string;
  skill_name: string;
  reason: string;
  current_level: Difficulty | null;
  target_level: Difficulty | null;
  gap: number | null;
  priority: Priority;
  relationship_type: RelationshipType | null;
  is_missing: boolean;
  is_verified: boolean;
  assessment_available: boolean;
  assessment_id: string | null;
}

/** Mirrors `SkillGapJobRoleResponse` -- GET /skill-gap when a target role
 * is set, or GET /skill-gap/job-role/{id} for any active role. */
export interface SkillGapJobRoleAnalysis {
  mode: "JOB_ROLE";
  job_role: JobRole;
  readiness_percentage: number;
  summary: SkillGapSummary;
  skills: SkillGapItem[];
  recommendations: Recommendation[];
}

/** Mirrors `PersonalSkillCounts`. */
export interface PersonalSkillCounts {
  total_active_skills: number;
  verified_skills: number;
  unverified_skills: number;
  beginner_skills: number;
  intermediate_skills: number;
  advanced_skills: number;
  expert_skills: number;
}

/** Mirrors `ProgressableSkill`. */
export interface ProgressableSkill {
  skill_id: string;
  skill_name: string;
  current_level: Difficulty;
  next_level: Difficulty;
  assessment_available: boolean;
  assessment_id: string | null;
}

/** Mirrors `PrerequisiteGap`. */
export interface PrerequisiteGap {
  skill_id: string;
  skill_name: string;
  required_for_skill_id: string;
  required_for_skill_name: string;
}

/** Mirrors `SkillGapPersonalResponse` -- GET /skill-gap when no target
 * role is set. */
export interface SkillGapPersonalAnalysis {
  mode: "PERSONAL";
  counts: PersonalSkillCounts;
  progressable_skills: ProgressableSkill[];
  recommendations: Recommendation[];
  prerequisite_gaps: PrerequisiteGap[];
}

/** GET /skill-gap's response is one of these two shapes -- `mode`
 * discriminates which. Never render one without checking `mode` first. */
export type SkillGapAnalysis = SkillGapJobRoleAnalysis | SkillGapPersonalAnalysis;
