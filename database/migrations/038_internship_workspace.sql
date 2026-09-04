-- Migration: 038_internship_workspace
-- Purpose: PHASE 1 (database foundation) of the approved post-selection
-- Internship Workspace architecture -- the WORKSPACE / INSTANCE half.
--
-- ============================================================
-- Where this sits in the approved architecture
-- ============================================================
-- When an application reaches status = 'SELECTED' (020_applications.sql --
-- UNCHANGED, no new status) for an internship whose work_mode is REMOTE or
-- HYBRID, ONE internship_workspace is provisioned for that application.
-- The workspace IS the offer (PENDING_ACCEPTANCE), the acceptance record,
-- the training container and the completion anchor. All per-student state
-- keys off workspace_id.
--
-- Phase 1 delivers the tables, the identity/derivation/transition
-- triggers, the RLS, and the work-mode protection trigger. It delivers NO
-- provisioning code: application_service.update_status() is NOT touched in
-- this phase, and no workspace rows are created for existing SELECTED
-- applications (a later explicit provisioning/healing phase does that).
--
-- ============================================================
-- Key guarantees enforced HERE, at the database
-- ============================================================
-- * UNIQUE(application_id)                -> one workspace per application;
--                                            the idempotency guarantee for
--                                            Phase 2 provisioning.
-- * set_workspace_derived_ids (BEFORE INSERT):
--     - student_id / industry_id / internship_id copied (and overwritten)
--       from the referenced application; work_mode copied from the
--       internship. Never trusted from client input.
--     - RAISES unless applications.status = 'SELECTED'.
--     - RAISES unless internships.work_mode IN ('REMOTE','HYBRID')  ->  an
--       ONSITE or NULL-work_mode internship can NEVER receive a workspace,
--       even via a direct REST insert.
-- * prevent_workspace_identity_change (BEFORE UPDATE): application / student
--   / industry / internship / work_mode are frozen after creation for
--   every ordinary caller (service_role steps aside) -- 020/030 pattern.
-- * enforce_workspace_status_transitions (BEFORE UPDATE): a STUDENT caller
--   may ONLY move PENDING_ACCEPTANCE -> ACCEPTED or -> DECLINED. Every
--   other transition (IN_PROGRESS / COMPLETED / RESCINDED) is
--   industry/system -- mirrors prevent_student_status_override on
--   applications (020). The full transition graph is the service layer's
--   job (later phase), exactly as it is for applications.
-- * Workspace RLS routes authorization through the WORKSPACE relationship
--   (student_id / industry_id, both immutable). It NEVER references
--   internships.status -- a SELECTED student keeps full workspace access
--   after the posting becomes CLOSED or ARCHIVED.
--
-- ============================================================
-- Skill selection and the verification boundary
-- ============================================================
-- workspace_skill_selections records which OPTIONAL program skills a
-- student chose to focus on. It references skills(id) (canonical catalog,
-- 003) and internship_workspaces(id) ONLY -- NEVER student_skills.
-- Selecting a workspace skill does not create a student_skill, change
-- proficiency, or mark anything verified. The assessment scoring path
-- (015_assessment_verification.sql) remains the sole writer of
-- student_skills verification state.
--
-- ============================================================
-- Conventions reused (001-037)
-- ============================================================
-- * uuid PK; created_at/updated_at; public.set_updated_at() (012).
-- * CHECK value lists, never enum types.
-- * public.is_student / public.is_industry (012/013/017).
-- * SECURITY DEFINER + set search_path = '' for every helper and trigger
--   function; defensive revoke of the trigger-typed ones.
-- * internship_workspaces is a record: explicit SELECT / INSERT / UPDATE
--   policies, NO DELETE policy (DECLINED / RESCINDED are soft-terminal).
-- * Idempotent in shape; forward-only; additive. The ONE existing-table
--   touch is an additive BEFORE UPDATE trigger on `internships` (same
--   "additive trigger on an existing table" pattern as
--   032_profile_role_immutability.sql on `profiles`) -- no column, policy,
--   or existing trigger on internships is changed.

-- ============================================================
-- 1. internship_workspaces
-- ============================================================

