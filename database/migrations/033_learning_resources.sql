-- Migration: 033_learning_resources
-- Purpose: the DATABASE FOUNDATION for the Student Learning MVP (Phase 6A).
--
-- Approved MVP scope (see the Phase 6 audit):
--   A -- browse a curated catalog of learning resources
--   D -- map each resource to one or more canonical skills
--   E -- (later) recommend resources from a student's Skill Gap -- this
--        migration only establishes the skill -> resource edge that makes
--        that possible; NO skill_gap code is touched here.
--   C -- minimal per-student progress: SAVED / IN_PROGRESS / COMPLETED.
--
-- The Learning feature's supporting numbered placeholder was
-- 007_learning.sql (never given DDL) -- NOT edited here, following the
-- same "placeholder superseded by a later real migration" pattern used
-- for 005_internships / 006_jobs -> 018 / 019. This is the real schema,
-- numbered after this branch's current tip (032), not a rewrite of 007.
--
-- ============================================================
-- Hard architectural boundaries (mandatory)
-- ============================================================
-- * student_skills (003_skills.sql) stays the ONLY source of a student's
--   proficiency. NOTHING here reads or writes it.
-- * Learning progress is NOT skill evidence: student_learning_progress
--   deliberately has no score / skill_level / is_verified / verified_at /
--   assessment_id / student_skill_id column. Completing a resource never
--   creates a skill, raises proficiency, or sets verification -- that
--   remains exclusively the job of score_assessment_attempt()
--   (015_assessment_verification.sql).
-- * No FK to, and no reference to: student_skills, job_roles,
--   career_roles, assessments, opportunities, industry_training,
--   portfolio_*. The skill mapping references the canonical `skills`
--   catalog (003_skills.sql) and nothing else.
--
-- ============================================================
-- Conventions reused from existing migrations
-- ============================================================
-- * uuid PK: `id uuid primary key default gen_random_uuid()` (003/004/016)
-- * created_at / updated_at timestamptz not null default now() (all)
-- * public.set_updated_at() trigger function (defined in
--   012_student_profiles.sql, reused by 003/004/015/016...) -- attached,
--   never redefined here.
-- * Curated read-only catalog: RLS enabled, a single
--   "Authenticated users can view active ..." SELECT policy, and NO
--   write policy for `authenticated` -> only service_role / seed SQL can
--   write. Same shape as skills / skill_categories (003_skills.sql) and
--   assessments (004_assessments.sql).
-- * Student-owned table: `student_id uuid not null references profiles(id)
--   on delete cascade`, ownership predicate
--   `auth.uid() = student_id and public.is_student(auth.uid())` -- same
--   shape as student_skills (003) and student_target_job_role (016).
-- * `skill_id ... references skills(id) on delete restrict` -- protect a
--   catalog skill referenced by real content (same as
--   student_skills.skill_id / job_role_skills.skill_id).
-- * Enum-like short scales -> CHECK constraints, never a Postgres enum
--   type (profiles.role / student_skills.proficiency_level precedent).
-- * CHECK values 'Beginner'/'Intermediate'/'Advanced'/'Expert' reuse the
--   exact 4-value proficiency scale (003/004/015/016) -- no new scale.
--
-- Idempotent in shape: create table if not exists, create index if not
-- exists, drop trigger if exists + create trigger. Forward-only,
-- additive, non-destructive: no DROP TABLE, no destructive ALTER, no
-- change to any existing table, policy, trigger, or function.

