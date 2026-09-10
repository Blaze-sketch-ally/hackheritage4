// Mirrors backend/app/schemas/reconciliation.py. Keep in sync.
//
// READ-ONLY (Faculty Assessment Governance audit): there is no
// resolution/decision mechanism in this phase -- see the audit report.
// This type surface exists purely so a Faculty member holding
// assessment_moderator can see which attempts are currently
// NEEDS_RECONCILIATION and compare the conflicting FINALIZED evaluator
// marks behind each one.

export interface ReconciliationCaseSummary {
  attempt_id: string;
  assessment_id: string;
  assessment_title: string;
  student_label: string;
  question_id: string;
  question_text: string;
  points: string;
}

export interface ReconciliationCaseListResponse {
  cases: ReconciliationCaseSummary[];
}

export interface ReconciliationEvaluatorMark {
  question_id: string;
  question_text: string;
  points: string;
  evaluator_id: string;
  awarded_marks: string;
  feedback: string | null;
  rubric_id: string;
  rubric_name: string;
  finalized_at: string | null;
}

export interface ReconciliationCaseDetailResponse {
  attempt_id: string;
  marks: ReconciliationEvaluatorMark[];
}
