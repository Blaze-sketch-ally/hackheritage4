import { api } from "@/lib/api";
import type {
  ReconciliationCaseDetailResponse,
  ReconciliationCaseListResponse,
} from "@/types/reconciliation";

/**
 * Thin, read-only wrappers over
 * GET /api/v1/faculty/reconciliation/cases[/{attemptId}]. No create/
 * update/delete function exists here: this phase implements no
 * resolution/decision mechanism (see the Faculty Assessment Governance
 * audit report).
 */
export function listReconciliationCases(): Promise<ReconciliationCaseListResponse> {
  return api.get("/api/v1/faculty/reconciliation/cases");
}

export function getReconciliationCase(attemptId: string): Promise<ReconciliationCaseDetailResponse> {
  return api.get(`/api/v1/faculty/reconciliation/cases/${encodeURIComponent(attemptId)}`);
}
