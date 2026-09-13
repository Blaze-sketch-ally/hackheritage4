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
