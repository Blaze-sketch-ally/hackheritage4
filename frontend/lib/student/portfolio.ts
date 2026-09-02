import { api } from "@/lib/api";
import type {
  AchievementInput,
  AchievementListResponse,
  CertificationInput,
  CertificationListResponse,
  PortfolioResponse,
  ProjectInput,
  ProjectListResponse,
  StudentAchievement,
  StudentCertification,
  StudentProject,
} from "@/types/student-portfolio";

/**
 * Talks to OUR Student Portfolio API
 * (backend/app/api/student_portfolio.py, /api/v1/student/{portfolio,
 * projects,certifications,achievements}). The only place the frontend
 * builds these requests -- components call these functions, never `api.*`
 * directly.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * student's own Supabase access token. No `student_id` / `owner_id` is
 * ever sent -- the backend derives identity from the token
 * (require_student -> current_user.id) and every request model is
 * `extra="forbid"`.
 */

// ---- portfolio aggregate ----

export function getPortfolio(): Promise<PortfolioResponse> {
  return api.get("/api/v1/student/portfolio");
}

// ---- projects ----

export function listProjects(): Promise<ProjectListResponse> {
  return api.get("/api/v1/student/projects");
}

export function getProject(id: string): Promise<StudentProject> {
  return api.get(`/api/v1/student/projects/${encodeURIComponent(id)}`);
}

export function createProject(input: ProjectInput): Promise<StudentProject> {
  return api.post("/api/v1/student/projects", input);
}

export function updateProject(id: string, input: ProjectInput): Promise<StudentProject> {
  return api.put(`/api/v1/student/projects/${encodeURIComponent(id)}`, input);
}

export function deleteProject(id: string): Promise<void> {
  return api.delete(`/api/v1/student/projects/${encodeURIComponent(id)}`);
}

// ---- certifications ----

export function listCertifications(): Promise<CertificationListResponse> {
  return api.get("/api/v1/student/certifications");
}

export function getCertification(id: string): Promise<StudentCertification> {
  return api.get(`/api/v1/student/certifications/${encodeURIComponent(id)}`);
}

export function createCertification(input: CertificationInput): Promise<StudentCertification> {
  return api.post("/api/v1/student/certifications", input);
}

export function updateCertification(
  id: string,
  input: CertificationInput,
): Promise<StudentCertification> {
  return api.put(`/api/v1/student/certifications/${encodeURIComponent(id)}`, input);
}

export function deleteCertification(id: string): Promise<void> {
  return api.delete(`/api/v1/student/certifications/${encodeURIComponent(id)}`);
}

// ---- achievements ----

export function listAchievements(): Promise<AchievementListResponse> {
  return api.get("/api/v1/student/achievements");
}

export function getAchievement(id: string): Promise<StudentAchievement> {
  return api.get(`/api/v1/student/achievements/${encodeURIComponent(id)}`);
}

export function createAchievement(input: AchievementInput): Promise<StudentAchievement> {
  return api.post("/api/v1/student/achievements", input);
}

export function updateAchievement(
  id: string,
  input: AchievementInput,
): Promise<StudentAchievement> {
  return api.put(`/api/v1/student/achievements/${encodeURIComponent(id)}`, input);
}

export function deleteAchievement(id: string): Promise<void> {
  return api.delete(`/api/v1/student/achievements/${encodeURIComponent(id)}`);
}
