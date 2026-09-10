import { api } from "@/lib/api";
import type {
  CompanyOptionListResponse,
  IndustryPartnerDetail,
  IndustryPartnerListResponse,
  IndustryPartnerMetricsResponse,
  IndustryPartnerRelationshipCreate,
  IndustryPartnerRelationshipResponse,
  IndustryPartnerRelationshipUpdate,
} from "@/types/institution-industry";

export interface IndustryPartnerListQuery {
  search?: string;
  relationship_type?: string | null;
  relationship_status?: string | null;
}

/** Talks to backend/app/api/institution.py, GET /api/v1/institution/industry-partners. */
export function getIndustryPartners(query: IndustryPartnerListQuery = {}): Promise<IndustryPartnerListResponse> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.relationship_type) params.set("relationship_type", query.relationship_type);
  if (query.relationship_status) params.set("relationship_status", query.relationship_status);
  const qs = params.toString();
  return api.get(`/api/v1/institution/industry-partners${qs ? `?${qs}` : ""}`);
}

export function getIndustryPartner(industryId: string): Promise<IndustryPartnerDetail> {
  return api.get(`/api/v1/institution/industry-partners/${industryId}`);
}

export function getIndustryPartnerMetrics(): Promise<IndustryPartnerMetricsResponse> {
  return api.get("/api/v1/institution/industry-partners/metrics");
}

export function searchIndustryPartnerCompanies(search?: string): Promise<CompanyOptionListResponse> {
  const qs = search && search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  return api.get(`/api/v1/institution/industry-partners/companies${qs}`);
}

export function createIndustryPartnerRelationship(
  body: IndustryPartnerRelationshipCreate,
): Promise<IndustryPartnerRelationshipResponse> {
  return api.post("/api/v1/institution/industry-partners", body);
}

export function updateIndustryPartnerRelationship(
  industryId: string,
  body: IndustryPartnerRelationshipUpdate,
): Promise<IndustryPartnerRelationshipResponse> {
  return api.patch(`/api/v1/institution/industry-partners/${industryId}/relationship`, body);
}
