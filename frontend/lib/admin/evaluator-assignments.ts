import { api } from "@/lib/api";
import type {
  AttemptForAssignment,
  CreateEvaluatorAssignmentInput,
  EligibleEvaluator,
  EvaluatorAssignment,
} from "@/types/evaluation";

/**
 * Thin, 1:1 wrappers over the ADMIN-only evaluator-assignment endpoints
 * (backend/app/api/admin_evaluator_assignments.py, Phase 2) -- same
 * shape as lib/admin/faculty-permissions.ts. Every call goes through
 * apiFetch (lib/api.ts); require_admin() + create_evaluator_assignment()/
 * revoke_evaluator_assignment() (045_evaluation_foundation.sql) are the
 * real enforcement -- this module holds no privileged credentials.
 */

export function listEligibleEvaluators(): Promise<EligibleEvaluator[]> {
  return api.get("/api/v1/admin/evaluator-assignments/eligible-evaluators");
}

export function listAttemptsForAssignment(assessmentId: string): Promise<AttemptForAssignment[]> {
  return api.get(`/api/v1/admin/evaluator-assignments/attempts?assessment_id=${assessmentId}`);
}

export function createEvaluatorAssignment(input: CreateEvaluatorAssignmentInput): Promise<EvaluatorAssignment> {
  return api.post("/api/v1/admin/evaluator-assignments", input);
}

export function revokeEvaluatorAssignment(assignmentId: string): Promise<EvaluatorAssignment> {
  return api.post(`/api/v1/admin/evaluator-assignments/${assignmentId}/revoke`);
}
