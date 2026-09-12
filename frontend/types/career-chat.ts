/**
 * Mirrors backend/app/ai/schemas/career_chat.py exactly -- every card
 * field is server-owned (the same canonical/deterministic sources every
 * other AI route already trusts); the assistant's `message` is the only
 * free text, and even that is grounded server-side against real cards
 * before being returned (see that module's own docstring).
 */

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export type ChatIntent =
  | "SKILL_GAP"
  | "LEARNING"
  | "YOUTUBE_LEARNING"
  | "JOB"
  | "INTERNSHIP"
  | "OPPORTUNITY"
  | "ASSESSMENT"
  | "CAREER_PLAN"
  | "READINESS"
  | "GENERAL_CAREER";

export interface SkillCard {
  type: "SKILL";
  skill_id: string;
  skill_name: string;
  current_level: string | null;
  target_level: string | null;
  status: string | null;
  priority: string | null;
  importance: string | null;
  reason: string | null;
}

export interface CourseCard {
  type: "COURSE";
  candidate_id: string;
  title: string;
  provider: string | null;
  url: string;
  level: string | null;
  duration_text: string | null;
  skill_name: string | null;
  reason: string | null;
}

export interface YouTubeVideoCard {
  type: "YOUTUBE_VIDEO";
  video_id: string;
  title: string;
  channel_title: string;
  thumbnail_url: string | null;
  watch_url: string;
  duration_text: string | null;
  view_count: number | null;
  published_at: string | null;
  skill_name: string | null;
  reason: string | null;
}

export interface OpportunityCard {
  type: "OPPORTUNITY";
  opportunity_id: string;
  opportunity_type: string;
  title: string;
  company: string | null;
  match_score: number | null;
  match_band: string | null;
  matched_count: number | null;
  gap_count: number | null;
  detail_url: string;
  reason: string | null;
}

export interface AssessmentCard {
  type: "ASSESSMENT";
  skill_id: string;
  skill_name: string;
  action: string;
  note: string;
  cta_url: string;
}

export interface CareerActionCard {
  type: "CAREER_ACTION";
  label: string;
  url: string;
}

export type ChatCard =
  | SkillCard
  | CourseCard
  | YouTubeVideoCard
  | OpportunityCard
  | AssessmentCard
  | CareerActionCard;

export interface SuggestedAction {
  label: string;
  url: string;
}

export interface CareerChatMeta {
  provider: "groq";
  model: string;
  ai_available: boolean;
  intent: ChatIntent;
  intent_source: "KEYWORD" | "AI_CLASSIFIER" | "DEFAULT";
}

export interface CareerChatResponse {
  message: string;
  intent: ChatIntent;
  cards: ChatCard[];
  suggested_actions: SuggestedAction[];
  meta: CareerChatMeta;
  disclaimer: string;
}

export interface CareerChatRequest {
  message: string;
  history: ChatMessage[];
}
