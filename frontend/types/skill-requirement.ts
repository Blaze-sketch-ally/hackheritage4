// Skill-requirement primitives shared by internships and jobs — the
// `internship_skills` and `job_skills` tables (migrations 018 / 019) have
// identical columns for the level/importance relationship.

export const REQUIRED_LEVELS = ["Beginner", "Intermediate", "Advanced", "Expert"] as const;
export type RequiredLevel = (typeof REQUIRED_LEVELS)[number];

export const SKILL_IMPORTANCES = ["CORE", "IMPORTANT", "OPTIONAL"] as const;
export type SkillImportance = (typeof SKILL_IMPORTANCES)[number];

export const SKILL_IMPORTANCE_LABELS: Record<SkillImportance, string> = {
  CORE: "Core",
  IMPORTANT: "Important",
  OPTIONAL: "Optional",
};

/** A skill requirement as sent to the API on create/update. */
export interface SkillRequirementInput {
  skill_id: string;
  required_level: RequiredLevel;
  importance: SkillImportance;
}

/** A skill requirement as returned, with catalog data joined in. */
export interface SkillRequirement extends SkillRequirementInput {
  skill_name: string;
  category_name: string | null;
}
