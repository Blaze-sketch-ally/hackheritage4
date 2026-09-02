/**
 * Mirrors backend/app/schemas/question_bank.py exactly -- field-for-field,
 * same nullability. This is the FACULTY-facing view of a question --
 * distinct from types/assessment.ts's AssessmentQuestion (student-facing),
 * which must never gain review_status/created_by/answer_key. Never import
 * anything from this file into a student-facing component.
 */

import type { AssessmentOption, Difficulty, QuestionType, ScoringMethod } from "@/types/assessment";

export type ReviewStatus = "PENDING" | "APPROVED" | "REJECTED";

/** Mirrors `QuestionAnswerKeyInput` -- also reused as the shape embedded
 * in `QuestionBankResponse.answer_key`. */
export interface QuestionAnswerKeyInput {
  correct_option_ids?: string[] | null;
  correct_answer_text?: string | null;
  explanation?: string | null;
}

/** `id` is optional and CLIENT-GENERATED -- an option has no real id
 * until it's inserted, but the answer key must reference option ids in
 * the SAME request that creates them. Generate one with
 * crypto.randomUUID() per option and reuse it as the matching
 * correct_option_ids entry. See backend/app/schemas/question_bank.py's
 * QuestionOptionInput docstring for the full reasoning. */
export interface QuestionOptionInput {
  id?: string;
  option_text: string;
  display_order: number;
}

/** Mirrors `QuestionCreateRequest`. */
export interface QuestionCreateInput {
  assessment_id: string;
  question_text: string;
  question_type: QuestionType;
  scoring_method: ScoringMethod;
  difficulty: Difficulty;
  points: string;
  display_order?: number;
  /** Phase F6.1-F6.3: optional additive metadata -- omitting either is
   * always valid; the database is authoritative for
   * estimated_time_minutes > 0, not duplicated here. */
  learning_objective?: string | null;
  estimated_time_minutes?: number | null;
  options: QuestionOptionInput[];
  answer_key?: QuestionAnswerKeyInput | null;
}

/** Mirrors `QuestionUpdateRequest` -- every field optional, partial
 * update. options/answer_key, when present, REPLACE the question's
 * entire current set -- omit them to leave options/the answer key
 * untouched. Pass `answer_key: null` explicitly to clear it. */
export interface QuestionUpdateInput {
  question_text?: string;
  question_type?: QuestionType;
  scoring_method?: ScoringMethod;
  difficulty?: Difficulty;
  points?: string;
  display_order?: number;
  /** Phase F6.1-F6.3: same optional additive metadata as
   * QuestionCreateInput. Omitting either leaves it unchanged; sending
   * `null` explicitly clears it (exclude_unset at the backend route
   * layer is what makes that distinction, not a sentinel here). */
  learning_objective?: string | null;
  estimated_time_minutes?: number | null;
  is_active?: boolean;
  /** Only "PENDING" is accepted (a resubmission after rejection) -- the
   * backend rejects anything else with a 422. Approve/reject a question
   * via the dedicated approveQuestion/rejectQuestion calls, never here. */
  review_status?: "PENDING";
  options?: QuestionOptionInput[];
  answer_key?: QuestionAnswerKeyInput | null;
}

/** Mirrors `QuestionBankResponse` -- the FACULTY-facing view. Never render
 * this on a student-facing page. */
export interface QuestionBank {
  id: string;
  assessment_id: string;
  question_text: string;
  question_type: QuestionType;
  scoring_method: ScoringMethod;
  difficulty: Difficulty;
  points: string;
  display_order: number;
  /** Phase F6.1-F6.3: assessment_questions.learning_objective/
   * estimated_time_minutes (043_question_authoring_metadata.sql) --
   * always present on the response, nullable. */
  learning_objective: string | null;
  estimated_time_minutes: number | null;
  review_status: ReviewStatus;
  is_active: boolean;
  created_by: string | null;
  /** Phase F7.1-F7.2: the CURRENT review decision's reviewer and optional
   * note (assessment_questions.reviewed_by/review_note,
   * 044_question_review_governance.sql). Latest-review-state, not a
   * history list -- both are always null for a never-reviewed or
   * just-resubmitted (PENDING) question, and both become permanently
   * fixed once APPROVED. */
  reviewed_by: string | null;
  review_note: string | null;
  created_at: string;
  updated_at: string;
  options: AssessmentOption[];
  answer_key: QuestionAnswerKeyInput | null;
}

/** Mirrors `BlueprintRuleRequest`. */
export interface BlueprintRuleInput {
  difficulty: Difficulty;
  question_count: number;
}

/** Mirrors `BlueprintRuleResponse`. */
export interface BlueprintRule {
  id: string;
  assessment_id: string;
  difficulty: Difficulty;
  question_count: number;
  created_at: string;
  updated_at: string;
}

/** Mirrors `BlueprintResponse`. */
export interface Blueprint {
  assessment_id: string;
  rules: BlueprintRule[];
}
