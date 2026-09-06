// Mirrors backend/app/schemas/student_institution.py
// (GET /api/v1/student/institution).
//
// PHASE 12. No new institution-relationship table -- reads
// student_profiles.institution_id (set only by the existing
// institution_link_requests approval workflow), institution_profiles,
// departments, placement_drives, institution_internships + internships,
// institution_events and the student's own applications. "Curated"
// internships means institution_internships.status = 'ACTIVE' only --
// never every PUBLISHED internship on the platform.

export interface StudentInstitutionIdentity {
  id: string;
  institution_name: string | null;
  institution_type: string | null;
  location: string | null;
  website_url: string | null;
}

export interface StudentInstitutionProfile {
  department_id: string | null;
  department: string | null;
  batch: number | null;
  cgpa: number | null;
  verified_at: string | null;
}

export interface StudentInstitutionKpis {
  placement_drives: number;
  internships: number;
  events: number;
  active_applications: number;
}

export interface StudentPlacementDriveRow {
  id: string;
  title: string;
  description: string | null;
  status: string;
  application_deadline: string | null;
  drive_date: string | null;
  mode: string | null;
  venue: string | null;
  company_name: string | null;
  job_id: string;
  is_eligible: boolean;
  eligibility_reasons: string[];
  already_applied: boolean;
  application_status: string | null;
}

export interface StudentCuratedInternshipRow {
  id: string;
  title: string;
  description: string | null;
  company_name: string | null;
  work_mode: string | null;
  duration_months: number | null;
  stipend_amount: number | null;
  stipend_currency: string | null;
  application_deadline: string | null;
  start_date: string | null;
  eligibility_criteria: string | null;
  already_applied: boolean;
  application_status: string | null;
}

export interface StudentInstitutionEventRow {
  id: string;
  title: string;
  description: string | null;
  event_type: string;
  mode: string | null;
  venue: string | null;
  start_at: string | null;
  end_at: string | null;
  company_name: string | null;
  is_relevant_to_me: boolean;
}

export interface StudentActivityItem {
  type: "INSTITUTION_VERIFIED" | "INTERNSHIP_APPLIED" | "PLACEMENT_APPLIED" | "SELECTED";
  label: string;
  occurred_at: string;
}

export interface StudentInstitutionResponse {
  linked: boolean;
  institution: StudentInstitutionIdentity | null;
  profile: StudentInstitutionProfile | null;
  kpis: StudentInstitutionKpis;
  placement_drives: StudentPlacementDriveRow[];
  internships: StudentCuratedInternshipRow[];
  events: StudentInstitutionEventRow[];
  activity: StudentActivityItem[];

  curation_note: string;
  eligibility_note: string;
  registration_note: string;
}

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
