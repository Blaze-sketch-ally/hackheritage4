// Mirrors the `industry_projects` table
// (database/migrations/022_industry_projects.sql) and
// backend/app/schemas/industry_project.py. Keep all three in sync.
//
// Named `industry-project` (not `project`) to avoid colliding with the
// still-unbuilt Student Portfolio "projects" feature
// (frontend/app/student/projects) -- a distinct, unrelated feature area.
// There is no skills relationship here: unlike internships/jobs, Projects
// has no application/matching flow yet this phase.

export const PROJECT_STATUSES = ["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"] as const;
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  CLOSED: "Closed",
  ARCHIVED: "Archived",
};

export const PROJECT_WORK_MODES = ["ONSITE", "REMOTE", "HYBRID"] as const;
export type ProjectWorkMode = (typeof PROJECT_WORK_MODES)[number];

export const PROJECT_WORK_MODE_LABELS: Record<ProjectWorkMode, string> = {
  ONSITE: "On-site",
  REMOTE: "Remote",
  HYBRID: "Hybrid",
};

export interface IndustryProject {
  id: string;
  industry_id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: ProjectWorkMode | null;
  duration_months: number | null;
  team_size: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: ProjectStatus;
  created_at: string | null;
  updated_at: string | null;
}

/** POST body. Always created as DRAFT — no `status`, no `industry_id`. */
export interface ProjectCreate {
  title: string;
  description: string;
  location: string | null;
  work_mode: ProjectWorkMode | null;
  duration_months: number | null;
  team_size: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
}

/** PUT body — partial. Any field omitted is left unchanged. */
export type ProjectUpdate = Partial<ProjectCreate>;
