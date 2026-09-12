/**
 * Mirrors backend/app/ai/schemas/career_guidance.py exactly -- field-for-
 * field, same nullability. This is the Phase 6 Career Orchestrator +
 * Career Advisor response: every canonical status/skill_id/score/band
 * field is attached server-side from the same deterministic engines every
 * other student page already trusts (skill_gap_service, match_service,
 * learning_recommendation_service) -- nothing here is recomputed
 * client-side, and nothing here is unrestricted LLM prose. `headline`,
 * `reason`, and `suggested_action` text are server-authored or
 * server-grounded, never raw model output rendered without grounding.
 */

import type { OpportunityMatch, StudentOpportunityDetail } from "@/types/student-opportunity";
import type { YouTubeVideoCandidate } from "@/types/youtube-learning";

export type AnalysisMode = "JOB_ROLE" | "PERSONAL";

export type AssessmentActionType =
  | "ADD_SKILL_THEN_ASSESS"
  | "TAKE_ASSESSMENT"
  | "ALREADY_VERIFIED"
  | "NO_ASSESSMENT_AVAILABLE";

export type CareerActionCode =
  | "LEARN_SKILL"
  | "TAKE_ASSESSMENT"
  | "START_COURSE"
  | "APPLY_OPPORTUNITY"
  | "BUILD_PROJECT"
  | "REASSESS_SKILL";

/** Mirrors `CourseCandidate` (app.ai.schemas.course_recommendation) --
 * every field here is source-owned (the internal learning catalog, or a
 * future configured external provider); never LLM-authored. */
export interface CourseCandidate {
  candidate_id: string;
  source_type: "INTERNAL" | "EXTERNAL";
  provider: string | null;
  title: string;
  url: string;
  description: string | null;
  skill_ids: string[];
  skill_names: string[];
  level: string | null;
  duration_text: string | null;
  price_text: string | null;
  rating: number | null;
  certificate_available: boolean | null;
  external_course_id: string | null;
  metadata_source: string;
}

/** Mirrors `CareerSummary`. `headline` is the only AI-authored field on
 * this whole response and is null whenever Career Advisor synthesis did
 * not run -- never fabricated as a substitute for a canonical number. */
export interface CareerSummary {
  mode: AnalysisMode;
  target_role: string | null;
  readiness_score: number | null;
  headline: string | null;
}

/** Mirrors `PrioritySkill`. `reason`/`suggested_action` come from the
 * Skill Gap Agent's own grounded analysis (Phase 3) -- never re-authored
 * here. `highlighted_by_advisor` is the only field the Career Advisor
 * influences, and it only ever reorders/flags, never invents. */
export interface PrioritySkill {
  skill_id: string;
  skill_name: string;
  canonical_status: string | null;
  canonical_priority: string | null;
  canonical_importance: string | null;
  reason: string;
  suggested_action: string;
  highlighted_by_advisor: boolean;
}

export interface LearningRecommendationItem {
  course: CourseCandidate;
  for_skill_id: string | null;
  for_skill_name: string | null;
  reason: string;
  highlighted_by_advisor: boolean;
}

/** Mirrors `YouTubeRecommendationItem` -- additive sibling of
 * `LearningRecommendationItem`, never merged into it (a video is not a
 * CourseCandidate). Never touched by the Career Advisor -- see the
 * backend class's own docstring -- so there is no
 * `highlighted_by_advisor` field here. */
export interface YouTubeRecommendationItem {
  video: YouTubeVideoCandidate;
  for_skill_id: string | null;
  for_skill_name: string | null;
  reason: string;
}

export interface OpportunityRecommendationItem {
  opportunity: StudentOpportunityDetail;
  match: OpportunityMatch;
  reason: string;
  highlighted_by_advisor: boolean;
}

export interface AssessmentRecommendationItem {
  skill_id: string;
  skill_name: string;
  action: AssessmentActionType;
  assessment_available: boolean;
  note: string;
  highlighted_by_advisor: boolean;
}

/** `entity_id`/`entity_name` are always copied from the referenced
 * specialist's own grounded object server-side -- never from LLM text. */
export interface NextAction {
  order: number;
  type: CareerActionCode;
  entity_type: "SKILL" | "COURSE" | "OPPORTUNITY" | "ASSESSMENT";
  entity_id: string;
  entity_name: string;
}

export interface AgentStatus {
  available: boolean;
  fallback_used: boolean;
  detail: string | null;
}

export interface CareerGuidanceAgentsUsed {
  skill_gap_agent: AgentStatus;
  course_agent: AgentStatus;
  opportunity_agent: AgentStatus;
  career_advisor: AgentStatus;
}

export interface CareerGuidanceMeta {
  provider: "groq";
  model: string;
  ai_available: boolean;
  agents_used: CareerGuidanceAgentsUsed;
}

export interface CareerGuidanceResponse {
  career_summary: CareerSummary;
  priority_skills: PrioritySkill[];
  learning_recommendations: LearningRecommendationItem[];
  youtube_videos: YouTubeRecommendationItem[];
  opportunity_recommendations: OpportunityRecommendationItem[];
  assessment_recommendations: AssessmentRecommendationItem[];
  next_actions: NextAction[];
  meta: CareerGuidanceMeta;
  disclaimer: string;
}
