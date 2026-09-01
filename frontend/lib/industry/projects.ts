import { api } from "@/lib/api";
import type {
  IndustryProject,
  ProjectCreate,
  ProjectStatus,
  ProjectUpdate,
} from "@/types/industry-project";

/**
 * Talks to the Industry project API (backend/app/api/industry_projects.py,
 * /api/v1/projects). The only place the frontend builds these requests —
 * components call these functions, never `api.*` directly. Ownership is
 * never sent: the backend derives `industry_id` from the caller's token
 * (require_industry → current_user.id).
 */

export function getProjects(params?: {
  status?: ProjectStatus | "";
  search?: string;
}): Promise<{ projects: IndustryProject[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/projects${qs ? `?${qs}` : ""}`);
}

export function getProject(id: string): Promise<IndustryProject> {
  return api.get(`/api/v1/projects/${id}`);
}

/** Creates a DRAFT project. Publishing is a separate explicit step. */
export function createProject(data: ProjectCreate): Promise<IndustryProject> {
  return api.post("/api/v1/projects", data);
}

export function updateProject(id: string, data: ProjectUpdate): Promise<IndustryProject> {
  return api.put(`/api/v1/projects/${id}`, data);
}

export function publishProject(id: string): Promise<IndustryProject> {
  return api.post(`/api/v1/projects/${id}/publish`);
}

export function closeProject(id: string): Promise<IndustryProject> {
  return api.post(`/api/v1/projects/${id}/close`);
}

export function archiveProject(id: string): Promise<IndustryProject> {
  return api.post(`/api/v1/projects/${id}/archive`);
}
