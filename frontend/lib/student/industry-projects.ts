import { api } from "@/lib/api";
import type { StudentProject, StudentProjectListResponse } from "@/types/student-project";
import type { ProjectApplication, ProjectApplicationListResponse } from "@/types/project-application";

/**
 * Talks to OUR Student Project API
 * (backend/app/api/student_projects.py, /api/v1/student/industry-projects).
 * Named "industry-projects" throughout (not "projects") to avoid
 * colliding with the existing Student Portfolio "projects" feature.
 */

export function listProjects(params?: { search?: string }): Promise<StudentProjectListResponse> {
  const query = new URLSearchParams();
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/student/industry-projects${qs ? `?${qs}` : ""}`);
}

export function getProject(id: string): Promise<StudentProject> {
  return api.get(`/api/v1/student/industry-projects/${encodeURIComponent(id)}`);
}

export function applyToProject(id: string): Promise<ProjectApplication> {
  return api.post(`/api/v1/student/industry-projects/${encodeURIComponent(id)}/applications`, {});
}

export function listMyProjectApplications(): Promise<ProjectApplicationListResponse> {
  return api.get("/api/v1/student/project-applications");
}

export function withdrawProjectApplication(applicationId: string): Promise<ProjectApplication> {
  return api.post(
    `/api/v1/student/project-applications/${encodeURIComponent(applicationId)}/withdraw`,
  );
}
