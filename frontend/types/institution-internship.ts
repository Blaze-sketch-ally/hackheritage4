// Mirrors backend/app/schemas/institution_internship.py
// (GET /api/v1/institution/internships...).
//
// Institution-Curated Internships. There is no
// institution_internship_applications table -- application/selection
// data still comes from the EXISTING applications table, scoped to
// whichever internships this institution has explicitly curated
// (institution_internships). "Selected" (a student) means exactly what
// it means everywhere else in the Institution module: an application row
// with status = 'SELECTED'. `association_status` is a DIFFERENT concept
// -- whether the INSTITUTION itself curated this internship -- never
// confused with a student's application status or the internship's own
// posting status.

export interface StatusCount {
  status: string;
  count: number;
}

export interface ParticipationBreakdown {
  not_started: number;
  active: number;
  completed: number;
  unknown: number;
}

export interface InstitutionInternshipRow {
  id: string;
  title: string;
  company_name: string | null;
  industry_id: string;
  work_mode: string | null;
  duration_months: number | null;
  stipend_amount: number | null;
  stipend_currency: string | null;
  application_deadline: string | null;
  start_date: string | null;
  /** The underlying internship POSTING's own status (DRAFT/PUBLISHED/CLOSED/ARCHIVED). */
  status: string;
  association_id: string;
  /** ACTIVE ("currently curated") or INACTIVE ("removed by your institution"). */
  association_status: "ACTIVE" | "INACTIVE";
  added_at: string | null;
  applicants_from_institution: number;
  selected_from_institution: number;
}

export interface InstitutionInternshipListResponse {
  internships: InstitutionInternshipRow[];
  mode_options: string[];
  status_options: string[];
}

export interface AvailableInternshipRow {
  id: string;
  title: string;
  company_name: string | null;
  industry_id: string;
  work_mode: string | null;
  duration_months: number | null;
  stipend_amount: number | null;
  stipend_currency: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: string;
}

export interface AvailableInternshipListResponse {
  internships: AvailableInternshipRow[];
  mode_options: string[];
}

export interface InternshipAssociationResponse {
  id: string;
  internship_id: string;
  status: "ACTIVE" | "INACTIVE";
  created_at: string | null;
  updated_at: string | null;
}

export interface InstitutionInternshipApplicant {
  application_id: string;
  student_id: string;
  full_name: string | null;
  username: string | null;
  department: string;
  cgpa: number | null;
  status: string;
  applied_at: string | null;
  /** Only set when status === "SELECTED" -- an ESTIMATE, see participation_note. */
  participation_estimate: "NOT_STARTED" | "ACTIVE" | "COMPLETED" | "UNKNOWN" | null;
  interview: { scheduled_at: string; mode: string; status: string } | null;
}

export interface InstitutionInternshipDetail {
  id: string;
  title: string;
  description: string | null;
  company_name: string | null;
  industry_id: string;
  location: string | null;
  work_mode: string | null;
  duration_months: number | null;
  stipend_amount: number | null;
  stipend_currency: string | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: string;

  association_id: string;
  association_status: "ACTIVE" | "INACTIVE";
  added_at: string | null;

  applicants_from_institution: number;
  selected_from_institution: number;
  participation: ParticipationBreakdown;
  status_distribution: StatusCount[];
  applicants: InstitutionInternshipApplicant[];

  eligibility_note: string;
  participation_note: string;
  privacy_note: string;
}

export interface InternshipKpis {
  curated_internships: number;
  active_internships: number;
  companies: number;
  applicants: number;
  selected_students: number;
  active_participants: number;
  completed_internships: number;
  participation_unknown: number;
}

export interface DepartmentInternshipBreakdown {
  id: string;
  name: string;
  student_count: number;
  participants: number;
  participation_rate: number | null;
  selected_count: number;
  completed_count: number;
}

export interface CompanyInternshipBreakdown {
  company_name: string;
  opportunities: number;
  applicants: number;
  selected: number;
  completed: number;
}

export interface ModeCount {
  mode: string;
  count: number;
}

export interface StipendCurrencyStats {
  currency: string;
  internship_count: number;
  average_stipend: number;
  min_stipend: number;
  max_stipend: number;
}

export interface StipendStats {
  available: boolean;
  note: string;
  by_currency: StipendCurrencyStats[];
}

export interface InstitutionInternshipOverviewResponse {
  kpis: InternshipKpis;
  departments: DepartmentInternshipBreakdown[];
  companies: CompanyInternshipBreakdown[];
  mode_distribution: ModeCount[];
  status_distribution: StatusCount[];
  application_status_distribution: StatusCount[];
  stipend: StipendStats;

  tenancy_note: string;
  eligibility_note: string;
  participation_note: string;
  curation_note: string;
}

export const APPLICATION_STATUS_LABELS: Record<string, string> = {
  APPLIED: "Applied",
  UNDER_REVIEW: "Under Review",
  SHORTLISTED: "Shortlisted",
  INTERVIEW_SCHEDULED: "Interview Scheduled",
  SELECTED: "Selected",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
};

export const PARTICIPATION_LABELS: Record<string, string> = {
  NOT_STARTED: "Not started",
  ACTIVE: "Active",
  COMPLETED: "Completed",
  UNKNOWN: "Unknown",
};
