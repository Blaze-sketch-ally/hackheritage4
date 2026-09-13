-- Migration: 063_participation_workspaces
-- Purpose: PHASE 2 of the shared Participation Workspace architecture --
-- the per-student WORKSPACE half, mirroring internship_workspaces (050)
-- for PROJECT / TRAINING / WORKSHOP. One workspace per application that
-- has reached an eligible post-selection status; all per-student state
-- (063+: submissions, reviews, feedback, skill recommendations,
-- evaluation, completion) keys off this table, never off
-- participation_programs.
--
-- Also adds (Part 2, at the end of this file) the STUDENT-read policies
-- for 062's content tables (participation_modules / _resources /
-- _assignments) -- exactly the same "student policies land with the
-- workspace migration" split 050 used for 049's tables, since a student
-- may only read published content for an opportunity they hold a
-- workspace in.
--
-- ============================================================
-- Eligible statuses per kind (no new application status introduced --
-- same "the recruitment/participation outcome is the ONLY gate" rule
-- set_workspace_derived_ids (050) uses for internships)
-- ============================================================
--   PROJECT:  SELECTED, ACTIVE, COMPLETED   (industry_project_applications, 057)
--   TRAINING: ACCEPTED, COMPLETED           (industry_training_applications, 059)
--   WORKSHOP: ACCEPTED, COMPLETED           (industry_workshop_applications, 056)
-- Unlike internships (which have an explicit PENDING_ACCEPTANCE step --
-- the student must accept a real offer before the workspace is theirs to
-- use), a Project/Training/Workshop application only reaches these
-- statuses via an explicit Industry decision the student already applied
-- for -- there is no separate "does the student accept" step in any of
-- those three pipelines. So workspace_status starts at 'ACTIVE'
-- immediately (never 'PENDING_ACCEPTANCE') and only ever needs one further
-- transition, to 'COMPLETED' -- kept in sync with the owning
-- application's own COMPLETED transition by the service layer (never a
-- second, independently-settable source of truth for "is this over").
--
-- ============================================================
-- Object creation order
-- ============================================================
--   1. participation_workspaces      (table + derivation trigger + guards + RLS)
--   2. participant_owns_workspace() / industry_owns_participation_workspace()
--                                     (ownership helpers, for 064/065's RLS)
--   3. student-read policies on participation_modules / _resources /
--      _assignments (062) -- published content only, workspace-gated

create table if not exists participation_workspaces (
  id uuid primary key default gen_random_uuid(),

  kind text not null check (kind in ('PROJECT', 'TRAINING', 'WORKSHOP')),

  -- All derived and OVERWRITTEN by set_participation_workspace_derived_ids
  -- from the referenced application, then frozen by
  -- prevent_participation_workspace_identity_change -- a client-supplied
  -- value is never trusted. Same shape as internship_workspaces (050).
  student_id uuid not null references profiles (id) on delete cascade,
  industry_id uuid not null references profiles (id) on delete restrict,
  project_id uuid references industry_projects (id) on delete restrict,
  training_id uuid references industry_training (id) on delete restrict,
  workshop_id uuid references industry_workshops (id) on delete restrict,

  project_application_id uuid references industry_project_applications (id) on delete cascade,
  training_application_id uuid references industry_training_applications (id) on delete cascade,
  workshop_application_id uuid references industry_workshop_applications (id) on delete cascade,

  workspace_status text not null default 'ACTIVE' check (workspace_status in ('ACTIVE', 'COMPLETED')),
  started_at timestamptz not null default now(),
  completed_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint participation_workspaces_kind_matches_fk check (
    (kind = 'PROJECT' and project_application_id is not null and project_id is not null
       and training_application_id is null and workshop_application_id is null
       and training_id is null and workshop_id is null)
    or (kind = 'TRAINING' and training_application_id is not null and training_id is not null
       and project_application_id is null and workshop_application_id is null
       and project_id is null and workshop_id is null)
    or (kind = 'WORKSHOP' and workshop_application_id is not null and workshop_id is not null
       and project_application_id is null and training_application_id is null
       and project_id is null and training_id is null)
  ),
  constraint participation_workspaces_completed_at_requires_completed
    check (completed_at is null or workspace_status = 'COMPLETED')
);

-- One workspace per application -- a duplicate provision attempt fails
-- with 23505 and the caller treats it as "already provisioned" (same
-- idempotent-ensure convention as internship_workspaces).
create unique index if not exists participation_workspaces_one_per_project_application_idx
  on participation_workspaces (project_application_id) where project_application_id is not null;
create unique index if not exists participation_workspaces_one_per_training_application_idx
  on participation_workspaces (training_application_id) where training_application_id is not null;
create unique index if not exists participation_workspaces_one_per_workshop_application_idx
  on participation_workspaces (workshop_application_id) where workshop_application_id is not null;

create index if not exists participation_workspaces_student_status_idx
  on participation_workspaces (student_id, workspace_status);
create index if not exists participation_workspaces_industry_status_idx
  on participation_workspaces (industry_id, workspace_status);

alter table participation_workspaces enable row level security;

-- ---- derivation + guards ----

create or replace function public.set_participation_workspace_derived_ids()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_student_id uuid;
  v_industry_id uuid;
  v_opportunity_id uuid;
  v_status text;
begin
  if new.project_application_id is not null then
    select student_id, industry_id, project_id, status
      into v_student_id, v_industry_id, v_opportunity_id, v_status
    from public.industry_project_applications where id = new.project_application_id;
    if v_student_id is null then
      raise exception 'Referenced project application does not exist.' using errcode = '23503';
    end if;
    if v_status not in ('SELECTED', 'ACTIVE', 'COMPLETED') then
      raise exception 'A participation workspace can only be created for a SELECTED/ACTIVE/COMPLETED project application.' using errcode = '42501';
    end if;
    new.kind := 'PROJECT';
    new.project_id := v_opportunity_id;
    new.training_id := null;
    new.workshop_id := null;

  elsif new.training_application_id is not null then
    select student_id, industry_id, training_id, status
      into v_student_id, v_industry_id, v_opportunity_id, v_status
    from public.industry_training_applications where id = new.training_application_id;
    if v_student_id is null then
      raise exception 'Referenced training application does not exist.' using errcode = '23503';
    end if;
    if v_status not in ('ACCEPTED', 'COMPLETED') then
      raise exception 'A participation workspace can only be created for an ACCEPTED/COMPLETED training application.' using errcode = '42501';
    end if;
    new.kind := 'TRAINING';
    new.training_id := v_opportunity_id;
    new.project_id := null;
    new.workshop_id := null;

  elsif new.workshop_application_id is not null then
    select student_id, industry_id, workshop_id, status
      into v_student_id, v_industry_id, v_opportunity_id, v_status
    from public.industry_workshop_applications where id = new.workshop_application_id;
    if v_student_id is null then
      raise exception 'Referenced workshop application does not exist.' using errcode = '23503';
    end if;
    if v_status not in ('ACCEPTED', 'COMPLETED') then
      raise exception 'A participation workspace can only be created for an ACCEPTED/COMPLETED workshop application.' using errcode = '42501';
    end if;
    new.kind := 'WORKSHOP';
    new.workshop_id := v_opportunity_id;
    new.project_id := null;
    new.training_id := null;

  else
    raise exception 'A participation workspace must reference exactly one application.' using errcode = '23514';
  end if;

  new.student_id := v_student_id;
  new.industry_id := v_industry_id;
  return new;
end;
$$;

revoke all on function public.set_participation_workspace_derived_ids() from public;

drop trigger if exists participation_workspaces_set_derived_ids on participation_workspaces;
create trigger participation_workspaces_set_derived_ids
  before insert on participation_workspaces
  for each row
  execute procedure public.set_participation_workspace_derived_ids();

create or replace function public.prevent_participation_workspace_identity_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.kind is distinct from old.kind
    or new.student_id is distinct from old.student_id
    or new.industry_id is distinct from old.industry_id
    or new.project_id is distinct from old.project_id
    or new.training_id is distinct from old.training_id
    or new.workshop_id is distinct from old.workshop_id
    or new.project_application_id is distinct from old.project_application_id
    or new.training_application_id is distinct from old.training_application_id
    or new.workshop_application_id is distinct from old.workshop_application_id
  then
    raise exception 'Cannot change the application, student, industry, or opportunity of an existing participation workspace.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_participation_workspace_identity_change() from public;

drop trigger if exists participation_workspaces_prevent_identity_change on participation_workspaces;
create trigger participation_workspaces_prevent_identity_change
  before update on participation_workspaces
  for each row
  execute procedure public.prevent_participation_workspace_identity_change();

drop trigger if exists participation_workspaces_set_updated_at on participation_workspaces;
create trigger participation_workspaces_set_updated_at
  before update on participation_workspaces
  for each row
  execute procedure public.set_updated_at();

-- ---- RLS ----

drop policy if exists "Students can view their own participation workspace" on participation_workspaces;
create policy "Students can view their own participation workspace"
  on participation_workspaces for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

-- No student UPDATE policy: unlike an internship workspace offer, there is
-- no student-side accept/decline step here (see header) -- the student
-- has nothing to change on this row. It is read-only to them.

drop policy if exists "Industry can view participation workspaces for their own opportunities" on participation_workspaces;
create policy "Industry can view participation workspaces for their own opportunities"
  on participation_workspaces for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- industry_id is derived by set_participation_workspace_derived_ids (which
-- runs BEFORE this WITH CHECK), so auth.uid() = industry_id here confirms
-- the derived owner -- and therefore the application's real owner -- is
-- the caller. Same construction as internship_workspaces' INSERT policy.
drop policy if exists "Industry can provision participation workspaces for their own opportunities" on participation_workspaces;
create policy "Industry can provision participation workspaces for their own opportunities"
  on participation_workspaces for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can manage participation workspaces for their own opportunities" on participation_workspaces;
create policy "Industry can manage participation workspaces for their own opportunities"
  on participation_workspaces for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No DELETE policy for any role -- a workspace is a permanent record.

-- ============================================================
-- Ownership helpers for 064/065's child tables
-- ============================================================

create or replace function public.student_owns_participation_workspace(p_workspace_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.participation_workspaces w
    where w.id = p_workspace_id
      and w.student_id = auth.uid()
      and public.is_student(auth.uid())
  );
$$;

revoke all on function public.student_owns_participation_workspace(uuid) from public;
revoke all on function public.student_owns_participation_workspace(uuid) from anon;
grant execute on function public.student_owns_participation_workspace(uuid) to authenticated;

create or replace function public.industry_owns_participation_workspace(p_workspace_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.participation_workspaces w
    where w.id = p_workspace_id
      and w.industry_id = auth.uid()
      and public.is_industry(auth.uid())
  );
$$;

revoke all on function public.industry_owns_participation_workspace(uuid) from public;
revoke all on function public.industry_owns_participation_workspace(uuid) from anon;
grant execute on function public.industry_owns_participation_workspace(uuid) to authenticated;

-- ============================================================
-- Part 2: student-read access to 062's PUBLISHED content, gated on
-- holding a workspace for that program (mirrors the split 050 used for
-- 049's tables: the workspace table must exist first).
-- ============================================================

create or replace function public.student_has_workspace_for_program(p_program_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.participation_workspaces w
    join public.participation_programs prog on prog.id = p_program_id
    where w.student_id = auth.uid()
      and public.is_student(auth.uid())
      and (
        (prog.kind = 'PROJECT' and w.project_id = prog.project_id)
        or (prog.kind = 'TRAINING' and w.training_id = prog.training_id)
        or (prog.kind = 'WORKSHOP' and w.workshop_id = prog.workshop_id)
      )
  );
$$;

revoke all on function public.student_has_workspace_for_program(uuid) from public;
revoke all on function public.student_has_workspace_for_program(uuid) from anon;
grant execute on function public.student_has_workspace_for_program(uuid) to authenticated;

drop policy if exists "Students can view published participation modules for their workspace" on participation_modules;
create policy "Students can view published participation modules for their workspace"
  on participation_modules for select
  to authenticated
  using (is_published and public.student_has_workspace_for_program(participation_modules.program_id));

drop policy if exists "Students can view published participation resources for their workspace" on participation_resources;
create policy "Students can view published participation resources for their workspace"
  on participation_resources for select
  to authenticated
  using (is_published and public.student_has_workspace_for_program(participation_resources.program_id));

drop policy if exists "Students can view published participation assignments for their workspace" on participation_assignments;
create policy "Students can view published participation assignments for their workspace"
  on participation_assignments for select
  to authenticated
  using (is_published and public.student_has_workspace_for_program(participation_assignments.program_id));
