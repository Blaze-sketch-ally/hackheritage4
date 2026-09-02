/** Mirrors backend/app/schemas/faculty_opportunity.py exactly.
 *
 * CORRECTION (Phase F3.4): this used to model `category` (PROJECT/
 * TRAINING/WORKSHOP/MENTORSHIP) over industry_projects/training/
 * workshops/mentorship -- tables the architecture review established are
 * explicitly Student-facing. It now models `source` (INDUSTRY/
 * INSTITUTION) over industry_faculty_opportunities /
 * institution_faculty_opportunities, the two tables built specifically
 * for Faculty participation. `source` is API response metadata only --
 * never a polymorphic database key. */
export const OPPORTUNITY_SOURCES = ["INDUSTRY", "INSTITUTION"] as const;
export type OpportunitySource = (typeof OPPORTUNITY_SOURCES)[number];

export const OPPORTUNITY_SOURCE_LABELS: Record<OpportunitySource, string> = {
  INDUSTRY: "Industry",
  INSTITUTION: "Institution",
};

export interface FacultyOpportunity {
  id: string;
  source: OpportunitySource;
  owner_id: string;
  owner_name: string | null;
  title: string;
  description: string | null;
  location: string | null;
  work_mode: string | null;
  capacity: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: "PUBLISHED";
  created_at: string | null;
  updated_at: string | null;
}

export interface FacultyOpportunityListResponse {
  opportunities: FacultyOpportunity[];
}
