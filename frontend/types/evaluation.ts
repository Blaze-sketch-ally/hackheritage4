/**
 * Mirrors backend/app/schemas/evaluation.py exactly -- field-for-field,
 * same nullability. IMPORTANT: awarded_marks/max_marks/points are
 * Pydantic Decimal fields, serialized as JSON STRINGS (matching
 * types/assessment.ts's own documented convention) -- never parse these
 * into a JS number to do arithmetic client-side; only the backend
 * computes/validates these values.
 */

import type { AssessmentAnswer, AssessmentQuestion } from "@/types/assessment";

export type EvaluationStatus = "ASSIGNED" | "IN_PROGRESS" | "SUBMITTED" | "FINALIZED";

/** Mirrors `RubricCriterionResponse`. */
export interface RubricCriterion {
  id: string;
  rubric_id: string;
  criterion: string;
  description: string | null;
  max_marks: string;
  display_order: number;
}

/** Mirrors `RubricResponse`. */
export interface Rubric {
  id: string;
  question_id: string;
  name: string;
  description: string | null;
  max_marks: string;
  status: "ACTIVE" | "ARCHIVED";
  criteria: RubricCriterion[];
}

/** Mirrors `EvaluationSummaryResponse` -- GET /faculty/evaluations. */
export interface EvaluationSummary {
  evaluation_id: string;
  assignment_id: string;
  status: EvaluationStatus;
  awarded_marks: string | null;
  attempt_id: string;
  question_id: string;
  student_id: string;
  assessment_title: string;
  assigned_at: string;
}

/** Mirrors `EvaluationDetailResponse` -- GET /faculty/evaluations/{id}.
 * question is the student-facing shape (no answer key, ever). */
export interface EvaluationDetail {
  evaluation_id: string;
  assignment_id: string;
  status: EvaluationStatus;
  awarded_marks: string | null;
  feedback: string | null;
  rubric_id: string | null;
  submitted_at: string | null;
  finalized_at: string | null;
  finalized_by: string | null;
  attempt_id: string;
  question_id: string;
  student_id: string;
  assessment_title: string;
  assigned_at: string;
  question: AssessmentQuestion;
  student_answer: AssessmentAnswer | null;
  rubric: Rubric | null;
}

/** Mirrors `SaveEvaluationRequest`. Every field optional -- only send
 * what actually changed (matches the backend's own exclude_unset
 * handling). */
export interface SaveEvaluationInput {
  rubric_id?: string | null;
  awarded_marks?: string | null;
  feedback?: string | null;
}

/** Mirrors `UpdateEvaluationStatusRequest` -- ASSIGNED is deliberately
 * excluded, matching the backend schema's own Literal. */
export type EvaluationStatusTarget = "IN_PROGRESS" | "SUBMITTED" | "FINALIZED";

// ============================================================
// Phase 2 -- ADMIN-facing evaluator assignment management.
// Mirrors the ADMIN-only section of backend/app/schemas/evaluation.py.
// Never import these into a Faculty-facing (non-admin) component.
// ============================================================

/** Mirrors `EligibleEvaluatorResponse`. */
export interface EligibleEvaluator {
  faculty_id: string;
  email: string;
  full_name: string | null;
}

/** Mirrors `ExistingAssignmentResponse`. */
export interface ExistingAssignment {
  assignment_id: string;
  evaluator_id: string;
  evaluator_email: string;
  evaluator_full_name: string | null;
  assignment_status: "ACTIVE" | "REVOKED";
  evaluation_status: EvaluationStatus;
}

/** Mirrors `AttemptQuestionForAssignmentResponse`. */
export interface AttemptQuestionForAssignment {
  question_id: string;
  question_text: string;
  points: string;
  existing_assignments: ExistingAssignment[];
}

/** Mirrors `AttemptForAssignmentResponse`. student_label is a
 * privacy-safe, truncated identifier -- never a name/email. */
export interface AttemptForAssignment {
  attempt_id: string;
  student_label: string;
  status: string;
  questions: AttemptQuestionForAssignment[];
}

/** Mirrors `CreateEvaluatorAssignmentRequest`. */
export interface CreateEvaluatorAssignmentInput {
  evaluator_id: string;
  attempt_id: string;
  question_id: string;
}

/** Mirrors `EvaluatorAssignmentResponse`. */
export interface EvaluatorAssignment {
  assignment_id: string;
  evaluator_id: string;
  attempt_id: string;
  question_id: string;
  status: "ACTIVE" | "REVOKED";
  created_at: string;
  revoked_at: string | null;
}
