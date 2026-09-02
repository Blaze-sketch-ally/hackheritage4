/**
 * Mirrors backend/app/schemas/student_portfolio.py -- field-for-field,
 * same nullability.
 *
 * Backed by database/migrations/034_student_portfolio.sql:
 * `student_projects`, `student_project_skills` (project -> canonical
 * `skills`), `student_certifications`, `student_achievements` -- all
 * owner-only.
 *
 * A project / certification / achievement is PORTFOLIO EVIDENCE ONLY:
 * there is no score, proficiency, or verification field here, because the
 * backend has none. Associating a skill with a project never touches
 * `student_skills` and never verifies a skill.
 *
 * `student_id` never appears -- every request derives identity from the
 * authenticated token (require_student -> current_user.id).
 */

// ---- Projects ----

export interface ProjectSkillRef {
  skill_id: string;
  skill_name: string;
  category_name: string | null;
}

export interface StudentProject {
  id: string;
  title: string;
  description: string | null;
  project_url: string | null;
  repo_url: string | null;
  start_date: string | null;
  end_date: string | null;
  is_ongoing: boolean;
  skills: ProjectSkillRef[];
  created_at: string | null;
  updated_at: string | null;
}

/** POST / PUT body. Only these fields; the backend rejects anything else. */
export interface ProjectInput {
  title: string;
  description?: string | null;
  project_url?: string | null;
  repo_url?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  is_ongoing?: boolean;
  skill_ids?: string[];
}

export interface ProjectListResponse {
  projects: StudentProject[];
}

// ---- Certifications ----

export interface StudentCertification {
  id: string;
  name: string;
  issuing_organization: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  credential_id: string | null;
  credential_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CertificationInput {
  name: string;
  issuing_organization?: string | null;
  issue_date?: string | null;
  expiry_date?: string | null;
  credential_id?: string | null;
  credential_url?: string | null;
}

export interface CertificationListResponse {
  certifications: StudentCertification[];
}

// ---- Achievements ----

export interface StudentAchievement {
  id: string;
  title: string;
  description: string | null;
  achievement_date: string | null;
  issuing_organization: string | null;
  url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AchievementInput {
  title: string;
  description?: string | null;
  achievement_date?: string | null;
  issuing_organization?: string | null;
  url?: string | null;
}

export interface AchievementListResponse {
  achievements: StudentAchievement[];
}

// ---- Portfolio aggregate (read-only) ----

export interface PortfolioSkillRef {
  skill_id: string;
  skill_name: string;
  category_name: string | null;
  proficiency_level: string;
  is_verified: boolean;
}

export interface PortfolioResponse {
  projects: StudentProject[];
  certifications: StudentCertification[];
  achievements: StudentAchievement[];
  skills: PortfolioSkillRef[];
}

// ---- display helpers ----

/** "Jan 2026 – Mar 2026", "Jan 2026 – Present", "Jan 2026", or "". Dates
 * are ISO `YYYY-MM-DD` strings from the API. */
export function formatDateRange(
  start: string | null,
  end: string | null,
  ongoing: boolean,
): string {
  const fmt = (d: string) => {
    const parsed = new Date(`${d}T00:00:00`);
    return Number.isNaN(parsed.getTime())
      ? d
      : parsed.toLocaleDateString(undefined, { month: "short", year: "numeric" });
  };
  if (!start && !end) return ongoing ? "Ongoing" : "";
  const left = start ? fmt(start) : "";
  const right = ongoing ? "Present" : end ? fmt(end) : "";
  if (left && right) return `${left} – ${right}`;
  return left || right;
}

export function formatMonthYear(d: string | null): string {
  if (!d) return "";
  const parsed = new Date(`${d}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? d
    : parsed.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}
