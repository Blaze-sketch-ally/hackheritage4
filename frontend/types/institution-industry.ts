// Mirrors backend/app/schemas/institution_industry.py
// (GET /api/v1/institution/industry-partners...).
//
// PHASE 8. The canonical company identity is the EXISTING industry
// profile (types/industry.ts-equivalent backend: industry_profiles) --
// there is no second company entity here. `relationship_*` fields are
// null when no institution_industry_partners row exists for this
// company yet (`has_explicit_relationship` makes that explicit).

export const RELATIONSHIP_TYPES = [
  "RECRUITMENT",
  "INTERNSHIP",
  "INDUSTRY_INTERACTION",
  "COLLABORATION",
  "TRAINING",
  "OTHER",
] as const;
export type IndustryPartnerRelationshipType = (typeof RELATIONSHIP_TYPES)[number];

export const RELATIONSHIP_STATUSES = ["PROSPECT", "ACTIVE", "INACTIVE"] as const;
export type IndustryPartnerStatus = (typeof RELATIONSHIP_STATUSES)[number];

export const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  RECRUITMENT: "Recruitment",
  INTERNSHIP: "Internship",
  INDUSTRY_INTERACTION: "Industry Interaction",
  COLLABORATION: "Collaboration",
  TRAINING: "Training",
  OTHER: "Other",
};

export const RELATIONSHIP_STATUS_LABELS: Record<string, string> = {
  PROSPECT: "Prospect",
  ACTIVE: "Active",
  INACTIVE: "Inactive",
};

export interface CompanyOption {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;
}

export interface CompanyOptionListResponse {
  companies: CompanyOption[];
}

export interface IndustryPartnerRelationshipCreate {
  industry_id: string;
  relationship_type?: IndustryPartnerRelationshipType;
  relationship_status?: IndustryPartnerStatus;
  notes?: string | null;
}

export interface IndustryPartnerRelationshipUpdate {
  relationship_type?: IndustryPartnerRelationshipType;
  relationship_status?: IndustryPartnerStatus;
  notes?: string | null;
}

export interface IndustryPartnerRelationshipResponse {
  id: string;
  industry_id: string;
  relationship_type: string;
  relationship_status: string;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface IndustryPartnerRow {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;
  website_url: string | null;
  headquarters_location: string | null;

  relationship_id: string | null;
  relationship_type: string | null;
  relationship_status: string | null;
  has_explicit_relationship: boolean;

  jobs_opportunities: number;
  jobs_selected_students: number;
  internship_opportunities: number;
  internship_selected: number;
  placement_drives_count: number;
  students_selected: number;
  last_activity_at: string | null;
}

export interface IndustryPartnerListResponse {
  partners: IndustryPartnerRow[];
  type_options: string[];
  status_options: string[];
}

export interface JobActivitySummary {
  opportunities: number;
  applicants: number;
  selected_students: number;
  titles: string[];
}

export interface InternshipActivitySummary {
  opportunities: number;
  applicants: number;
  selected: number;
  completed: number;
  titles: string[];
}

export interface DriveRow {
  id: string;
  title: string;
  status: string;
  applied_count: number;
  selected_count: number;
  selection_rate: number | null;
}

export interface PlacementDriveActivitySummary {
  count: number;
  unique_students_selected: number;
  drives: DriveRow[];
}

export interface CollaborationSummary {
  count: number;
  latest_status: string | null;
  latest_title: string | null;
}

export interface IndustryPartnerDetail {
  id: string;
  company_name: string | null;
  industry_sector: string | null;
  company_size: string | null;
  website_url: string | null;
  headquarters_location: string | null;
  company_description: string | null;
  logo_url: string | null;
  linkedin_url: string | null;

  relationship_id: string | null;
  relationship_type: string | null;
  relationship_status: string | null;
  notes: string | null;
  has_explicit_relationship: boolean;

  jobs: JobActivitySummary;
  internships: InternshipActivitySummary;
  placement_drives: PlacementDriveActivitySummary;
  collaborations: CollaborationSummary;
  students_selected: number;
  last_activity_at: string | null;

  tenancy_note: string;
  privacy_note: string;
}

export interface IndustryPartnerMetrics {
  total_partners: number;
  active_partners: number;
  recruiting_partners: number;
  internship_partners: number;
  placement_drives_total: number;
  students_selected_total: number;
  internship_students_total: number;
}

export interface IndustryPartnerMetricsResponse {
  metrics: IndustryPartnerMetrics;
  tenancy_note: string;
}
