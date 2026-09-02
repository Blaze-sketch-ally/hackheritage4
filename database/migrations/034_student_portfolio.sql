-- Migration: 034_student_portfolio
-- Purpose: the DATABASE FOUNDATION for the Student Portfolio MVP (Phase S2)
-- -- the "Digital Portfolio" stage of the workflow: a student's own
-- projects, certifications, and achievements, plus an optional
-- project -> canonical-skill mapping that is PORTFOLIO EVIDENCE ONLY.
--
-- The Portfolio feature's numbered placeholder was 008_portfolio.sql
-- (never given DDL) -- NOT edited here, following the same "placeholder
-- superseded by a later real migration" pattern used for
-- 005_internships / 006_jobs -> 018 / 019 and 007_learning -> 033. This is
-- the real schema, numbered after this branch's current tip (033).
--
-- ============================================================
-- Live divergent-lineage tables left completely untouched
-- ============================================================
-- The shared Supabase project already carries `portfolio_projects` and
-- `portfolio_certifications` -- thin tables from a contributor's divergent
-- migration lineage that is NOT part of this repo (same situation as
-- `career_roles`, `opportunities`, `faculty_*`). Neither has a repo
-- migration, any backend/service/schema, any frontend code, or a single
-- row. This migration deliberately does NOT adopt, reconcile, alter, or
-- drop them:
--   * they are incomplete for this MVP (no dates, no skill mapping, no
--     credential id / expiry, and there is no achievements table at all);
--   * the established repo posture for divergent/orphan live tables is
--     "leave alone, build our own canonical model" (cf. applications_legacy,
--     and the deliberate non-adoption of the contributor opportunities
--     model).
-- The new tables here use the `student_*` prefix (matching student_skills,
-- student_profiles, student_learning_progress, student_target_job_role),
-- so there is NO name collision with the orphan `portfolio_*` tables on a
-- fresh replay OR on the live project.
--
-- ============================================================
-- Hard architectural boundaries (mandatory)
-- ============================================================
-- * A project / certification / achievement is PORTFOLIO EVIDENCE ONLY.
--   Nothing here reads or writes student_skills. Associating a skill with
--   a project never creates a student_skills row and never changes
--   proficiency_level / proficiency_score / is_verified / verified_at --
--   skill verification stays exclusively the job of
--   score_assessment_attempt() (015_assessment_verification.sql).
-- * No FK to, and no reference to: student_skills, assessments,
--   assessment_attempts, learning_resources, job_roles, career_roles,
--   opportunities, portfolio_projects, portfolio_certifications. The
--   optional project -> skill edge references the canonical `skills`
--   catalog (003_skills.sql) and nothing else.
-- * There is NO `portfolio` table. The portfolio is an aggregation/view
--   over profiles + student_profiles + student_skills + these three
--   entities, composed by the backend read path -- not a stored record.
--   Student identity is never duplicated into these tables.
--
-- ============================================================
-- Conventions reused from existing migrations
-- ============================================================
-- * uuid PK: `id uuid primary key default gen_random_uuid()` (003/004/016/033)
-- * created_at / updated_at timestamptz not null default now() (all)
-- * public.set_updated_at() trigger (012_student_profiles.sql) -- attached,
--   never redefined here.
-- * Student-owned table: `student_id uuid not null references profiles(id)
--   on delete cascade`, ownership predicate
--   `auth.uid() = student_id and public.is_student(auth.uid())` on ALL
--   FOUR directions (select/insert/update/delete) -- same shape as
--   student_skills (003), which also allows the student to delete their
--   own rows. (student_learning_progress omits DELETE by design; portfolio
--   entities need it -- a student manages their own portfolio.)
-- * `skill_id ... references skills(id) on delete restrict` -- protect a
--   catalog skill referenced by real content (same as
--   student_skills.skill_id / job_role_skills.skill_id / 033).
-- * Idempotent in shape: create table if not exists, create index if not
--   exists, drop policy/trigger if exists + create. Forward-only,
--   additive, non-destructive: no DROP TABLE, no destructive ALTER, no
--   change to any existing table, policy, trigger, or function.
--
-- No seed data -- a student's portfolio is created entirely through the
-- authenticated app; there is nothing to pre-populate.

-- ============================================================
-- 1. student_projects -- a project the student built / contributed to.
-- ============================================================
create table if not exists student_projects (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text,

  -- Optional outbound links. No format CHECK -- over-constraining URLs
  -- (scheme/host rules) has bitten other projects (same reasoning as
  -- learning_resources.url in 033); the app validates the shape.
  project_url text,
  repo_url text,

  start_date date,
  end_date date,
  -- An ongoing project has no end date. `false` is the safe default for
  -- a finished project a student is just recording.
  is_ongoing boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- If both dates are given, they must be in order (same loose check
  -- style as student_learning_progress in 033).
  constraint student_projects_date_order
    check (end_date is null or start_date is null or end_date >= start_date),
  -- An ongoing project cannot also carry an end date.
  constraint student_projects_ongoing_has_no_end
    check (not (is_ongoing and end_date is not null))
);

