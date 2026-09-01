import { api } from "@/lib/api";
import type {
  IndustryTraining,
  TrainingCreate,
  TrainingStatus,
  TrainingUpdate,
} from "@/types/industry-training";

/**
 * Talks to the Industry training API (backend/app/api/industry_trainings.py,
 * /api/v1/trainings). The only place the frontend builds these requests —
 * components call these functions, never `api.*` directly. Ownership is
 * never sent: the backend derives `industry_id` from the caller's token
 * (require_industry → current_user.id).
 */

export function getTrainings(params?: {
  status?: TrainingStatus | "";
  search?: string;
}): Promise<{ trainings: IndustryTraining[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/trainings${qs ? `?${qs}` : ""}`);
}

export function getTraining(id: string): Promise<IndustryTraining> {
  return api.get(`/api/v1/trainings/${id}`);
}

/** Creates a DRAFT training record. Publishing is a separate explicit step. */
export function createTraining(data: TrainingCreate): Promise<IndustryTraining> {
  return api.post("/api/v1/trainings", data);
}

export function updateTraining(id: string, data: TrainingUpdate): Promise<IndustryTraining> {
  return api.put(`/api/v1/trainings/${id}`, data);
}

export function publishTraining(id: string): Promise<IndustryTraining> {
  return api.post(`/api/v1/trainings/${id}/publish`);
}

export function closeTraining(id: string): Promise<IndustryTraining> {
  return api.post(`/api/v1/trainings/${id}/close`);
}

export function archiveTraining(id: string): Promise<IndustryTraining> {
  return api.post(`/api/v1/trainings/${id}/archive`);
}
