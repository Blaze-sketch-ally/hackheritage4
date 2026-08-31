/**
 * Mirrors backend/app/schemas/portfolio.py exactly -- field-for-field,
 * same nullability (Phase 1N). Two normalized resources (projects,
 * certifications), not a single generic "portfolio" shape -- see
 * database/migrations/025_portfolio_projects_and_certifications.sql's
 * own header comment for why they aren't merged.
 */

export interface Project {
  id: string;
  student_id: string;
  title: string;
  description: string;
  technologies: string[];
  project_url: string | null;
  github_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateInput {
  title: string;
  description: string;
  technologies: string[];
  project_url?: string | null;
  github_url?: string | null;
}

/** Mirrors `ProjectUpdateRequest` -- every field optional, partial update. */
export interface ProjectUpdateInput {
  title?: string;
  description?: string;
  technologies?: string[];
  project_url?: string | null;
  github_url?: string | null;
}

export interface Certification {
  id: string;
  student_id: string;
  name: string;
  issuer: string;
  issue_date: string | null;
  credential_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface CertificationCreateInput {
  name: string;
  issuer: string;
  issue_date?: string | null;
  credential_url?: string | null;
}

export interface CertificationUpdateInput {
  name?: string;
  issuer?: string;
  issue_date?: string | null;
  credential_url?: string | null;
}

/** Mirrors `PortfolioResponse` -- the combined view returned by both
 * GET /portfolio (student, own) and GET /applications/{id}/portfolio
 * (industry, a legitimate applicant's) -- same shape either way, RLS
 * alone decides what each caller sees. */
export interface Portfolio {
  student_id: string;
  projects: Project[];
  certifications: Certification[];
}
