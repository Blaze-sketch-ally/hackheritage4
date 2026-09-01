// Mirrors the `industry_training` table
// (database/migrations/023_industry_training.sql) and
// backend/app/schemas/industry_training.py. Keep all three in sync.
//
// Named `industry-training` (not `training`/`trainings`) to avoid
// colliding with Faculty's own unimplemented, unrelated "FDP" (Faculty
// Development Programs) feature area, which is also training-shaped.
// There is no skills relationship and no certificate fields here —
// standalone entity, same precedent as industry-project.

export const TRAINING_STATUSES = ["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"] as const;
export type TrainingStatus = (typeof TRAINING_STATUSES)[number];

export const TRAINING_STATUS_LABELS: Record<TrainingStatus, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  CLOSED: "Closed",
  ARCHIVED: "Archived",
};

export const TRAINING_WORK_MODES = ["ONSITE", "REMOTE", "HYBRID"] as const;
export type TrainingWorkMode = (typeof TRAINING_WORK_MODES)[number];

export const TRAINING_WORK_MODE_LABELS: Record<TrainingWorkMode, string> = {
  ONSITE: "On-site",
  REMOTE: "Remote",
  HYBRID: "Hybrid",
};

export interface IndustryTraining {
  id: string;
  industry_id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: TrainingWorkMode | null;
  duration_months: number | null;
  capacity: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: TrainingStatus;
  created_at: string | null;
  updated_at: string | null;
}

/** POST body. Always created as DRAFT — no `status`, no `industry_id`. */
export interface TrainingCreate {
  title: string;
  description: string;
  location: string | null;
  work_mode: TrainingWorkMode | null;
  duration_months: number | null;
  capacity: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
}

/** PUT body — partial. Any field omitted is left unchanged. */
export type TrainingUpdate = Partial<TrainingCreate>;
