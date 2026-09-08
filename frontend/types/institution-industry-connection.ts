// Mirrors backend/app/schemas/institution_industry_connection.py
// (GET /api/v1/institution/industry-connections...).
//
// PHASE 9. The canonical company identity is still the EXISTING
// industry profile (industry_profiles) -- a connection never carries its
// own company name/logo; those are always resolved live by industry_id,
// same as types/institution-industry.ts's IndustryPartnerRow.

export const CONTACT_TYPES = ["RECRUITMENT", "ACADEMIC", "INTERNSHIP", "PARTNERSHIP", "TRAINING", "OTHER"] as const;
export type ContactType = (typeof CONTACT_TYPES)[number];

export const CONTACT_TYPE_LABELS: Record<string, string> = {
  RECRUITMENT: "Recruitment",
  ACADEMIC: "Academic",
  INTERNSHIP: "Internship",
  PARTNERSHIP: "Partnership",
  TRAINING: "Training",
  OTHER: "Other",
};

export interface IndustryConnectionCreate {
  industry_id: string;
  contact_name: string;
  designation?: string | null;
  contact_type?: ContactType;
  email?: string | null;
  phone?: string | null;
  notes?: string | null;
}

export interface IndustryConnectionUpdate {
  contact_name?: string;
  designation?: string | null;
  contact_type?: ContactType;
  email?: string | null;
  phone?: string | null;
  notes?: string | null;
  is_active?: boolean;
}

export interface IndustryConnectionRow {
  id: string;
  industry_id: string;
  company_name: string | null;
  industry_sector: string | null;
  logo_url: string | null;

  contact_name: string;
  designation: string | null;
  contact_type: string;
  email: string | null;
  phone: string | null;
  notes: string | null;
  is_active: boolean;

  created_at: string | null;
  updated_at: string | null;
}

export interface IndustryConnectionListResponse {
  connections: IndustryConnectionRow[];
  type_options: string[];
}
