import { api } from "@/lib/api";
import type { CareerGuidanceResponse, NextAction } from "@/types/career-guidance";

/**
 * Talks to the live Career Guidance API
 * (backend/app/api/ai.py::get_career_guidance, POST /api/v1/ai/career-guidance).
 * Only place in the frontend that constructs this request -- components
 * call this function, never `api.post` directly. Every call goes
 * through lib/api.ts's apiFetch(), which attaches the student's own
 * Supabase access token; no student_id is ever sent -- the backend
 * derives it from the token.
 *
 * The orchestrator (backend/app/ai/orchestrator.py) always returns 200
 * with a fully-shaped response, even when one or more specialist agents
 * or the Career Advisor synthesis itself is unavailable -- check
 * `meta.agents_used` / `meta.ai_available` to know what degraded,
 * never assume every section is AI-derived.
 */
export function getCareerGuidance(): Promise<CareerGuidanceResponse> {
  return api.post("/api/v1/ai/career-guidance");
}

/** Short, human-readable label for one server-grounded next action --
 * `entity_name` always came from a real specialist object; this only
 * chooses the verb phrasing for the fixed `type` code, never invents
 * detail. Shared between the Dashboard card and the full Career page so
 * the two surfaces never disagree on wording. */
export function describeNextAction(action: NextAction): string {
  switch (action.type) {
    case "LEARN_SKILL":
      return `Learn ${action.entity_name}`;
    case "TAKE_ASSESSMENT":
      return `Take the ${action.entity_name} assessment`;
    case "START_COURSE":
      return `Start "${action.entity_name}"`;
    case "APPLY_OPPORTUNITY":
      return `Apply to ${action.entity_name}`;
    case "BUILD_PROJECT":
      return `Build a project using ${action.entity_name}`;
    case "REASSESS_SKILL":
      return `Re-verify ${action.entity_name}`;
    default:
      return action.entity_name;
  }
}
