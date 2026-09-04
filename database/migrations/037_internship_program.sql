-- Migration: 037_internship_program
-- Purpose: PHASE 1 (database foundation) of the approved post-selection
-- Internship Workspace architecture -- the PROGRAM / TEMPLATE half.
--
-- ============================================================
-- Where this sits in the approved architecture
-- ============================================================
-- Template + Instance. An INDUSTRY account authors exactly ONE
-- internship_program for an existing internship posting (018_internships.sql):
-- ordered modules, learning items, offered skills and gradable
-- assignments. When a student is later SELECTED for that internship and it
-- is REMOTE/HYBRID, migration 038 provisions ONE internship_workspace per
-- application that REFERENCES this program's content. All per-student
-- state (acceptance, chosen skills, submissions, reviews, completion,
-- certificate, stipend) keys off the workspace, never off the program.
--
-- This migration adds ONLY the program side (5 tables) + its INDUSTRY-side
-- RLS. The student-read policies for this migration's tables depend on
-- internship_workspaces existing, so they are added by 038 (documented
-- again there). Submissions / completion / certificate / stipend are 039.
--
-- ============================================================
-- Relationship to the existing schema
-- ============================================================
-- * internship_programs.internship_id -> internships(id) ON DELETE CASCADE.
--   internships can no longer be hard-deleted (028_forbid_internship_job_deletes.sql),
--   so this CASCADE only ever fires on a service_role / GDPR path.
-- * program_skills.skill_id / program_assignments.linked_skill_id ->
--   skills(id), the CANONICAL catalog (003_skills.sql). No new skill
--   taxonomy. RESTRICT on program_skills (a skill referenced by real
--   curriculum is protected content, same as internship_skills.skill_id);
--   SET NULL on program_assignments.linked_skill_id (a deactivated
--   catalog skill must not destroy assignment history).
-- * NOTHING here references or writes student_skills. Curriculum authoring
--   is not skill evidence -- the assessment scoring path
--   (015_assessment_verification.sql) stays the only writer of
--   student_skills verification state.
-- * industry_id is resolved THROUGH internships.industry_id (ownership
--   chain), never stored again on the program tables -- one source of
--   truth for "who owns this".
--
-- ============================================================
-- Conventions reused (001-036)
-- ============================================================
-- * uuid PK default gen_random_uuid(); created_at / updated_at timestamptz
--   not null default now(); public.set_updated_at() trigger (012), reused
--   never redefined.
-- * Enum-like columns -> CHECK value lists, never a Postgres enum type.
-- * public.is_industry(uuid) (017) for the role half of every owner
--   predicate.
-- * Record tables (internship_programs, program_modules, module_items,
--   program_assignments): explicit per-command SELECT / INSERT / UPDATE
--   policies and NO DELETE policy -- hard delete is denied for every
--   RLS-governed caller (020/027/028/030 precedent). Authoring mistakes
--   are corrected by unpublish + edit.
-- * program_skills is a mutable *_skills child table (like internship_skills,
--   018): it keeps a `for all` owner policy so a later _replace_skills()
--   service helper can DELETE+INSERT the set.
-- * Idempotent in shape: create table / index if not exists;
--   drop policy/trigger if exists + create; create or replace function.
--   Forward-only, additive: no DROP TABLE, no destructive ALTER, no change
--   to any existing table, policy, trigger, or function.
--
-- No seed data -- programs are authored by the running system.

-- ============================================================
-- Object creation order in this file (dependency-correct)
-- ============================================================
--   1. internship_programs           (table + RLS + trigger)
--   2. owns_internship_program()     -- language sql: its body is
--                                       validated at CREATE time
--                                       (check_function_bodies), so it
--                                       MUST follow internship_programs
--   3. program_modules               (RLS uses the helper)
--   4. module_items                  (RLS uses the helper)
--   5. program_skills                (RLS uses the helper)
--   6. program_assignments           (+ its plpgsql derivation trigger)
-- internship_programs' own policies use an inline `exists (...)` against
-- `internships` (018) -- they do NOT need the helper, so they can be
-- created before it.

-- ============================================================
-- 1. internship_programs -- one training template per internship posting
-- ============================================================

