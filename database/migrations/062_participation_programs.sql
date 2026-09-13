-- Migration: 062_participation_programs
-- Purpose: PHASE 1 (database foundation) of the shared Participation
-- Workspace architecture for PROJECT / TRAINING / WORKSHOP -- the
-- PROGRAM / TEMPLATE half. Mirrors the approved Internship Workspace
-- Template+Instance split (049/050/051) as closely as this domain allows:
-- an INDUSTRY account authors ONE participation_program per opportunity
-- (project/training/workshop posting): ordered modules, resources, and
-- gradable assignments. When a student's application later reaches an
-- eligible post-selection status, migration 063 provisions ONE
-- participation_workspace per application that references this program's
-- content. All per-student state (submissions, reviews, feedback, skill
-- recommendations, evaluation, completion -- 064/065) keys off the
-- workspace, never off the program.
--
-- ============================================================
-- Why ONE shared domain, not three
-- ============================================================
-- Projects/Training/Workshops each already have their own posting table
-- (022/023/024) and their own application table (057/059/056) with their
-- own status vocabulary -- those are UNCHANGED here. What they were
-- missing is the internship's post-selection half: real content
-- (modules/resources/assignments), a workspace, submissions, review,
-- feedback, skill recommendations, and a structured final evaluation.
-- Building that three times, once per module, would triplicate every
-- table, trigger, RLS policy, service, and UI component in this file for
-- no behavioural difference between them -- so instead this is ONE
-- polymorphic domain, keyed by a `kind` discriminator column
-- ('PROJECT' | 'TRAINING' | 'WORKSHOP'), exactly the same shape
-- `applications.opportunity_type` already uses to discriminate
-- INTERNSHIP/JOB rows in one table (020_applications.sql).
--
-- ============================================================
-- Deliberate differences from the Internship Workspace precedent
-- ============================================================
-- * Ownership is NOT stored on participation_programs (no industry_id
--   column) -- it is resolved live through whichever of
--   project_id/training_id/workshop_id is set, joined to that table's own
--   industry_id, exactly like internship_programs resolves ownership
--   through internships.industry_id rather than storing it again. One
--   source of truth for "who owns this"; see owns_participation_program()
--   below.
-- * participation_resources.module_id and participation_assignments.module_id
--   are NULLABLE (module_items.module_id / program_assignments.module_id
--   are NOT NULL for internships) -- this is an explicit, approved product
--   difference: a Project/Training/Workshop program can attach a resource
--   or assignment directly at the program level (e.g. a single
--   "Final project submission" task with no module structure), which a
--   lightweight Workshop program especially needs.
-- * participation_assignments.due_at is an ABSOLUTE timestamp, not an
--   offset-from-acceptance like program_assignments.due_offset_days --
--   simpler, and matches the product brief's explicit field list.
--
-- ============================================================
-- Relationship to the existing schema
-- ============================================================
-- * participation_programs references exactly ONE of industry_projects(id)
--   / industry_training(id) / industry_workshops(id), ON DELETE CASCADE --
--   none of those three postings can be hard-deleted at the application
--   layer (no delete route exists), so this CASCADE only ever fires on a
--   service_role / GDPR path, matching every other opportunity-owned
--   child table in this schema.
-- * participation_resources / participation_assignments reference canonical
--   skills(id) nowhere in this migration (assignments link a skill in a
--   later phase if ever needed) -- kept minimal per the brief.
-- * NOTHING here touches internships / internship_programs / program_modules
--   / module_items / program_assignments / internship_workspaces or any of
--   their RLS, triggers, or policies. The Internship Workspace is entirely
--   unchanged.
--
-- ============================================================
-- Conventions reused (001-061)
-- ============================================================
-- * uuid PK default gen_random_uuid(); created_at / updated_at timestamptz
--   not null default now(); public.set_updated_at() trigger (012), reused
--   never redefined.
-- * Enum-like columns -> CHECK value lists, never a Postgres enum type.
-- * public.is_industry(uuid) (017) for the role half of every owner
--   predicate.
-- * Record tables: explicit per-command SELECT / INSERT / UPDATE policies
--   and NO DELETE policy -- hard delete denied for every RLS-governed
--   caller (020/027/028/030/049 precedent). Authoring mistakes are
--   corrected by unpublish + edit.
-- * Idempotent in shape: create table / index if not exists; drop
--   policy/trigger if exists + create; create or replace function.
--   Forward-only, additive.
--
-- No seed data -- programs are authored by the running system.

