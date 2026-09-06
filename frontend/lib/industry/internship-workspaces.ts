import { api } from "@/lib/api";
import type { CompletionSummary, VerifyCompletionInput } from "@/types/internship-completion";
import type {
  CreateStipendInput,
  StipendSummary,
  UpdateStipendInput,
} from "@/types/internship-stipend";

/**
 * Talks to the Industry Internship Workspace API
 * (backend/app/api/internship_workspaces.py,
 * /api/v1/internship-workspaces). Components call these functions, never
 * `api.*` directly. Ownership is never sent -- the backend derives the
 * industry from the caller's token and RLS (auth.uid() = industry_id)
 * is the real boundary.
 *
 * Phase 7: the completion summary (requirements met / outstanding /
 * verification state / certificate) and the explicit verification action.
 * Phase 8: the stipend summary and its lifecycle (configure / approve /
 * release / cancel) -- RECORD-KEEPING ONLY, no payment gateway. Both are
 * always computed / enforced server-side -- never recomputed here.
 */

function base(workspaceId: string): string {
  return `/api/v1/internship-workspaces/${encodeURIComponent(workspaceId)}`;
}

export function getWorkspaceCompletion(workspaceId: string): Promise<CompletionSummary> {
  return api.get(`${base(workspaceId)}/completion`);
}

/** Explicitly verify that this workspace's REQUIRED assignments are all
 * ACCEPTED. Idempotent: a repeat call returns the SAME completion +
 * certificate. 409 if requirements are outstanding or the workspace is
 * in an invalid state. */
export function verifyWorkspaceCompletion(
  workspaceId: string,
  data: VerifyCompletionInput = {},
): Promise<CompletionSummary> {
  return api.post(`${base(workspaceId)}/completion/verify`, data);
}

// ---- Phase 8: stipend record-keeping. `stipend: null` in the summary
// means none has been configured yet -- a normal response, not an error. ----

export function getWorkspaceStipend(workspaceId: string): Promise<StipendSummary> {
  return api.get(`${base(workspaceId)}/stipend`);
}

/** Configure the ONE stipend record for this workspace -- starts PENDING.
 * 409 if one already exists. */
export function createWorkspaceStipend(
  workspaceId: string,
  data: CreateStipendInput,
): Promise<StipendSummary> {
  return api.post(`${base(workspaceId)}/stipend`, data);
}

/** Edit amount / currency / reference / notes -- only while PENDING. */
export function updateWorkspaceStipend(
  workspaceId: string,
  data: UpdateStipendInput,
): Promise<StipendSummary> {
  return api.put(`${base(workspaceId)}/stipend`, data);
}

/** PENDING -> APPROVED. */
export function approveWorkspaceStipend(workspaceId: string): Promise<StipendSummary> {
  return api.post(`${base(workspaceId)}/stipend/approve`, {});
}

/** APPROVED -> RELEASED. RECORD-KEEPING ONLY: this records that a
 * disbursement happened: it never moves money. */
export function releaseWorkspaceStipend(workspaceId: string): Promise<StipendSummary> {
  return api.post(`${base(workspaceId)}/stipend/release`, {});
}

/** PENDING -> CANCELLED. Terminal. */
export function cancelWorkspaceStipend(workspaceId: string): Promise<StipendSummary> {
  return api.post(`${base(workspaceId)}/stipend/cancel`, {});
}
