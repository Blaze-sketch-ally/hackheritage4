import type { SupabaseClient } from "@supabase/supabase-js";

/**
 * Mirrors the LIVE skill_categories / skills / student_skills tables
 * (database/migrations/003_skills.sql — applied and verified). This
 * module is the only place that talks to those tables from the
 * frontend — components never construct Supabase queries directly.
 */

export type ProficiencyLevel = "Beginner" | "Intermediate" | "Advanced" | "Expert";

// Mirrors student_skills.proficiency_level's CHECK constraint exactly.
export const PROFICIENCY_LEVELS: ProficiencyLevel[] = ["Beginner", "Intermediate", "Advanced", "Expert"];

// Value->label map for Select's `items` prop (lets the trigger resolve a
// label without the popup having to be opened/mounted first).
export const PROFICIENCY_LEVEL_ITEMS: Record<ProficiencyLevel, string> = {
  Beginner: "Beginner",
  Intermediate: "Intermediate",
  Advanced: "Advanced",
  Expert: "Expert",
};

export interface SkillCategory {
  id: string;
  name: string;
}

/** A row from the master skill catalog (`skills`). */
export interface CatalogSkill {
  id: string;
  name: string;
  category_id: string;
  description: string | null;
}

/** A student's own skill, joined with the catalog skill + its category. */
export interface StudentSkill {
  id: string;
  skill_id: string;
  proficiency_level: ProficiencyLevel;
  proficiency_score: number | null;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  skill: {
    id: string;
    name: string;
    description: string | null;
    category: { id: string; name: string } | null;
  };
}

const STUDENT_SKILL_SELECT =
  "id, skill_id, proficiency_level, proficiency_score, is_verified, created_at, updated_at, skill:skills(id, name, description, category:skill_categories(id, name))";

export async function fetchSkillCategories(supabase: SupabaseClient): Promise<SkillCategory[]> {
  const { data, error } = await supabase.from("skill_categories").select("id, name").order("name");

  if (error) {
    console.error("skill_categories read failed:", error.message);
    return [];
  }

  return (data ?? []) as SkillCategory[];
}

/** Only skills.is_active = true — matches the "Authenticated users can view active skills" RLS policy. */
export async function fetchActiveSkills(supabase: SupabaseClient): Promise<CatalogSkill[]> {
  const { data, error } = await supabase
    .from("skills")
    .select("id, name, category_id, description")
    .eq("is_active", true)
    .order("name");

  if (error) {
    console.error("skills read failed:", error.message);
    return [];
  }

  return (data ?? []) as CatalogSkill[];
}

/** The caller's own skills. Returns [] on error rather than failing the page — same pattern as fetchStudentProfile. */
export async function fetchStudentSkills(supabase: SupabaseClient, studentId: string): Promise<StudentSkill[]> {
  const { data, error } = await supabase
    .from("student_skills")
    .select(STUDENT_SKILL_SELECT)
    .eq("student_id", studentId)
    .order("created_at", { ascending: false });

  if (error) {
    console.error("student_skills read failed:", error.message);
    return [];
  }

  return (data ?? []) as unknown as StudentSkill[];
}

/**
 * Adds a skill to the caller's own profile. `studentId` must always be the
 * authenticated user's own id (never taken from a URL/query param) — RLS
 * independently enforces `auth.uid() = student_id` plus
 * `is_student(auth.uid())`, and the unique (student_id, skill_id)
 * constraint rejects a duplicate regardless of client-side prevention.
 */
export async function addStudentSkill(
  supabase: SupabaseClient,
  studentId: string,
  input: { skillId: string; proficiencyLevel: ProficiencyLevel },
) {
  return supabase
    .from("student_skills")
    .insert({ student_id: studentId, skill_id: input.skillId, proficiency_level: input.proficiencyLevel })
    .select(STUDENT_SKILL_SELECT)
    .single();
}

/**
 * Updates only proficiency_level. student_id/skill_id/is_verified are
 * never sent in this payload — is_verified specifically is blocked
 * server-side by the prevent_self_skill_verification trigger regardless.
 */
export async function updateStudentSkillProficiency(
  supabase: SupabaseClient,
  studentId: string,
  studentSkillId: string,
  proficiencyLevel: ProficiencyLevel,
) {
  return supabase
    .from("student_skills")
    .update({ proficiency_level: proficiencyLevel })
    .eq("id", studentSkillId)
    .eq("student_id", studentId)
    .select(STUDENT_SKILL_SELECT)
    .single();
}

export async function deleteStudentSkill(supabase: SupabaseClient, studentId: string, studentSkillId: string) {
  return supabase.from("student_skills").delete().eq("id", studentSkillId).eq("student_id", studentId);
}

const FRIENDLY_SKILL_ERRORS: Record<string, string> = {
  "23505": "You've already added this skill.",
  "23503": "That skill is no longer available. Please refresh and try again.",
  "42501": "You don't have permission to do that.",
  "23514": "That value isn't allowed. Please check your input.",
};

/** Maps a raw Supabase/Postgres error to a safe, user-facing message. Never echoes the raw error. */
export function getSkillErrorMessage(error: unknown): string {
  const code =
    error && typeof error === "object" && "code" in error ? String((error as { code?: unknown }).code ?? "") : "";
  if (code && FRIENDLY_SKILL_ERRORS[code]) return FRIENDLY_SKILL_ERRORS[code];

  const message =
    error && typeof error === "object" && "message" in error
      ? String((error as { message?: unknown }).message ?? "")
      : "";
  const normalized = message.toLowerCase();
  if (normalized.includes("fetch") || normalized.includes("network")) {
    return "Network error. Please check your connection and try again.";
  }

  return "Something went wrong. Please try again.";
}
