/** Mirrors backend/app/schemas/faculty_engagement.py exactly (Phase F4.1).
 * A Faculty Engagement is the relationship created once an Industry or
 * Institution accepts a Faculty expression of interest. It is NOT an
 * EOI, NOT an opportunity, NOT an industry_collaboration, and NOT a
 * mentorship relationship -- those remain distinct concepts. */
export const ENGAGEMENT_SOURCES = ["INDUSTRY_EOI", "INSTITUTION_EOI"] as const;
export type EngagementSource = (typeof ENGAGEMENT_SOURCES)[number];

export const ENGAGEMENT_STATUSES = ["PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"] as const;
export type EngagementStatus = (typeof ENGAGEMENT_STATUSES)[number];

export const ENGAGEMENT_STATUS_LABELS: Record<EngagementStatus, string> = {
  PLANNED: "Planned",
  ACTIVE: "Active",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export interface FacultyEngagement {
  id: string;
  source_kind: EngagementSource;
  industry_eoi_id: string | null;
  institution_eoi_id: string | null;
  faculty_id: string;
  organization_id: string;
  status: EngagementStatus;
  start_date: string | null;
  end_date: string | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface FacultyEngagementListResponse {
  engagements: FacultyEngagement[];
}
