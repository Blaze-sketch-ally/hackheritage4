import { api } from "@/lib/api";
import type { CompletionSummary } from "@/types/internship-completion";
import type { StipendSummary } from "@/types/internship-stipend";
import type {
  CreateSubmissionInput,
  InternshipWorkspaceDetail,
  InternshipWorkspaceSummary,
  WorkspaceAssignmentDetail,
  WorkspaceAssignmentList,
} from "@/types/internship-workspace";

/**
 * Talks to OUR student Internship Workspace API
 * (backend/app/api/student_internship_workspaces.py,
 * /api/v1/student/internship-workspaces). Components call these functions,
 * never `api.*` directly.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * student's own Supabase access token. No `student_id` / `workspace`
 * ownership is ever sent -- the backend derives identity from the token
 * (require_student -> current_user.id) and RLS + the workspace DB triggers
 * are the real access-control boundary.
 *
 * The industry-only provisioning / heal endpoint is deliberately NOT
 * wrapped here -- students never provision a workspace.
 */

export function listMyInternshipWorkspaces(): Promise<{
  workspaces: InternshipWorkspaceSummary[];
}> {
  return api.get("/api/v1/student/internship-workspaces");
}

export function getMyInternshipWorkspace(
  workspaceId: string,
): Promise<InternshipWorkspaceDetail> {
  return api.get(
    `/api/v1/student/internship-workspaces/${encodeURIComponent(workspaceId)}`,
  );
}

/** PENDING_ACCEPTANCE -> ACCEPTED. 409 if the workspace is no longer
 * pending. Returns the updated detail. */
export function acceptMyInternshipWorkspace(
  workspaceId: string,
): Promise<InternshipWorkspaceDetail> {
  return api.post(
    `/api/v1/student/internship-workspaces/${encodeURIComponent(workspaceId)}/accept`,
    {},
  );
}

/** PENDING_ACCEPTANCE -> DECLINED. 409 if the workspace is no longer
 * pending. Returns the updated detail. */
export function declineMyInternshipWorkspace(
  workspaceId: string,
  reason?: string,
): Promise<InternshipWorkspaceDetail> {
  return api.post(
    `/api/v1/student/internship-workspaces/${encodeURIComponent(workspaceId)}/decline`,
    { reason: reason?.trim() ? reason.trim() : null },
  );
}

/** Replace-set the student's OPTIONAL training-skill selections. An empty
 * array clears them. REQUIRED skills are always in scope and cannot be
 * sent. Returns the updated detail (incl. `selected_skill_ids`). */
export function setMyInternshipWorkspaceSkills(
  workspaceId: string,
  skillIds: string[],
): Promise<InternshipWorkspaceDetail> {
  return api.put(
    `/api/v1/student/internship-workspaces/${encodeURIComponent(workspaceId)}/skills`,
    { skill_ids: skillIds },
  );
}

// ---- Phase 5: the workspace's published assignments + the student's own
// append-only submissions. A resubmission is always a NEW attempt -- the
// previous one is never modified (enforced by the DB triggers in 039). ----

function wsBase(workspaceId: string): string {
  return `/api/v1/student/internship-workspaces/${encodeURIComponent(workspaceId)}`;
}

export function listMyWorkspaceAssignments(
  workspaceId: string,
): Promise<WorkspaceAssignmentList> {
  return api.get(`${wsBase(workspaceId)}/assignments`);
}

export function getMyWorkspaceAssignment(
  workspaceId: string,
  assignmentId: string,
): Promise<WorkspaceAssignmentDetail> {
  return api.get(
    `${wsBase(workspaceId)}/assignments/${encodeURIComponent(assignmentId)}`,
  );
}

/** Create the next append-only attempt. `attempt_number` and
 * `submission_status` are always server-set. 409 if the workspace is no
 * longer active or the previous attempt has not been sent back. */
export function submitMyWorkspaceAssignment(
  workspaceId: string,
  assignmentId: string,
  data: CreateSubmissionInput,
): Promise<WorkspaceAssignmentDetail> {
  return api.post(
    `${wsBase(workspaceId)}/assignments/${encodeURIComponent(assignmentId)}/submissions`,
    data,
  );
}

// ---- Phase 7: read-only completion + certificate summary. Students never
// verify their own completion. ----

export function getMyWorkspaceCompletion(workspaceId: string): Promise<CompletionSummary> {
  return api.get(`${wsBase(workspaceId)}/completion`);
}

// ---- Phase 8: read-only stipend summary. Students never create / edit /
// approve / release / cancel a stipend record. ----

export function getMyWorkspaceStipend(workspaceId: string): Promise<StipendSummary> {
  return api.get(`${wsBase(workspaceId)}/stipend`);
}