-- ============================================================
-- Object creation order in this file (dependency-correct)
-- ============================================================
--   1. participation_programs        (table + RLS)
--   2. owns_participation_program()  -- language sql; AFTER the table
--   3. participation_modules         (RLS uses the helper)
--   4. participation_resources       (+ derivation trigger for program_id)
--   5. participation_assignments     (+ derivation trigger for program_id)

-- ============================================================
-- 1. participation_programs -- one content template per opportunity
-- ============================================================

create table if not exists participation_programs (
  id uuid primary key default gen_random_uuid(),

  kind text not null check (kind in ('PROJECT', 'TRAINING', 'WORKSHOP')),
  project_id uuid references industry_projects (id) on delete cascade,
  training_id uuid references industry_training (id) on delete cascade,
  workshop_id uuid references industry_workshops (id) on delete cascade,

  title text not null,
  description text,

  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'ARCHIVED')),
  published_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint participation_programs_kind_matches_fk check (
    (kind = 'PROJECT' and project_id is not null and training_id is null and workshop_id is null)
    or (kind = 'TRAINING' and training_id is not null and project_id is null and workshop_id is null)
    or (kind = 'WORKSHOP' and workshop_id is not null and project_id is null and training_id is null)
  )
);

-- STRICTLY 1:1 with the posting -- partial unique indexes (one per FK,
-- since at most one is ever non-null per row) are the cardinality
-- guarantee, same intent as internship_programs_one_per_internship.
create unique index if not exists participation_programs_one_per_project_idx
  on participation_programs (project_id) where project_id is not null;
create unique index if not exists participation_programs_one_per_training_idx
  on participation_programs (training_id) where training_id is not null;
create unique index if not exists participation_programs_one_per_workshop_idx
  on participation_programs (workshop_id) where workshop_id is not null;

alter table participation_programs enable row level security;

drop policy if exists "Industry can view their own participation programs" on participation_programs;
create policy "Industry can view their own participation programs"
  on participation_programs for select
  to authenticated
  using (
    public.is_industry(auth.uid()) and (
      exists (select 1 from industry_projects p where p.id = participation_programs.project_id and p.industry_id = auth.uid())
      or exists (select 1 from industry_training t where t.id = participation_programs.training_id and t.industry_id = auth.uid())
      or exists (select 1 from industry_workshops w where w.id = participation_programs.workshop_id and w.industry_id = auth.uid())
    )
  );

drop policy if exists "Industry can create a program for their own opportunity" on participation_programs;
create policy "Industry can create a program for their own opportunity"
  on participation_programs for insert
  to authenticated
  with check (
    public.is_industry(auth.uid()) and (
      exists (select 1 from industry_projects p where p.id = participation_programs.project_id and p.industry_id = auth.uid())
      or exists (select 1 from industry_training t where t.id = participation_programs.training_id and t.industry_id = auth.uid())
      or exists (select 1 from industry_workshops w where w.id = participation_programs.workshop_id and w.industry_id = auth.uid())
    )
  );

drop policy if exists "Industry can update their own participation programs" on participation_programs;
create policy "Industry can update their own participation programs"
  on participation_programs for update
  to authenticated
  using (
    public.is_industry(auth.uid()) and (
      exists (select 1 from industry_projects p where p.id = participation_programs.project_id and p.industry_id = auth.uid())
      or exists (select 1 from industry_training t where t.id = participation_programs.training_id and t.industry_id = auth.uid())
      or exists (select 1 from industry_workshops w where w.id = participation_programs.workshop_id and w.industry_id = auth.uid())
    )
  )
  with check (
    public.is_industry(auth.uid()) and (
      exists (select 1 from industry_projects p where p.id = participation_programs.project_id and p.industry_id = auth.uid())
      or exists (select 1 from industry_training t where t.id = participation_programs.training_id and t.industry_id = auth.uid())
      or exists (select 1 from industry_workshops w where w.id = participation_programs.workshop_id and w.industry_id = auth.uid())
    )
  );

