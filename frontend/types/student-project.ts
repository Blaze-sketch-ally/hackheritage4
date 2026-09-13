// Mirrors backend/app/schemas/student_project.py, a read-only adapter
// over `industry_projects` (database/migrations/022_industry_projects.sql).
// Named "student-project" for the type but surfaced at the
// /student/industry-projects route to avoid colliding with the existing
// Student Portfolio "projects" feature.

export interface StudentProjectIndustry {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;
}

export interface StudentProject {
  id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: string | null;
  duration_months: number | null;
  team_size: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: string;
  created_at: string | null;
  industry: StudentProjectIndustry;
  has_applied: boolean;
}

export interface StudentProjectListResponse {
  projects: StudentProject[];
}