-- ============================================================
-- 1. learning_resources -- the curated catalog.
--    service_role / seed writes only; every authenticated user may read
--    the ACTIVE rows.
-- ============================================================
create table if not exists learning_resources (
  id uuid primary key default gen_random_uuid(),

  title text not null,
  description text,
  -- The outbound link a student follows. NOT NULL -- a resource with no
  -- URL is not a usable learning resource. No format CHECK: curated
  -- content, and over-constraining URLs (scheme/host rules) has bitten
  -- other projects; the seed/admin path is trusted.
  url text not null,
  -- Free-text label for who publishes it (e.g. "freeCodeCamp",
  -- "PostgreSQL Docs"). Never an enum or FK -- same "provider is a label,
  -- not a vendor table" reasoning as assessment_questions.generation_model
  -- (004_assessments.sql).
  provider text,

  -- Small, stable set -> CHECK, matching the project convention. 'OTHER'
  -- keeps podcasts / interactive playgrounds / books from needing a
  -- schema change.
  resource_type text not null check (resource_type in ('COURSE', 'ARTICLE', 'VIDEO', 'OTHER')),

  -- Optional overall difficulty of the resource itself, independent of
  -- any skill it teaches. Reuses the 4-value proficiency scale.
  difficulty text check (difficulty in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),

  estimated_minutes int check (estimated_minutes is null or estimated_minutes > 0),

  is_active boolean not null default true,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Duplicate-curated-resource guard: the same URL should not be catalogued
-- twice. Case-insensitive on the URL only -- provider/title can legitimately
-- vary in casing across curation passes, the URL is the stable identity.
-- Partial index style (lower(url)) matches skills_name_lower_idx
-- (003_skills.sql) / assessments_skill_id_title_lower_idx (004).
create unique index if not exists learning_resources_url_lower_idx
  on learning_resources (lower(url));

-- Partial index for the "browse active catalog" read path -- same pattern
-- as skills' implicit active browsing / internships_published_idx (018) /
-- assessments_active_skill_id_idx (004).
create index if not exists learning_resources_active_idx
  on learning_resources (id) where is_active = true;

alter table learning_resources enable row level security;

-- Every signed-in user (any role) can browse the ACTIVE catalog -- same
-- decision as "Authenticated users can view active skills" (003): a
-- resource list is not student-specific or sensitive, and faculty /
-- industry may plausibly browse the same catalog later. Inactive rows are
-- never exposed through this path. NO insert/update/delete policy for
-- `authenticated` -> with RLS enabled, only service_role can write the
-- catalog.
drop policy if exists "Authenticated users can view active learning resources" on learning_resources;
create policy "Authenticated users can view active learning resources"
  on learning_resources for select
  to authenticated
  using (is_active = true);

drop trigger if exists learning_resources_set_updated_at on learning_resources;
create trigger learning_resources_set_updated_at
  before update on learning_resources
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 2. learning_resource_skills -- the critical skill -> resource edge.
--    Maps a catalogued resource to one or more canonical `skills`, at an
--    optional target level. This is what a future Skill Gap integration
--    (Phase 6D) will look up: "for skill X, which active resources exist".
-- ============================================================
create table if not exists learning_resource_skills (
  id uuid primary key default gen_random_uuid(),

  resource_id uuid not null references learning_resources (id) on delete cascade,
  -- restrict, not cascade: a skill referenced by real curated content is
  -- protected -- deactivate the skill instead of deleting it out from
  -- under a live mapping. Same reasoning as student_skills.skill_id /
  -- job_role_skills.skill_id (003 / 016).
  skill_id uuid not null references skills (id) on delete restrict,

  -- The proficiency level this resource helps a student reach for this
  -- skill. Optional -- a general "intro to X" resource may not target a
  -- specific level. Reuses the 4-value scale.
  target_level text check (target_level in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),

  created_at timestamptz not null default now(),

  -- One mapping per (resource, skill) pair.
  constraint learning_resource_skills_unique_pair unique (resource_id, skill_id)
);

-- The gap -> resource lookup ("resources for skill X") -- skill_id is a
-- foreign key, which Postgres does not index automatically, and it is the
-- primary access pattern for Phase 6D.
create index if not exists learning_resource_skills_skill_id_idx
  on learning_resource_skills (skill_id);
-- resource_id also FK-indexed for the reverse ("skills this resource
-- covers", used by the resource detail view). The UNIQUE(resource_id,
-- skill_id) index leads with resource_id so a bare resource_id lookup is
-- already served -- but keep an explicit one for clarity/parity with the
-- rest of the schema's FK-index convention (job_role_skills has both).
create index if not exists learning_resource_skills_resource_id_idx
  on learning_resource_skills (resource_id);

alter table learning_resource_skills enable row level security;

-- Readable only when the parent resource is active -- so an inactive
-- resource's skill mapping is not exposed either (mirrors
-- "Authenticated users can view skills for published internships",
-- 018_internships.sql). NO write policy for `authenticated` -> curated,
-- service_role only.
drop policy if exists "Authenticated users can view skills for active resources" on learning_resource_skills;
create policy "Authenticated users can view skills for active resources"
  on learning_resource_skills for select
  to authenticated
  using (
    exists (
      select 1 from learning_resources r
      where r.id = learning_resource_skills.resource_id
        and r.is_active = true
    )
  );