-- No DELETE policy -- ARCHIVE (status) is the lifecycle end.

drop trigger if exists participation_programs_set_updated_at on participation_programs;
create trigger participation_programs_set_updated_at
  before update on participation_programs
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 2. Ownership helper -- defined AFTER participation_programs exists
-- ============================================================
-- True when auth.uid() is the INDUSTRY account that owns the opportunity
-- behind the given program, whichever of the three it is. SECURITY
-- DEFINER + pinned empty search_path + STABLE -- same pattern as
-- owns_internship_program (049). Every program-content policy below (and
-- the student-read policies added in 063) routes ownership through this
-- one function.

create or replace function public.owns_participation_program(p_program_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.participation_programs prog
    left join public.industry_projects p on p.id = prog.project_id
    left join public.industry_training t on t.id = prog.training_id
    left join public.industry_workshops w on w.id = prog.workshop_id
    where prog.id = p_program_id
      and coalesce(p.industry_id, t.industry_id, w.industry_id) = auth.uid()
      and public.is_industry(auth.uid())
  );
$$;

revoke all on function public.owns_participation_program(uuid) from public;
revoke all on function public.owns_participation_program(uuid) from anon;
grant execute on function public.owns_participation_program(uuid) to authenticated;

-- ============================================================
-- 3. participation_modules -- ordered sections of a program
-- ============================================================

