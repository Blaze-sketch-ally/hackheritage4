import { api } from "@/lib/api";
import type {
  ParticipantListResponse,
  ParticipantOpportunityType,
} from "@/types/industry-participant";

/**
 * Talks to OUR Industry Participants API
 * (backend/app/api/industry_participants.py, /api/v1/industry/participants).
 * A read-only, composed feed over the four existing Applicants sources --
 * no new table.
 */
export function listParticipants(params?: {
  opportunityType?: ParticipantOpportunityType;
  search?: string;
}): Promise<ParticipantListResponse> {
  const query = new URLSearchParams();
  if (params?.opportunityType) query.set("opportunity_type", params.opportunityType);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/industry/participants${qs ? `?${qs}` : ""}`);
}
