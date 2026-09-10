import { api } from "@/lib/api";
import type { WorkMode } from "@/types/job";
import type {
  OpportunityMatch,
  OpportunitySort,
  SourceType,
  StudentApplication,
  StudentOpportunityDetail,
  StudentOpportunitySummary,
} from "@/types/student-opportunity";

/**
 * Talks to OUR Student opportunity/application API
 * (backend/app/api/student_opportunities.py,
 * /api/v1/student/opportunities + /api/v1/student/applications). The only
 * place the frontend builds these requests -- components call these
 * functions, never `api.*` directly.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * student's own Supabase access token. No `student_id` is ever sent --
 * the backend derives it from the token (require_student ->
 * current_user.id). Apply sends ONLY `cover_note`; `industry_id` /
 * `status` / `match_score` / `internship_id` / `job_id` /
 * `opportunity_type` are all derived server-side.
 *
 * This is a rewrite of the teammate's opportunity API client for OUR
 * endpoints -- it does NOT talk to any `opportunities` table or send an
 * `opportunity_id`; the opportunity id here is the prefixed
 * `internship_<uuid>` / `job_<uuid>` string the backend returns.
 */

/**
 * Browse published internships/jobs. Every filter is a server-side query
 * param — the list is NOT downloaded whole and filtered in the browser.
 * Defaults (`sort: "newest"`, unset filters) are omitted from the query
 * string entirely, so a clean browse is just `?source_type=…`.
 */
export function listOpportunities(params?: {
  sourceType?: SourceType;
  search?: string;
  workMode?: WorkMode;
  minStipend?: number;
  minSalary?: number;
  sort?: OpportunitySort;
}): Promise<{ opportunities: StudentOpportunitySummary[] }> {
  const query = new URLSearchParams();
  if (params?.sourceType) query.set("source_type", params.sourceType);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  if (params?.workMode) query.set("work_mode", params.workMode);
  if (params?.minStipend != null && params.minStipend > 0) {
    query.set("min_stipend", String(params.minStipend));
  }
  if (params?.minSalary != null && params.minSalary > 0) {
    query.set("min_salary", String(params.minSalary));
  }
  if (params?.sort && params.sort !== "newest") query.set("order_by", params.sort);
  const qs = query.toString();
  return api.get(`/api/v1/student/opportunities${qs ? `?${qs}` : ""}`);
}

export function getOpportunity(opportunityId: string): Promise<StudentOpportunityDetail> {
  return api.get(`/api/v1/student/opportunities/${encodeURIComponent(opportunityId)}`);
}

/** The caller's own advisory skill match against one opportunity --
 * computed fresh server-side by the same deterministic engine the
 * Industry applicant-match endpoint uses. Never client-computed, never
 * persisted. A failure here must not block applying. */
export function getOpportunityMatch(opportunityId: string): Promise<OpportunityMatch> {
  return api.get(`/api/v1/student/opportunities/${encodeURIComponent(opportunityId)}/match`);
}

/** Creates the existing `applications` row for this student. Returns 409
 * for a duplicate or a posting that is no longer accepting applications. */
export function applyToOpportunity(
  opportunityId: string,
  coverNote?: string,
): Promise<StudentApplication> {
  return api.post(
    `/api/v1/student/opportunities/${encodeURIComponent(opportunityId)}/applications`,
    { cover_note: coverNote?.trim() ? coverNote.trim() : null },
  );
}

/** The authenticated student's own applications only. `status` always
 * reflects whatever the owning Industry account last set. */
export function listMyApplications(): Promise<{ applications: StudentApplication[] }> {
  return api.get("/api/v1/student/applications");
}

/** Withdraw the caller's OWN application (status -> WITHDRAWN). Allowed
 * only while the application is still an active candidate application
 * (APPLIED / UNDER_REVIEW / SHORTLISTED / INTERVIEW_SCHEDULED) -- the
 * backend returns 409 otherwise, and 404 for an application the student
 * does not own. No `student_id` is ever sent; identity is the token.
 * Resolves with the updated application (same shape as `applyToOpportunity`). */
export function withdrawApplication(applicationId: string): Promise<StudentApplication> {
  return api.post(
    `/api/v1/student/applications/${encodeURIComponent(applicationId)}/withdraw`,
  );
}
