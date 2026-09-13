// Mirrors backend/app/schemas/student_workshop.py, a read-only adapter
// over `industry_workshops` (database/migrations/024_industry_workshops.sql).

export interface StudentWorkshopIndustry {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;
}

export interface StudentWorkshop {
  id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: string | null;
  duration_days: number | null;
  capacity: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: string;
  created_at: string | null;
  industry: StudentWorkshopIndustry;
  has_applied: boolean;
}

export interface StudentWorkshopListResponse {
  workshops: StudentWorkshop[];
}
