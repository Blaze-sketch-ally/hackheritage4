// Mirrors backend/app/schemas/student_training.py, a read-only adapter
// over `industry_training` (database/migrations/023_industry_training.sql).

export interface StudentTrainingIndustry {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;
}

export interface StudentTraining {
  id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: string | null;
  duration_months: number | null;
  capacity: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: string;
  created_at: string | null;
  industry: StudentTrainingIndustry;
  has_applied: boolean;
}

export interface StudentTrainingListResponse {
  trainings: StudentTraining[];
}
