// Mirrors backend/app/schemas/student_event.py, which is itself a
// read-only adapter over the `industry_workshops` table
// (database/migrations/024_industry_workshops.sql). Keep in sync.
//
// A student-facing "event" is one PUBLISHED industry workshop. There is no
// `events` table and no registration/attendance model in this
// architecture, so this type has no registration fields beyond the
// `registration_available` flag (always false this phase) the backend
// sends so the UI can render an honest state.

export const STUDENT_EVENT_WORK_MODES = ["ONSITE", "REMOTE", "HYBRID"] as const;
export type StudentEventWorkMode = (typeof STUDENT_EVENT_WORK_MODES)[number];

export const STUDENT_EVENT_WORK_MODE_LABELS: Record<StudentEventWorkMode, string> = {
  ONSITE: "In person",
  REMOTE: "Online",
  HYBRID: "Hybrid",
};

export interface StudentEventOrganizer {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;
}

export interface StudentEventSummary {
  id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: StudentEventWorkMode | null;
  start_date: string | null;
  application_deadline: string | null;
  duration_days: number | null;
  organizer: StudentEventOrganizer | null;
  created_at: string | null;
}

export interface StudentEventDetail extends StudentEventSummary {
  capacity: number | null;
  eligibility_criteria: string | null;
  registration_available: boolean;
}

export interface StudentEventListResponse {
  events: StudentEventSummary[];
}
