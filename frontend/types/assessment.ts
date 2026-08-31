/**
 * Mirrors backend/app/schemas/assessment.py exactly -- field-for-field,
 * same nullability. Do not add fields that don't exist on the backend
 * response models (no correct_option_ids/correct_answer_text/explanation
 * anywhere except AssessmentAnswerKey, which only ever appears inside an
 * AssessmentResult -- i.e. only after the attempt is COMPLETED).
 *
 * IMPORTANT: score/total_marks/percentage/points/awarded_marks are all
 * Pydantic Decimal fields, which this API serializes as JSON STRINGS
 * (verified against real responses, e.g. "score":"40.0"), not numbers.
 * Typed as `string` here on purpose -- never parse these into a JS number
 * to do arithmetic client-side; only the backend computes these values.
 */

export type Difficulty = "Beginner" | "Intermediate" | "Advanced" | "Expert";

export type QuestionType = "MCQ" | "MULTIPLE_SELECT" | "SHORT_ANSWER" | "CODE" | "SUBJECTIVE";

export type ScoringMethod = "OBJECTIVE" | "AI_EVALUATED";

export type AttemptStatus = "IN_PROGRESS" | "COMPLETED" | "ABANDONED";

/** Mirrors `AssessmentResponse` / the `assessments` table. */
export interface Assessment {
  id: string;
  skill_id: string;
  title: string;
  description: string | null;
  difficulty: Difficulty;
  duration_minutes: number | null;
  question_count: number | null;
  /** Decimal serialized as a string, e.g. "70.00" -- never parse this into
   * a JS number to make a pass/fail decision client-side; the backend
   * already returns `passed` wherever that decision matters. */
  passing_percentage: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Mirrors `AssessmentOptionResponse`. Never carries a correctness flag --
 * that column does not exist on assessment_question_options at all. */
export interface AssessmentOption {
  id: string;
  question_id: string;
  option_text: string;
  display_order: number;
}

/** Mirrors `AssessmentQuestionResponse`, options embedded. */
export interface AssessmentQuestion {
  id: string;
  assessment_id: string;
  question_text: string;
  question_type: QuestionType;
  scoring_method: ScoringMethod;
  difficulty: Difficulty;
  points: string;
  display_order: number;
  options: AssessmentOption[];
}

/** Mirrors `AssessmentAttemptResponse`. Represents both an IN_PROGRESS and
 * a COMPLETED attempt -- score/total_marks/percentage/submitted_at are
 * null until scoring has actually happened. */
export interface AssessmentAttempt {
  id: string;
  student_id: string;
  assessment_id: string;
  status: AttemptStatus;
  started_at: string;
  submitted_at: string | null;
  score: string | null;
  total_marks: string | null;
  percentage: string | null;
  created_at: string;
  updated_at: string;
}

/** Mirrors `AssessmentAnswerResponse`. `awarded_marks`/`is_correct` stay
 * null until the attempt is scored -- never derive correctness from
 * anything else client-side. */
export interface AssessmentAnswer {
  id: string;
  attempt_id: string;
  question_id: string;
  answer_text: string | null;
  selected_option_ids: string[] | null;
  awarded_marks: string | null;
  is_correct: boolean | null;
  created_at: string;
  updated_at: string;
}

/** Mirrors `SubmitAttemptResponse` -- despite the name, this is the
 * response shape of `POST /attempts/{id}/score`, not `/submit` (`/submit`
 * itself returns a plain AssessmentAttempt). Score fields are required
 * here, matching the one moment they're guaranteed non-null. */
export interface ScoredAttempt {
  id: string;
  student_id: string;
  assessment_id: string;
  status: AttemptStatus;
  started_at: string;
  submitted_at: string;
  score: string;
  total_marks: string;
  percentage: string;
  /** Server-computed: percentage >= the assessment's own passing_percentage.
   * Never derive this client-side from the two raw values above. */
  passed: boolean;
  /** Server-computed: the CURRENT is_verified state of the matching
   * (skill_id, proficiency_level) student_skills row, read back after
   * scoring. False whenever no such row exists (the student never
   * declared this exact skill at this exact level) -- never implies one
   * was created. */
  skill_verified: boolean;
}

/** Mirrors `AssessmentAnswerKeyResponse`. Only ever appears inside an
 * AssessmentResult -- the backend itself refuses to return this for
 * anything but the student's own COMPLETED attempt. */
export interface AssessmentAnswerKey {
  question_id: string;
  correct_option_ids: string[] | null;
  correct_answer_text: string | null;
  explanation: string | null;
}

/** Mirrors `AssessmentResultQuestionResponse`. `student_answer` being
 * null-ish here (or shaped like the unanswered placeholder --
 * answer_text: null, selected_option_ids: []) means the question was
 * never answered; see isUnansweredResult() in lib/student/assessment.ts
 * rather than re-deriving this check inline. */
export interface AssessmentResultQuestion {
  question: AssessmentQuestion;
  student_answer: AssessmentAnswer | null;
  answer_key: AssessmentAnswerKey;
}

/** Mirrors `AssessmentResultResponse`. POST-COMPLETION ONLY -- the
 * backend itself never constructs this for a non-COMPLETED attempt. */
export interface AssessmentResult {
  attempt: AssessmentAttempt;
  /** Same server-computed meaning as ScoredAttempt.passed/skill_verified --
   * read back here so revisiting a result later (or the history list)
   * shows the same authoritative outcome every time. */
  passed: boolean;
  skill_verified: boolean;
  questions: AssessmentResultQuestion[];
}

/** Mirrors `AttemptHistoryItemResponse`. assessment/passed/skill_verified
 * are all null together only when the attempt's assessment has since been
 * deactivated -- the attempt itself is still real historical data. */
export interface AttemptHistoryItem {
  id: string;
  status: AttemptStatus;
  started_at: string;
  submitted_at: string | null;
  score: string | null;
  total_marks: string | null;
  percentage: string | null;
  passed: boolean | null;
  skill_verified: boolean | null;
  assessment: Assessment | null;
}
