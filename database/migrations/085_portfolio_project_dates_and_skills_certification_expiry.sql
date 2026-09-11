-- Migration: 085_portfolio_project_dates_and_skills_certification_expiry
-- Purpose: extend the Digital Portfolio schema
-- (025_portfolio_projects_and_certifications.sql) with fields a
-- collaborator's parallel migration lineage independently built as a
-- separate `student_projects`/`student_certifications` schema (their
-- 034_student_portfolio.sql). Rather than running two parallel portfolio
-- schemas, this migration ADDs the genuinely new fields onto the
-- existing, already-live portfolio_projects/portfolio_certifications
-- tables -- additive only, no rename, no data migration needed.
--
-- portfolio_projects gains: start_date, end_date, is_ongoing (a project's
-- timeline), plus an optional project -> canonical skill mapping table
-- (portfolio_project_skills), same "evidence only, never student_skills"
-- boundary as the parent migration's own header comment.
--
-- portfolio_certifications gains: expiry_date, credential_id (the
-- issuer's own credential identifier -- distinct from credential_url,
-- which is a link to verify it).
--
-- student_achievements (052_student_achievements.sql) needed no change --
-- the collaborator's parallel lineage's own achievements table is
-- byte-for-byte identical in shape to 052's, so there was nothing to
-- port there.

-- ============================================================
-- portfolio_projects: timeline fields
-- ============================================================

alter table portfolio_projects
  add column if not exists start_date date,
  add column if not exists end_date date,
  -- An ongoing project has no end date. `false` is the safe default for
  -- a project a student is just recording after the fact.
  add column if not exists is_ongoing boolean not null default false;

-- If both dates are given, they must be in order.
alter table portfolio_projects
  drop constraint if exists portfolio_projects_date_order;
alter table portfolio_projects
  add constraint portfolio_projects_date_order
  check (end_date is null or start_date is null or end_date >= start_date);

-- An ongoing project cannot also carry an end date.
alter table portfolio_projects
  drop constraint if exists portfolio_projects_ongoing_has_no_end;
alter table portfolio_projects
  add constraint portfolio_projects_ongoing_has_no_end
  check (not (is_ongoing and end_date is not null));

-- ============================================================
-- portfolio_project_skills -- optional project -> canonical skill edge.
-- PORTFOLIO EVIDENCE ONLY, matching 025's own historical-integrity
-- boundary: adding a row here never touches student_skills, never
-- creates a skill, never verifies anything, and is never read by
-- compute_alignment() / application matching.
-- ============================================================

create table if not exists portfolio_project_skills (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null references portfolio_projects (id) on delete cascade,
  -- restrict, not cascade: a catalog skill referenced by real portfolio
  -- content is protected -- deactivate the skill instead of deleting it.
  skill_id uuid not null references skills (id) on delete restrict,

  created_at timestamptz not null default now(),

  -- One link per (project, skill).
  constraint portfolio_project_skills_unique_pair unique (project_id, skill_id)
);

-- "which skills does this project show" is served by the leading column
-- of the unique index; the reverse ("which projects use skill X") needs
-- its own index since skill_id is an unindexed FK.
create index if not exists portfolio_project_skills_skill_id_idx
  on portfolio_project_skills (skill_id);

alter table portfolio_project_skills enable row level security;

-- Ownership is inherited from the parent portfolio_projects row, same
-- join-through-ownership-chain shape 025 already uses for the industry
-- applicant read.
drop policy if exists "Students can view skills on their own projects" on portfolio_project_skills;
create policy "Students can view skills on their own projects"
  on portfolio_project_skills for select
  to authenticated
  using (
    exists (
      select 1 from portfolio_projects p
      where p.id = portfolio_project_skills.project_id
        and p.student_id = auth.uid()
    )
  );

drop policy if exists "Industry can view skills on projects of their own applicants" on portfolio_project_skills;
create policy "Industry can view skills on projects of their own applicants"
  on portfolio_project_skills for select
  to authenticated
  using (
    public.is_industry(auth.uid())
    and exists (
      select 1
      from portfolio_projects p
      join applications a on a.student_id = p.student_id
      join opportunities o on o.id = a.opportunity_id
      where p.id = portfolio_project_skills.project_id
        and o.industry_id = auth.uid()
    )
  );

drop policy if exists "Students can add skills to their own projects" on portfolio_project_skills;
create policy "Students can add skills to their own projects"
  on portfolio_project_skills for insert
  to authenticated
  with check (
    exists (
      select 1 from portfolio_projects p
      where p.id = portfolio_project_skills.project_id
        and p.student_id = auth.uid()
        and public.is_student(auth.uid())
    )
  );

drop policy if exists "Students can remove skills from their own projects" on portfolio_project_skills;
create policy "Students can remove skills from their own projects"
  on portfolio_project_skills for delete
  to authenticated
  using (
    exists (
      select 1 from portfolio_projects p
      where p.id = portfolio_project_skills.project_id
        and p.student_id = auth.uid()
        and public.is_student(auth.uid())
    )
  );

-- No updated_at / update policy -- a link row is created or deleted,
-- never edited in place.

-- ============================================================
-- portfolio_certifications: expiry + issuer credential id
-- ============================================================

alter table portfolio_certifications
  add column if not exists expiry_date date,
  -- The issuer's own credential identifier -- NOT anything this platform
  -- computes or trusts, and distinct from credential_url (a link to
  -- verify it). Never a skill-verification signal.
  add column if not exists credential_id text;

alter table portfolio_certifications
  drop constraint if exists portfolio_certifications_date_order;
alter table portfolio_certifications
  add constraint portfolio_certifications_date_order
  check (expiry_date is null or issue_date is null or expiry_date >= issue_date);
