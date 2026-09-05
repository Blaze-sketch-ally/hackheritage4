import { api } from "@/lib/api";
import type {
  EvaluationDetail,
  EvaluationStatus,
  EvaluationStatusTarget,
  EvaluationSummary,
  Rubric,
  SaveEvaluationInput,
} from "@/types/evaluation";

/**
 * Thin, 1:1 wrappers over the Faculty-facing evaluator workflow
 * endpoints (backend/app/api/faculty_evaluations.py, Phase F8.3/Phase 2)
 * -- same shape as lib/faculty/question-bank.ts. Every call goes through
 * apiFetch (lib/api.ts), which attaches the caller's own Supabase
 * session; require_assessment_evaluator() + RLS (046/047/051) are the
 * real enforcement -- this module holds no privileged credentials and
 * makes no authorization decisions of its own.
 */

export function listMyEvaluations(statusFilter?: EvaluationStatus): Promise<EvaluationSummary[]> {
  const query = statusFilter ? `?status_filter=${statusFilter}` : "";
  return api.get(`/api/v1/faculty/evaluations${query}`);
}

export function getEvaluation(evaluationId: string): Promise<EvaluationDetail> {
  return api.get(`/api/v1/faculty/evaluations/${evaluationId}`);
}

export function listCandidateRubrics(evaluationId: string): Promise<Rubric[]> {
  return api.get(`/api/v1/faculty/evaluations/${evaluationId}/rubrics`);
}

export function saveEvaluation(evaluationId: string, input: SaveEvaluationInput): Promise<EvaluationSummary> {
  return api.patch(`/api/v1/faculty/evaluations/${evaluationId}`, input);
}

export function updateEvaluationStatus(
  evaluationId: string,
  status: EvaluationStatusTarget,
): Promise<EvaluationSummary> {
  return api.patch(`/api/v1/faculty/evaluations/${evaluationId}/status`, { status });
}
