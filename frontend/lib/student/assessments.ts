import type { SupabaseClient } from "@supabase/supabase-js";

/**
 * Mirrors the LIVE assessments / assessment_questions /
 * assessment_question_options / assessment_attempts / assessment_answers
 * tables (database/migrations/004_assessments.sql — applied and verified).
 * This module is the only place that talks to those tables from the
 * frontend. It never queries assessment_question_answers (the protected
 * answer key) — that table has no student-readable path relevant to this
 * phase (listing, taking, and submitting an assessment never needs it;
 * see the migration's own comments for when a student *can* read it).
 *
 * Scoring is intentionally out of scope here: assessment_attempts can
 * only ever be marked COMPLETED (with a real score) by a service_role
 * caller — see prevent_self_attempt_scoring() in 004_assessments.sql.
 * submitAttempt() below sets submitted_at only, which the trigger allows;
 * it never attempts to set status or score fields, since that write would
 * always be rejected by design until a backend scoring service exists.
 */

export type Difficulty = "Beginner" | "Intermediate" | "Advanced" | "Expert";
export type QuestionType = "MCQ" | "MULTIPLE_SELECT" | "SHORT_ANSWER" | "CODE" | "SUBJECTIVE";
export type AttemptStatus = "IN_PROGRESS" | "COMPLETED" | "ABANDONED";

export interface Assessment {
  id: string;
  skill_id: string;
  title: string;
  description: string | null;
  difficulty: Difficulty;
  duration_minutes: number | null;
  question_count: number | null;
  is_active: boolean;
  created_at: string;
  skill: { id: string; name: string } | null;
}

export interface QuestionOption {
  id: string;
  option_text: string;
  display_order: number;
}

export interface AssessmentQuestion {
  id: string;
  assessment_id: string;
  question_text: string;
  question_type: QuestionType;
  difficulty: Difficulty;
  points: number;
  display_order: number;
  options: QuestionOption[];
}

export interface AssessmentAttempt {
  id: string;
  student_id: string;
  assessment_id: string;
  status: AttemptStatus;
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  total_marks: number | null;
  percentage: number | null;
}

export interface AttemptWithAssessment extends AssessmentAttempt {
  assessment: {
    id: string;
    title: string;
    difficulty: Difficulty;
    skill: { id: string; name: string } | null;
  } | null;
}

export interface AssessmentAnswer {
  id: string;
  attempt_id: string;
  question_id: string;
  answer_text: string | null;
  selected_option_ids: string[] | null;
  awarded_marks: number | null;
  is_correct: boolean | null;
}

const ASSESSMENT_SELECT =
  "id, skill_id, title, description, difficulty, duration_minutes, question_count, is_active, created_at, skill:skills(id, name)";

/** Active assessments visible to the caller (RLS: STUDENT role, is_active = true). */
export async function fetchActiveAssessments(supabase: SupabaseClient): Promise<Assessment[]> {
  const { data, error } = await supabase
    .from("assessments")
    .select(ASSESSMENT_SELECT)
    .order("created_at", { ascending: false });

  if (error) {
    console.error("assessments read failed:", error.message);
    return [];
  }
  return (data ?? []) as unknown as Assessment[];
}

/** A single assessment, or null if it doesn't exist or isn't visible to the caller (RLS). */
export async function fetchAssessmentById(supabase: SupabaseClient, assessmentId: string): Promise<Assessment | null> {
  const { data, error } = await supabase.from("assessments").select(ASSESSMENT_SELECT).eq("id", assessmentId).maybeSingle();

  if (error) {
    console.error("assessment read failed:", error.message);
    return null;
  }
  return (data as unknown as Assessment | null) ?? null;
}

/** Approved, active questions for an assessment, with their options in display order (RLS-filtered). */
export async function fetchAssessmentQuestions(supabase: SupabaseClient, assessmentId: string): Promise<AssessmentQuestion[]> {
  const { data, error } = await supabase
    .from("assessment_questions")
    .select("id, assessment_id, question_text, question_type, difficulty, points, display_order, options:assessment_question_options(id, option_text, display_order)")
    .eq("assessment_id", assessmentId)
    .order("display_order", { ascending: true })
    .order("display_order", { ascending: true, referencedTable: "assessment_question_options" });

  if (error) {
    console.error("assessment_questions read failed:", error.message);
    return [];
  }
  return (data ?? []) as unknown as AssessmentQuestion[];
}

