import { api } from "@/lib/api";
import type {
  AssignmentResponse,
  CompletionResponse,
  CriterionResponse,
  EvaluationResponse,
  FeedbackResponse,
  ModuleResponse,
  ParticipationKind,
  ResourceResponse,
  SkillRecommendationResponse,
  SubmissionResponse,
  WorkspaceResponse,
} from "@/types/participation";

/**
 * Talks to OUR Student Participation API
 * (backend/app/api/student_participation.py, /api/v1/student/participation).
 */

const BASE = "/api/v1/student/participation";

export function listMyWorkspaces(params?: { kind?: ParticipationKind }): Promise<{ workspaces: WorkspaceResponse[] }> {
  const query = new URLSearchParams();
  if (params?.kind) query.set("kind", params.kind);
  const qs = query.toString();
  return api.get(`${BASE}/workspaces${qs ? `?${qs}` : ""}`);
}

export function getWorkspace(workspaceId: string): Promise<WorkspaceResponse> {
  return api.get(`${BASE}/workspaces/${workspaceId}`);
}

export function getModules(workspaceId: string): Promise<{ modules: ModuleResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/modules`);
}

export function getResources(workspaceId: string): Promise<{ resources: ResourceResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/resources`);
}

export function getAssignments(workspaceId: string): Promise<{ assignments: AssignmentResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/assignments`);
}

export function getCriteria(workspaceId: string): Promise<{ criteria: CriterionResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/criteria`);
}

export function getSubmissions(workspaceId: string): Promise<{ submissions: SubmissionResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/submissions`);
}

export function submitWork(
  workspaceId: string,
  data: { assignment_id: string; submission_text?: string | null; submission_url?: string | null },
): Promise<SubmissionResponse> {
  return api.post(`${BASE}/workspaces/${workspaceId}/submissions`, data);
}

export function getFeedback(workspaceId: string): Promise<{ feedback: FeedbackResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/feedback`);
}

export function getRecommendations(workspaceId: string): Promise<{ recommendations: SkillRecommendationResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/recommendations`);
}

export function getEvaluation(workspaceId: string): Promise<EvaluationResponse> {
  return api.get(`${BASE}/workspaces/${workspaceId}/evaluation`);
}

export function getCompletion(workspaceId: string): Promise<CompletionResponse> {
  return api.get(`${BASE}/workspaces/${workspaceId}/completion`);
}

// ---- Submission eligibility ----
//
// IMPORTANT: the backend (participation_submission_service.create_submission,
// and the "Students can submit to their own participation workspace" INSERT
// policy, 064_participation_submissions_feedback.sql) enforces NO eligibility
// rule at all beyond workspace ownership + the assignment being published --
// a student can technically POST a new attempt at any time, regardless of
// any prior submission's status. There is no partial-unique-index or
// trigger here comparable to assessment_attempts' "one IN_PROGRESS attempt"
// guard. The lifecycle below (no-submission / pending-review /
// needs-revision / accepted) is therefore a FRONTEND-ONLY UX policy, not a
// security boundary -- this helper exists so that policy is expressed once,
// correctly, and testably, instead of as an inline (and previously
// inverted) boolean at the call site.

/** Whether the student should be offered a Submit/Resubmit action for an
 * assignment, given its most recent submission (if any):
 *   - no submission yet                        -> true  (first submission)
 *   - submission exists, not yet reviewed       -> false (SUBMITTED/UNDER_REVIEW -- wait for Industry)
 *   - latest review is NEEDS_REVISION           -> true  (the one case that explicitly asks for another attempt)
 *   - latest review is ACCEPTED or REVIEWED     -> false (both are a completed verdict -- REVIEWED is
 *                                                         Industry's neutral "reviewed, nothing further
 *                                                         requested" option, distinct from NEEDS_REVISION;
 *                                                         it does not invite a new attempt any more than
 *                                                         ACCEPTED does) */
export function canSubmitAssignment(latestSubmission: SubmissionResponse | undefined): boolean {
  if (!latestSubmission) return true;
  return latestSubmission.latest_review?.status === "NEEDS_REVISION";
}
