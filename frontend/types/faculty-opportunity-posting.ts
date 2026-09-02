/** Mirrors backend/app/schemas/faculty_opportunity_posting.py exactly.
 * Shared shape for both industry_faculty_opportunities and
 * institution_faculty_opportunities -- the owner-management side (create/
 * edit/publish/close), as distinct from types/faculty-opportunity.ts
 * (the read-only Faculty discovery side, PUBLISHED rows only). */
export type PostingStatus = "DRAFT" | "PUBLISHED" | "CLOSED";
export type WorkMode = "ONSITE" | "REMOTE" | "HYBRID";

export interface FacultyOpportunityPosting {
  id: string;
  owner_id: string;
  title: string;
  description: string;
  location: string | null;
  work_mode: WorkMode | null;
  capacity: number | null;
  eligibility_criteria: string | null;
  application_deadline: string | null;
  start_date: string | null;
  status: PostingStatus;
  created_at: string | null;
  updated_at: string | null;
}

export interface FacultyOpportunityPostingListResponse {
  opportunities: FacultyOpportunityPosting[];
}

export interface FacultyOpportunityPostingInput {
  title: string;
  description: string;
  location?: string | null;
  work_mode?: WorkMode | null;
  capacity?: number | null;
  eligibility_criteria?: string | null;
  application_deadline?: string | null;
  start_date?: string | null;
}
