import { api } from "@/lib/api";
import type {
  AvailableInternshipListResponse,
  InstitutionInternshipDetail,
  InstitutionInternshipListResponse,
  InstitutionInternshipOverviewResponse,
  InternshipAssociationResponse,
} from "@/types/institution-internship";

export interface InternshipListQuery {
  search?: string;
  status?: string | null;
  mode?: string | null;
  company_id?: string | null;
}

export interface AvailableInternshipQuery {
  search?: string;
  mode?: string | null;
  company_id?: string | null;
}

/** Talks to backend/app/api/institution.py, GET /api/v1/institution/internships
 * -- this institution's CURATED internship list (the module's default view). */
export function getInstitutionInternships(
  query: InternshipListQuery = {},
): Promise<InstitutionInternshipListResponse> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.status) params.set("status", query.status);
  if (query.mode) params.set("mode", query.mode);
  if (query.company_id) params.set("company_id", query.company_id);
  const qs = params.toString();
  return api.get(`/api/v1/institution/internships${qs ? `?${qs}` : ""}`);
}

/** GET /api/v1/institution/internships/available -- PUBLISHED internships
 * not yet curated by this institution, the "Browse Available Internships" source. */
export function getAvailableInternships(
  query: AvailableInternshipQuery = {},
): Promise<AvailableInternshipListResponse> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.mode) params.set("mode", query.mode);
  if (query.company_id) params.set("company_id", query.company_id);
  const qs = params.toString();
  return api.get(`/api/v1/institution/internships/available${qs ? `?${qs}` : ""}`);
}

/** GET /api/v1/institution/internships/{id}. */
export function getInstitutionInternship(id: string): Promise<InstitutionInternshipDetail> {
  return api.get(`/api/v1/institution/internships/${id}`);
}

/** GET /api/v1/institution/internships/overview. */
export function getInstitutionInternshipOverview(): Promise<InstitutionInternshipOverviewResponse> {
  return api.get("/api/v1/institution/internships/overview");
}

/** POST /api/v1/institution/internships/{id}/select -- "Add to Institution". */
export function selectInstitutionInternship(id: string): Promise<InternshipAssociationResponse> {
  return api.post(`/api/v1/institution/internships/${id}/select`, {});
}

/** PATCH /api/v1/institution/internships/{id}/association -- removes
 * (soft-deactivates) this internship from the curated list. */
export function removeInstitutionInternship(id: string): Promise<InternshipAssociationResponse> {
  return api.patch(`/api/v1/institution/internships/${id}/association`, {});
}