create table if not exists internship_workspaces (
  id uuid primary key default gen_random_uuid(),

  -- One workspace per application. A duplicate provision attempt fails
  -- with 23505 and the caller treats it as "already provisioned".
  application_id uuid not null references applications (id) on delete cascade,

  -- All four are copied and OVERWRITTEN by set_workspace_derived_ids from
  -- the application / internship, then frozen by
  -- prevent_workspace_identity_change. Same deletion strategy as
  -- applications (020) / interviews (030): student_id CASCADE (a student
  -- takes their own rows on account deletion); industry_id / internship_id
  -- RESTRICT (workspace history survives an industry/posting removal
  -- attempt -- which 027/028 already block anyway).
  student_id uuid not null references profiles (id) on delete cascade,
  industry_id uuid not null references profiles (id) on delete restrict,
  internship_id uuid not null references internships (id) on delete restrict,

  -- Snapshot of internships.work_mode at provision time. Only the two
  -- eligible modes are storable; set_workspace_derived_ids raises for
  -- ONSITE / NULL. The program is NOT snapshotted as a column -- it is
  -- 1:1 with the internship (037) and derived via internship_id wherever
  -- needed, so there is nothing to keep in sync.
  work_mode text not null check (work_mode in ('REMOTE', 'HYBRID')),

  workspace_status text not null default 'PENDING_ACCEPTANCE' check (
    workspace_status in (
      'PENDING_ACCEPTANCE', 'ACCEPTED', 'IN_PROGRESS', 'COMPLETED', 'DECLINED', 'RESCINDED'
    )
  ),

  accepted_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  declined_at timestamptz,
  decline_reason text,
  rescinded_at timestamptz,
  rescind_reason text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint internship_workspaces_one_per_application unique (application_id),
  constraint internship_workspaces_completed_at_requires_completed
    check (completed_at is null or workspace_status = 'COMPLETED'),
  constraint internship_workspaces_declined_fields_require_declined
    check ((declined_at is null and decline_reason is null) or workspace_status = 'DECLINED'),
  constraint internship_workspaces_rescinded_fields_require_rescinded
    check ((rescinded_at is null and rescind_reason is null) or workspace_status = 'RESCINDED')
);

create index if not exists internship_workspaces_student_status_idx
  on internship_workspaces (student_id, workspace_status);
create index if not exists internship_workspaces_industry_status_idx
  on internship_workspaces (industry_id, workspace_status);
create index if not exists internship_workspaces_internship_id_idx
  on internship_workspaces (internship_id);

-- ---- derivation + guards ----

create or replace function public.set_workspace_derived_ids()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_student_id uuid;
  v_industry_id uuid;
  v_internship_id uuid;
  v_app_status text;
  v_opportunity_type text;
  v_work_mode text;
begin
  select a.student_id, a.industry_id, a.internship_id, a.status, a.opportunity_type
    into v_student_id, v_industry_id, v_internship_id, v_app_status, v_opportunity_type
  from public.applications a
  where a.id = new.application_id;

  if v_student_id is null then
    raise exception 'Referenced application does not exist.' using errcode = '23503';
  end if;

  if v_opportunity_type <> 'INTERNSHIP' or v_internship_id is null then
    raise exception 'An internship workspace can only be created for an INTERNSHIP application.'
      using errcode = '42501';
  end if;

  -- The recruitment outcome is the ONLY gate. No new application status is
  -- introduced (approved architecture) -- the application stays SELECTED.
  if v_app_status <> 'SELECTED' then
    raise exception 'An internship workspace can only be created for a SELECTED application.'
      using errcode = '42501';
  end if;

  select i.work_mode into v_work_mode
  from public.internships i
  where i.id = v_internship_id;

  -- REMOTE / HYBRID only. ONSITE and NULL are ineligible: the student
  -- coordinates directly with the company and no workspace exists.
  if v_work_mode is null or v_work_mode not in ('REMOTE', 'HYBRID') then
    raise exception 'An internship workspace is only available for a REMOTE or HYBRID internship.'
      using errcode = '42501';
  end if;

  new.student_id    := v_student_id;
  new.industry_id   := v_industry_id;
  new.internship_id := v_internship_id;
  new.work_mode     := v_work_mode;
  return new;
end;
$$;

revoke all on function public.set_workspace_derived_ids() from public;

drop trigger if exists internship_workspaces_set_derived_ids on internship_workspaces;
create trigger internship_workspaces_set_derived_ids
  before insert on internship_workspaces
  for each row
  execute procedure public.set_workspace_derived_ids();

