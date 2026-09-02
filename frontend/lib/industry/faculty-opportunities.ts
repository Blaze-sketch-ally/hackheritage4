import { api } from "@/lib/api";
import type {
  FacultyOpportunityPosting,
  FacultyOpportunityPostingInput,
  FacultyOpportunityPostingListResponse,
} from "@/types/faculty-opportunity-posting";
import type { FacultyOpportunityExpression, FacultyOpportunityExpressionListResponse } from "@/types/faculty-opportunity-expression";

/**
 * Thin wrappers over backend/app/api/industry_faculty_opportunities.py
 * (/api/v1/industry/faculty-opportunities). Same shape as
 * lib/industry/collaborations.ts -- ownership (industry_id) is never
 * sent, the backend derives it from the caller's token.
 */

export function listOwnFacultyOpportunities(): Promise<FacultyOpportunityPostingListResponse> {
  return api.get("/api/v1/industry/faculty-opportunities");
}

export function createFacultyOpportunity(input: FacultyOpportunityPostingInput): Promise<FacultyOpportunityPosting> {
  return api.post("/api/v1/industry/faculty-opportunities", input);
}

export function updateFacultyOpportunity(
  id: string,
  input: Partial<FacultyOpportunityPostingInput>,
): Promise<FacultyOpportunityPosting> {
  return api.put(`/api/v1/industry/faculty-opportunities/${id}`, input);
}

export function publishFacultyOpportunity(id: string): Promise<FacultyOpportunityPosting> {
  return api.post(`/api/v1/industry/faculty-opportunities/${id}/publish`);
}

export function closeFacultyOpportunity(id: string): Promise<FacultyOpportunityPosting> {
  return api.post(`/api/v1/industry/faculty-opportunities/${id}/close`);
}

export function listFacultyOpportunityEois(): Promise<FacultyOpportunityExpressionListResponse> {
  return api.get("/api/v1/industry/faculty-opportunities/eoi");
}

export function reviewFacultyOpportunityEoi(
  eoiId: string,
  status: "UNDER_REVIEW" | "ACCEPTED" | "REJECTED",
  reviewerNote?: string,
): Promise<FacultyOpportunityExpression> {
  return api.patch(`/api/v1/industry/faculty-opportunities/eoi/${eoiId}/review`, {
    status,
    reviewer_note: reviewerNote || null,
  });
}
