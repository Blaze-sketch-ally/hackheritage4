import { api } from "@/lib/api";
import type { Application } from "@/types/application";
import type { Opportunity, OpportunityMatch } from "@/types/opportunity";

/**
 * Talks to the live Opportunity/Application API (backend/app/api/
 * opportunities.py, applications.py -- Phase 1M). Same shape as
 * lib/student/career-roles.ts. Every call goes through lib/api.ts's
 * apiFetch(), which attaches the student's own Supabase access token --
 * no student_id is ever sent in a request; the backend derives it from
 * the token.
 */

export function listOpportunities(
  opportunityType?: "JOB" | "INTERNSHIP",
): Promise<{ opportunities: Opportunity[] }> {
  const query = opportunityType ? `?opportunity_type=${opportunityType}` : "";
  return api.get(`/api/v1/opportunities${query}`);
}

export function getOpportunity(opportunityId: string): Promise<Opportunity> {
  return api.get(`/api/v1/opportunities/${opportunityId}`);
}

/** The authenticated student's own derived match against one opportunity
 * -- computed fresh server-side from real assessment evidence, via the
 * same Phase 1L alignment engine skill-gap analysis uses. Never
 * client-computed. */
export function getOpportunityMatch(opportunityId: string): Promise<OpportunityMatch> {
  return api.get(`/api/v1/opportunities/${opportunityId}/match`);
}

export function applyToOpportunity(opportunityId: string, coverNote?: string): Promise<Application> {
  return api.post(`/api/v1/opportunities/${opportunityId}/applications`, {
    cover_note: coverNote || null,
  });
}

export function listMyApplications(): Promise<{ applications: Application[] }> {
  return api.get("/api/v1/applications");
}
