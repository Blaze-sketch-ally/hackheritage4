import { api } from "@/lib/api";
import type { InstitutionLinkRequest, InstitutionResolution, LinkRequestStatus } from "@/types/institution-link";

/**
 * Talks to the student <-> institution linking API
 * (backend/app/api/institution_link_requests.py — /api/v1/institution-links).
 * The only place the frontend builds these requests. Serves BOTH sides
 * of the bilateral relationship — the requesting Student and the
 * approving Institution — since they share the same underlying API, the
 * same way lib/industry/collaborations.ts serves both Industry and its
 * recipients. Ownership is never sent: the backend derives
 * student_id/institution_id from the caller's token.
 */

// ---- Resolution (student-side create form) ----

/** Looks up an institution by username — a single exact lookup, never a
 * browsable list. Throws ApiError(404) when no match exists. */
export function resolveInstitution(identifier: string): Promise<InstitutionResolution> {
  return api.get(`/api/v1/institution-links/resolve?identifier=${encodeURIComponent(identifier)}`);
}

// ---- Student side ----

export function getMyLinkRequests(): Promise<{ requests: InstitutionLinkRequest[] }> {
  return api.get("/api/v1/institution-links/mine");
}

export function createLinkRequest(institutionId: string): Promise<InstitutionLinkRequest> {
  return api.post("/api/v1/institution-links", { institution_id: institutionId });
}

export function cancelLinkRequest(id: string): Promise<InstitutionLinkRequest> {
  return api.post(`/api/v1/institution-links/${id}/cancel`);
}

// ---- Institution side ----

export function getIncomingLinkRequests(params?: {
  status?: LinkRequestStatus | "";
}): Promise<{ requests: InstitutionLinkRequest[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return api.get(`/api/v1/institution-links/incoming${qs ? `?${qs}` : ""}`);
}

export function approveLinkRequest(id: string): Promise<InstitutionLinkRequest> {
  return api.post(`/api/v1/institution-links/${id}/approve`);
}

export function rejectLinkRequest(id: string): Promise<InstitutionLinkRequest> {
  return api.post(`/api/v1/institution-links/${id}/reject`);
}

export function unlinkStudent(id: string): Promise<InstitutionLinkRequest> {
  return api.post(`/api/v1/institution-links/${id}/unlink`);
}
