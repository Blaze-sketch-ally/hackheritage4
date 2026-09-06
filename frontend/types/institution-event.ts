// Mirrors backend/app/schemas/institution_event.py
// (GET /api/v1/institution/events...).
//
// PHASE 10. `industry_workshops` remains the ONLY entity a company uses
// to post its own event -- untouched by this module. `institution_events`
// is additive, for sessions the INSTITUTION itself organizes. The
// directory is a UNION of both: `source` tells you which one a row is
// ("INSTITUTION" = this institution organizes and can edit it;
// "INDUSTRY_WORKSHOP" = a platform-wide published company workshop,
// strictly read-only here). There is NO registration or attendance
// tracking anywhere in this schema -- see `registration_note`, always
// rendered, rather than a fabricated count.

export const EVENT_TYPES = [
  "SEMINAR",
  "WORKSHOP",
  "GUEST_LECTURE",
  "INDUSTRY_TALK",
  "TRAINING",
  "FDP",
  "CAREER_SESSION",
  "PLACEMENT_ORIENTATION",
  "OTHER",
] as const;
export type EventType = (typeof EVENT_TYPES)[number];

export const EVENT_STATUSES = ["DRAFT", "PUBLISHED", "ONGOING", "COMPLETED", "CANCELLED"] as const;
export type EventStatus = (typeof EVENT_STATUSES)[number];

export const EVENT_MODES = ["ONSITE", "REMOTE", "HYBRID"] as const;
export type EventMode = (typeof EVENT_MODES)[number];

export type EventSource = "INSTITUTION" | "INDUSTRY_WORKSHOP";

export const EVENT_TYPE_LABELS: Record<string, string> = {
  SEMINAR: "Seminar",
  WORKSHOP: "Workshop",
  GUEST_LECTURE: "Guest Lecture",
  INDUSTRY_TALK: "Industry Talk",
  TRAINING: "Training",
  FDP: "FDP",
  CAREER_SESSION: "Career Session",
  PLACEMENT_ORIENTATION: "Placement Orientation",
  OTHER: "Other",
};

export const EVENT_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  ONGOING: "Ongoing",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export interface InstitutionEventCreate {
  title: string;
  description?: string | null;
  event_type?: EventType;
  industry_id?: string | null;
  mode?: EventMode | null;
  venue?: string | null;
  start_at?: string | null;
  end_at?: string | null;
  registration_deadline?: string | null;
  target_department_ids?: string[];
  target_batches?: number[];
  includes_faculty?: boolean;
  instructions?: string | null;
}

export type InstitutionEventUpdate = Partial<InstitutionEventCreate>;

export interface EventRow {
  id: string;
  source: EventSource;
  title: string;
  event_type: string;
  status: string;
  industry_id: string | null;
  company_name: string | null;
  mode: string | null;
  venue: string | null;
  start_at: string | null;
  end_at: string | null;
  registration_deadline: string | null;
  target_department_ids: string[];
  target_department_names: string[];
  target_batches: number[];
  includes_faculty: boolean;
  platform_wide: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface EventDetail extends EventRow {
  description: string | null;
  instructions: string | null;
  registration_note: string;
}

export interface EventListResponse {
  events: EventRow[];
  type_options: string[];
  status_options: string[];
  mode_options: string[];
  registration_note: string;
}

export interface EventKpis {
  total_events: number;
  upcoming_events: number;
  ongoing_events: number;
  completed_events: number;
  industry_events: number;
  institution_organized_events: number;
  platform_workshops: number;
}

export interface EventOverviewResponse {
  kpis: EventKpis;
  tenancy_note: string;
  registration_note: string;
}
