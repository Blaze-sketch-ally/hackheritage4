import { api } from "@/lib/api";
import type { FacultyOpportunityListResponse, OpportunitySource } from "@/types/faculty-opportunity";
import type { FacultyOpportunityExpression, FacultyOpportunityExpressionListResponse } from "@/types/faculty-opportunity-expression";

/**
 * Thin wrappers over the Faculty opportunity-discovery and
 * expression-of-interest endpoints (backend/app/api/faculty_opportunities.py)
 * -- same shape as lib/faculty/question-bank.ts. Read-only for discovery;
 * Faculty never creates or edits a posting here, only discovers one and
 * expresses interest.
 */

export function listFacultyOpportunities(source?: OpportunitySource): Promise<FacultyOpportunityListResponse> {
  const query = source ? `?source=${source}` : "";
  return api.get(`/api/v1/faculty/opportunities${query}`);
}

export function expressInterest(
  source: OpportunitySource,
  opportunityId: string,
  message?: string,
): Promise<FacultyOpportunityExpression> {
  return api.post(`/api/v1/faculty/opportunities/${source}/${opportunityId}/express-interest`, {
    message: message || null,
  });
}

export function listMyExpressions(): Promise<FacultyOpportunityExpressionListResponse> {
  return api.get("/api/v1/faculty/opportunities/eoi/mine");
}

export function withdrawExpression(
  source: OpportunitySource,
  eoiId: string,
): Promise<FacultyOpportunityExpression> {
  return api.post(`/api/v1/faculty/opportunities/eoi/${source}/${eoiId}/withdraw`);
}
