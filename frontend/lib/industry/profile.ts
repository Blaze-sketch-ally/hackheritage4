import { api } from "@/lib/api";
import type { IndustryProfile, IndustryProfileFields } from "@/types/industry";

/**
 * Talks to the Industry company-profile API
 * (backend/app/api/industry.py — /api/v1/industry/profile).
 *
 * The only place in the frontend that builds these requests — components
 * call these functions, never `api.get/put` directly. Every call goes
 * through lib/api.ts's apiFetch(), which attaches the caller's own
 * Supabase access token; no industry/user id is ever sent — the backend
 * derives ownership from the token (require_industry → current_user.id).
 */

/** The caller's own company profile. When nothing has been saved yet the
 * backend still returns 200 with `id` set and every other field null
 * (`created_at === null`) — never a 404. */
export function getIndustryProfile(): Promise<IndustryProfile> {
  return api.get<IndustryProfile>("/api/v1/industry/profile");
}

/** Create (first call) or replace the caller's own company profile. PUT
 * semantics: every field is sent, and a blank field is cleared. */
export function updateIndustryProfile(
  fields: IndustryProfileFields,
): Promise<IndustryProfile> {
  return api.put<IndustryProfile>("/api/v1/industry/profile", fields);
}
