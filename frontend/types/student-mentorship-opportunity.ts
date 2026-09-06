// Mirrors backend/app/schemas/student_mentorship_opportunity.py, which is
// itself a read-only adapter over the `industry_mentorship` table
// (database/migrations/031_industry_mentorship.sql). Keep in sync.
//
// A student-facing "mentorship opportunity" is one PUBLISHED
// industry_mentorship row. There is no mentor<->mentee pairing table and
// no request/enrollment model in this architecture, so this type has no
// request fields beyond the `requests_available` flag (always false this
// phase) the backend sends so the UI can render an honest state.
//
// Distinct from types/faculty-student-mentorship (the FACULTY<->STUDENT
// 1:1 mentorship-request feature) -- this is read-only discovery of
// INDUSTRY-published mentorship programs.

export const STUDENT_MENTORSHIP_OPPORTUNITY_WORK_MODES = ["ONSITE", "REMOTE", "HYBRID"] as const;
export type StudentMentorshipOpportunityWorkMode =
  (typeof STUDENT_MENTORSHIP_OPPORTUNITY_WORK_MODES)[number];

export const STUDENT_MENTORSHIP_OPPORTUNITY_WORK_MODE_LABELS: Record<
  StudentMentorshipOpportunityWorkMode,
  string
> = {
  ONSITE: "In person",
  REMOTE: "Online",
  HYBRID: "Hybrid",
};

export interface StudentMentorshipOpportunityOrganizer {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;
}

export interface StudentMentorshipOpportunitySummary {
  id: string;
  title: string;
  description: string;
  location: string;
  work_mode: StudentMentorshipOpportunityWorkMode;
  duration_months: number;
  capacity: number;
  start_date: string | null;
  application_deadline: string | null;
  organizer: StudentMentorshipOpportunityOrganizer | null;
  created_at: string | null;
}

export interface StudentMentorshipOpportunityDetail extends StudentMentorshipOpportunitySummary {
  eligibility_criteria: string | null;
  requests_available: boolean;
}

export interface StudentMentorshipOpportunityListResponse {
  mentorship_opportunities: StudentMentorshipOpportunitySummary[];
}