/** The caller's own in-progress attempt at this assessment, if one exists. */
export async function findInProgressAttempt(
  supabase: SupabaseClient,
  studentId: string,
  assessmentId: string,
): Promise<AssessmentAttempt | null> {
  const { data, error } = await supabase
    .from("assessment_attempts")
    .select("id, student_id, assessment_id, status, started_at, submitted_at, score, total_marks, percentage")
    .eq("student_id", studentId)
    .eq("assessment_id", assessmentId)
    .eq("status", "IN_PROGRESS")
    .maybeSingle();

  if (error) {
    console.error("assessment_attempts read failed:", error.message);
    return null;
  }
  return (data as AssessmentAttempt | null) ?? null;
}

export async function fetchAttemptById(supabase: SupabaseClient, attemptId: string): Promise<AssessmentAttempt | null> {
  const { data, error } = await supabase
    .from("assessment_attempts")
    .select("id, student_id, assessment_id, status, started_at, submitted_at, score, total_marks, percentage")
    .eq("id", attemptId)
    .maybeSingle();

  if (error) {
    console.error("assessment_attempts read failed:", error.message);
    return null;
  }
  return (data as AssessmentAttempt | null) ?? null;
}

/** The caller's most recent attempt at this assessment (any status). */
export async function fetchLatestAttempt(
  supabase: SupabaseClient,
  studentId: string,
  assessmentId: string,
): Promise<AssessmentAttempt | null> {
  const { data, error } = await supabase
    .from("assessment_attempts")
    .select("id, student_id, assessment_id, status, started_at, submitted_at, score, total_marks, percentage")
    .eq("student_id", studentId)
    .eq("assessment_id", assessmentId)
    .order("started_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) {
    console.error("assessment_attempts read failed:", error.message);
    return null;
  }
  return (data as AssessmentAttempt | null) ?? null;
}

/** All of the caller's own attempts, most recent first, with assessment context for the history page. */
export async function fetchMyAttempts(supabase: SupabaseClient, studentId: string): Promise<AttemptWithAssessment[]> {
  const { data, error } = await supabase
    .from("assessment_attempts")
    .select(
      "id, student_id, assessment_id, status, started_at, submitted_at, score, total_marks, percentage, assessment:assessments(id, title, difficulty, skill:skills(id, name))",
    )
    .eq("student_id", studentId)
    .order("started_at", { ascending: false });

  if (error) {
    console.error("assessment_attempts read failed:", error.message);
    return [];
  }
  return (data ?? []) as unknown as AttemptWithAssessment[];
}

/**
 * Starts a new attempt. student_id always comes from the authenticated
 * caller (passed in from a server-resolved user.id — never from a URL or
 * other client-controlled value). RLS additionally enforces
 * auth.uid() = student_id and a fresh IN_PROGRESS row shape regardless.
 */
export async function startAttempt(supabase: SupabaseClient, studentId: string, assessmentId: string) {
  return supabase
    .from("assessment_attempts")
    .insert({ student_id: studentId, assessment_id: assessmentId })
    .select("id, student_id, assessment_id, status, started_at, submitted_at, score, total_marks, percentage")
    .single();
}

export async function fetchMyAnswers(supabase: SupabaseClient, attemptId: string): Promise<AssessmentAnswer[]> {
  const { data, error } = await supabase
    .from("assessment_answers")
    .select("id, attempt_id, question_id, answer_text, selected_option_ids, awarded_marks, is_correct")
    .eq("attempt_id", attemptId);

  if (error) {
    console.error("assessment_answers read failed:", error.message);
    return [];
  }
  return (data ?? []) as AssessmentAnswer[];
}

/**
 * Saves (or revises) the caller's answer to one question in one attempt.
 * Upserts on the (attempt_id, question_id) unique constraint — RLS's
 * insert policy requires the attempt to be the caller's own and
 * IN_PROGRESS; the update policy (for the revision path) requires the
 * same. awarded_marks/is_correct are never sent from here.
 */
export async function saveAnswer(
  supabase: SupabaseClient,
  attemptId: string,
  questionId: string,
  input: { answerText?: string | null; selectedOptionIds?: string[] | null },
) {
  return supabase
    .from("assessment_answers")
    .upsert(
      {
        attempt_id: attemptId,
        question_id: questionId,
        answer_text: input.answerText ?? null,
        selected_option_ids: input.selectedOptionIds ?? null,
      },
      { onConflict: "attempt_id,question_id" },
    )
    .select("id, attempt_id, question_id, answer_text, selected_option_ids, awarded_marks, is_correct")
    .single();
}

