import { api } from "@/lib/api";
import type {
  IndustryWorkshop,
  WorkshopCreate,
  WorkshopStatus,
  WorkshopUpdate,
} from "@/types/industry-workshop";

/**
 * Talks to the Industry workshop API (backend/app/api/industry_workshops.py,
 * /api/v1/workshops). The only place the frontend builds these requests —
 * components call these functions, never `api.*` directly. Ownership is
 * never sent: the backend derives `industry_id` from the caller's token
 * (require_industry → current_user.id).
 */

export function getWorkshops(params?: {
  status?: WorkshopStatus | "";
  search?: string;
}): Promise<{ workshops: IndustryWorkshop[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/workshops${qs ? `?${qs}` : ""}`);
}

export function getWorkshop(id: string): Promise<IndustryWorkshop> {
  return api.get(`/api/v1/workshops/${id}`);
}

/** Creates a DRAFT workshop. Publishing is a separate explicit step. */
export function createWorkshop(data: WorkshopCreate): Promise<IndustryWorkshop> {
  return api.post("/api/v1/workshops", data);
}

export function updateWorkshop(id: string, data: WorkshopUpdate): Promise<IndustryWorkshop> {
  return api.put(`/api/v1/workshops/${id}`, data);
}

export function publishWorkshop(id: string): Promise<IndustryWorkshop> {
  return api.post(`/api/v1/workshops/${id}/publish`);
}

export function closeWorkshop(id: string): Promise<IndustryWorkshop> {
  return api.post(`/api/v1/workshops/${id}/close`);
}

export function archiveWorkshop(id: string): Promise<IndustryWorkshop> {
  return api.post(`/api/v1/workshops/${id}/archive`);
}