create or replace function public.prevent_workspace_identity_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.application_id is distinct from old.application_id
    or new.student_id is distinct from old.student_id
    or new.industry_id is distinct from old.industry_id
    or new.internship_id is distinct from old.internship_id
    or new.work_mode is distinct from old.work_mode
  then
    raise exception 'Cannot change the application, student, industry, internship, or work mode of an existing internship workspace.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_workspace_identity_change() from public;

drop trigger if exists internship_workspaces_prevent_identity_change on internship_workspaces;
create trigger internship_workspaces_prevent_identity_change
  before update on internship_workspaces
  for each row
  execute procedure public.prevent_workspace_identity_change();

create or replace function public.enforce_workspace_status_transitions()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.workspace_status is not distinct from old.workspace_status then
    return new;
  end if;

  -- A STUDENT caller (the workspace owner) may only accept or decline a
  -- still-pending offer. IN_PROGRESS / COMPLETED / RESCINDED are
  -- industry/system transitions. Mirrors prevent_student_status_override
  -- on applications (020).
  if auth.uid() = old.student_id then
    if not (
      old.workspace_status = 'PENDING_ACCEPTANCE'
      and new.workspace_status in ('ACCEPTED', 'DECLINED')
    ) then
      raise exception 'A student may only accept or decline a pending internship workspace.'
        using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_workspace_status_transitions() from public;

drop trigger if exists internship_workspaces_enforce_status_transitions on internship_workspaces;
create trigger internship_workspaces_enforce_status_transitions
  before update on internship_workspaces
  for each row
  execute procedure public.enforce_workspace_status_transitions();

drop trigger if exists internship_workspaces_set_updated_at on internship_workspaces;
create trigger internship_workspaces_set_updated_at
  before update on internship_workspaces
  for each row
  execute procedure public.set_updated_at();

-- ---- RLS ----

alter table internship_workspaces enable row level security;

drop policy if exists "Students can view their own internship workspace" on internship_workspaces;
create policy "Students can view their own internship workspace"
  on internship_workspaces for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

-- Student UPDATE is ownership-scoped here and further constrained to
-- accept/decline by enforce_workspace_status_transitions.
drop policy if exists "Students can respond to their own internship workspace" on internship_workspaces;
create policy "Students can respond to their own internship workspace"
  on internship_workspaces for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Industry can view internship workspaces for their own internships" on internship_workspaces;
create policy "Industry can view internship workspaces for their own internships"
  on internship_workspaces for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- industry_id is set by set_workspace_derived_ids (which runs BEFORE this
-- WITH CHECK) from the referenced application, so auth.uid() = industry_id
-- here confirms the derived owner -- and therefore the application's real
-- owner -- is the caller. Same construction as the interviews INSERT
-- policy (030).
drop policy if exists "Industry can provision internship workspaces for their own internships" on internship_workspaces;
create policy "Industry can provision internship workspaces for their own internships"
  on internship_workspaces for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can manage internship workspaces for their own internships" on internship_workspaces;
create policy "Industry can manage internship workspaces for their own internships"
  on internship_workspaces for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No DELETE policy for any role -- DECLINED / RESCINDED are soft-terminal;
-- workspaces are permanent records (020/027/028/030 precedent).

