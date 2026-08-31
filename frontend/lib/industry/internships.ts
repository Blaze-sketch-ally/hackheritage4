import { api } from "@/lib/api";
import type {
  Internship,
  InternshipCreate,
  InternshipStatus,
  InternshipUpdate,
} from "@/types/internship";

/**
 * Talks to the Industry internship API (backend/app/api/internships.py,
 * /api/v1/internships). The only place the frontend builds these
 * requests — components call these functions, never `api.*` directly.
 * Ownership is never sent: the backend derives `industry_id` from the
 * caller's token (require_industry → current_user.id).
 */

export function getInternships(params?: {
  status?: InternshipStatus | "";
  search?: string;
}): Promise<{ internships: Internship[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/internships${qs ? `?${qs}` : ""}`);
}

export function getInternship(id: string): Promise<Internship> {
  return api.get(`/api/v1/internships/${id}`);
}

/** Creates a DRAFT internship. Publishing is a separate explicit step. */
export function createInternship(data: InternshipCreate): Promise<Internship> {
  return api.post("/api/v1/internships", data);
}

export function updateInternship(id: string, data: InternshipUpdate): Promise<Internship> {
  return api.put(`/api/v1/internships/${id}`, data);
}

export function publishInternship(id: string): Promise<Internship> {
  return api.post(`/api/v1/internships/${id}/publish`);
}

export function closeInternship(id: string): Promise<Internship> {
  return api.post(`/api/v1/internships/${id}/close`);
}

export function archiveInternship(id: string): Promise<Internship> {
  return api.post(`/api/v1/internships/${id}/archive`);
}
