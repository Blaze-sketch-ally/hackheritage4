// Mirrors the `industry_profiles` table (database/migrations/
// 017_industry_profiles.sql) and backend/app/schemas/industry.py
// (IndustryProfileResponse / IndustryProfileUpdate). Keep all three in
// sync — every field here has a real column behind it.

export const COMPANY_SIZES = [
  "1-10",
  "11-50",
  "51-200",
  "201-500",
  "501-1000",
  "1000+",
] as const;

export type CompanySize = (typeof COMPANY_SIZES)[number];

export const COMPANY_SIZE_LABELS: Record<CompanySize, string> = {
  "1-10": "1–10 employees",
  "11-50": "11–50 employees",
  "51-200": "51–200 employees",
  "201-500": "201–500 employees",
  "501-1000": "501–1,000 employees",
  "1000+": "1,000+ employees",
};

/** The editable company-profile fields — everything except identity and
 * timestamps. This is exactly what the edit form submits (PUT body). */
export interface IndustryProfileFields {
  company_name: string | null;
  industry_sector: string | null;
  company_size: CompanySize | null;
  website_url: string | null;
  company_description: string | null;
  headquarters_location: string | null;
  founded_year: number | null;
  contact_phone: string | null;
  linkedin_url: string | null;
  logo_url: string | null;
}

export interface IndustryProfile extends IndustryProfileFields {
  id: string;
  /** Null only in the no-row-yet window — before the company profile is
   * saved for the first time. */
  created_at: string | null;
  updated_at: string | null;
}

export const EMPTY_INDUSTRY_PROFILE_FIELDS: IndustryProfileFields = {
  company_name: null,
  industry_sector: null,
  company_size: null,
  website_url: null,
  company_description: null,
  headquarters_location: null,
  founded_year: null,
  contact_phone: null,
  linkedin_url: null,
  logo_url: null,
};

const COMPLETION_FIELDS: Array<keyof IndustryProfileFields> = [
  "company_name",
  "industry_sector",
  "company_size",
  "website_url",
  "company_description",
  "headquarters_location",
  "founded_year",
  "contact_phone",
  "linkedin_url",
  "logo_url",
];

/** Share of the company profile that's filled in, derived directly from
 * the fields — there is no stored completion column. */
export function getIndustryProfileCompletion(fields: IndustryProfileFields): number {
  const filled = COMPLETION_FIELDS.filter((key) => {
    const value = fields[key];
    return value !== null && value !== "" && value !== undefined;
  }).length;
  return Math.round((filled / COMPLETION_FIELDS.length) * 100);
}
