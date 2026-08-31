-- Migration: 016_skill_gap
-- Purpose: the foundation for deterministic Skill Gap Analysis --
-- job_roles + their per-skill requirements, a student's own target role,
-- and a skill-to-skill relationship graph for data-driven
-- recommendations. No LLM anywhere in this migration or the feature it
-- supports; the gap/recommendation calculation itself is Python business
-- logic (see backend/app/services/skill_gap_service.py), reading these
-- tables plus the EXISTING student_skills/assessments tables through
-- ordinary RLS-respecting reads.
--
-- Reuses, does not duplicate:
--   - student_skills (003_skills.sql) remains the ONLY place a student's
--     declared/verified proficiency lives. This migration adds no
--     second proficiency table and no second proficiency enum.
--   - assessments (004_assessments.sql) remains the ONLY source of
--     "is there an assessment for skill X at level Y" -- this migration
--     does not duplicate or cache that.
--
-- LEVEL SYSTEM NOTE: student_skills.proficiency_level and
-- assessments.difficulty both already use a FOUR-value scale --
-- ('Beginner', 'Intermediate', 'Advanced', 'Expert') -- not the
-- three-value scale a generic "skill gap" spec might assume. Every
-- level column added below reuses this exact same four-value CHECK
-- constraint, for the same reason 004/015 reused it: one proficiency
-- scale for the whole project, never a second incompatible one. The
-- application-layer ordinal mapping (Beginner=1, Intermediate=2,
-- Advanced=3, Expert=4, missing=0) lives in skill_gap_service.py, not
-- in the schema.
--
-- ============================================================
-- job_roles -- a curated career-role catalog (Backend Developer, Data
-- Scientist, etc.). Content is service_role-managed, exactly like
-- assessments and skills content today -- no student/faculty write API
-- exists or is planned for this migration.
-- ============================================================

