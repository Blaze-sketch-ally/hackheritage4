import { api } from "@/lib/api";
import type {
  FacultyOpportunityPosting,
  FacultyOpportunityPostingInput,
  FacultyOpportunityPostingListResponse,
} from "@/types/faculty-opportunity-posting";
import type { FacultyOpportunityExpression, FacultyOpportunityExpressionListResponse } from "@/types/faculty-opportunity-expression";

/**
 * Thin wrappers over backend/app/api/institution_faculty_opportunities.py
 * (/api/v1/institution/faculty-opportunities). Structural twin of
 * lib/industry/faculty-opportunities.ts -- this is Institution's first
 * content-management API client in this codebase.
 */

export function listOwnFacultyOpportunities(): Promise<FacultyOpportunityPostingListResponse> {
  return api.get("/api/v1/institution/faculty-opportunities");
}

export function createFacultyOpportunity(input: FacultyOpportunityPostingInput): Promise<FacultyOpportunityPosting> {
  return api.post("/api/v1/institution/faculty-opportunities", input);
}

export function updateFacultyOpportunity(
  id: string,
  input: Partial<FacultyOpportunityPostingInput>,
): Promise<FacultyOpportunityPosting> {
  return api.put(`/api/v1/institution/faculty-opportunities/${id}`, input);
}

export function publishFacultyOpportunity(id: string): Promise<FacultyOpportunityPosting> {
  return api.post(`/api/v1/institution/faculty-opportunities/${id}/publish`);
}

export function closeFacultyOpportunity(id: string): Promise<FacultyOpportunityPosting> {
  return api.post(`/api/v1/institution/faculty-opportunities/${id}/close`);
}

export function listFacultyOpportunityEois(): Promise<FacultyOpportunityExpressionListResponse> {
  return api.get("/api/v1/institution/faculty-opportunities/eoi");
}

export function reviewFacultyOpportunityEoi(
  eoiId: string,
  status: "UNDER_REVIEW" | "ACCEPTED" | "REJECTED",
  reviewerNote?: string,
): Promise<FacultyOpportunityExpression> {
  return api.patch(`/api/v1/institution/faculty-opportunities/eoi/${eoiId}/review`, {
    status,
    reviewer_note: reviewerNote || null,
  });
}
