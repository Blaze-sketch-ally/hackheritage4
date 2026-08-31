import { api, ApiError } from "@/lib/api";
import type {
  Assessment,
  AssessmentAnswer,
  AssessmentAttempt,
  AssessmentQuestion,
  AssessmentResult,
  AssessmentResultQuestion,
  AttemptHistoryItem,
  ScoredAttempt,
} from "@/types/assessment";

/**
 * Talks to the live Assessment API (backend/app/api/assessments.py,
 * attempts.py -- Phase 1C-1I, merged in PR #6). This is the only place in
 * the frontend that constructs these requests; components call these
 * functions, never `api.get/post` directly, so the exact request/response
 * shapes stay in one place. Every call goes through lib/api.ts's
 * apiFetch(), which attaches the student's own Supabase access token --
 * there is no other authorization mechanism here, and none is added
 * client-side (no student_id is ever sent in a request; the backend
 * derives it from the token).
 */

export function listAssessments(): Promise<{ assessments: Assessment[] }> {
  return api.get("/api/v1/assessments");
}

export function getAssessment(assessmentId: string): Promise<Assessment> {
  return api.get(`/api/v1/assessments/${assessmentId}`);
}

/** The caller's own IN_PROGRESS attempt at this assessment, or null if
 * none exists. Backed by GET /assessments/{id}/attempts/current
 * (015_assessment_verification.sql) -- lets the taking UI offer a real
 * "Resume Assessment" instead of only discovering one exists via a 409
 * from createAttempt(). Any error status other than 404 still throws. */
export async function getCurrentAttempt(assessmentId: string): Promise<AssessmentAttempt | null> {
  try {
    return await api.get<AssessmentAttempt>(`/api/v1/assessments/${assessmentId}/attempts/current`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

/** Starts a new attempt. The backend randomly selects and permanently
 * freezes this attempt's question set in the same atomic operation
 * (create_assessment_attempt(), 015_assessment_verification.sql) -- the
 * frontend never chooses, sees, or influences which questions are picked.
 * Returns 409 (ApiError.status === 409) if the student already has an
 * IN_PROGRESS attempt; use getCurrentAttempt() first to resume it instead. */
export function createAttempt(assessmentId: string): Promise<AssessmentAttempt> {
  return api.post(`/api/v1/assessments/${assessmentId}/attempts`);
}

/** The calling student's own FROZEN question selection for one attempt --
 * never the live question bank. The same attempt_id always returns the
 * same questions in the same order, on first load, on refresh, and on
 * resume, because this reads a permanent record persisted when the
 * attempt started, not a live re-query. Never call the removed
 * assessment-level questions endpoint (it no longer exists) -- this is
 * the only source of exam questions in the app. */
export function getAttemptQuestions(attemptId: string): Promise<AssessmentQuestion[]> {
  return api.get(`/api/v1/attempts/${attemptId}/questions`);
}

/** The caller's own full assessment history, most recent first. */
export async function getAttemptHistory(): Promise<AttemptHistoryItem[]> {
  const { attempts } = await api.get<{ attempts: AttemptHistoryItem[] }>("/api/v1/attempts");
  return attempts;
}

export interface SaveAnswerInput {
  question_id: string;
  answer_text?: string | null;
  selected_option_ids?: string[] | null;
}

/** Saves (inserts or revises) the student's answer to one question. Mirrors
 * AssessmentAnswerRequest exactly: at least one of answer_text /
 * selected_option_ids must be set, and selected_option_ids must not be an
 * empty array -- both enforced backend-side (422 otherwise), not
 * duplicated here, so this function never fabricates a placeholder
 * answer. Leaving a question unanswered means simply never calling this
 * for it -- the backend's own scoring RPC is what persists an "unanswered"
 * historical record, at scoring time, not the frontend. */
export function saveAnswer(attemptId: string, input: SaveAnswerInput): Promise<AssessmentAnswer> {
  return api.post(`/api/v1/attempts/${attemptId}/answers`, input);
}

/** No request body -- attempt_id comes from the URL, nothing else is
 * accepted (SubmitAttemptRequest is empty, extra="forbid"). */
export function submitAttempt(attemptId: string): Promise<AssessmentAttempt> {
  return api.post(`/api/v1/attempts/${attemptId}/submit`);
}

/** Triggers the trusted, atomic PostgreSQL scoring RPC. No request body.
 * The frontend never computes score/total_marks/percentage itself -- this
 * call's response is the only source of them. */
export function scoreAttempt(attemptId: string): Promise<ScoredAttempt> {
  return api.post(`/api/v1/attempts/${attemptId}/score`);
}

/** COMPLETED-only. 409 if the attempt isn't scored yet, 404 if it doesn't
 * exist or isn't the caller's own. */
export function getAttemptResult(attemptId: string): Promise<AssessmentResult> {
  return api.get(`/api/v1/attempts/${attemptId}/result`);
}

/** True when a result question's student_answer represents "never
 * answered" -- either the field is genuinely null, or it's the Phase 1H
 * unanswered-placeholder sentinel (answer_text: null, selected_option_ids:
 * an empty array). A real student answer can never produce that exact
 * shape (the request schema rejects an empty selected_option_ids array),
 * so this check is unambiguous. Centralized here so no component ever
 * re-derives it, and so the raw empty-array sentinel is never rendered
 * directly to a student. */
export function isUnansweredResult(result: AssessmentResultQuestion): boolean {
  const answer = result.student_answer;
  if (!answer) return true;
  const hasText = answer.answer_text !== null && answer.answer_text !== "";
  const hasOptions = Array.isArray(answer.selected_option_ids) && answer.selected_option_ids.length > 0;
  return !hasText && !hasOptions;
}
