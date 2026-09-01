// Mirrors the `industry_workshops` table
// (database/migrations/024_industry_workshops.sql) and
// backend/app/schemas/industry_workshop.py. Keep all three in sync.
//
// Named `industry-workshop` (not `workshop`/`workshops`) to avoid
// colliding with the separate, unimplemented academia-industry
// Collaboration feature (009_collaboration.sql) that also mentions
// workshops as part of a broader, unrelated concept. There is no skills
// relationship and no certificate fields here — standalone entity, same
// precedent as industry-project/industry-training.
//
// `duration_days` (not `duration_months`) reflects that a workshop is a
// short event, not a long-running engagement.

export const WORKSHOP_STATUSES = ["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"] as const;
export type WorkshopStatus = (typeof WORKSHOP_STATUSES)[number];

export const WORKSHOP_STATUS_LABELS: Record<WorkshopStatus, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  CLOSED: "Closed",
  ARCHIVED: "Archived",
};

export const WORKSHOP_WORK_MODES = ["ONSITE", "REMOTE", "HYBRID"] as const;
export type WorkshopWorkMode = (typeof WORKSHOP_WORK_MODES)[number];

export const WORKSHOP_WORK_MODE_LABELS: Record<WorkshopWorkMode, string> = {
  ONSITE: "On-site",
  REMOTE: "Remote",
  HYBRID: "Hybrid",
};

export interface IndustryWorkshop {
  id: string;
  industry_id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: WorkshopWorkMode | null;
  duration_days: number | null;
  capacity: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: WorkshopStatus;
  created_at: string | null;
  updated_at: string | null;
}

/** POST body. Always created as DRAFT — no `status`, no `industry_id`. */
export interface WorkshopCreate {
  title: string;
  description: string;
  location: string | null;
  work_mode: WorkshopWorkMode | null;
  duration_days: number | null;
  capacity: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
}

/** PUT body — partial. Any field omitted is left unchanged. */
export type WorkshopUpdate = Partial<WorkshopCreate>;