create table if not exists job_roles (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  category text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Case-insensitive uniqueness -- same "lower(name)" pattern already used
-- for profiles.username, skills.name, and skill_categories.name.
create unique index if not exists job_roles_name_lower_idx on job_roles (lower(name));
create index if not exists job_roles_active_idx on job_roles (id) where is_active = true;

alter table job_roles enable row level security;

-- STUDENT-gated, matching the 004_assessments.sql precedent (narrower
-- than 003_skills.sql's catalog tables): job-role requirement content is
-- curated career-guidance data, not generic taxonomy. No write policy
-- for `authenticated` -- only service_role manages this catalog, same as
-- assessments/skills content today.
create policy "Students can view active job roles"
  on job_roles for select
  to authenticated
  using (is_active = true and public.is_student(auth.uid()));

create trigger job_roles_set_updated_at
  before update on job_roles
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- job_role_skills -- required skills + level + importance per role.
-- ============================================================

create table if not exists job_role_skills (
  id uuid primary key default gen_random_uuid(),
  job_role_id uuid not null references job_roles (id) on delete cascade,
  -- restrict, not cascade: a skill referenced by a real job-role
  -- requirement is protected content, same "protect historical/
  -- referenced content" reasoning used throughout this project
  -- (student_skills.skill_id, assessments.skill_id, etc.) -- deactivate
  -- the skill instead of deleting it out from under a live requirement.
  skill_id uuid not null references skills (id) on delete restrict,
  required_level text not null check (required_level in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),
  -- CORE/IMPORTANT/OPTIONAL: a small, stable scale -- a CHECK-constrained
  -- enum, matching this project's existing convention for short stable
  -- scales (profiles.role, student_skills.proficiency_level) rather than
  -- a lookup table.
  importance text not null default 'IMPORTANT' check (importance in ('CORE', 'IMPORTANT', 'OPTIONAL')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint job_role_skills_unique_per_role unique (job_role_id, skill_id)
);

create index if not exists job_role_skills_job_role_id_idx on job_role_skills (job_role_id);
create index if not exists job_role_skills_skill_id_idx on job_role_skills (skill_id);

alter table job_role_skills enable row level security;

create policy "Students can view job role skills for active roles"
  on job_role_skills for select
  to authenticated
  using (
    public.is_student(auth.uid())
    and exists (
      select 1 from job_roles jr
      where jr.id = job_role_skills.job_role_id
        and jr.is_active = true
    )
  );

create trigger job_role_skills_set_updated_at
  before update on job_role_skills
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- student_target_job_role -- the student's own single active target
-- role (V1: one per student, enforced by the unique index below).
--
-- References profiles(id), NOT student_profiles(id) -- identical
-- reasoning to student_skills.student_id (003_skills.sql) and
-- assessment_attempts.student_id (004_assessments.sql): a profiles row
-- exists for every user from signup, but student_profiles is created
-- lazily. A student must be able to pick a target role before ever
-- touching the profile form.
-- ============================================================

create table if not exists student_target_job_role (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references profiles (id) on delete cascade,
  -- restrict: a student's target-role selection referencing a role that
  -- later gets deactivated should surface as "target role no longer
  -- active" at the application layer (job_roles.is_active = false),
  -- never silently orphaned or cascaded away.
  job_role_id uuid not null references job_roles (id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint student_target_job_role_one_per_student unique (student_id)
);

create index if not exists student_target_job_role_job_role_id_idx on student_target_job_role (job_role_id);

alter table student_target_job_role enable row level security;

-- Ownership policies, same shape as student_skills' own policies in
-- 003_skills.sql.
create policy "Students can view their own target job role"
  on student_target_job_role for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

create policy "Students can set their own target job role"
  on student_target_job_role for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

create policy "Students can update their own target job role"
  on student_target_job_role for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

create policy "Students can clear their own target job role"
  on student_target_job_role for delete
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

create trigger student_target_job_role_set_updated_at
  before update on student_target_job_role
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- skill_relationships -- a directed skill-to-skill graph for
-- deterministic, non-LLM recommendations.
--
-- Semantics of a row (skill_id = A, related_skill_id = B, relationship_type = T):
--   PREREQUISITE   A should typically be learned before B (A is a
--                  prerequisite of B). Used to surface "prerequisite
--                  gaps": look up rows WHERE related_skill_id = <a
--                  missing/target skill> AND relationship_type =
--                  'PREREQUISITE' to find what the student needs first.
--   NEXT_STEP      Having A, B is a natural next skill to learn.
--   RELATED        A and B are commonly used together / conceptually
--                  adjacent (stored one direction; queries needing the
--                  reverse direction can query related_skill_id instead).
--   COMPLEMENTARY  B nicely complements A (a softer pairing than
--                  NEXT_STEP -- not a progression, just a good pairing).
-- For "what should this student learn next" (personal mode), the
-- service queries WHERE skill_id = <a skill the student already has>,
-- across NEXT_STEP/RELATED/COMPLEMENTARY.
-- ============================================================

create table if not exists skill_relationships (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid not null references skills (id) on delete cascade,
  related_skill_id uuid not null references skills (id) on delete cascade,
  relationship_type text not null check (relationship_type in ('PREREQUISITE', 'RELATED', 'NEXT_STEP', 'COMPLEMENTARY')),
  -- Lower number = surfaced first among same-type recommendations from
  -- the same source skill. Purely a display/ranking aid, not part of the
  -- gap/priority calculation itself.
  priority int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint skill_relationships_no_self_reference check (skill_id <> related_skill_id),
  constraint skill_relationships_unique_edge unique (skill_id, related_skill_id, relationship_type)
);

create index if not exists skill_relationships_skill_id_idx on skill_relationships (skill_id);
create index if not exists skill_relationships_related_skill_id_idx on skill_relationships (related_skill_id);

alter table skill_relationships enable row level security;

create policy "Students can view skill relationships"
  on skill_relationships for select
  to authenticated
  using (public.is_student(auth.uid()));

create trigger skill_relationships_set_updated_at
  before update on skill_relationships
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- No seed data in this migration -- see database/seed/job_roles.sql,
-- matching this project's existing convention (003_skills.sql's own
-- closing comment: "Migrations should stay pure schema; seeding real
-- catalog rows is a separate, explicitly-approved step").
-- ============================================================