/**
 * Marks the student's side of an attempt done. Deliberately sets only
 * submitted_at — status stays IN_PROGRESS. The database trigger
 * (prevent_self_attempt_scoring) unconditionally rejects any non-
 * service_role attempt to transition status to COMPLETED or to set
 * score/total_marks/percentage, since that requires a real scoring
 * result that only a future backend service can produce. This function
 * never attempts that write, so it never triggers that rejection —
 * "submitted, awaiting scoring" is a real, valid state the schema
 * already supports (no constraint ties submitted_at to status).
 */
export async function submitAttempt(supabase: SupabaseClient, attemptId: string) {
  return supabase
    .from("assessment_attempts")
    .update({ submitted_at: new Date().toISOString() })
    .eq("id", attemptId)
    .select("id, student_id, assessment_id, status, started_at, submitted_at, score, total_marks, percentage")
    .single();
}

/** A student may abandon their own in-progress attempt — the one status transition RLS allows directly. */
export async function abandonAttempt(supabase: SupabaseClient, attemptId: string) {
  return supabase
    .from("assessment_attempts")
    .update({ status: "ABANDONED" })
    .eq("id", attemptId)
    .select("id, student_id, assessment_id, status, started_at, submitted_at, score, total_marks, percentage")
    .single();
}

export interface ScoredAttemptResult {
  attempt_id: string;
  status: AttemptStatus;
  score: number;
  total_marks: number;
  percentage: number;
  correct_count: number;
  incorrect_count: number;
  submitted_at: string | null;
}

/**
 * Asks the FastAPI backend to authoritatively score and complete the
 * caller's own attempt (POST /api/assessments/{attemptId}/submit). The
 * frontend never computes or sends a score itself — this call sends only
 * the attempt id (as a path segment, to identify *which* attempt) plus
 * the student's own Supabase access token as a bearer credential; the
 * backend independently verifies that token and resolves the student's
 * identity itself (see backend/app/core/dependencies.py). No
 * service_role credential is ever present in this frontend code.
 *
 * Deliberately never throws — a failure here (backend unreachable, not
 * yet configured, etc.) is not treated as blocking: submitAttempt()
 * already recorded submitted_at directly against Supabase before this is
 * called, so the attempt remains in a valid, honestly-displayed
 * "submitted, awaiting scoring" state either way (see the result page).
 */
export async function scoreAttemptViaBackend(
  supabase: SupabaseClient,
  attemptId: string,
): Promise<{ data: ScoredAttemptResult | null; error: string | null }> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return { data: null, error: "Your session has expired. Please sign in again." };
  }

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  try {
    const response = await fetch(`${apiBaseUrl}/api/assessments/${attemptId}/submit`, {
      method: "POST",
      headers: { Authorization: `Bearer ${session.access_token}` },
    });

    if (!response.ok) {
      // Never surface the backend's raw error body to the user.
      console.error("Backend scoring request failed:", response.status, await response.text().catch(() => ""));
      return {
        data: null,
        error: "We couldn't score your assessment right now. Your submission has been saved — please try again shortly.",
      };
    }

    const data = (await response.json()) as ScoredAttemptResult;
    return { data, error: null };
  } catch (err) {
    console.error("Backend scoring request failed:", err);
    return {
      data: null,
      error: "We couldn't reach the scoring service. Your submission has been saved — please try again shortly.",
    };
  }
}

const FRIENDLY_ASSESSMENT_ERRORS: Record<string, string> = {
  "23505": "You already have this assessment in progress.",
  "42501": "You don't have permission to do that.",
  "23514": "That value isn't allowed. Please check your input.",
};

/** Maps a raw Supabase/Postgres error to a safe, user-facing message. Never echoes the raw error. */
export function getAssessmentErrorMessage(error: unknown): string {
  const code =
    error && typeof error === "object" && "code" in error ? String((error as { code?: unknown }).code ?? "") : "";
  if (code && FRIENDLY_ASSESSMENT_ERRORS[code]) return FRIENDLY_ASSESSMENT_ERRORS[code];

  const message =
    error && typeof error === "object" && "message" in error
      ? String((error as { message?: unknown }).message ?? "")
      : "";
  const normalized = message.toLowerCase();
  if (normalized.includes("fetch") || normalized.includes("network")) {
    return "Network error. Please check your connection and try again.";
  }

  return "Something went wrong. Please try again.";
}
