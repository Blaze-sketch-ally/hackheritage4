// Mirrors the `internships` + `internship_skills` tables
// (database/migrations/018_internships.sql) and
// backend/app/schemas/internship.py. Keep all three in sync.
//
// The migration models compensation as a single `stipend_amount` +
// `stipend_currency` (not a min/max range), internship length as
// `duration_months`, and mode as `work_mode` — these types follow the
// real columns.

export const INTERNSHIP_STATUSES = ["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"] as const;
export type InternshipStatus = (typeof INTERNSHIP_STATUSES)[number];

export const INTERNSHIP_STATUS_LABELS: Record<InternshipStatus, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  CLOSED: "Closed",
  ARCHIVED: "Archived",
};

export const WORK_MODES = ["ONSITE", "REMOTE", "HYBRID"] as const;
export type WorkMode = (typeof WORK_MODES)[number];

export const WORK_MODE_LABELS: Record<WorkMode, string> = {
  ONSITE: "On-site",
  REMOTE: "Remote",
  HYBRID: "Hybrid",
};

// The level/importance skill-requirement primitives are shared with jobs.
export {
  REQUIRED_LEVELS,
  SKILL_IMPORTANCES,
  SKILL_IMPORTANCE_LABELS,
} from "@/types/skill-requirement";
export type { RequiredLevel, SkillImportance } from "@/types/skill-requirement";

import type { SkillRequirement, SkillRequirementInput } from "@/types/skill-requirement";

/** A skill requirement as returned on an internship (catalog data joined in). */
export type InternshipSkill = SkillRequirement;

/** A skill requirement as sent to the API on create/update. */
export type InternshipSkillInput = SkillRequirementInput;

export interface Internship {
  id: string;
  industry_id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: WorkMode | null;
  duration_months: number | null;
  stipend_amount: number | null;
  stipend_currency: string | null;
  openings: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: InternshipStatus;
  created_at: string | null;
  updated_at: string | null;
  skills: InternshipSkill[];
}

/** POST body. Always created as DRAFT — no `status`, no `industry_id`. */
export interface InternshipCreate {
  title: string;
  description: string;
  location: string | null;
  work_mode: WorkMode | null;
  duration_months: number | null;
  stipend_amount: number | null;
  stipend_currency: string | null;
  openings: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  skills: InternshipSkillInput[];
}

/** PUT body — partial. Any field omitted is left unchanged; `skills`
 * omitted leaves the list alone, a list replaces it. */
export type InternshipUpdate = Partial<InternshipCreate>;
