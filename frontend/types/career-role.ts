/**
 * Mirrors backend/app/schemas/career_role.py exactly -- field-for-field,
 * same nullability (Phase 1L).
 *
 * IMPORTANT: required_level/student_score/gap/weight/overall_score are
 * all Pydantic Decimal fields, which this API serializes as JSON
 * STRINGS (same convention as score/percentage/points in
 * types/assessment.ts) -- never parse these into a JS number to do
 * arithmetic client-side; only the backend (app.services.
 * skill_alignment_service) computes these values.
 */

export type AlignmentStatus = "STRONG" | "GAP" | "NOT_ASSESSED";

/** Mirrors `CareerRoleResponse` / the `career_roles` table. */
export interface CareerRole {
  id: string;
  title: string;
  description: string | null;
  category: string | null;
  created_at: string;
  updated_at: string;
}

/** Mirrors `SkillGapSkillResponse`. */
export interface SkillGapSkill {
  skill_id: string;
  skill_name: string;
  required_level: string;
  student_score: string;
  gap: string;
  weight: string;
  status: AlignmentStatus;
}

/** Mirrors `SkillGapResponse` -- the authenticated student's own derived
 * skill evidence compared against one career role. Never contains
 * another student's data. */
export interface SkillGap {
  career_role: CareerRole;
  overall_score: string;
  skills: SkillGapSkill[];
}
