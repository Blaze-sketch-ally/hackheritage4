// Mirrors backend/app/schemas/institution_department.py -- the
// Institution Departments module (database/migrations/
// 040_institution_departments.sql).
//
// Student/placement counts reuse the EXACT SAME placement definition as
// the Institution Dashboard and Student Directory (placed = >=1 SELECTED
// application) -- this module never defines "placed" differently.

export interface DepartmentSummary {
  id: string;
  name: string;
  code: string | null;
  description: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;

  student_count: number;
  placed_count: number;
  unplaced_count: number;
  no_applications_count: number;
  /** None when student_count === 0 -- never a fabricated 0%. */
  placement_rate: number | null;
  internship_selected_count: number;
}

export type DepartmentDetail = DepartmentSummary;

export interface DepartmentListResponse {
  departments: DepartmentSummary[];
}

export interface DepartmentFields {
  name: string;
  code: string | null;
  description: string | null;
}

export interface DepartmentUpdateFields {
  name?: string;
  code?: string | null;
  description?: string | null;
  is_active?: boolean;
}
