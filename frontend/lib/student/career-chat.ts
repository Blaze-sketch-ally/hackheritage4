import { api } from "@/lib/api";
import type { CareerChatResponse, ChatMessage } from "@/types/career-chat";

const MAX_HISTORY = 6;

/**
 * Talks to the live Career AI Chat API
 * (backend/app/api/ai.py::post_career_chat, POST /api/v1/ai/career-chat).
 * Only place in the frontend that constructs this request -- components
 * call this function, never `api.post` directly. Goes through
 * lib/api.ts's apiFetch(), which attaches the student's own Supabase
 * access token; no student_id is ever sent -- the backend derives it
 * from the token.
 *
 * `history` is trimmed to the last MAX_HISTORY turns here too (the
 * backend also bounds it, but trimming client-side keeps the request
 * small and matches what the widget actually keeps in memory -- see
 * components/ai/career-chat-widget.tsx). History is conversational
 * context only; every canonical fact in the response is re-fetched
 * fresh by the backend for this request.
 */
export function sendCareerChatMessage(
  message: string,
  history: ChatMessage[],
): Promise<CareerChatResponse> {
  return api.post("/api/v1/ai/career-chat", {
    message,
    history: history.slice(-MAX_HISTORY),
  });
}
