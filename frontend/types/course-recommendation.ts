/**
 * Mirrors backend/app/ai/schemas/course_recommendation.py exactly --
 * the raw response of POST /api/v1/ai/course-recommendations. Every
 * canonical/course/video field here is server-owned (the internal
 * catalog, a configured external provider, or a configured YouTube
 * provider); nothing here is unrestricted LLM prose.
 */

import type { AnalysisMode, CourseCandidate } from "@/types/career-guidance";
import type { YouTubeVideoCandidate } from "@/types/youtube-learning";

export interface CourseSkill {
  ref: string;
  skill_id: string;
  skill_name: string;
  status: string | null;
  priority: string | null;
  importance: string | null;
  current_level: string | null;
  target_level: string | null;
  reason: string | null;
}

export interface CourseCanonical {
  mode: AnalysisMode;
  target_role: string | null;
  skills_considered: CourseSkill[];
}

export interface CourseRecommendation {
  course: CourseCandidate;
  for_skill: CourseSkill;
  reason: string;
  rank: number;
}

export interface CoursePlanStep {
  order: number;
  candidate_id: string;
  skill_id: string;
  instruction: string;
}

/** Mirrors `YouTubeSkillRef` -- an independent, minimal copy of the
 * same canonical skill fields (see that class's own backend docstring
 * for why it isn't literally CourseSkill). */
export interface YouTubeSkillRef {
  ref: string;
  skill_id: string;
  skill_name: string;
  status: string | null;
  importance: string | null;
  target_level: string | null;
}

export interface YouTubeRecommendation {
  video: YouTubeVideoCandidate;
  for_skill: YouTubeSkillRef;
  reason: string;
  rank: number;
}

export interface CourseResponseMeta {
  provider: "groq";
  model: string;
  ai_ranking_available: boolean;
  ranking_status: "AI" | "DETERMINISTIC" | "NO_GAPS" | "NO_COURSES";
  external_discovery_available: boolean;
  external_discovery_status: "AVAILABLE" | "CONFIGURATION_REQUIRED" | "FAILED";
  internal_discovery_available: boolean;
  message: string | null;
  youtube_available: boolean;
  youtube_ai_ranking_available: boolean;
  youtube_status: "AVAILABLE" | "CONFIGURATION_REQUIRED" | "QUOTA_EXCEEDED" | "TEMPORARILY_UNAVAILABLE" | "FAILED";
}

export interface CourseRecommendationResponse {
  canonical: CourseCanonical;
  recommendations: CourseRecommendation[];
  learning_plan: CoursePlanStep[];
  youtube_videos: YouTubeRecommendation[];
  meta: CourseResponseMeta;
  disclaimer: string;
}
