// Mirrors the `jobs` + `job_skills` tables
// (database/migrations/019_jobs.sql) and backend/app/schemas/job.py.
// Keep all three in sync.
//
// `jobs` differs from `internships`: it has `employment_type` and
// `experience_min_years`, a salary *range* (salary_min / salary_max /
// salary_currency), and no `duration_months` / `start_date` / stipend.

import type { SkillRequirement, SkillRequirementInput } from "@/types/skill-requirement";

export {
  REQUIRED_LEVELS,
  SKILL_IMPORTANCES,
  SKILL_IMPORTANCE_LABELS,
} from "@/types/skill-requirement";
export type { RequiredLevel, SkillImportance } from "@/types/skill-requirement";

export const JOB_STATUSES = ["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
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

export const EMPLOYMENT_TYPES = ["FULL_TIME", "PART_TIME", "CONTRACT"] as const;
export type EmploymentType = (typeof EMPLOYMENT_TYPES)[number];

export const EMPLOYMENT_TYPE_LABELS: Record<EmploymentType, string> = {
  FULL_TIME: "Full-time",
  PART_TIME: "Part-time",
  CONTRACT: "Contract",
};

/** A skill requirement as returned on a job (catalog data joined in). */
export type JobSkill = SkillRequirement;

/** A skill requirement as sent to the API on create/update. */
export type JobSkillInput = SkillRequirementInput;

export interface Job {
  id: string;
  industry_id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: WorkMode | null;
  employment_type: EmploymentType | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  experience_min_years: number | null;
  openings: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  status: JobStatus;
  created_at: string | null;
  updated_at: string | null;
  skills: JobSkill[];
}

/** POST body. Always created as DRAFT — no `status`, no `industry_id`. */
export interface JobCreate {
  title: string;
  description: string;
  location: string | null;
  work_mode: WorkMode | null;
  employment_type: EmploymentType | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  experience_min_years: number | null;
  openings: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  skills: JobSkillInput[];
}

/** PUT body — partial. Any field omitted is left unchanged; `skills`
 * omitted leaves the list alone, a list replaces it. */
export type JobUpdate = Partial<JobCreate>;
