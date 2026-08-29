-- Migration: 003_skills
-- Purpose: the reusable SKILLS FOUNDATION for the Student Portal — a
-- normalized master skill catalog (`skills`, categorized via
-- `skill_categories`) plus the per-student relationship to it
-- (`student_skills`: which skills a student has, at what self-reported
-- proficiency, and whether that's been verified).
--
-- Architecture:
--   skill_categories  small, evolving taxonomy — a lookup table, not a
--                     CHECK-constrained enum, so adding a new category
--                     never requires a schema migration.
--     ↑ category_id
--   skills            master catalog — one row per distinct skill.
--     ↑ skill_id
--   student_skills    one row per (student, skill) pair a student has —
--                     proficiency level/score + verification status.
--     → student_id references profiles(id), NOT student_profiles(id) —
--       see the comment on that table below for why.
--
-- Explicitly OUT of scope for this migration (later phases):
--   - Skill assessments, assessment results, computed skill scores.
--   - Skill gap analysis, career readiness scoring.
--   - Job/internship skill requirements and matching.
--   - AI recommendations.
--   - The actual verification workflow (who verifies, how, what
--     evidence) — this migration only makes `student_skills.is_verified`
--     exist and protects it from self-verification; nothing verifies
--     anything yet.
--
-- No seed data is inserted here — see the note at the end of this file.

create table if not exists skill_categories (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Case-insensitive uniqueness, same pattern as profiles.username and
-- (below) skills.name — prevents "Programming Language" and
-- "programming language" existing as two different categories.
create unique index if not exists skill_categories_name_lower_idx on skill_categories (lower(name));

alter table skill_categories enable row level security;

-- Read-only reference data for every signed-in user (any role) — the
-- skill selector UI needs category names to group/filter by, and this
-- isn't student-specific or sensitive. No insert/update/delete policy
-- exists for `authenticated` here, so — with RLS enabled — only
-- service_role can write to it; that's deliberate: categories are
-- curated, not student-editable.
create policy "Authenticated users can view skill categories"
  on skill_categories for select
  to authenticated
  using (true);

create trigger skill_categories_set_updated_at
  before update on skill_categories
  for each row
  execute procedure public.set_updated_at();

create table if not exists skills (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  category_id uuid not null references skill_categories (id) on delete restrict,
  description text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Case-insensitive uniqueness — same pattern as profiles.username.
create unique index if not exists skills_name_lower_idx on skills (lower(name));
-- category_id is a foreign key; Postgres does not index those
-- automatically, and filtering/grouping the catalog by category is a
-- core access pattern for the future skill selector UI.
create index if not exists skills_category_id_idx on skills (category_id);

alter table skills enable row level security;

-- Every signed-in user (any role) can browse the ACTIVE catalog — needed
-- for the student skill selector, and useful later for faculty/industry
-- browsing the same taxonomy. Inactive/deprecated skills are hidden from
-- this read path. No write policy exists for `authenticated` here, so —
-- with RLS enabled — normal users (including students) cannot insert,
-- update, or delete master skills at all; only service_role can. That's
-- deliberate: this is a curated catalog, not user-generated content.
create policy "Authenticated users can view active skills"
  on skills for select
  to authenticated
  using (is_active = true);

create trigger skills_set_updated_at
  before update on skills
  for each row
  execute procedure public.set_updated_at();

-- student_skills: one row per (student, skill) a student has added to
-- their profile.
--
-- References profiles(id), not student_profiles(id): profiles rows are
-- guaranteed to exist for every user from the moment they sign up (the
-- on_auth_user_created trigger in 001_profiles.sql), but student_profiles
-- rows are created lazily — only once a student visits their profile
-- page and saves it. A student should be able to add skills before ever
-- touching that form; requiring a student_profiles row first would be an
-- artificial, unnecessary dependency (the same reasoning already applied
-- when 012_student_profiles.sql was designed — see its own comments).
create table if not exists student_skills (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references profiles (id) on delete cascade,
  skill_id uuid not null references skills (id) on delete restrict,

  -- Self-reported by the student. A short, stable ordinal scale — unlike
  -- skill categories, this is not expected to grow or change, so (like
  -- profiles.role) a CHECK constraint is the right fit here, not a
  -- lookup table.
  proficiency_level text not null check (proficiency_level in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),
  -- Optional finer-grained score, left null until something (a future
  -- assessment) actually computes one — never implied by proficiency_level.
  proficiency_score numeric(5, 2) check (proficiency_score >= 0 and proficiency_score <= 100),

  -- Never true just because a student added the skill — the
  -- prevent_self_skill_verification trigger below blocks students from
  -- changing this themselves. No verifier/method/evidence columns yet —
  -- that's the actual verification workflow, a later phase; this is only
  -- the minimal "is it verified, yes or no" representation.
  is_verified boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint student_skills_unique_per_student unique (student_id, skill_id)
);

-- Reverse lookup direction for future matching queries ("which students
-- have skill X") — the unique constraint above already indexes
-- (student_id, skill_id) with student_id leading, which doesn't serve a
-- bare `where skill_id = ...` efficiently.
create index if not exists student_skills_skill_id_idx on student_skills (skill_id);

alter table student_skills enable row level security;

-- Blocks a student from setting is_verified themselves — mirrors
-- prevent_self_admin_promotion in 002_protect_admin_role.sql exactly:
-- service_role (the only trusted path a future verification mechanism
-- would use) steps aside entirely; every ordinary RLS-governed caller is
-- blocked from changing is_verified at all, in either direction.
create or replace function public.prevent_self_skill_verification()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.is_verified is distinct from old.is_verified then
    raise exception 'Cannot change skill verification status directly.' using errcode = '42501';
  end if;

  return new;
end;
$$;

-- Same defensive revoke as set_updated_at() in 012_student_profiles.sql:
-- trigger-typed (returns trigger) functions aren't exposed by PostgREST
-- as callable RPC endpoints regardless of grants (confirmed empirically
-- during the Student Profile verification — a direct RPC call to
-- set_updated_at() returned "PGRST202: could not find the function" even
-- before that function's own revoke was added), so this closes off
-- direct invocation as a normal call without affecting the trigger.
revoke all on function public.prevent_self_skill_verification() from public;

create trigger student_skills_prevent_self_verification
  before update on student_skills
  for each row
  execute procedure public.prevent_self_skill_verification();

create trigger student_skills_set_updated_at
  before update on student_skills
  for each row
  execute procedure public.set_updated_at();

-- Ownership + role policies, same shape as student_profiles' own
-- policies in 012_student_profiles.sql — reuses the existing
-- public.is_student(uuid) helper (hardened in 013_harden_is_student.sql)
-- rather than defining a new one.
create policy "Students can view their own skills"
  on student_skills for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

create policy "Students can add their own skills"
  on student_skills for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

create policy "Students can update their own skills"
  on student_skills for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

create policy "Students can delete their own skills"
  on student_skills for delete
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

-- Seed data (an initial skill catalog + the categories it depends on)
-- intentionally does NOT live in this migration. This project already
-- separates schema from content: database/README.md documents
-- database/seed/ as "sample/demo data, applied after migrations", and
-- database/seed/skills.sql already exists as an empty placeholder for
-- exactly this. Migrations should stay pure schema; seeding real catalog
-- rows is a separate, explicitly-approved step — proposed content is in
-- this migration's approval report, not inserted here.
