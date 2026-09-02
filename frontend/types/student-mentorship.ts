// Mirrors backend/app/schemas/student_mentorship.py, which is itself a
// read-only adapter over the `industry_mentorship` table
// (database/migrations/025_industry_mentorship.sql). Keep in sync.
//
// A student-facing "mentorship opportunity" is one PUBLISHED
// industry_mentorship row. There is no mentor<->mentee pairing table and
// no request/enrollment model in this architecture, so this type has no
// request fields beyond the `requests_available` flag (always false this
// phase) the backend sends so the UI can render an honest state.

export const STUDENT_MENTORSHIP_WORK_MODES = ["ONSITE", "REMOTE", "HYBRID"] as const;
export type StudentMentorshipWorkMode = (typeof STUDENT_MENTORSHIP_WORK_MODES)[number];

export const STUDENT_MENTORSHIP_WORK_MODE_LABELS: Record<StudentMentorshipWorkMode, string> = {
  ONSITE: "In person",
  REMOTE: "Online",
  HYBRID: "Hybrid",
};

export interface StudentMentorshipOrganizer {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;
}

export interface StudentMentorshipSummary {
  id: string;
  title: string;
  description: string;
  location: string;
  work_mode: StudentMentorshipWorkMode;
  duration_months: number;
  capacity: number;
  start_date: string | null;
  application_deadline: string | null;
  organizer: StudentMentorshipOrganizer | null;
  created_at: string | null;
}

export interface StudentMentorshipDetail extends StudentMentorshipSummary {
  eligibility_criteria: string | null;
  requests_available: boolean;
}

export interface StudentMentorshipListResponse {
  mentorship_opportunities: StudentMentorshipSummary[];
}
