import { api } from "@/lib/api";
import type { StudentWorkshop, StudentWorkshopListResponse } from "@/types/student-workshop";
import type { WorkshopApplication, WorkshopApplicationListResponse } from "@/types/workshop-application";

/**
 * Talks to OUR Student Workshop API
 * (backend/app/api/student_workshops.py, /api/v1/student/workshops).
 * The only place the frontend builds these requests -- components call
 * these functions, never `api.*` directly.
 */

export function listWorkshops(params?: { search?: string }): Promise<StudentWorkshopListResponse> {
  const query = new URLSearchParams();
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/student/workshops${qs ? `?${qs}` : ""}`);
}

export function getWorkshop(id: string): Promise<StudentWorkshop> {
  return api.get(`/api/v1/student/workshops/${encodeURIComponent(id)}`);
}

export function applyToWorkshop(id: string): Promise<WorkshopApplication> {
  return api.post(`/api/v1/student/workshops/${encodeURIComponent(id)}/applications`, {});
}

export function listMyWorkshopApplications(): Promise<WorkshopApplicationListResponse> {
  return api.get("/api/v1/student/workshop-applications");
}

export function withdrawWorkshopApplication(applicationId: string): Promise<WorkshopApplication> {
  return api.post(
    `/api/v1/student/workshop-applications/${encodeURIComponent(applicationId)}/withdraw`,
  );
}