-- No updated_at column here -- append-only mapping rows, same as
-- assessment_attempt_questions (015): a mapping is created or deleted by
-- curation, never edited in place.

-- ============================================================
-- 3. student_learning_progress -- the authenticated student's own
--    relationship with a resource. SAVED (bookmarked) -> IN_PROGRESS ->
--    COMPLETED. Owner-only, every direction.
--
--    NOT skill verification -- see the "Hard architectural boundaries"
--    note above. No score / skill_level / verified / assessment_id here,
--    by design.
-- ============================================================
create table if not exists student_learning_progress (
  id uuid primary key default gen_random_uuid(),

  -- references profiles(id), not student_profiles(id) -- identical
  -- reasoning to student_skills.student_id (003) and
  -- assessment_attempts.student_id (004): a profiles row exists from
  -- signup, student_profiles is lazy. A student may save a resource
  -- before ever touching their profile form.
  student_id uuid not null references profiles (id) on delete cascade,
  resource_id uuid not null references learning_resources (id) on delete cascade,

  status text not null default 'SAVED' check (status in ('SAVED', 'IN_PROGRESS', 'COMPLETED')),

  started_at timestamptz,
  completed_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- One progress row per (student, resource) -- the student's current
  -- relationship with that resource. Revisions are an UPDATE to this row,
  -- same model as assessment_answers_unique_per_attempt_question (004).
  constraint student_learning_progress_unique_per_student
    unique (student_id, resource_id),

  -- completed_at only ever set on a COMPLETED row.
  constraint student_learning_progress_completed_at_requires_completed
    check (completed_at is null or status = 'COMPLETED'),
  -- A COMPLETED or IN_PROGRESS row must have a started_at (the student
  -- began it at some point); a SAVED bookmark need not. Kept loose (>=
  -- not strict ordering enforcement beyond the below) -- exact timestamp
  -- sequencing is an application concern, matching how
  -- assessment_attempts only checks `submitted_at >= started_at`.
  constraint student_learning_progress_active_requires_started
    check (status = 'SAVED' or started_at is not null),
  constraint student_learning_progress_completed_after_started
    check (completed_at is null or started_at is null or completed_at >= started_at)
);

-- student_id is a foreign key (no auto-index) and every read of this
-- table is "my progress" -- so a plain index on student_id serves the
-- "My Learning" list. resource_id lookups ("did I save THIS resource")
-- are already served by the leading column of the UNIQUE index.
create index if not exists student_learning_progress_student_id_idx
  on student_learning_progress (student_id);

alter table student_learning_progress enable row level security;

-- Owner-only, all three directions -- exact shape of student_skills'
-- policies (003) and student_target_job_role's (016). auth.uid() =
-- student_id is the ownership check; public.is_student(auth.uid()) blocks
-- a non-STUDENT (or role-less) user from having progress rows at all.
-- A student_id supplied by a client is irrelevant: the WITH CHECK forces
-- it to equal auth.uid() regardless of what the request body says.
drop policy if exists "Students can view their own learning progress" on student_learning_progress;
create policy "Students can view their own learning progress"
  on student_learning_progress for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can start their own learning progress" on student_learning_progress;
create policy "Students can start their own learning progress"
  on student_learning_progress for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can update their own learning progress" on student_learning_progress;
create policy "Students can update their own learning progress"
  on student_learning_progress for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

-- No DELETE policy -- MVP: a student changes status (e.g. back to SAVED),
-- never hard-deletes a progress row. With RLS enabled and no delete
-- policy, DELETE is denied for every `authenticated` caller. Matches the
-- "no delete policy" stance of assessment_attempts / applications.

drop trigger if exists student_learning_progress_set_updated_at on student_learning_progress;
create trigger student_learning_progress_set_updated_at
  before update on student_learning_progress
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- No seed data in this migration -- see database/seed/learning_resources.sql,
-- matching the project convention (003_skills.sql / 016_skill_gap.sql
-- closing comments: migrations stay pure schema; catalog rows are a
-- separate, explicitly-applied step).
-- ============================================================
