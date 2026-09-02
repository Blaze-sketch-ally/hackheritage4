import { api } from "@/lib/api";
import type { Assessment } from "@/types/assessment";
import type {
  Blueprint,
  BlueprintRuleInput,
  QuestionBank,
  QuestionCreateInput,
  QuestionUpdateInput,
} from "@/types/question-bank";

/**
 * Thin, 1:1 wrappers over the Phase 1K question-bank/review/blueprint
 * FastAPI endpoints -- same shape as lib/student/assessment.ts. Every
 * function here goes through apiFetch (lib/api.ts), which attaches the
 * caller's own Supabase session as a Bearer token; RLS + require_faculty
 * are the real enforcement, this module holds no privileged credentials.
 */

export function listAssessmentsForFaculty(): Promise<{ assessments: Assessment[] }> {
  return api.get("/api/v1/assessments");
}

export function listMyQuestions(assessmentId?: string): Promise<QuestionBank[]> {
  const query = assessmentId ? `?assessment_id=${assessmentId}` : "";
  return api.get(`/api/v1/questions${query}`);
}

export function getQuestion(questionId: string): Promise<QuestionBank> {
  return api.get(`/api/v1/questions/${questionId}`);
}

export function createQuestion(input: QuestionCreateInput): Promise<QuestionBank> {
  return api.post("/api/v1/questions", input);
}

export function updateQuestion(questionId: string, input: QuestionUpdateInput): Promise<QuestionBank> {
  return api.patch(`/api/v1/questions/${questionId}`, input);
}

/** note is optional (Phase F7.2) -- omitting it, or passing an empty/
 * whitespace-only string, sends no body at all, byte-for-byte identical
 * to how this call worked before F7.3 (the backend already treats "no
 * body" and "{}" the same way). Never sends a reviewer identity of any
 * kind -- reviewed_by is exclusively server-derived from auth.uid()
 * inside review_question(). */
export function approveQuestion(questionId: string, note?: string | null): Promise<QuestionBank> {
  const trimmed = note?.trim();
  return api.post(`/api/v1/questions/${questionId}/approve`, trimmed ? { note: trimmed } : undefined);
}

export function rejectQuestion(questionId: string, note?: string | null): Promise<QuestionBank> {
  const trimmed = note?.trim();
  return api.post(`/api/v1/questions/${questionId}/reject`, trimmed ? { note: trimmed } : undefined);
}

export function getBlueprint(assessmentId: string): Promise<Blueprint> {
  return api.get(`/api/v1/assessments/${assessmentId}/blueprint`);
}

export function replaceBlueprint(assessmentId: string, rules: BlueprintRuleInput[]): Promise<Blueprint> {
  return api.put(`/api/v1/assessments/${assessmentId}/blueprint`, { rules });
}
