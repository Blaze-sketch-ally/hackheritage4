import type { SaveAnswerInput } from "@/lib/student/assessment";

/**
 * Per Decision A (see the assessment-UI phase report): the backend has no
 * endpoint to read back an in-progress attempt's id or its saved answers
 * (only `POST .../answers`, `/submit`, `/score`, and the COMPLETED-only
 * `GET .../result` exist). There is deliberately no resume system here --
 * this module only lets a same-tab reload during one sitting recover the
 * UI state that a hard navigation away would otherwise lose. If this
 * storage is unavailable, cleared, or the student opens a different tab
 * or device, the attempt genuinely cannot be recovered from here -- see
 * the "already in progress, cannot be recovered from this device" state
 * in the assessment-taking page, which is the honest fallback for that
 * case, not a silently-started new attempt.
 */

const STORAGE_PREFIX = "aic:assessment-attempt:";

export interface StoredAttemptState {
  assessmentId: string;
  attemptId: string;
  /** Keyed by question_id -- the last input successfully saved via
   * POST .../answers, so the taking UI can repaint prior selections after
   * a reload without re-fetching anything. */
  answers: Record<string, SaveAnswerInput>;
}

function storageKey(assessmentId: string): string {
  return `${STORAGE_PREFIX}${assessmentId}`;
}

function hasSessionStorage(): boolean {
  return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";
}

export function loadStoredAttempt(assessmentId: string): StoredAttemptState | null {
  if (!hasSessionStorage()) return null;
  try {
    const raw = window.sessionStorage.getItem(storageKey(assessmentId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredAttemptState;
    if (!parsed || typeof parsed.attemptId !== "string" || parsed.assessmentId !== assessmentId) {
      return null;
    }
    return parsed;
  } catch {
    // Corrupt/unavailable storage -- treat exactly like "nothing stored".
    return null;
  }
}

export function saveStoredAttempt(state: StoredAttemptState): void {
  if (!hasSessionStorage()) return;
  try {
    window.sessionStorage.setItem(storageKey(state.assessmentId), JSON.stringify(state));
  } catch {
    // Storage full/unavailable -- the current tab's React state still
    // drives the UI; only cross-reload recovery is lost, silently.
  }
}

export function saveStoredAnswer(
  assessmentId: string,
  attemptId: string,
  answer: SaveAnswerInput,
): void {
  const existing = loadStoredAttempt(assessmentId);
  const answers = existing?.attemptId === attemptId ? { ...existing.answers } : {};
  answers[answer.question_id] = answer;
  saveStoredAttempt({ assessmentId, attemptId, answers });
}

export function clearStoredAttempt(assessmentId: string): void {
  if (!hasSessionStorage()) return;
  try {
    window.sessionStorage.removeItem(storageKey(assessmentId));
  } catch {
    // Nothing to do -- the entry is either gone or was never readable.
  }
}
