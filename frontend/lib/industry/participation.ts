import { api } from "@/lib/api";
import type {
  AssignmentResponse,
  CompletionResponse,
  CriterionResponse,
  EvaluationResponse,
  FeedbackResponse,
  FeedbackType,
  ModuleResponse,
  ParticipationKind,
  ProgramResponse,
  RecommendationPriority,
  RecommendedLevel,
  ResourceResponse,
  ResourceType,
  ReviewStatus,
  SkillRecommendationResponse,
  SubmissionResponse,
  WorkspaceResponse,
  WorkspaceStatus,
} from "@/types/participation";

/**
 * Talks to OUR Industry Participation API
 * (backend/app/api/participation.py, /api/v1/participation). One client
 * module for PROJECT/TRAINING/WORKSHOP, never three.
 */

const BASE = "/api/v1/participation";

// ---- programs ----

export function getProgramForOpportunity(kind: ParticipationKind, opportunityId: string): Promise<ProgramResponse> {
  return api.get(`${BASE}/programs/by-opportunity?kind=${kind}&opportunity_id=${encodeURIComponent(opportunityId)}`);
}

export function createProgram(data: {
  kind: ParticipationKind;
  project_id?: string;
  training_id?: string;
  workshop_id?: string;
  title: string;
  description?: string | null;
}): Promise<ProgramResponse> {
  return api.post(`${BASE}/programs`, data);
}

export function getProgram(programId: string): Promise<ProgramResponse> {
  return api.get(`${BASE}/programs/${programId}`);
}

export function updateProgram(programId: string, data: { title?: string; description?: string | null }): Promise<ProgramResponse> {
  return api.put(`${BASE}/programs/${programId}`, data);
}

export function publishProgram(programId: string): Promise<ProgramResponse> {
  return api.post(`${BASE}/programs/${programId}/publish`);
}

export function archiveProgram(programId: string): Promise<ProgramResponse> {
  return api.post(`${BASE}/programs/${programId}/archive`);
}

// ---- modules ----

export function getModules(programId: string): Promise<{ modules: ModuleResponse[] }> {
  return api.get(`${BASE}/programs/${programId}/modules`);
}

export function createModule(programId: string, data: { title: string; description?: string | null; sequence_order?: number }): Promise<ModuleResponse> {
  return api.post(`${BASE}/programs/${programId}/modules`, data);
}

export function updateModule(programId: string, moduleId: string, data: Partial<{ title: string; description: string | null; sequence_order: number }>): Promise<ModuleResponse> {
  return api.put(`${BASE}/programs/${programId}/modules/${moduleId}`, data);
}

export function publishModule(programId: string, moduleId: string): Promise<ModuleResponse> {
  return api.post(`${BASE}/programs/${programId}/modules/${moduleId}/publish`);
}

export function unpublishModule(programId: string, moduleId: string): Promise<ModuleResponse> {
  return api.post(`${BASE}/programs/${programId}/modules/${moduleId}/unpublish`);
}

// ---- resources ----

export function getResources(programId: string): Promise<{ resources: ResourceResponse[] }> {
  return api.get(`${BASE}/programs/${programId}/resources`);
}

export function createResource(
  programId: string,
  data: { module_id?: string | null; title: string; description?: string | null; resource_type: ResourceType; resource_url?: string | null; sequence_order?: number },
): Promise<ResourceResponse> {
  return api.post(`${BASE}/programs/${programId}/resources`, data);
}

export function publishResource(programId: string, resourceId: string): Promise<ResourceResponse> {
  return api.post(`${BASE}/programs/${programId}/resources/${resourceId}/publish`);
}

export function unpublishResource(programId: string, resourceId: string): Promise<ResourceResponse> {
  return api.post(`${BASE}/programs/${programId}/resources/${resourceId}/unpublish`);
}

// ---- assignments ----

export function getAssignments(programId: string): Promise<{ assignments: AssignmentResponse[] }> {
  return api.get(`${BASE}/programs/${programId}/assignments`);
}

export function createAssignment(
  programId: string,
  data: {
    module_id?: string | null;
    title: string;
    description?: string | null;
    instructions?: string | null;
    due_at?: string | null;
    max_score?: number | null;
    is_required?: boolean;
  },
): Promise<AssignmentResponse> {
  return api.post(`${BASE}/programs/${programId}/assignments`, data);
}

