// Mirrors backend/app/schemas/institution_skill_gap.py.
//
// An APPLICATION-scoped skill gap tool, not an institution-wide dashboard:
// student -> application -> job/internship -> required skills -> student
// skills -> gap. The match fields (score/recommendation/skill_coverage/
// matched_skills/needs_improvement_skills/missing_skills) reuse the EXACT
// same `MatchSkill` / `MatchRecommendation` shape Industry's own
// ApplicationMatchResponse already defines (types/application.ts) --
// imported, not redefined, so the institution and industry views can never
// silently drift into two different skill-match shapes.

import type {
  ApplicationStatus,
  MatchRecommendation,
  MatchSkill,
  OpportunityType,
} from "@/types/application";

export interface SkillGapApplicationSummary {
  application_id: string;
  student_id: string;
  full_name: string | null;
  username: string | null;
  opportunity_type: OpportunityType;
  opportunity_title: string | null;
  company_name: string | null;
  status: ApplicationStatus;
  applied_at: string | null;
  score: number;
  recommendation: MatchRecommendation;
  skill_coverage: string;
  matched_count: number;
  needs_improvement_count: number;
  missing_count: number;
}

export interface SkillGapListResponse {
  applications: SkillGapApplicationSummary[];
}

/** The student's own recorded skill -- not just the subset a particular
 * opportunity requires. Same shape as the Student Directory's
 * StudentSkillSummary (backend/app/schemas/institution_student.py). */
export interface StudentSkillEntry {
  skill_name: string;
  proficiency_level: string;
  is_verified: boolean;
}

export interface SkillGapDetail extends SkillGapApplicationSummary {
  required_count: number;
  matched_skills: MatchSkill[];
  needs_improvement_skills: MatchSkill[];
  missing_skills: MatchSkill[];
  student_skills: StudentSkillEntry[];
}

export interface SkillGapListParams {
  search?: string;
  opportunity_type?: OpportunityType;
  status?: ApplicationStatus;
}
