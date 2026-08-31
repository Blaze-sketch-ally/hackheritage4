-- Migration: 022_career_roles_skill_gap
-- Purpose: Phase 1L -- the CAREER ROLE reference catalog and its required
-- skills, the configuration half of skill-gap analysis. The evidence half
-- (a student's assessed skill scores) is deliberately NOT a new table --
-- see the architectural note below.
--
-- Architecture:
--   career_roles                    one row per role a student can
--                                    compare themselves against (e.g.
--                                    "Software Engineer", "Data Analyst")
--     ↑ career_role_id
--   career_role_skill_requirements  which skills that role needs, at what
--     ↑ skill_id                    level (0-100, same scale as
--                                    assessment_attempts.percentage) and
--                                    weight
--
-- HARD ARCHITECTURAL DECISION -- no new "student skill level" table:
--   A student's current skill evidence is fully derivable from EXISTING
--   data: the best `percentage` across their own COMPLETED
--   assessment_attempts, joined through assessments.skill_id. Phase 1K
--   already owns and protects that data (immutable once scored -- see
--   docs/architecture/assessment-lifecycle.md). Materializing it into a
--   new table here would duplicate a fact Phase 1K already owns and risk
--   drift between the two. app.services.assessment_service.
--   get_student_skill_scores() (Phase 1L, added additively, not a
--   modification of any existing function) computes this on demand,
--   read-only, from assessment_attempts/assessments -- see that
--   function's own docstring.
--
--   This is explicitly NOT the same thing as the pre-existing
--   `student_skills` table (003_skills.sql): that table holds
--   SELF-REPORTED proficiency a student typed in themselves, with no
--   assessment behind it. 004_assessments.sql's own closing comment
--   ("FUTURE INTEGRATION POINTS") describes a hypothetical future sync
--   from completed attempts into student_skills -- that sync was never
--   built, and Phase 1L does not build it either: doing so would mean
--   writing to student_skills from inside (or immediately after) the
--   trusted scoring path, which is exactly the kind of change to Phase
--   1K's existing scoring model this phase is explicitly scoped NOT to
--   make. Phase 1L reads assessment_attempts directly instead, and never
--   touches student_skills at all, in either direction.
--
-- No RLS write policy exists for `authenticated` on either table below --
-- both are curated reference data, following the exact same precedent as
-- `skills`/`skill_categories` (003_skills.sql) and `assessments`
-- (004_assessments.sql): readable by any authenticated role, writable
-- only by service_role (see database/seed/career_roles.sql for the
-- actual seeded content, applied as a separate step, matching how
-- database/seed/skills_fixed.sql is kept separate from
-- 003_skills.sql's schema).

-- ============================================================
-- career_roles
-- ============================================================

create table if not exists career_roles (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  -- Free-text grouping label (e.g. "Engineering", "Data") -- a lookup
  -- table would be over-engineering for what is, for this MVP, a small,
  -- rarely-changing seeded catalog; matches assessments.difficulty's
  -- "CHECK constraint for a small stable scale" reasoning in spirit, but
  -- deliberately left unconstrained here since the set of categories is
  -- not yet known to be stable the way difficulty's four values are.
  category text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Case-insensitive uniqueness -- same pattern as skills.name /
-- assessments' per-skill title uniqueness / profiles.username.
create unique index if not exists career_roles_title_lower_idx on career_roles (lower(title));

alter table career_roles enable row level security;

-- Same precedent as skills/skill_categories/assessments: readable by ANY
-- authenticated role (not gated to STUDENT) -- catalog-like reference
-- data, not personal student data. No insert/update/delete policy exists
-- for `authenticated`, so -- with RLS enabled -- only service_role can
-- write. Career-role content is curated/seeded, not user-authored.
create policy "Authenticated users can view career roles"
  on career_roles for select
  to authenticated
  using (true);

create trigger career_roles_set_updated_at
  before update on career_roles
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- career_role_skill_requirements
-- ============================================================

create table if not exists career_role_skill_requirements (
  id uuid primary key default gen_random_uuid(),
  career_role_id uuid not null references career_roles (id) on delete cascade,

  -- restrict, not cascade: a required skill is referenced content, same
  -- "protect historical/referenced content" reasoning already used for
  -- assessments.skill_id and student_skills.skill_id in this project --
  -- deactivating/removing a skill from the catalog should not silently
  -- delete a role's requirement for it.
  skill_id uuid not null references skills (id) on delete restrict,

  -- Same 0-100 scale as assessment_attempts.percentage -- see the
  -- "Skill Evidence Boundary" section of
  -- docs/architecture/assessment-lifecycle.md for why this scale was
  -- chosen and what it means for a required_level of exactly 0.
  required_level numeric(5, 2) not null check (required_level >= 0 and required_level <= 100),

  -- Relative importance within one role's weighted alignment score
  -- (app.services.skill_alignment_service.compute_alignment). Zero is
  -- allowed (a requirement can be recorded but excluded from the
  -- weighted score) -- negative is not.
  weight numeric(5, 2) not null default 1.0 check (weight >= 0),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- One requirement row per (role, skill) -- also what makes
  -- database/seed/career_roles.sql's ON CONFLICT DO NOTHING idempotent.
  constraint career_role_skill_requirements_unique unique (career_role_id, skill_id)
);

create index if not exists career_role_skill_requirements_career_role_id_idx
  on career_role_skill_requirements (career_role_id);
-- skill_id is a foreign key; Postgres does not index those automatically.
-- Serves a future reverse lookup ("which roles need skill X").
create index if not exists career_role_skill_requirements_skill_id_idx
  on career_role_skill_requirements (skill_id);

alter table career_role_skill_requirements enable row level security;

create policy "Authenticated users can view career role skill requirements"
  on career_role_skill_requirements for select
  to authenticated
  using (true);

create trigger career_role_skill_requirements_set_updated_at
  before update on career_role_skill_requirements
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- FUTURE INTEGRATION POINTS (explicitly NOT built in this migration)
-- ============================================================
--
-- Phase 1M (opportunities): app.services.skill_alignment_service is
-- deliberately generic over SkillRequirement, not career-role-specific --
-- an opportunity's required skills (a future opportunity_required_skills
-- table) can be passed through the exact same compute_alignment()
-- function without duplicating this algorithm. See that module's own
-- docstring.
--
-- career_roles/career_role_skill_requirements have no write API in this
-- migration or Phase 1L's backend -- adding CRUD for faculty/admin-curated
-- roles is a future, separate decision, not assumed here.
