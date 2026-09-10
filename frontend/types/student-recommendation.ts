// Mirrors backend/app/schemas/student_recommendation.py. Keep in sync.
//
// The aggregate recommendation surface is a thin composer over three
// canonical, unchanged systems: the Skill Gap engine (target-role /
// personal context), the deterministic internship/job skill matcher
// (match_service), and the Skill Gap -> learning-resource mapping. No new
// score, probability, or percentage is invented anywhere.

import type { LearningRecommendation } from "@/types/student-learning";

export type RecommendationMode = "AGGREGATE";

export interface RecommendedTargetRole {
  id: string;
  name: string;
}

export interface RecommendedAssessment {
  id: string;
  title: string;
  skill_id: string;
  skill_name: string;
  difficulty: string;
  duration_minutes: number | null;
  /** Mirrors the underlying AlignmentStatus the Skill Gap entry came from. */
  reason_type: "SKILL_GAP" | "NOT_ASSESSED";
  /** The Skill Gap engine's own explanation string -- never hardcoded here. */
  reason: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
}

export interface RecommendedOpportunity {
  type: "INTERNSHIP" | "JOB";
  /** Existing prefixed id: `internship_<uuid>` / `job_<uuid>`. */
  id: string;
  title: string;
  description: string;
  company: string | null;
  location: string | null;
  work_mode: string | null;
  /** Server-built fixed-prefix student route — never a free-form string. */
  detail_path: string;
  /** Canonical match_service skill-coverage score (0–100). NOT a probability. */
  match_score: number;
  match_band: "STRONG" | "GOOD" | "PARTIAL" | "LOW";
  matched_skill_count: number;
  required_skill_count: number;
  relevant_skills: string[];
}

export interface StudentRecommendationsResponse {
  mode: RecommendationMode;
  target_role: RecommendedTargetRole | null;
  assessments: RecommendedAssessment[];
  opportunities: RecommendedOpportunity[];
  learning: LearningRecommendation[];
}
