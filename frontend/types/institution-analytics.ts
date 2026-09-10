// Mirrors backend/app/schemas/institution.py (InstitutionOverviewResponse).
//
// Student-level fields (studentMetrics, departmentMetrics, studentInsights)
// only ever cover students explicitly linked to this institution account
// (student_profiles.institution_id) -- see `tenancyNote`, always rendered
// in the UI. `platformWide: true` on a field marks data this schema
// cannot scope to one institution (jobs/internships/workshops/company
// directory) -- never label it as "your institution's" in the UI.

export interface StudentMetrics {
  total_linked_students: number;
  placed: number;
  unplaced_active: number;
  not_participating: number;
  placement_percentage: number | null;
}

export interface DepartmentMetric {
  /** Real department name, or "Unassigned" when department_id is null.
   * Grouped by student_profiles.department_id (types/institution-department.ts),
   * not free text. */
  department: string;
  department_id: string | null;
  total_students: number;
  placed_students: number;
  placement_percentage: number | null;
}

export interface RecentOpportunity {
  id: string;
  title: string;
  opportunity_type: "INTERNSHIP" | "JOB";
  company_name: string | null;
  posted_at: string | null;
  applicants_from_your_institution: number;
}

export interface OpportunitiesOverview {
  active_jobs: number;
  active_internships: number;
  recent: RecentOpportunity[];
  platform_wide: true;
}

export interface IndustryOverview {
  total_industry_partners: number;
  recent_postings_count: number;
  platform_wide: true;
}

export interface CollaborationsOverview {
  pending: number;
  active: number;
  total: number;
}

export interface UpcomingEvent {
  id: string;
  title: string;
  event_type: string;
  start_date: string | null;
  organizer: string | null;
  platform_wide: true;
}

export interface SkillCount {
  skill_name: string;
  student_count: number;
}

export interface StudentInsights {
  students_with_no_applications: number;
  students_actively_applying: number;
  top_skills: SkillCount[];
  assessments_completed: number;
  average_assessment_percentage: number | null;
}

export interface InstitutionOverview {
  generated_at: string;
  institution_name: string | null;
  student_metrics: StudentMetrics;
  department_metrics: DepartmentMetric[];
  opportunities: OpportunitiesOverview;
  industry: IndustryOverview;
  collaborations: CollaborationsOverview;
  upcoming_events: UpcomingEvent[];
  student_insights: StudentInsights;
  tenancy_note: string;
  eligibility_note: string;
}
