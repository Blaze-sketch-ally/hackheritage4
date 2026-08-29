import type { SupabaseClient } from "@supabase/supabase-js";
import type { Profile } from "@/types/user";

/**
 * Mirrors the LIVE `student_profiles` table (database/migrations/
 * 012_student_profiles.sql — applied and verified). One row per STUDENT
 * user, keyed by `id = profiles.id = auth.users.id`. Every field here has
 * a real column behind it — do not add fields that don't exist in the
 * migration (technical_skills, academic_year, resume/links, etc. are
 * intentionally not part of this table yet).
 */
export interface StudentProfile {
  id: string;
  phone: string | null;
  date_of_birth: string | null;
  gender: string | null;
  location: string | null;
  institution_name: string | null;
  department: string | null;
  degree: string | null;
  graduation_year: number | null;
  cgpa: number | null;
  percentage: number | null;
  career_goals: string | null;
  preferred_roles: string[];
  preferred_locations: string[];
  interests: string[];
  created_at: string;
  updated_at: string;
}

export type StudentProfileFields = Omit<StudentProfile, "id" | "created_at" | "updated_at">;

export const EMPTY_STUDENT_PROFILE_FIELDS: StudentProfileFields = {
  phone: null,
  date_of_birth: null,
  gender: null,
  location: null,
  institution_name: null,
  department: null,
  degree: null,
  graduation_year: null,
  cgpa: null,
  percentage: null,
  career_goals: null,
  preferred_roles: [],
  preferred_locations: [],
  interests: [],
};

/**
 * Reads the caller's own student_profiles row. Returns null both when no
 * row exists yet (new student, hasn't saved a profile) and on any read
 * error — callers render the form with empty/default fields either way
 * rather than failing the whole page.
 */
export async function fetchStudentProfile(
  supabase: SupabaseClient,
  userId: string,
): Promise<StudentProfile | null> {
  const { data, error } = await supabase
    .from("student_profiles")
    .select("*")
    .eq("id", userId)
    .maybeSingle();

  if (error) {
    console.error("student_profiles read failed:", error.message);
    return null;
  }

  return (data as StudentProfile | null) ?? null;
}

/**
 * Creates or updates the caller's own student_profiles row. `userId` must
 * always be the authenticated caller's own id (never taken from a
 * URL/query param) — RLS independently enforces `auth.uid() = id` plus
 * `is_student(auth.uid())`, so a spoofed id would just be rejected, but
 * the call site should never construct one in the first place. Only the
 * columns that actually exist on student_profiles are ever sent —
 * `updated_at` is deliberately omitted: the column default covers INSERT,
 * and the `student_profiles_set_updated_at` trigger covers UPDATE.
 */
export async function upsertStudentProfile(
  supabase: SupabaseClient,
  userId: string,
  fields: StudentProfileFields,
) {
  return supabase
    .from("student_profiles")
    .upsert({ id: userId, ...fields })
    .select("*")
    .single();
}

const COMPLETION_CHECKS: Array<(profile: Profile | null, student: StudentProfile | null) => boolean> = [
  (p) => !!p?.full_name,
  (p) => !!p?.username,
  (p) => !!p?.avatar_url,
  (_p, s) => !!s?.phone,
  (_p, s) => !!s?.date_of_birth,
  (_p, s) => !!s?.gender,
  (_p, s) => !!s?.location,
  (_p, s) => !!s?.institution_name,
  (_p, s) => !!s?.department,
  (_p, s) => !!s?.degree,
  (_p, s) => !!s?.graduation_year,
  (_p, s) => s?.cgpa != null || s?.percentage != null,
  (_p, s) => !!s?.career_goals,
  (_p, s) => (s?.preferred_roles.length ?? 0) > 0,
  (_p, s) => (s?.preferred_locations.length ?? 0) > 0,
  (_p, s) => (s?.interests.length ?? 0) > 0,
];

/**
 * Percentage of the profile that's filled in, derived directly from
 * profiles + student_profiles — no stored `profile_completion` column.
 * Shared by /student/profile and /student/dashboard so they never drift.
 */
export function getProfileCompletion(
  profile: Profile | null,
  studentProfile: StudentProfile | null,
): number {
  const completed = COMPLETION_CHECKS.filter((check) => check(profile, studentProfile)).length;
  return Math.round((completed / COMPLETION_CHECKS.length) * 100);
}
