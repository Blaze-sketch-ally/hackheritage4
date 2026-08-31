-- Migration: 025_portfolio_projects_and_certifications
-- Purpose: Phase 1N -- the Digital Portfolio. Two normalized,
-- student-owned tables (portfolio_projects, portfolio_certifications),
-- not a single generic "portfolio" table -- the two concepts have
-- distinct fields and no shared query pattern that would justify merging
-- them.
--
-- This is the schema 007/008_portfolio.sql's own header comment
-- deferred ("Not implemented yet -- schema defined when the Portfolio
-- feature is built."). That file is left byte-identical -- historical
-- migrations are never rewritten -- this migration is what it was
-- deferring to.
--
-- ============================================================
-- Historical-integrity boundary (extends the law established by
-- 022_career_roles_skill_gap.sql and
-- 024_opportunities_and_applications.sql)
-- ============================================================
--
-- Portfolio rows are a NEW, fourth kind of evidence, distinct from the
-- three that already exist:
--
--   student_skills (003_skills.sql)        -- self-reported, unverified
--   assessment evidence (assessment_attempts) -- objectively derived
--   portfolio_projects / portfolio_certifications (this migration) --
--     student-presented work/context, authored by the student, never
--     scored, never converted into skill evidence
--
-- Portfolio content (e.g. a project's `technologies` array) is NEVER
-- automatically written into student_skills, never alters
-- assessment-derived skill scores, and is never treated as trusted
-- assessment evidence by opportunity_service/application_service's
-- matching -- compute_alignment() (app.services.skill_alignment_service,
-- unmodified since Phase 1L) is never called with anything derived from
-- these two tables. A future explicit "infer skills from portfolio"
-- feature, if ever built, would need its own evidence model -- not a
-- silent write into either of these two systems.
--
-- ============================================================
-- RLS ownership design
-- ============================================================
--
-- Student CRUD needs no SECURITY DEFINER helper and no service-role
-- access: RLS's own symmetric USING/WITH CHECK on UPDATE already
-- prevents student_id reassignment for free, because the owner of a row
-- (auth.uid() = student_id) is the same identity permitted to write to
-- it -- unlike applications (owned by the applying student, but written
-- by the *industry* owner of the opportunity), which is why that table
-- needed an explicit trigger
-- (prevent_unauthorized_application_change) to block reassignment.
-- Here, a student attempting `UPDATE ... SET student_id = <someone
-- else>` still passes the USING clause against their own existing row,
-- but fails the WITH CHECK clause against the new row (auth.uid() no
-- longer equals the new student_id) -- RLS rejects the write outright.
--
-- Industry visibility reuses the exact join-through-ownership-chain
-- shape already proven safe by 024_opportunities_and_applications.sql's
-- "Industry can view profiles of their own applicants" policy:
--
--   industry (auth.uid()) -> owns opportunity -> student applied
--   (applications.student_id) -> industry may SELECT that student's
--   portfolio rows
--
-- No new SECURITY DEFINER function is needed (is_student/is_industry
-- already exist, from 003_skills.sql/013_harden_is_student.sql and
-- 024_opportunities_and_applications.sql respectively) and no
-- service-role access is introduced anywhere in this migration or in
-- the portfolio API built on top of it -- normal RLS fully satisfies
-- every access pattern this feature needs, including the industry
-- applicant-portfolio read (backend/app/api/applications.py's
-- GET /applications/{id}/portfolio proves application ownership via the
-- caller's own RLS-scoped application_service.get_application() first,
-- then reads the portfolio through that SAME caller-scoped client --
-- this table's own SELECT policy below is what actually authorizes
-- that second read, independently).
--
-- No RLS recursion risk: the EXISTS subquery below joins through
-- applications -> opportunities, exactly the shape already proven safe
-- in migration 024 -- neither of those tables' own policies subqueries
-- back into portfolio_projects/portfolio_certifications.

-- ============================================================
-- portfolio_projects
-- ============================================================

create table if not exists portfolio_projects (
  id uuid primary key default gen_random_uuid(),

  -- cascade: a project has no independent meaning once the owning
  -- account is gone -- same reasoning as opportunities.industry_id
  -- (024_opportunities_and_applications.sql).
  student_id uuid not null references profiles (id) on delete cascade,

  title text not null check (length(trim(title)) > 0),
  description text not null check (length(trim(description)) > 0),

  -- Descriptive portfolio metadata only -- never resolved to skill_id
  -- rows, never written into student_skills. See this migration's own
  -- header comment.
  technologies text[] not null default '{}',

  project_url text,
  github_url text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists portfolio_projects_student_id_idx
  on portfolio_projects (student_id);

alter table portfolio_projects enable row level security;

create policy "Students can view their own projects"
  on portfolio_projects for select
  to authenticated
  using (auth.uid() = student_id);

create policy "Industry can view projects of their own applicants"
  on portfolio_projects for select
  to authenticated
  using (
    public.is_industry(auth.uid())
    and exists (
      select 1
      from applications a
      join opportunities o on o.id = a.opportunity_id
      where a.student_id = portfolio_projects.student_id
        and o.industry_id = auth.uid()
    )
  );

create policy "Students can insert their own projects"
  on portfolio_projects for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

create policy "Students can update their own projects"
  on portfolio_projects for update
  to authenticated
  using (auth.uid() = student_id)
  with check (auth.uid() = student_id);

create policy "Students can delete their own projects"
  on portfolio_projects for delete
  to authenticated
  using (auth.uid() = student_id);

drop trigger if exists portfolio_projects_set_updated_at on portfolio_projects;
create trigger portfolio_projects_set_updated_at
  before update on portfolio_projects
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- portfolio_certifications
-- ============================================================

create table if not exists portfolio_certifications (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,

  name text not null check (length(trim(name)) > 0),
  issuer text not null check (length(trim(issuer)) > 0),
  issue_date date,
  credential_url text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists portfolio_certifications_student_id_idx
  on portfolio_certifications (student_id);

alter table portfolio_certifications enable row level security;

create policy "Students can view their own certifications"
  on portfolio_certifications for select
  to authenticated
  using (auth.uid() = student_id);

create policy "Industry can view certifications of their own applicants"
  on portfolio_certifications for select
  to authenticated
  using (
    public.is_industry(auth.uid())
    and exists (
      select 1
      from applications a
      join opportunities o on o.id = a.opportunity_id
      where a.student_id = portfolio_certifications.student_id
        and o.industry_id = auth.uid()
    )
  );

create policy "Students can insert their own certifications"
  on portfolio_certifications for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

create policy "Students can update their own certifications"
  on portfolio_certifications for update
  to authenticated
  using (auth.uid() = student_id)
  with check (auth.uid() = student_id);

create policy "Students can delete their own certifications"
  on portfolio_certifications for delete
  to authenticated
  using (auth.uid() = student_id);

drop trigger if exists portfolio_certifications_set_updated_at on portfolio_certifications;
create trigger portfolio_certifications_set_updated_at
  before update on portfolio_certifications
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- Explicitly NOT built in this migration
-- ============================================================
--
-- Faculty/institution/admin portfolio access: no policy grants it. Only
-- the owning student (full CRUD) and an industry account with a real,
-- current applications row proving the relationship (SELECT only) can
-- ever see a portfolio row -- see this migration's own header comment
-- for the full authorization chain.
--
-- File storage, portfolio visibility toggles, skill inference from
-- `technologies`, portfolio scoring: explicitly out of scope for Phase
-- 1N -- see the Phase 1N master prompt's own "DO NOT OVERBUILD" section.
