import { api } from "@/lib/api";
import type {
  Application,
  ApplicationMatch,
  ApplicationStatus,
  ApplicationSummary,
  IndustrySettableStatus,
  OpportunityType,
} from "@/types/application";

/**
 * Talks to the Industry application API
 * (backend/app/api/applications.py, /api/v1/applications). The only place
 * the frontend builds these requests — components call these functions,
 * never `api.*` directly. Ownership is never sent: the backend derives
 * the owning Industry account from the caller's token
 * (require_industry → current_user.id).
 */

export function getApplications(params?: {
  status?: ApplicationStatus | "";
  opportunity_type?: OpportunityType | "";
  internship_id?: string;
  job_id?: string;
}): Promise<{ applications: Application[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.opportunity_type) query.set("opportunity_type", params.opportunity_type);
  if (params?.internship_id) query.set("internship_id", params.internship_id);
  if (params?.job_id) query.set("job_id", params.job_id);
  const qs = query.toString();
  return api.get(`/api/v1/applications${qs ? `?${qs}` : ""}`);
}

export function getApplication(id: string): Promise<Application> {
  return api.get(`/api/v1/applications/${id}`);
}

/** Per-status counts of the caller's own applications, for the funnel. */
export function getApplicationsSummary(): Promise<ApplicationSummary> {
  return api.get("/api/v1/applications/summary");
}

/** Deterministic, advisory skill-match for one application. The backend
 * recomputes the authoritative result on every call and best-effort
 * caches the score onto the application. The application id is the only
 * identifier the frontend ever sends. */
export function getApplicationMatch(applicationId: string): Promise<ApplicationMatch> {
  return api.get(`/api/v1/applications/${applicationId}/match`);
}

/** Move an application along the recruitment pipeline. The backend
 * re-validates the transition and returns 409 for an invalid one. */
export function updateApplicationStatus(
  id: string,
  status: IndustrySettableStatus,
): Promise<Application> {
  return api.patch(`/api/v1/applications/${id}/status`, { status });
}
