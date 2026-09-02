import { api } from "@/lib/api";
import type { FacultyProfile, FacultyProfileUpdateInput } from "@/types/faculty-profile";

/**
 * Thin, 1:1 wrappers over GET/PUT /api/v1/faculty/profile -- same shape
 * as lib/faculty/question-bank.ts and lib/industry/profile.ts. Every call
 * goes through apiFetch (lib/api.ts), which attaches the caller's own
 * Supabase session; require_faculty + RLS are the real enforcement, this
 * module holds no privileged credentials.
 */

export function getFacultyProfile(): Promise<FacultyProfile> {
  return api.get("/api/v1/faculty/profile");
}

export function updateFacultyProfile(input: FacultyProfileUpdateInput): Promise<FacultyProfile> {
  return api.put("/api/v1/faculty/profile", input);
}