create table if not exists participation_modules (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references participation_programs (id) on delete cascade,

  title text not null,
  description text,

  sequence_order int not null default 0 check (sequence_order >= 0),
  is_published boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists participation_modules_program_id_idx on participation_modules (program_id);

alter table participation_modules enable row level security;

-- Explicit per-command SELECT/INSERT/UPDATE policies, no DELETE policy --
-- hard delete denied for every RLS-governed caller (020/027/028/030/049
-- precedent). Authoring mistakes are corrected by unpublish + edit.
drop policy if exists "Industry can view their own participation modules" on participation_modules;
create policy "Industry can view their own participation modules"
  on participation_modules for select
  to authenticated
  using (public.owns_participation_program(participation_modules.program_id));

drop policy if exists "Industry can create their own participation modules" on participation_modules;
create policy "Industry can create their own participation modules"
  on participation_modules for insert
  to authenticated
  with check (public.owns_participation_program(participation_modules.program_id));

drop policy if exists "Industry can update their own participation modules" on participation_modules;
create policy "Industry can update their own participation modules"
  on participation_modules for update
  to authenticated
  using (public.owns_participation_program(participation_modules.program_id))
  with check (public.owns_participation_program(participation_modules.program_id));

drop trigger if exists participation_modules_set_updated_at on participation_modules;
create trigger participation_modules_set_updated_at
  before update on participation_modules
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 4. participation_resources -- videos/documents/links, program- or
--    module-scoped
-- ============================================================

create table if not exists participation_resources (
  id uuid primary key default gen_random_uuid(),
  -- Denormalized from the parent module when module_id is set (mirrors
  -- set_program_assignment_program_id, 049) -- always non-null so RLS and
  -- listing queries never need a conditional join.
  program_id uuid not null references participation_programs (id) on delete cascade,
  module_id uuid references participation_modules (id) on delete cascade,

  title text not null,
  description text,
  resource_type text not null check (resource_type in ('VIDEO', 'DOCUMENT', 'LINK', 'REFERENCE', 'OTHER')),
  resource_url text,

  sequence_order int not null default 0 check (sequence_order >= 0),
  is_published boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists participation_resources_program_id_idx on participation_resources (program_id);
create index if not exists participation_resources_module_id_idx on participation_resources (module_id);

create or replace function public.set_participation_resource_program_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_program_id uuid;
begin
  if new.module_id is not null then
    select program_id into v_program_id from public.participation_modules where id = new.module_id;
    if v_program_id is null then
      raise exception 'Referenced module does not exist.' using errcode = '23503';
    end if;
    new.program_id := v_program_id;
  elsif new.program_id is null then
    raise exception 'A resource must reference a module or a program.' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke all on function public.set_participation_resource_program_id() from public;

drop trigger if exists participation_resources_set_program_id on participation_resources;
create trigger participation_resources_set_program_id
  before insert or update on participation_resources
  for each row
  execute procedure public.set_participation_resource_program_id();

alter table participation_resources enable row level security;

drop policy if exists "Industry can view their own participation resources" on participation_resources;
create policy "Industry can view their own participation resources"
  on participation_resources for select
  to authenticated
  using (public.owns_participation_program(participation_resources.program_id));

drop policy if exists "Industry can create their own participation resources" on participation_resources;
create policy "Industry can create their own participation resources"
  on participation_resources for insert
  to authenticated
  with check (public.owns_participation_program(participation_resources.program_id));

drop policy if exists "Industry can update their own participation resources" on participation_resources;
create policy "Industry can update their own participation resources"
  on participation_resources for update
  to authenticated
  using (public.owns_participation_program(participation_resources.program_id))
  with check (public.owns_participation_program(participation_resources.program_id));

drop trigger if exists participation_resources_set_updated_at on participation_resources;
create trigger participation_resources_set_updated_at
  before update on participation_resources
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 5. participation_assignments -- gradable tasks, program- or
--    module-scoped
-- ============================================================

create table if not exists participation_assignments (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references participation_programs (id) on delete cascade,
  module_id uuid references participation_modules (id) on delete cascade,

  title text not null,
  description text,
  instructions text,

  due_at timestamptz,
  max_score numeric(6, 2) check (max_score is null or max_score > 0),

  is_required boolean not null default true,
  is_published boolean not null default false,
  sequence_order int not null default 0 check (sequence_order >= 0),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists participation_assignments_program_id_idx on participation_assignments (program_id);
create index if not exists participation_assignments_module_id_idx on participation_assignments (module_id);

create or replace function public.set_participation_assignment_program_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_program_id uuid;
begin
  if new.module_id is not null then
    select program_id into v_program_id from public.participation_modules where id = new.module_id;
    if v_program_id is null then
      raise exception 'Referenced module does not exist.' using errcode = '23503';
    end if;
    new.program_id := v_program_id;
  elsif new.program_id is null then
    raise exception 'An assignment must reference a module or a program.' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke all on function public.set_participation_assignment_program_id() from public;

drop trigger if exists participation_assignments_set_program_id on participation_assignments;
create trigger participation_assignments_set_program_id
  before insert or update on participation_assignments
  for each row
  execute procedure public.set_participation_assignment_program_id();

alter table participation_assignments enable row level security;

drop policy if exists "Industry can view their own participation assignments" on participation_assignments;
create policy "Industry can view their own participation assignments"
  on participation_assignments for select
  to authenticated
  using (public.owns_participation_program(participation_assignments.program_id));

drop policy if exists "Industry can create their own participation assignments" on participation_assignments;
create policy "Industry can create their own participation assignments"
  on participation_assignments for insert
  to authenticated
  with check (public.owns_participation_program(participation_assignments.program_id));

drop policy if exists "Industry can update their own participation assignments" on participation_assignments;
create policy "Industry can update their own participation assignments"
  on participation_assignments for update
  to authenticated
  using (public.owns_participation_program(participation_assignments.program_id))
  with check (public.owns_participation_program(participation_assignments.program_id));

drop trigger if exists participation_assignments_set_updated_at on participation_assignments;
create trigger participation_assignments_set_updated_at
  before update on participation_assignments
  for each row
  execute procedure public.set_updated_at();
