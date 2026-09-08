import { api } from "@/lib/api";
import type {
  IndustryConnectionCreate,
  IndustryConnectionListResponse,
  IndustryConnectionRow,
  IndustryConnectionUpdate,
} from "@/types/institution-industry-connection";

export interface IndustryConnectionListQuery {
  search?: string;
  contact_type?: string | null;
  is_active?: boolean | null;
  industry_id?: string | null;
}

/** Talks to backend/app/api/institution.py, GET /api/v1/institution/industry-connections. */
export function getIndustryConnections(
  query: IndustryConnectionListQuery = {},
): Promise<IndustryConnectionListResponse> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.contact_type) params.set("contact_type", query.contact_type);
  if (query.is_active != null) params.set("is_active", String(query.is_active));
  if (query.industry_id) params.set("industry_id", query.industry_id);
  const qs = params.toString();
  return api.get(`/api/v1/institution/industry-connections${qs ? `?${qs}` : ""}`);
}

export function getIndustryConnection(id: string): Promise<IndustryConnectionRow> {
  return api.get(`/api/v1/institution/industry-connections/${id}`);
}

export function createIndustryConnection(body: IndustryConnectionCreate): Promise<IndustryConnectionRow> {
  return api.post("/api/v1/institution/industry-connections", body);
}

export function updateIndustryConnection(
  id: string,
  body: IndustryConnectionUpdate,
): Promise<IndustryConnectionRow> {
  return api.patch(`/api/v1/institution/industry-connections/${id}`, body);
}
