import { api } from "@/lib/api";
import type {
  CollaborationCreate,
  CollaborationStatus,
  CollaborationUpdate,
  IndustryCollaboration,
  RecipientResolution,
} from "@/types/industry-collaboration";

/**
 * Talks to the Industry collaboration API
 * (backend/app/api/industry_collaborations.py, /api/v1/collaborations).
 * The only place the frontend builds these requests — components call
 * these functions, never `api.*` directly. Ownership is never sent: the
 * backend derives `industry_id`/`recipient_id` from the caller's token.
 *
 * Functions here serve BOTH sides of the bilateral relationship —
 * Industry (initiator) and the Faculty/Institution recipient — since
 * they share the same underlying API and are used by
 * components/industry/collaborations/* and
 * components/collaborations/recipient-collaborations-view.tsx
 * respectively.
 */

// ---- Industry side ----

export function getCollaborations(params?: {
  status?: CollaborationStatus | "";
  search?: string;
}): Promise<{ collaborations: IndustryCollaboration[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/collaborations${qs ? `?${qs}` : ""}`);
}

export function getCollaboration(id: string): Promise<IndustryCollaboration> {
  return api.get(`/api/v1/collaborations/${id}`);
}

/** Creates a DRAFT collaboration. Sending is a separate explicit step. */
export function createCollaboration(data: CollaborationCreate): Promise<IndustryCollaboration> {
  return api.post("/api/v1/collaborations", data);
}

export function updateCollaboration(
  id: string,
  data: CollaborationUpdate,
): Promise<IndustryCollaboration> {
  return api.put(`/api/v1/collaborations/${id}`, data);
}

export function sendCollaboration(id: string): Promise<IndustryCollaboration> {
  return api.post(`/api/v1/collaborations/${id}/send`);
}

export function activateCollaboration(id: string): Promise<IndustryCollaboration> {
  return api.post(`/api/v1/collaborations/${id}/activate`);
}

export function completeCollaboration(id: string): Promise<IndustryCollaboration> {
  return api.post(`/api/v1/collaborations/${id}/complete`);
}

export function cancelCollaboration(id: string): Promise<IndustryCollaboration> {
  return api.post(`/api/v1/collaborations/${id}/cancel`);
}

/** Resolves a username to a Faculty/Institution recipient — id/role/full_name
 * only. Used by the create-collaboration form. */
export function resolveRecipient(identifier: string): Promise<RecipientResolution> {
  return api.get(`/api/v1/collaborations/recipients/resolve?identifier=${encodeURIComponent(identifier)}`);
}

// ---- Recipient side (Faculty / Institution) ----

export function getIncomingCollaborations(params?: {
  status?: CollaborationStatus | "";
}): Promise<{ collaborations: IndustryCollaboration[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return api.get(`/api/v1/collaborations/incoming${qs ? `?${qs}` : ""}`);
}

export function acceptCollaboration(id: string): Promise<IndustryCollaboration> {
  return api.post(`/api/v1/collaborations/${id}/accept`);
}

export function rejectCollaboration(id: string): Promise<IndustryCollaboration> {
  return api.post(`/api/v1/collaborations/${id}/reject`);
}