export function publishAssignment(programId: string, assignmentId: string): Promise<AssignmentResponse> {
  return api.post(`${BASE}/programs/${programId}/assignments/${assignmentId}/publish`);
}

export function unpublishAssignment(programId: string, assignmentId: string): Promise<AssignmentResponse> {
  return api.post(`${BASE}/programs/${programId}/assignments/${assignmentId}/unpublish`);
}

// ---- evaluation criteria ----

export function getCriteria(programId: string): Promise<{ criteria: CriterionResponse[] }> {
  return api.get(`${BASE}/programs/${programId}/criteria`);
}

export function createCriterion(
  programId: string,
  data: { name: string; description?: string | null; max_score: number; weight: number; sequence_order?: number },
): Promise<CriterionResponse> {
  return api.post(`${BASE}/programs/${programId}/criteria`, data);
}

export function deleteCriterion(programId: string, criterionId: string): Promise<void> {
  return api.delete(`${BASE}/programs/${programId}/criteria/${criterionId}`);
}

// ---- workspaces ----

export function ensureWorkspace(data: {
  kind: ParticipationKind;
  project_application_id?: string;
  training_application_id?: string;
  workshop_application_id?: string;
}): Promise<WorkspaceResponse> {
  return api.post(`${BASE}/workspaces/ensure`, data);
}

export function listWorkspaces(params?: { kind?: ParticipationKind; status?: WorkspaceStatus }): Promise<{ workspaces: WorkspaceResponse[] }> {
  const query = new URLSearchParams();
  if (params?.kind) query.set("kind", params.kind);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return api.get(`${BASE}/workspaces${qs ? `?${qs}` : ""}`);
}

export function getWorkspace(workspaceId: string): Promise<WorkspaceResponse> {
  return api.get(`${BASE}/workspaces/${workspaceId}`);
}

// ---- submissions / reviews ----

export function getSubmissions(workspaceId: string): Promise<{ submissions: SubmissionResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/submissions`);
}

export function createReview(
  submissionId: string,
  data: { score?: number | null; feedback?: string | null; status: ReviewStatus },
) {
  return api.post(`${BASE}/submissions/${submissionId}/reviews`, data);
}

// ---- feedback ----

export function getFeedback(workspaceId: string): Promise<{ feedback: FeedbackResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/feedback`);
}

export function createFeedback(workspaceId: string, data: { feedback_type: FeedbackType; title?: string | null; feedback: string }): Promise<FeedbackResponse> {
  return api.post(`${BASE}/workspaces/${workspaceId}/feedback`, data);
}

// ---- skill recommendations ----

export function getRecommendations(workspaceId: string): Promise<{ recommendations: SkillRecommendationResponse[] }> {
  return api.get(`${BASE}/workspaces/${workspaceId}/recommendations`);
}

export function createRecommendation(
  workspaceId: string,
  data: { skill_id: string; recommended_level?: RecommendedLevel | null; reason: string; priority?: RecommendationPriority },
): Promise<SkillRecommendationResponse> {
  return api.post(`${BASE}/workspaces/${workspaceId}/recommendations`, data);
}

// ---- evaluation ----

export function getEvaluation(workspaceId: string): Promise<EvaluationResponse> {
  return api.get(`${BASE}/workspaces/${workspaceId}/evaluation`);
}

export function saveEvaluation(
  workspaceId: string,
  data: { overall_feedback?: string | null; scores: { criterion_id: string; score: number; feedback?: string | null }[] },
): Promise<EvaluationResponse> {
  return api.put(`${BASE}/workspaces/${workspaceId}/evaluation`, data);
}

export function finalizeEvaluation(workspaceId: string): Promise<EvaluationResponse> {
  return api.post(`${BASE}/workspaces/${workspaceId}/evaluation/finalize`);
}

// ---- completion ----

export function getCompletion(workspaceId: string): Promise<CompletionResponse> {
  return api.get(`${BASE}/workspaces/${workspaceId}/completion`);
}

export function completeWorkspace(workspaceId: string): Promise<CompletionResponse> {
  return api.post(`${BASE}/workspaces/${workspaceId}/complete`);
}