create table if not exists internship_programs (
  id uuid primary key default gen_random_uuid(),

  -- STRICTLY 1:1 with the posting -- the UNIQUE below is the approved
  -- cardinality guarantee. A new curriculum "version" is ARCHIVE + a new
  -- program on a new posting, not a second row here.
  internship_id uuid not null references internships (id) on delete cascade,

  title text not null,
  summary text,
  estimated_weeks int check (estimated_weeks is null or (estimated_weeks between 1 and 52)),

  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'ARCHIVED')),
  published_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint internship_programs_one_per_internship unique (internship_id)
);

-- unique(internship_id) already indexes the only lookup key.

alter table internship_programs enable row level security;

drop policy if exists "Industry can view their own internship programs" on internship_programs;
create policy "Industry can view their own internship programs"
  on internship_programs for select
  to authenticated
  using (
    exists (
      select 1 from internships i
      where i.id = internship_programs.internship_id
        and i.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

drop policy if exists "Industry can create a program for their own internship" on internship_programs;
create policy "Industry can create a program for their own internship"
  on internship_programs for insert
  to authenticated
  with check (
    exists (
      select 1 from internships i
      where i.id = internship_programs.internship_id
        and i.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

drop policy if exists "Industry can update their own internship programs" on internship_programs;
create policy "Industry can update their own internship programs"
  on internship_programs for update
  to authenticated
  using (
    exists (
      select 1 from internships i
      where i.id = internship_programs.internship_id
        and i.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  )
  with check (
    exists (
      select 1 from internships i
      where i.id = internship_programs.internship_id
        and i.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

-- No DELETE policy: a program is a record. ARCHIVE (status) is the
-- lifecycle end. CASCADE from internships only reaches it on a
-- service_role path.

drop trigger if exists internship_programs_set_updated_at on internship_programs;
create trigger internship_programs_set_updated_at
  before update on internship_programs
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 2. Ownership helper -- defined AFTER internship_programs exists
-- ============================================================
-- True when auth.uid() is the INDUSTRY account that owns the internship
-- behind the given program. SECURITY DEFINER + pinned empty search_path +
-- STABLE -- same pattern as public.is_student / public.is_industry.
-- Reads the ownership chain
--   internship_programs -> internships -> internships.industry_id -> auth.uid()
-- directly, immune to RLS-recursion by construction, and also checks
-- public.is_industry(auth.uid()). Every program-content policy below (and
-- the student-read policies added in 038) route ownership through this one
-- function.
--
-- Placement: `language sql` function bodies ARE validated at CREATE time
-- (check_function_bodies = on, the default), so this must be created after
-- internship_programs -- unlike a plpgsql body, which is not name-resolved
-- until first execution.

create or replace function public.owns_internship_program(p_program_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.internship_programs prog
    join public.internships intr on intr.id = prog.internship_id
    where prog.id = p_program_id
      and intr.industry_id = auth.uid()
      and public.is_industry(auth.uid())
  );
$$;

revoke all on function public.owns_internship_program(uuid) from public;
revoke all on function public.owns_internship_program(uuid) from anon;
grant execute on function public.owns_internship_program(uuid) to authenticated;

-- ============================================================
-- 3. program_modules -- ordered sections of a program
-- ============================================================

create table if not exists program_modules (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references internship_programs (id) on delete cascade,

  title text not null,
  description text,
  -- Presentation order. NOT unique -- reordering a curriculum must not
  -- fight a constraint; ties break on created_at at read time.
  order_index int not null default 0 check (order_index >= 0),
  is_published boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists program_modules_program_id_idx on program_modules (program_id);

alter table program_modules enable row level security;

drop policy if exists "Industry can view modules for their own programs" on program_modules;
create policy "Industry can view modules for their own programs"
  on program_modules for select
  to authenticated
  using (public.owns_internship_program(program_modules.program_id));

drop policy if exists "Industry can add modules to their own programs" on program_modules;
create policy "Industry can add modules to their own programs"
  on program_modules for insert
  to authenticated
  with check (public.owns_internship_program(program_modules.program_id));

drop policy if exists "Industry can update modules for their own programs" on program_modules;
create policy "Industry can update modules for their own programs"
  on program_modules for update
  to authenticated
  using (public.owns_internship_program(program_modules.program_id))
  with check (public.owns_internship_program(program_modules.program_id));

-- No DELETE policy -- unpublish instead.

drop trigger if exists program_modules_set_updated_at on program_modules;
create trigger program_modules_set_updated_at
  before update on program_modules
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 4. module_items -- learning content inside a module
-- ============================================================
-- One table, semantics by item_type -- same "one table, CHECK-constrained
-- vocabulary" pattern as interviews.mode / student_notifications.type.
-- Future content types are added by widening this CHECK in a later
-- forward migration (exactly as 039 widens student_notifications).

create table if not exists module_items (
  id uuid primary key default gen_random_uuid(),
  module_id uuid not null references program_modules (id) on delete cascade,

  title text not null,
  item_type text not null check (item_type in ('VIDEO', 'PDF', 'LINK', 'TEXT')),
  -- VIDEO / PDF / LINK carry a resource URL; TEXT carries inline body.
  content_url text,
  content_text text,
  order_index int not null default 0 check (order_index >= 0),
  is_published boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint module_items_content_matches_type check (
    (item_type = 'TEXT' and content_text is not null)
    or (item_type in ('VIDEO', 'PDF', 'LINK') and content_url is not null)
  )
);

create index if not exists module_items_module_id_idx on module_items (module_id);

alter table module_items enable row level security;

drop policy if exists "Industry can view items for their own programs" on module_items;
create policy "Industry can view items for their own programs"
  on module_items for select
  to authenticated
  using (
    exists (
      select 1 from program_modules m
      where m.id = module_items.module_id
        and public.owns_internship_program(m.program_id)
    )
  );

drop policy if exists "Industry can add items to their own programs" on module_items;
create policy "Industry can add items to their own programs"
  on module_items for insert
  to authenticated
  with check (
    exists (
      select 1 from program_modules m
      where m.id = module_items.module_id
        and public.owns_internship_program(m.program_id)
    )
  );

drop policy if exists "Industry can update items for their own programs" on module_items;
create policy "Industry can update items for their own programs"
  on module_items for update
  to authenticated
  using (
    exists (
      select 1 from program_modules m
      where m.id = module_items.module_id
        and public.owns_internship_program(m.program_id)
    )
  )
  with check (
    exists (
      select 1 from program_modules m
      where m.id = module_items.module_id
        and public.owns_internship_program(m.program_id)
    )
  );

-- No DELETE policy -- unpublish instead.

drop trigger if exists module_items_set_updated_at on module_items;
create trigger module_items_set_updated_at
  before update on module_items
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 5. program_skills -- skills this program trains, required or optional
-- ============================================================
-- Distinct from internship_skills (018), which is recruitment screening.
-- Same normalized shape as internship_skills / learning_resource_skills
-- (033). Mutable child content: `for all` owner policy so a later
-- _replace_skills() can DELETE+INSERT the set (internship_skills precedent,
-- explicitly carved out of the no-delete lockdown in 027/028).

create table if not exists program_skills (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references internship_programs (id) on delete cascade,
  skill_id uuid not null references skills (id) on delete restrict,

  requirement text not null default 'REQUIRED' check (requirement in ('REQUIRED', 'OPTIONAL')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint program_skills_unique_per_program unique (program_id, skill_id)
);

create index if not exists program_skills_skill_id_idx on program_skills (skill_id);

alter table program_skills enable row level security;

drop policy if exists "Industry can manage skills for their own programs" on program_skills;
create policy "Industry can manage skills for their own programs"
  on program_skills for all
  to authenticated
  using (public.owns_internship_program(program_skills.program_id))
  with check (public.owns_internship_program(program_skills.program_id));

drop trigger if exists program_skills_set_updated_at on program_skills;
create trigger program_skills_set_updated_at
  before update on program_skills
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 6. program_assignments -- ONE normalized deliverable table
-- ============================================================
-- assignment_type discriminates ASSIGNMENT / QUIZ / PROJECT. No separate
-- assignments / quizzes / projects tables. Project-specific expectations
-- are nullable columns + a CHECK. MVP quiz submissions are reviewed
-- manually -- no quiz engine in Phase 1.

create table if not exists program_assignments (
  id uuid primary key default gen_random_uuid(),
  module_id uuid not null references program_modules (id) on delete cascade,
  -- Denormalized from the parent module. set_program_assignment_program_id
  -- forces it to equal the module's program_id on every insert/update, so
  -- progress / RLS / in-scope queries never need a three-table hop and it
  -- can never drift.
  program_id uuid not null references internship_programs (id) on delete cascade,
  -- Which canonical skill this deliverable trains. NULL = general (always
  -- in scope). SET NULL so deactivating a catalog skill never destroys
  -- assignment history.
  linked_skill_id uuid references skills (id) on delete set null,

  title text not null,
  description text,
  instructions text,
  assignment_type text not null check (assignment_type in ('ASSIGNMENT', 'QUIZ', 'PROJECT')),
  is_required boolean not null default true,
  is_published boolean not null default false,
  order_index int not null default 0 check (order_index >= 0),

  -- Deadline RELATIVE to each workspace's accepted_at (every student
  -- accepts at a different time). Resolved per-workspace in a later phase;
  -- never an absolute date here. NULL = no deadline.
  due_offset_days int check (due_offset_days is null or due_offset_days >= 0),

  submission_kind text not null default 'LINK'
    check (submission_kind in ('LINK', 'REPO', 'FILE', 'TEXT', 'MIXED')),
  repo_required boolean not null default false,
  live_url_expected boolean not null default false,
  max_score numeric(6, 2) check (max_score is null or max_score > 0),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- An assignment that requires a repo must accept one.
  constraint program_assignments_repo_kind_consistent check (
    not (repo_required and submission_kind not in ('REPO', 'MIXED'))
  )
);

create index if not exists program_assignments_module_id_idx on program_assignments (module_id);
create index if not exists program_assignments_program_id_idx on program_assignments (program_id);
create index if not exists program_assignments_linked_skill_id_idx on program_assignments (linked_skill_id);

-- Keeps program_assignments.program_id equal to the parent module's
-- program_id, always -- any client-supplied value is overwritten. Same
-- BEFORE-trigger derivation pattern as set_application_industry_id (020).
create or replace function public.set_program_assignment_program_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_program_id uuid;
begin
  select m.program_id into v_program_id
  from public.program_modules m
  where m.id = new.module_id;

  if v_program_id is null then
    raise exception 'Referenced program module does not exist.' using errcode = '23503';
  end if;

  new.program_id := v_program_id;
  return new;
end;
$$;

revoke all on function public.set_program_assignment_program_id() from public;

drop trigger if exists program_assignments_set_program_id on program_assignments;
create trigger program_assignments_set_program_id
  before insert or update on program_assignments
  for each row
  execute procedure public.set_program_assignment_program_id();

alter table program_assignments enable row level security;

drop policy if exists "Industry can view assignments for their own programs" on program_assignments;
create policy "Industry can view assignments for their own programs"
  on program_assignments for select
  to authenticated
  using (public.owns_internship_program(program_assignments.program_id));

drop policy if exists "Industry can add assignments to their own programs" on program_assignments;
create policy "Industry can add assignments to their own programs"
  on program_assignments for insert
  to authenticated
  with check (
    exists (
      select 1 from program_modules m
      where m.id = program_assignments.module_id
        and public.owns_internship_program(m.program_id)
    )
  );

drop policy if exists "Industry can update assignments for their own programs" on program_assignments;
create policy "Industry can update assignments for their own programs"
  on program_assignments for update
  to authenticated
  using (public.owns_internship_program(program_assignments.program_id))
  with check (
    exists (
      select 1 from program_modules m
      where m.id = program_assignments.module_id
        and public.owns_internship_program(m.program_id)
    )
  );

-- No DELETE policy -- unpublish the module instead (see 039 edge cases).

drop trigger if exists program_assignments_set_updated_at on program_assignments;
create trigger program_assignments_set_updated_at
  before update on program_assignments
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- Post-conditions (for a live check after `supabase db push`)
-- ============================================================
--   -- 5 new tables, RLS on:
--   select tablename, rowsecurity from pg_tables
--   where schemaname = 'public'
--     and tablename in ('internship_programs','program_modules','module_items',
--                       'program_skills','program_assignments');
--
--   -- 1:1 program <-> internship:
--   -- a second internship_programs row for the same internship_id fails
--   -- with 23505 (internship_programs_one_per_internship).
--
--   -- No DELETE / ALL policy on the record tables:
--   select tablename, policyname, cmd from pg_policies
--   where schemaname = 'public'
--     and tablename in ('internship_programs','program_modules','module_items','program_assignments')
--   order by tablename, cmd;
--   -- expect only SELECT / INSERT / UPDATE. program_skills alone shows ALL.
--
--   -- Student-read policies for THESE tables are added by 038, once
--   -- internship_workspaces exists.