-- ============================================================
-- 2. workspace ownership helpers (for every child table's RLS)
-- ============================================================

create or replace function public.student_owns_workspace(p_workspace_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.internship_workspaces w
    where w.id = p_workspace_id
      and w.student_id = auth.uid()
      and public.is_student(auth.uid())
  );
$$;

revoke all on function public.student_owns_workspace(uuid) from public;
revoke all on function public.student_owns_workspace(uuid) from anon;
grant execute on function public.student_owns_workspace(uuid) to authenticated;

create or replace function public.industry_owns_workspace(p_workspace_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.internship_workspaces w
    where w.id = p_workspace_id
      and w.industry_id = auth.uid()
      and public.is_industry(auth.uid())
  );
$$;

revoke all on function public.industry_owns_workspace(uuid) from public;
revoke all on function public.industry_owns_workspace(uuid) from anon;
grant execute on function public.industry_owns_workspace(uuid) to authenticated;

-- True when the caller is a student with a workspace on the internship
-- behind this program, that workspace is not DECLINED/RESCINDED, and the
-- program is PUBLISHED. Does NOT reference internships.status -- a closed
-- or archived posting does not revoke a selected student's access.
create or replace function public.student_can_access_program(p_program_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.internship_programs prog
    join public.internship_workspaces w on w.internship_id = prog.internship_id
    where prog.id = p_program_id
      and prog.status = 'PUBLISHED'
      and w.student_id = auth.uid()
      and public.is_student(auth.uid())
      and w.workspace_status not in ('DECLINED', 'RESCINDED')
  );
$$;

revoke all on function public.student_can_access_program(uuid) from public;
revoke all on function public.student_can_access_program(uuid) from anon;
grant execute on function public.student_can_access_program(uuid) to authenticated;

-- ============================================================
-- 3. workspace_skill_selections
-- ============================================================

create table if not exists workspace_skill_selections (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references internship_workspaces (id) on delete cascade,
  -- Canonical catalog only. NEVER student_skills.
  skill_id uuid not null references skills (id) on delete restrict,

  created_at timestamptz not null default now(),

  constraint workspace_skill_selections_unique_per_workspace unique (workspace_id, skill_id)
);

create index if not exists workspace_skill_selections_skill_id_idx
  on workspace_skill_selections (skill_id);

-- A selection is valid only for an OPTIONAL skill that this workspace's
-- program actually offers, and only while the workspace is live. The
-- "cannot remove a skill that already has submissions" guard needs
-- workspace_submissions and is added in 039.
create or replace function public.enforce_workspace_skill_selectable()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_internship_id uuid;
  v_status text;
  v_selectable boolean;
begin
  if tg_op = 'DELETE' then
    select w.workspace_status into v_status
    from public.internship_workspaces w where w.id = old.workspace_id;
    if v_status in ('COMPLETED', 'DECLINED', 'RESCINDED') then
      raise exception 'Skill selections cannot change once the workspace is completed or closed.'
        using errcode = '42501';
    end if;
    return old;
  end if;

  select w.internship_id, w.workspace_status
    into v_internship_id, v_status
  from public.internship_workspaces w
  where w.id = new.workspace_id;

  if v_internship_id is null then
    raise exception 'Referenced internship workspace does not exist.' using errcode = '23503';
  end if;

  if v_status in ('COMPLETED', 'DECLINED', 'RESCINDED') then
    raise exception 'Skill selections cannot change once the workspace is completed or closed.'
      using errcode = '42501';
  end if;

  select exists (
    select 1
    from public.internship_programs prog
    join public.program_skills ps on ps.program_id = prog.id
    where prog.internship_id = v_internship_id
      and ps.skill_id = new.skill_id
      and ps.requirement = 'OPTIONAL'
  ) into v_selectable;

  if not v_selectable then
    raise exception 'Only an optional skill offered by this internship program can be selected.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_workspace_skill_selectable() from public;

drop trigger if exists workspace_skill_selections_enforce_selectable on workspace_skill_selections;
create trigger workspace_skill_selections_enforce_selectable
  before insert or delete on workspace_skill_selections
  for each row
  execute procedure public.enforce_workspace_skill_selectable();

alter table workspace_skill_selections enable row level security;

drop policy if exists "Students can view their own workspace skill selections" on workspace_skill_selections;
create policy "Students can view their own workspace skill selections"
  on workspace_skill_selections for select
  to authenticated
  using (public.student_owns_workspace(workspace_skill_selections.workspace_id));

drop policy if exists "Students can add skills to their own workspace" on workspace_skill_selections;
create policy "Students can add skills to their own workspace"
  on workspace_skill_selections for insert
  to authenticated
  with check (public.student_owns_workspace(workspace_skill_selections.workspace_id));

drop policy if exists "Students can remove skills from their own workspace" on workspace_skill_selections;
create policy "Students can remove skills from their own workspace"
  on workspace_skill_selections for delete
  to authenticated
  using (public.student_owns_workspace(workspace_skill_selections.workspace_id));

drop policy if exists "Industry can view workspace skill selections for their own internships" on workspace_skill_selections;
create policy "Industry can view workspace skill selections for their own internships"
  on workspace_skill_selections for select
  to authenticated
  using (public.industry_owns_workspace(workspace_skill_selections.workspace_id));

-- No industry write, no UPDATE for anyone (a selection is add/remove only).

-- ============================================================
-- 4. Student-read policies for the 037 program-content tables
-- ============================================================
-- Deferred from 037 because they depend on internship_workspaces (via
-- student_can_access_program). Published content only; access is anchored
-- on the workspace relationship, NOT on internships.status.

drop policy if exists "Students can view published programs for their workspace" on internship_programs;
create policy "Students can view published programs for their workspace"
  on internship_programs for select
  to authenticated
  using (public.student_can_access_program(internship_programs.id));

drop policy if exists "Students can view published modules for their workspace" on program_modules;
create policy "Students can view published modules for their workspace"
  on program_modules for select
  to authenticated
  using (
    program_modules.is_published = true
    and public.student_can_access_program(program_modules.program_id)
  );

drop policy if exists "Students can view published items for their workspace" on module_items;
create policy "Students can view published items for their workspace"
  on module_items for select
  to authenticated
  using (
    module_items.is_published = true
    and exists (
      select 1 from program_modules m
      where m.id = module_items.module_id
        and m.is_published = true
        and public.student_can_access_program(m.program_id)
    )
  );

drop policy if exists "Students can view published assignments for their workspace" on program_assignments;
create policy "Students can view published assignments for their workspace"
  on program_assignments for select
  to authenticated
  using (
    program_assignments.is_published = true
    and exists (
      select 1 from program_modules m
      where m.id = program_assignments.module_id
        and m.is_published = true
        and public.student_can_access_program(program_assignments.program_id)
    )
  );

drop policy if exists "Students can view program skills for their workspace" on program_skills;
create policy "Students can view program skills for their workspace"
  on program_skills for select
  to authenticated
  using (public.student_can_access_program(program_skills.program_id));

-- ============================================================
-- 5. Work-mode protection trigger on `internships`
-- ============================================================
-- Approved rule: once an ACTIVE workspace exists for an internship, the
-- posting cannot be made workspace-ineligible (REMOTE/HYBRID -> ONSITE or
-- -> NULL) and orphan it. Only that transition is blocked; ONSITE ->
-- REMOTE/HYBRID and REMOTE <-> HYBRID stay free. Additive BEFORE UPDATE
-- trigger -- same "additive trigger on an existing table" pattern as
-- 032_profile_role_immutability.sql; internships' columns, policies and
-- existing internships_set_updated_at trigger are untouched. service_role
-- steps aside (matching every guard trigger in this project).

create or replace function public.prevent_ineligible_workmode_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if old.work_mode in ('REMOTE', 'HYBRID')
     and (new.work_mode is null or new.work_mode not in ('REMOTE', 'HYBRID'))
     and exists (
       select 1 from public.internship_workspaces w
       where w.internship_id = old.id
         and w.workspace_status not in ('DECLINED', 'RESCINDED')
     )
  then
    raise exception 'Cannot change this internship to an on-site work mode while an active internship workspace depends on it.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_ineligible_workmode_change() from public;

drop trigger if exists internships_prevent_ineligible_workmode_change on internships;
create trigger internships_prevent_ineligible_workmode_change
  before update on internships
  for each row
  execute procedure public.prevent_ineligible_workmode_change();

-- ============================================================
-- Post-conditions (for a live check after `supabase db push`)
-- ============================================================
--   -- one workspace per application:
--   -- inserting a second internship_workspaces row with the same
--   -- application_id fails with 23505.
--
--   -- ONSITE / NULL cannot receive a workspace:
--   -- a direct insert against a SELECTED application whose internship is
--   -- ONSITE raises "... only available for a REMOTE or HYBRID internship."
--
--   -- identity immutability (as the owning industry, non-service_role):
--   -- update internship_workspaces set student_id = '...'  ->  42501.
--
--   -- student transition guard (as the student):
--   -- update internship_workspaces set workspace_status = 'COMPLETED'  ->  42501.
--   -- update internship_workspaces set workspace_status = 'ACCEPTED'
--   --   where workspace_status = 'PENDING_ACCEPTANCE'  ->  ok.
--
--   -- closed/archived internship keeps student access:
--   -- set the internship status to 'CLOSED', then re-run the student's
--   -- select on internship_programs / program_modules  ->  still returns rows.
--
--   -- work-mode guard:
--   -- update internships set work_mode = 'ONSITE' for an internship with an
--   -- ACCEPTED workspace  ->  42501; the same update with only DECLINED /
--   -- RESCINDED workspaces  ->  ok.
--
--   select tablename, cmd, policyname from pg_policies
--   where schemaname='public'
--     and tablename in ('internship_workspaces','workspace_skill_selections')
--   order by tablename, cmd;
--   -- expect: internship_workspaces  SELECT/INSERT/UPDATE (no DELETE);
--   --         workspace_skill_selections  SELECT/INSERT/DELETE (no UPDATE).
