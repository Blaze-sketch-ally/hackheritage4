import { api } from "@/lib/api";
import type { Applicant, ApplicantDetail } from "@/types/application";
import type {
  Opportunity,
  OpportunityCreateInput,
  OpportunityRequirement,
  OpportunityRequirementInput,
  OpportunityUpdateInput,
} from "@/types/opportunity";

/**
 * Talks to the live Opportunity API's industry-facing routes
 * (backend/app/api/opportunities.py -- Phase 1M). Every call goes
 * through lib/api.ts's apiFetch(), which attaches the industry account's
 * own Supabase access token -- no industry_id is ever sent in a
 * request; the backend derives it from the token, and RLS is what
 * actually enforces "only your own opportunities" either way.
 */

export function listMyOpportunities(
  opportunityType?: "JOB" | "INTERNSHIP",
): Promise<{ opportunities: Opportunity[] }> {
  const params = new URLSearchParams({ mine: "true" });
  if (opportunityType) params.set("opportunity_type", opportunityType);
  return api.get(`/api/v1/opportunities?${params.toString()}`);
}

export function getOpportunity(opportunityId: string): Promise<Opportunity> {
  return api.get(`/api/v1/opportunities/${opportunityId}`);
}

export function createOpportunity(input: OpportunityCreateInput): Promise<Opportunity> {
  return api.post("/api/v1/opportunities", input);
}

export function updateOpportunity(
  opportunityId: string,
  input: OpportunityUpdateInput,
): Promise<Opportunity> {
  return api.patch(`/api/v1/opportunities/${opportunityId}`, input);
}

export function publishOpportunity(opportunityId: string): Promise<Opportunity> {
  return api.post(`/api/v1/opportunities/${opportunityId}/publish`);
}

export function closeOpportunity(opportunityId: string): Promise<Opportunity> {
  return api.post(`/api/v1/opportunities/${opportunityId}/close`);
}

export function getRequirements(
  opportunityId: string,
): Promise<{ opportunity_id: string; requirements: OpportunityRequirement[] }> {
  return api.get(`/api/v1/opportunities/${opportunityId}/requirements`);
}

/** Full replace -- only accepted while the opportunity is still DRAFT
 * (enforced by RLS + an explicit backend check, see
 * app/api/opportunities.py). */
export function replaceRequirements(
  opportunityId: string,
  requirements: OpportunityRequirementInput[],
): Promise<{ opportunity_id: string; requirements: OpportunityRequirement[] }> {
  return api.put(`/api/v1/opportunities/${opportunityId}/requirements`, { requirements });
}

export function listApplicants(
  opportunityId: string,
): Promise<{ opportunity_id: string; applicants: Applicant[] }> {
  return api.get(`/api/v1/opportunities/${opportunityId}/applicants`);
}

/** Phase 1N: the "Applicant" step of Industry -> My Opportunities ->
 * Applicants -> Applicant -> Portfolio -- candidate overview plus the
 * full skill-alignment breakdown (listApplicants above only returns the
 * aggregate score, to stay lean). Portfolio itself is a separate call,
 * lib/industry/portfolio.ts's getApplicationPortfolio(). */
export function getApplicantDetail(
  opportunityId: string,
  applicationId: string,
): Promise<ApplicantDetail> {
  return api.get(`/api/v1/opportunities/${opportunityId}/applicants/${applicationId}`);
}

export function updateApplicationStatus(
  applicationId: string,
  applicationStatus: string,
): Promise<unknown> {
  return api.patch(`/api/v1/applications/${applicationId}/status`, { status: applicationStatus });
}
