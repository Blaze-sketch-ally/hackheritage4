import { api } from "@/lib/api";
import type { Job, JobCreate, JobStatus, JobUpdate } from "@/types/job";

/**
 * Talks to the Industry job API (backend/app/api/jobs.py, /api/v1/jobs).
 * The only place the frontend builds these requests — components call
 * these functions, never `api.*` directly. Ownership is never sent: the
 * backend derives `industry_id` from the caller's token
 * (require_industry → current_user.id).
 */

export function getJobs(params?: {
  status?: JobStatus | "";
  search?: string;
}): Promise<{ jobs: Job[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/jobs${qs ? `?${qs}` : ""}`);
}

export function getJob(id: string): Promise<Job> {
  return api.get(`/api/v1/jobs/${id}`);
}

/** Creates a DRAFT job. Publishing is a separate explicit step. */
export function createJob(data: JobCreate): Promise<Job> {
  return api.post("/api/v1/jobs", data);
}

export function updateJob(id: string, data: JobUpdate): Promise<Job> {
  return api.put(`/api/v1/jobs/${id}`, data);
}

export function publishJob(id: string): Promise<Job> {
  return api.post(`/api/v1/jobs/${id}/publish`);
}

export function closeJob(id: string): Promise<Job> {
  return api.post(`/api/v1/jobs/${id}/close`);
}

export function archiveJob(id: string): Promise<Job> {
  return api.post(`/api/v1/jobs/${id}/archive`);
}
