import { api } from "@/lib/api";
import type {
  Certification,
  CertificationCreateInput,
  CertificationUpdateInput,
  Portfolio,
  Project,
  ProjectCreateInput,
  ProjectUpdateInput,
} from "@/types/portfolio";

/**
 * Talks to the live Portfolio API's student-facing routes
 * (backend/app/api/portfolio.py -- Phase 1N). Every call goes through
 * lib/api.ts's apiFetch(), which attaches the student's own Supabase
 * access token -- no student_id is ever sent in a request; the backend
 * derives it from the token, and RLS is what actually enforces "only
 * your own portfolio" either way.
 */

export function getMyPortfolio(): Promise<Portfolio> {
  return api.get("/api/v1/portfolio");
}

export function listMyProjects(): Promise<{ projects: Project[] }> {
  return api.get("/api/v1/portfolio/projects");
}

export function createProject(input: ProjectCreateInput): Promise<Project> {
  return api.post("/api/v1/portfolio/projects", input);
}

export function updateProject(projectId: string, input: ProjectUpdateInput): Promise<Project> {
  return api.patch(`/api/v1/portfolio/projects/${projectId}`, input);
}

export function deleteProject(projectId: string): Promise<void> {
  return api.delete(`/api/v1/portfolio/projects/${projectId}`);
}

export function listMyCertifications(): Promise<{ certifications: Certification[] }> {
  return api.get("/api/v1/portfolio/certifications");
}

export function createCertification(input: CertificationCreateInput): Promise<Certification> {
  return api.post("/api/v1/portfolio/certifications", input);
}

export function updateCertification(
  certificationId: string,
  input: CertificationUpdateInput,
): Promise<Certification> {
  return api.patch(`/api/v1/portfolio/certifications/${certificationId}`, input);
}

export function deleteCertification(certificationId: string): Promise<void> {
  return api.delete(`/api/v1/portfolio/certifications/${certificationId}`);
}