create index if not exists student_projects_student_id_idx
  on student_projects (student_id);

alter table student_projects enable row level security;

drop policy if exists "Students can view their own projects" on student_projects;
create policy "Students can view their own projects"
  on student_projects for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can add their own projects" on student_projects;
create policy "Students can add their own projects"
  on student_projects for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can update their own projects" on student_projects;
create policy "Students can update their own projects"
  on student_projects for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can delete their own projects" on student_projects;
create policy "Students can delete their own projects"
  on student_projects for delete
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop trigger if exists student_projects_set_updated_at on student_projects;
create trigger student_projects_set_updated_at
  before update on student_projects
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 2. student_project_skills -- optional project -> canonical skill edge.
--    PORTFOLIO EVIDENCE ONLY. Adding a row here never touches
--    student_skills, never creates a skill, never verifies anything.
-- ============================================================
create table if not exists student_project_skills (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null references student_projects (id) on delete cascade,
  -- restrict, not cascade: a catalog skill referenced by real portfolio
  -- content is protected -- deactivate the skill instead of deleting it.
  skill_id uuid not null references skills (id) on delete restrict,

  created_at timestamptz not null default now(),

  -- One link per (project, skill).
  constraint student_project_skills_unique_pair unique (project_id, skill_id)
);

-- "which skills does this project show" is served by the leading column
-- of the unique index; the reverse ("which projects use skill X") needs
-- its own index since skill_id is an unindexed FK.
create index if not exists student_project_skills_skill_id_idx
  on student_project_skills (skill_id);

alter table student_project_skills enable row level security;

-- Readable / writable only for a project the caller owns -- ownership is
-- inherited from the parent student_projects row (mirrors 033's
-- learning_resource_skills EXISTS-on-parent pattern, but here the parent
-- is student-owned so the predicate also checks auth.uid()).
drop policy if exists "Students can view skills on their own projects" on student_project_skills;
create policy "Students can view skills on their own projects"
  on student_project_skills for select
  to authenticated
  using (
    exists (
      select 1 from student_projects p
      where p.id = student_project_skills.project_id
        and p.student_id = auth.uid()
        and public.is_student(auth.uid())
    )
  );

drop policy if exists "Students can add skills to their own projects" on student_project_skills;
create policy "Students can add skills to their own projects"
  on student_project_skills for insert
  to authenticated
  with check (
    exists (
      select 1 from student_projects p
      where p.id = student_project_skills.project_id
        and p.student_id = auth.uid()
        and public.is_student(auth.uid())
    )
  );

drop policy if exists "Students can remove skills from their own projects" on student_project_skills;
create policy "Students can remove skills from their own projects"
  on student_project_skills for delete
  to authenticated
  using (
    exists (
      select 1 from student_projects p
      where p.id = student_project_skills.project_id
        and p.student_id = auth.uid()
        and public.is_student(auth.uid())
    )
  );

-- No updated_at / update policy -- a link row is created or deleted, never
-- edited in place (same append-only stance as 033's learning_resource_skills).

-- ============================================================
-- 3. student_certifications -- a credential the student earned.
-- ============================================================
create table if not exists student_certifications (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,

  name text not null,
  issuing_organization text,

  issue_date date,
  expiry_date date,

  -- Optional verification info the credential itself carries -- this is
  -- the issuer's credential id, NOT anything this platform computes or
  -- trusts. Never a skill-verification signal.
  credential_id text,
  credential_url text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint student_certifications_date_order
    check (expiry_date is null or issue_date is null or expiry_date >= issue_date)
);

create index if not exists student_certifications_student_id_idx
  on student_certifications (student_id);

alter table student_certifications enable row level security;

drop policy if exists "Students can view their own certifications" on student_certifications;
create policy "Students can view their own certifications"
  on student_certifications for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can add their own certifications" on student_certifications;
create policy "Students can add their own certifications"
  on student_certifications for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can update their own certifications" on student_certifications;
create policy "Students can update their own certifications"
  on student_certifications for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can delete their own certifications" on student_certifications;
create policy "Students can delete their own certifications"
  on student_certifications for delete
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop trigger if exists student_certifications_set_updated_at on student_certifications;
create trigger student_certifications_set_updated_at
  before update on student_certifications
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 4. student_achievements -- an award / recognition / milestone.
-- ============================================================
create table if not exists student_achievements (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text,

  achievement_date date,
  issuing_organization text,
  url text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists student_achievements_student_id_idx
  on student_achievements (student_id);

alter table student_achievements enable row level security;

drop policy if exists "Students can view their own achievements" on student_achievements;
create policy "Students can view their own achievements"
  on student_achievements for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can add their own achievements" on student_achievements;
create policy "Students can add their own achievements"
  on student_achievements for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can update their own achievements" on student_achievements;
create policy "Students can update their own achievements"
  on student_achievements for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can delete their own achievements" on student_achievements;
create policy "Students can delete their own achievements"
  on student_achievements for delete
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop trigger if exists student_achievements_set_updated_at on student_achievements;
create trigger student_achievements_set_updated_at
  before update on student_achievements
  for each row
  execute procedure public.set_updated_at();
