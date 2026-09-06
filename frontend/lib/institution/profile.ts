import { api } from "@/lib/api";
import type { InstitutionProfile, InstitutionProfileFields } from "@/types/institution";

/**
 * Talks to the Institution profile API
 * (backend/app/api/institution.py — /api/v1/institution/profile). Same
 * pattern as lib/industry/profile.ts.
 */

/** The caller's own institution profile. When nothing has been saved yet
 * the backend still returns 200 with `id` set and every other field null
 * (`created_at === null`) — never a 404. */
export function getInstitutionProfile(): Promise<InstitutionProfile> {
  return api.get<InstitutionProfile>("/api/v1/institution/profile");
}

/** Create (first call) or replace the caller's own institution profile.
 * PUT semantics: every field is sent, and a blank field is cleared. */
export function updateInstitutionProfile(
  fields: InstitutionProfileFields,
): Promise<InstitutionProfile> {
  return api.put<InstitutionProfile>("/api/v1/institution/profile", fields);
}
