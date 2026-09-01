import { api } from "@/lib/api";
import type {
  IndustryMentorship,
  MentorshipCreate,
  MentorshipStatus,
  MentorshipUpdate,
} from "@/types/industry-mentorship";

/**
 * Talks to the Industry mentorship-opportunity API
 * (backend/app/api/industry_mentorship_opportunities.py,
 * /api/v1/mentorship-opportunities). The only place the frontend builds
 * these requests — components call these functions, never `api.*`
 * directly. Ownership is never sent: the backend derives `industry_id`
 * from the caller's token (require_industry → current_user.id).
 */

export function getMentorshipOpportunities(params?: {
  status?: MentorshipStatus | "";
  search?: string;
}): Promise<{ mentorship_opportunities: IndustryMentorship[] }> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/mentorship-opportunities${qs ? `?${qs}` : ""}`);
}

export function getMentorshipOpportunity(id: string): Promise<IndustryMentorship> {
  return api.get(`/api/v1/mentorship-opportunities/${id}`);
}

/** Creates a DRAFT mentorship opportunity. Publishing is a separate
 * explicit step. */
export function createMentorshipOpportunity(data: MentorshipCreate): Promise<IndustryMentorship> {
  return api.post("/api/v1/mentorship-opportunities", data);
}

export function updateMentorshipOpportunity(
  id: string,
  data: MentorshipUpdate,
): Promise<IndustryMentorship> {
  return api.put(`/api/v1/mentorship-opportunities/${id}`, data);
}

export function publishMentorshipOpportunity(id: string): Promise<IndustryMentorship> {
  return api.post(`/api/v1/mentorship-opportunities/${id}/publish`);
}

export function closeMentorshipOpportunity(id: string): Promise<IndustryMentorship> {
  return api.post(`/api/v1/mentorship-opportunities/${id}/close`);
}

export function archiveMentorshipOpportunity(id: string): Promise<IndustryMentorship> {
  return api.post(`/api/v1/mentorship-opportunities/${id}/archive`);
}
