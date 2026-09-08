// Mirrors the `institution_profiles` table (database/migrations/
// 037_institution_tenancy.sql) and backend/app/schemas/institution.py
// (InstitutionProfileResponse / InstitutionProfileUpdate).

/** The editable institution-profile fields — everything except identity
 * and timestamps. This is exactly what the edit form submits (PUT body). */
export interface InstitutionProfileFields {
  institution_name: string | null;
  institution_type: string | null;
  location: string | null;
  website_url: string | null;
  contact_phone: string | null;
}

export interface InstitutionProfile extends InstitutionProfileFields {
  id: string;
  /** Null only in the no-row-yet window — before the institution profile
   * is saved for the first time. */
  created_at: string | null;
  updated_at: string | null;
}

export const EMPTY_INSTITUTION_PROFILE_FIELDS: InstitutionProfileFields = {
  institution_name: null,
  institution_type: null,
  location: null,
  website_url: null,
  contact_phone: null,
};

const COMPLETION_FIELDS: Array<keyof InstitutionProfileFields> = [
  "institution_name",
  "institution_type",
  "location",
  "website_url",
  "contact_phone",
];

/** Share of the institution profile that's filled in, derived directly
 * from the fields — there is no stored completion column. */
export function getInstitutionProfileCompletion(fields: InstitutionProfileFields): number {
  const filled = COMPLETION_FIELDS.filter((key) => {
    const value = fields[key];
    return value !== null && value !== "" && value !== undefined;
  }).length;
  return Math.round((filled / COMPLETION_FIELDS.length) * 100);
}
