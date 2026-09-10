// Mirrors backend/app/schemas/faculty_recommendation.py. Keep in sync.
//
// A thin, deterministic "what needs my attention" surface -- no LLM call,
// no invented relevance score. Every item here is something the caller
// could already see via the existing question bank / evaluation /
// mentorship pages; this only aggregates and ranks by a real lifecycle
// signal (age, or a documented status).

export interface PendingReviewItem {
  question_id: string;
  assessment_id: string;
  question_text: string;
  created_at: string;
}

export interface PendingEvaluationItem {
  evaluation_id: string;
  attempt_id: string | null;
  assessment_title: string | null;
  status: "ASSIGNED" | "IN_PROGRESS";
  assigned_at: string | null;
}

export interface MentorshipAttentionItem {
  mentorship_id: string;
  student_id: string;
  student_name: string;
  status: "REQUESTED" | "ACCEPTED";
  reason: string;
  updated_at: string;
}

export interface PendingReconciliationItem {
  attempt_id: string;
  assessment_id: string;
  assessment_title: string;
  student_label: string;
  question_id: string;
  question_text: string;
  points: string;
}

export interface FacultyTasks {
  pending_reviews: PendingReviewItem[];
  pending_evaluations: PendingEvaluationItem[];
  mentorship_attention: MentorshipAttentionItem[];
  pending_reconciliations: PendingReconciliationItem[];
}
