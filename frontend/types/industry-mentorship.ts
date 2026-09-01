// Mirrors the `industry_mentorship` table
// (database/migrations/025_industry_mentorship.sql) and
// backend/app/schemas/industry_mentorship.py. Keep all three in sync.
//
// Named `industry-mentorship` (not `mentorship`/`mentorships`) to avoid
// colliding with the future Student mentorship module
// (frontend/app/student/mentorship) or the Collaboration hub
// (frontend/app/collaboration/mentorship) — both untouched, unrelated
// "Coming Soon" stubs. There is no mentor<->mentee pairing, no
// request/enrollment, and no skills/expertise relationship here —
// standalone Industry-side opportunity only (Model C), same precedent as
// industry-project/industry-training/industry-workshop.
//
// Unlike IndustryProject/IndustryTraining/IndustryWorkshop, `location`,
// `work_mode`, `duration_months`, and `capacity` are REQUIRED (matching
// the migration's NOT NULL columns), and `application_deadline` is a
// full timestamp (matching the migration's TIMESTAMPTZ column) — both
// per explicit product decision.

export const MENTORSHIP_STATUSES = ["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"] as const;
export type MentorshipStatus = (typeof MENTORSHIP_STATUSES)[number];

export const MENTORSHIP_STATUS_LABELS: Record<MentorshipStatus, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  CLOSED: "Closed",
  ARCHIVED: "Archived",
};

export const MENTORSHIP_WORK_MODES = ["ONSITE", "REMOTE", "HYBRID"] as const;
export type MentorshipWorkMode = (typeof MENTORSHIP_WORK_MODES)[number];

export const MENTORSHIP_WORK_MODE_LABELS: Record<MentorshipWorkMode, string> = {
  ONSITE: "On-site",
  REMOTE: "Remote",
  HYBRID: "Hybrid",
};

export interface IndustryMentorship {
  id: string;
  industry_id: string;
  title: string;
  description: string;
  location: string;
  work_mode: MentorshipWorkMode;
  duration_months: number;
  capacity: number;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: MentorshipStatus;
  created_at: string | null;
  updated_at: string | null;
}

/** POST body. Always created as DRAFT — no `status`, no `industry_id`.
 * `location`/`work_mode`/`duration_months`/`capacity` are required. */
export interface MentorshipCreate {
  title: string;
  description: string;
  location: string;
  work_mode: MentorshipWorkMode;
  duration_months: number;
  capacity: number;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
}

/** PUT body — partial. Any field omitted is left unchanged. */
export type MentorshipUpdate = Partial<MentorshipCreate>;
