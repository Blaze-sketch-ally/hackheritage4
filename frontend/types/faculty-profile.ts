/** Mirrors backend/app/schemas/faculty_profile.py exactly. */
export interface FacultyProfile {
  id: string;
  designation: string | null;
  department: string | null;
  institution_name: string | null;
  phone: string | null;
  bio: string | null;
  expertise_areas: string[];
  years_of_experience: number | null;
  created_at: string | null;
  updated_at: string | null;
  /** Derived server-side (0-1), never stored -- see the migration's own
   * header for why this isn't a column. */
  completeness: number;
}

export interface FacultyProfileUpdateInput {
  designation?: string | null;
  department?: string | null;
  institution_name?: string | null;
  phone?: string | null;
  bio?: string | null;
  expertise_areas?: string[];
  years_of_experience?: number | null;
}
