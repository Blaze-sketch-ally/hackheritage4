-- Migration: 052_job_training
-- Purpose: PHASE J1 (database foundation) of the approved Job Training
-- architecture -- the JOB-side parallel of the Internship Workspace
-- (049/050/051). Two halves in one file:
--   * PROGRAM / TEMPLATE half -- an INDUSTRY account authors ONE
--     job_program for an existing job posting (019_jobs.sql): ordered
--     modules, learning items, trained skills and gradable assignments.
--   * ENROLLMENT / INSTANCE half -- when a student's application reaches
--     status = 'SELECTED' for a JOB, ONE job_training_enrollment is the
--     student-side access record that references that program's content.
--
-- ============================================================
-- Non-negotiable business rule enforced HERE, at the database
-- ============================================================
--   JOB       + SELECTED  -> a job_training_enrollment may be created.
--   JOB       + any other status (APPLIED / UNDER_REVIEW / SHORTLISTED /
--               INTERVIEW_SCHEDULED / REJECTED / WITHDRAWN) -> REJECTED.
--   INTERNSHIP + any status (SELECTED included) -> REJECTED.
-- The gate lives in the set_job_training_enrollment_derived_ids
-- BEFORE-INSERT trigger and is therefore effective even against a direct
-- PostgREST insert that bypasses the API. It is NOT a backend-only check.
--
-- Training is EXCLUSIVE to selected JOB candidates. Internships keep their
-- own separate Internship Workspace (050) and never touch anything here.
--
-- ============================================================
-- Relationship to the existing schema (nothing existing is modified,
-- except the additive student_notifications CHECK widening at the end --
-- exactly the shape 051 used)
-- ============================================================
-- * job_programs.job_id -> jobs(id) ON DELETE CASCADE. jobs can no longer
--   be hard-deleted (028_forbid_internship_job_deletes.sql), so this
--   CASCADE only ever fires on a service_role / GDPR path.
-- * There is deliberately NO internship_id column anywhere in this file.
--   A job_program references jobs(id) and only jobs(id) -- it is
--   structurally impossible to attach one to an internship.
-- * job_program_skills.skill_id / job_program_assignments.linked_skill_id
--   -> skills(id), the CANONICAL catalog (003_skills.sql). No new skill
--   taxonomy. RESTRICT on job_program_skills (a skill referenced by real
--   curriculum is protected content, same as internship program_skills /
--   job_skills); SET NULL on linked_skill_id (a deactivated catalog skill
--   must not destroy assignment history).
-- * job_training_enrollments.application_id -> applications(id)
--   (020_applications.sql -- UNCHANGED, no new status). student_id /
--   industry_id / job_id are COPIED and OVERWRITTEN from the referenced
--   application by a BEFORE-INSERT trigger and then FROZEN -- never
--   trusted from client input. Same pattern as
--   set_workspace_derived_ids (050) / set_application_industry_id (020).
-- * NOTHING here references or writes student_skills. Curriculum authoring
--   and training completion are NOT skill evidence -- the assessment
--   scoring path (015_assessment_verification.sql) stays the only writer
--   of student_skills verification state.
-- * industry_id on the program tables is resolved THROUGH jobs.industry_id
--   (ownership chain), never stored again -- one source of truth, same as
--   internship_programs.
--
-- ============================================================
-- Enrollment lifecycle (documented transition rules)
-- ============================================================
--   ACTIVE     -- default at creation. There is NO student opt-in step
--                 (no ACCEPTED/DECLINED) -- the approved design does not
--                 require one, so it is not invented here.
--   COMPLETED  -- set by an explicit industry/system action in a later
--                 phase (never automatic; there is no producer in J1).
--   REVOKED    -- selection rescinded / enrollment withdrawn by
--                 industry/system.
-- Allowed transitions (enforce_job_training_enrollment_transitions):
--   ACTIVE    -> COMPLETED | REVOKED
--   COMPLETED -> REVOKED
--   REVOKED   -> (terminal, no outgoing edges)
-- A STUDENT caller may never change enrollment_status (there is no student
-- UPDATE policy, and the trigger blocks it as defence in depth).
-- service_role steps aside from the transition guard, matching every guard
-- trigger in this project.
--
-- Training access must SURVIVE the job posting being CLOSED or ARCHIVED:
-- neither student_can_access_job_program() nor any RLS policy here ever
-- reads jobs.status. A selected candidate keeps training access after the
-- posting closes -- identical stance to student_can_access_program (050),
-- which never reads internships.status.
--
-- ============================================================
-- Conventions reused (001-051)
-- ============================================================
-- * uuid PK default gen_random_uuid(); created_at / updated_at timestamptz
--   not null default now(); public.set_updated_at() trigger (012), reused
--   never redefined.
-- * Enum-like columns -> CHECK value lists, never a Postgres enum type.
-- * public.is_student(uuid) / public.is_industry(uuid) (012/013/017) for
--   the role half of every predicate, used never redefined.
-- * SECURITY DEFINER + set search_path = '' on every helper and trigger
--   function; defensive `revoke all ... from public` on the trigger-typed
--   ones; `revoke ... from public, anon` + `grant execute ... to
--   authenticated` on the two boolean RLS helpers -- same as
--   owns_internship_program / student_can_access_program (049/050).
-- * Record tables (job_programs, job_program_modules, job_program_items,
--   job_program_assignments, job_training_enrollments): explicit
--   per-command SELECT / INSERT / UPDATE policies and NO DELETE / NO `for
--   all` policy -- hard delete is denied for every RLS-governed caller
--   (020/027/028/030/049/050 precedent). Authoring mistakes are corrected
--   by unpublish + edit; enrollment mistakes by the REVOKED status.
-- * job_program_skills is a mutable *_skills child table (like internship
--   program_skills / internship_skills): it keeps a `for all` owner policy
--   so a later _replace_skills() service helper can DELETE+INSERT the set.
-- * Idempotent in shape: create table / index if not exists;
--   drop policy/trigger if exists + create; create or replace function.
--   Forward-only, additive: no DROP TABLE, no TRUNCATE, no destructive
--   ALTER, no change to any existing table/policy/trigger/function other
--   than the additive student_notifications CHECK widening (section 8).
--
-- No seed data -- programs are authored by the running system; enrollments
-- are provisioned from a SELECTED application in a later phase.
--
-- ============================================================
-- Object creation order in this file (dependency-correct)
-- ============================================================
-- The 049 live-push bug was a `language sql` helper created BEFORE its
-- table (its body is validated at CREATE time by check_function_bodies).
-- This file is ordered so that:
--   * every table exists before any FK / index / policy / trigger names it;
--   * every function exists before any policy or trigger references it;
--   * `language sql` helper bodies (owns_job_program,
--     student_can_access_job_program) are created AFTER every table they
--     read;
--   * RLS is enabled on a table before any policy is created on it.
-- Concretely:
--   1.  job_programs                     (table + RLS + industry policies + trigger)
--   2.  public.owns_job_program()        -- language sql; AFTER job_programs
--   3.  job_program_modules              (RLS uses owns_job_program)
--   4.  job_program_items                (RLS uses owns_job_program via parent)
--   5.  job_program_skills               (RLS uses owns_job_program)
--   6.  job_program_assignments          (+ program_id derivation trigger)
--   7.  job_training_enrollments         (table + identity/derivation/
--                                         transition triggers + RLS)
--   8.  public.student_can_access_job_program()  -- language sql; AFTER
--       BOTH job_programs AND job_training_enrollments exist -- then the
--       deferred student-read policies for tables 1 and 3-6.
--   9.  student_notifications CHECK widening (additive)
-- job_programs' OWN policies (step 1) use an inline `exists (...)` against
-- `jobs` (019) -- they do NOT need owns_job_program, so step 1 precedes
-- step 2 safely.

-- ============================================================
-- 1. job_programs -- one training template per job posting
-- ============================================================

create table if not exists job_programs (
  id uuid primary key default gen_random_uuid(),

  -- STRICTLY 1:1 with the posting -- the UNIQUE below is the approved
  -- cardinality guarantee. A new curriculum "version" is ARCHIVE + a new
  -- program on a new posting, not a second row here. NO internship_id: a
  -- job program cannot be attached to an internship.
  job_id uuid not null references jobs (id) on delete cascade,

  title text not null,
  summary text,
  estimated_weeks int check (estimated_weeks is null or (estimated_weeks between 1 and 52)),

  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'ARCHIVED')),
  published_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint job_programs_one_per_job unique (job_id)
);

-- unique(job_id) already indexes the only lookup key.

alter table job_programs enable row level security;

drop policy if exists "Industry can view their own job programs" on job_programs;
create policy "Industry can view their own job programs"
  on job_programs for select
  to authenticated
  using (
    exists (
      select 1 from jobs j
      where j.id = job_programs.job_id
        and j.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

drop policy if exists "Industry can create a program for their own job" on job_programs;
create policy "Industry can create a program for their own job"
  on job_programs for insert
  to authenticated
  with check (
    exists (
      select 1 from jobs j
      where j.id = job_programs.job_id
        and j.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

drop policy if exists "Industry can update their own job programs" on job_programs;
create policy "Industry can update their own job programs"
  on job_programs for update
  to authenticated
  using (
    exists (
      select 1 from jobs j
      where j.id = job_programs.job_id
        and j.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  )
  with check (
    exists (
      select 1 from jobs j
      where j.id = job_programs.job_id
        and j.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

-- No DELETE policy: a program is a record. ARCHIVE (status) is the
-- lifecycle end. CASCADE from jobs only reaches it on a service_role path.
-- The student-read policy is deferred to section 8 (it needs
-- student_can_access_job_program, which needs job_training_enrollments).

drop trigger if exists job_programs_set_updated_at on job_programs;
create trigger job_programs_set_updated_at
  before update on job_programs
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 2. Ownership helper -- defined AFTER job_programs exists
-- ============================================================
-- True when auth.uid() is the INDUSTRY account that owns the job behind
-- the given program. SECURITY DEFINER + pinned empty search_path + STABLE,
-- exactly like public.owns_internship_program (049). Reads the ownership
-- chain  job_programs -> jobs -> jobs.industry_id -> auth.uid()  directly,
-- immune to RLS-recursion by construction, and also checks
-- public.is_industry(auth.uid()). Every program-content policy below
-- routes industry ownership through this one function.
--
-- Placement: `language sql` bodies ARE validated at CREATE time
-- (check_function_bodies = on, the default), so this MUST come after
-- job_programs.

create or replace function public.owns_job_program(p_program_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.job_programs prog
    join public.jobs j on j.id = prog.job_id
    where prog.id = p_program_id
      and j.industry_id = auth.uid()
      and public.is_industry(auth.uid())
  );
$$;

revoke all on function public.owns_job_program(uuid) from public;
revoke all on function public.owns_job_program(uuid) from anon;
grant execute on function public.owns_job_program(uuid) to authenticated;

-- ============================================================
-- 3. job_program_modules -- ordered sections of a program
-- ============================================================

create table if not exists job_program_modules (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references job_programs (id) on delete cascade,

  title text not null,
  description text,
  -- Presentation order. NOT unique -- reordering a curriculum must not
  -- fight a constraint; ties break on created_at at read time.
  order_index int not null default 0 check (order_index >= 0),
  is_published boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists job_program_modules_program_id_idx on job_program_modules (program_id);

alter table job_program_modules enable row level security;

drop policy if exists "Industry can view modules for their own job programs" on job_program_modules;
create policy "Industry can view modules for their own job programs"
  on job_program_modules for select
  to authenticated
  using (public.owns_job_program(job_program_modules.program_id));

drop policy if exists "Industry can add modules to their own job programs" on job_program_modules;
create policy "Industry can add modules to their own job programs"
  on job_program_modules for insert
  to authenticated
  with check (public.owns_job_program(job_program_modules.program_id));

drop policy if exists "Industry can update modules for their own job programs" on job_program_modules;
create policy "Industry can update modules for their own job programs"
  on job_program_modules for update
  to authenticated
  using (public.owns_job_program(job_program_modules.program_id))
  with check (public.owns_job_program(job_program_modules.program_id));

-- No DELETE policy -- unpublish instead.

drop trigger if exists job_program_modules_set_updated_at on job_program_modules;
create trigger job_program_modules_set_updated_at
  before update on job_program_modules
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 4. job_program_items -- learning content inside a module
-- ============================================================
-- One table, semantics by item_type -- same "one table, CHECK-constrained
-- vocabulary" pattern as internship module_items (049). VIDEO / PDF / LINK
-- carry a resource URL; TEXT carries inline body.

create table if not exists job_program_items (
  id uuid primary key default gen_random_uuid(),
  module_id uuid not null references job_program_modules (id) on delete cascade,

  title text not null,
  item_type text not null check (item_type in ('VIDEO', 'PDF', 'LINK', 'TEXT')),
  content_url text,
  content_text text,
  order_index int not null default 0 check (order_index >= 0),
  is_published boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint job_program_items_content_matches_type check (
    (item_type = 'TEXT' and content_text is not null)
    or (item_type in ('VIDEO', 'PDF', 'LINK') and content_url is not null)
  )
);

create index if not exists job_program_items_module_id_idx on job_program_items (module_id);

alter table job_program_items enable row level security;

drop policy if exists "Industry can view items for their own job programs" on job_program_items;
create policy "Industry can view items for their own job programs"
  on job_program_items for select
  to authenticated
  using (
    exists (
      select 1 from job_program_modules m
      where m.id = job_program_items.module_id
        and public.owns_job_program(m.program_id)
    )
  );

drop policy if exists "Industry can add items to their own job programs" on job_program_items;
create policy "Industry can add items to their own job programs"
  on job_program_items for insert
  to authenticated
  with check (
    exists (
      select 1 from job_program_modules m
      where m.id = job_program_items.module_id
        and public.owns_job_program(m.program_id)
    )
  );

drop policy if exists "Industry can update items for their own job programs" on job_program_items;
create policy "Industry can update items for their own job programs"
  on job_program_items for update
  to authenticated
  using (
    exists (
      select 1 from job_program_modules m
      where m.id = job_program_items.module_id
        and public.owns_job_program(m.program_id)
    )
  )
  with check (
    exists (
      select 1 from job_program_modules m
      where m.id = job_program_items.module_id
        and public.owns_job_program(m.program_id)
    )
  );

-- No DELETE policy -- unpublish instead.

drop trigger if exists job_program_items_set_updated_at on job_program_items;
create trigger job_program_items_set_updated_at
  before update on job_program_items
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 5. job_program_skills -- skills this program trains, required or optional
-- ============================================================
-- Distinct from job_skills (019), which is recruitment screening. Same
-- normalized shape as internship program_skills (049). Mutable child
-- content: `for all` owner policy so a later _replace_skills() can
-- DELETE+INSERT the set.

create table if not exists job_program_skills (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references job_programs (id) on delete cascade,
  skill_id uuid not null references skills (id) on delete restrict,

  requirement text not null default 'REQUIRED' check (requirement in ('REQUIRED', 'OPTIONAL')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint job_program_skills_unique_per_program unique (program_id, skill_id)
);

create index if not exists job_program_skills_skill_id_idx on job_program_skills (skill_id);

alter table job_program_skills enable row level security;

drop policy if exists "Industry can manage skills for their own job programs" on job_program_skills;
create policy "Industry can manage skills for their own job programs"
  on job_program_skills for all
  to authenticated
  using (public.owns_job_program(job_program_skills.program_id))
  with check (public.owns_job_program(job_program_skills.program_id));

drop trigger if exists job_program_skills_set_updated_at on job_program_skills;
create trigger job_program_skills_set_updated_at
  before update on job_program_skills
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 6. job_program_assignments -- ONE normalized deliverable table
-- ============================================================
-- assignment_type discriminates ASSIGNMENT / QUIZ / PROJECT. No separate
-- assignments / quizzes / projects tables -- same decision as internship
-- program_assignments (049). MVP quiz submissions are reviewed manually.

create table if not exists job_program_assignments (
  id uuid primary key default gen_random_uuid(),
  module_id uuid not null references job_program_modules (id) on delete cascade,
  -- Denormalized from the parent module. set_job_program_assignment_program_id
  -- forces it to equal the module's program_id on every insert/update, so
  -- progress / RLS / in-scope queries never need a three-table hop and it
  -- can never drift. Same BEFORE-trigger derivation as
  -- set_program_assignment_program_id (049) / set_application_industry_id (020).
  program_id uuid not null references job_programs (id) on delete cascade,
  -- Which canonical skill this deliverable trains. NULL = general. SET NULL
  -- so deactivating a catalog skill never destroys assignment history.
  linked_skill_id uuid references skills (id) on delete set null,

  title text not null,
  description text,
  instructions text,
  assignment_type text not null check (assignment_type in ('ASSIGNMENT', 'QUIZ', 'PROJECT')),
  is_required boolean not null default true,
  is_published boolean not null default false,
  order_index int not null default 0 check (order_index >= 0),

  -- Deadline RELATIVE to each enrollment's created_at (every student is
  -- selected at a different time). Resolved per-enrollment in a later
  -- phase; never an absolute date here. NULL = no deadline.
  due_offset_days int check (due_offset_days is null or due_offset_days >= 0),

  submission_kind text not null default 'LINK'
    check (submission_kind in ('LINK', 'REPO', 'FILE', 'TEXT', 'MIXED')),
  repo_required boolean not null default false,
  live_url_expected boolean not null default false,
  max_score numeric(6, 2) check (max_score is null or max_score > 0),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- An assignment that requires a repo must accept one.
  constraint job_program_assignments_repo_kind_consistent check (
    not (repo_required and submission_kind not in ('REPO', 'MIXED'))
  )
);

create index if not exists job_program_assignments_module_id_idx on job_program_assignments (module_id);
create index if not exists job_program_assignments_program_id_idx on job_program_assignments (program_id);
create index if not exists job_program_assignments_linked_skill_id_idx on job_program_assignments (linked_skill_id);

-- Keeps job_program_assignments.program_id equal to the parent module's
-- program_id, always -- any client-supplied value is overwritten.
create or replace function public.set_job_program_assignment_program_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_program_id uuid;
begin
  select m.program_id into v_program_id
  from public.job_program_modules m
  where m.id = new.module_id;

  if v_program_id is null then
    raise exception 'Referenced job program module does not exist.' using errcode = '23503';
  end if;

  new.program_id := v_program_id;
  return new;
end;
$$;

revoke all on function public.set_job_program_assignment_program_id() from public;

drop trigger if exists job_program_assignments_set_program_id on job_program_assignments;
create trigger job_program_assignments_set_program_id
  before insert or update on job_program_assignments
  for each row
  execute procedure public.set_job_program_assignment_program_id();

alter table job_program_assignments enable row level security;

drop policy if exists "Industry can view assignments for their own job programs" on job_program_assignments;
create policy "Industry can view assignments for their own job programs"
  on job_program_assignments for select
  to authenticated
  using (public.owns_job_program(job_program_assignments.program_id));

drop policy if exists "Industry can add assignments to their own job programs" on job_program_assignments;
create policy "Industry can add assignments to their own job programs"
  on job_program_assignments for insert
  to authenticated
  with check (
    exists (
      select 1 from job_program_modules m
      where m.id = job_program_assignments.module_id
        and public.owns_job_program(m.program_id)
    )
  );

drop policy if exists "Industry can update assignments for their own job programs" on job_program_assignments;
create policy "Industry can update assignments for their own job programs"
  on job_program_assignments for update
  to authenticated
  using (public.owns_job_program(job_program_assignments.program_id))
  with check (
    exists (
      select 1 from job_program_modules m
      where m.id = job_program_assignments.module_id
        and public.owns_job_program(m.program_id)
    )
  );

-- No DELETE policy -- unpublish the module/assignment instead.

drop trigger if exists job_program_assignments_set_updated_at on job_program_assignments;
create trigger job_program_assignments_set_updated_at
  before update on job_program_assignments
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 7. job_training_enrollments -- the student-side access instance
-- ============================================================

create table if not exists job_training_enrollments (
  id uuid primary key default gen_random_uuid(),

  -- One enrollment per application. A duplicate provision attempt fails
  -- with 23505 and the caller treats it as "already provisioned" -- the
  -- idempotency guarantee for the later provisioning phase.
  application_id uuid not null references applications (id) on delete cascade,

  -- All three are copied and OVERWRITTEN by set_job_training_enrollment_derived_ids
  -- from the referenced application, then frozen by
  -- prevent_job_training_enrollment_identity_change. Deletion strategy
  -- mirrors internship_workspaces (050): student_id CASCADE (a student
  -- takes their own rows on account deletion); industry_id / job_id
  -- RESTRICT (enrollment history survives an industry/posting removal
  -- attempt -- which 027/028 already block anyway).
  student_id uuid not null references profiles (id) on delete cascade,
  industry_id uuid not null references profiles (id) on delete restrict,
  job_id uuid not null references jobs (id) on delete restrict,

  enrollment_status text not null default 'ACTIVE' check (
    enrollment_status in ('ACTIVE', 'COMPLETED', 'REVOKED')
  ),

  completed_at timestamptz,
  revoked_at timestamptz,
  revoke_reason text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint job_training_enrollments_one_per_application unique (application_id),
  constraint job_training_enrollments_completed_at_requires_completed
    check (completed_at is null or enrollment_status = 'COMPLETED'),
  constraint job_training_enrollments_revoked_fields_require_revoked
    check ((revoked_at is null and revoke_reason is null) or enrollment_status = 'REVOKED')
);

create index if not exists job_training_enrollments_student_status_idx
  on job_training_enrollments (student_id, enrollment_status);
create index if not exists job_training_enrollments_industry_status_idx
  on job_training_enrollments (industry_id, enrollment_status);
create index if not exists job_training_enrollments_job_id_idx
  on job_training_enrollments (job_id);

-- ---- derivation + guards ----

-- BEFORE INSERT: derive student_id / industry_id / job_id from the
-- canonical application, and enforce the ABSOLUTE gate:
--   * the application must be a JOB application (opportunity_type = 'JOB'
--     with a non-null job_id), and
--   * its status must be exactly 'SELECTED'.
-- Any other combination -- a non-selected job, or ANY internship
-- application including a SELECTED one -- raises and the insert fails.
-- No new applications status is introduced; the application stays SELECTED.
create or replace function public.set_job_training_enrollment_derived_ids()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_student_id uuid;
  v_industry_id uuid;
  v_job_id uuid;
  v_app_status text;
  v_opportunity_type text;
begin
  select a.student_id, a.industry_id, a.job_id, a.status, a.opportunity_type
    into v_student_id, v_industry_id, v_job_id, v_app_status, v_opportunity_type
  from public.applications a
  where a.id = new.application_id;

  if v_student_id is null then
    raise exception 'Referenced application does not exist.' using errcode = '23503';
  end if;

  if v_opportunity_type <> 'JOB' or v_job_id is null then
    raise exception 'A job training enrollment can only be created for a JOB application.'
      using errcode = '42501';
  end if;

  if v_app_status <> 'SELECTED' then
    raise exception 'A job training enrollment can only be created for a SELECTED application.'
      using errcode = '42501';
  end if;

  new.student_id  := v_student_id;
  new.industry_id := v_industry_id;
  new.job_id      := v_job_id;
  return new;
end;
$$;

revoke all on function public.set_job_training_enrollment_derived_ids() from public;

drop trigger if exists job_training_enrollments_set_derived_ids on job_training_enrollments;
create trigger job_training_enrollments_set_derived_ids
  before insert on job_training_enrollments
  for each row
  execute procedure public.set_job_training_enrollment_derived_ids();

-- BEFORE UPDATE: application / student / industry / job are frozen after
-- creation for every ordinary caller (service_role steps aside). Same
-- OLD-vs-NEW pattern as prevent_workspace_identity_change (050) /
-- prevent_application_identity_change (020). A student or industry user
-- can never rewrite enrollment ownership.
create or replace function public.prevent_job_training_enrollment_identity_change()
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
    or new.job_id is distinct from old.job_id
  then
    raise exception 'Cannot change the application, student, industry, or job of an existing job training enrollment.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_job_training_enrollment_identity_change() from public;

drop trigger if exists job_training_enrollments_prevent_identity_change on job_training_enrollments;
create trigger job_training_enrollments_prevent_identity_change
  before update on job_training_enrollments
  for each row
  execute procedure public.prevent_job_training_enrollment_identity_change();

-- BEFORE UPDATE: enforce the documented lifecycle
--   ACTIVE    -> COMPLETED | REVOKED
--   COMPLETED -> REVOKED
--   REVOKED   -> (terminal)
-- A STUDENT caller may never change enrollment_status (there is no student
-- UPDATE policy either -- this is defence in depth). service_role steps
-- aside. Mirrors enforce_workspace_status_transitions (050).
create or replace function public.enforce_job_training_enrollment_transitions()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.enrollment_status is not distinct from old.enrollment_status then
    return new;
  end if;

  if auth.uid() = old.student_id then
    raise exception 'A student cannot change the status of a job training enrollment.'
      using errcode = '42501';
  end if;

  if old.enrollment_status = 'REVOKED' then
    raise exception 'A revoked job training enrollment cannot change state.'
      using errcode = '42501';
  end if;

  if old.enrollment_status = 'COMPLETED' and new.enrollment_status <> 'REVOKED' then
    raise exception 'A completed job training enrollment can only move to REVOKED.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_job_training_enrollment_transitions() from public;

drop trigger if exists job_training_enrollments_enforce_transitions on job_training_enrollments;
create trigger job_training_enrollments_enforce_transitions
  before update on job_training_enrollments
  for each row
  execute procedure public.enforce_job_training_enrollment_transitions();

drop trigger if exists job_training_enrollments_set_updated_at on job_training_enrollments;
create trigger job_training_enrollments_set_updated_at
  before update on job_training_enrollments
  for each row
  execute procedure public.set_updated_at();

-- ---- RLS ----

alter table job_training_enrollments enable row level security;

drop policy if exists "Students can view their own job training enrollment" on job_training_enrollments;
create policy "Students can view their own job training enrollment"
  on job_training_enrollments for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Industry can view job training enrollments for their own jobs" on job_training_enrollments;
create policy "Industry can view job training enrollments for their own jobs"
  on job_training_enrollments for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- industry_id is set by set_job_training_enrollment_derived_ids (which
-- runs BEFORE this WITH CHECK) from the referenced application, so
-- auth.uid() = industry_id here confirms the derived owner -- and
-- therefore the application's real owner -- is the caller. Same
-- construction as the internship workspace provisioning INSERT policy (050).
drop policy if exists "Industry can provision job training enrollments for their own jobs" on job_training_enrollments;
create policy "Industry can provision job training enrollments for their own jobs"
  on job_training_enrollments for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can manage job training enrollments for their own jobs" on job_training_enrollments;
create policy "Industry can manage job training enrollments for their own jobs"
  on job_training_enrollments for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No student UPDATE policy -- there is no student action on an enrollment
-- in this design (no accept/decline). No DELETE policy for any role --
-- REVOKED is the soft-terminal state; enrollments are permanent records
-- (020/027/028/030/050 precedent).

-- ============================================================
-- 8. Student access helper + deferred student-read policies
-- ============================================================
-- Defined here because it depends on BOTH job_programs (section 1) and
-- job_training_enrollments (section 7). `language sql` body -> validated
-- at CREATE time -> must follow both tables.
--
-- True when the caller is a student with a non-REVOKED enrollment on the
-- job behind this program AND the program is PUBLISHED. Does NOT reference
-- jobs.status -- a CLOSED or ARCHIVED posting does not revoke a selected
-- student's training access. Identical stance to
-- public.student_can_access_program (050), which never reads
-- internships.status. (A COMPLETED enrollment keeps read access to its own
-- materials; only REVOKED loses it -- mirrors student_can_access_program's
-- `workspace_status not in ('DECLINED','RESCINDED')`.)

create or replace function public.student_can_access_job_program(p_program_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.job_programs prog
    join public.job_training_enrollments e on e.job_id = prog.job_id
    where prog.id = p_program_id
      and prog.status = 'PUBLISHED'
      and e.student_id = auth.uid()
      and public.is_student(auth.uid())
      and e.enrollment_status <> 'REVOKED'
  );
$$;

revoke all on function public.student_can_access_job_program(uuid) from public;
revoke all on function public.student_can_access_job_program(uuid) from anon;
grant execute on function public.student_can_access_job_program(uuid) to authenticated;

-- Published content only; access anchored on the enrollment relationship,
-- NOT on jobs.status. Same shape as the 050 student-read policies for the
-- 049 program tables.

drop policy if exists "Students can view published job programs for their enrollment" on job_programs;
create policy "Students can view published job programs for their enrollment"
  on job_programs for select
  to authenticated
  using (public.student_can_access_job_program(job_programs.id));

drop policy if exists "Students can view published job program modules for their enrollment" on job_program_modules;
create policy "Students can view published job program modules for their enrollment"
  on job_program_modules for select
  to authenticated
  using (
    job_program_modules.is_published = true
    and public.student_can_access_job_program(job_program_modules.program_id)
  );

drop policy if exists "Students can view published job program items for their enrollment" on job_program_items;
create policy "Students can view published job program items for their enrollment"
  on job_program_items for select
  to authenticated
  using (
    job_program_items.is_published = true
    and exists (
      select 1 from job_program_modules m
      where m.id = job_program_items.module_id
        and m.is_published = true
        and public.student_can_access_job_program(m.program_id)
    )
  );

drop policy if exists "Students can view job program skills for their enrollment" on job_program_skills;
create policy "Students can view job program skills for their enrollment"
  on job_program_skills for select
  to authenticated
  using (public.student_can_access_job_program(job_program_skills.program_id));

drop policy if exists "Students can view published job program assignments for their enrollment" on job_program_assignments;
create policy "Students can view published job program assignments for their enrollment"
  on job_program_assignments for select
  to authenticated
  using (
    job_program_assignments.is_published = true
    and exists (
      select 1 from job_program_modules m
      where m.id = job_program_assignments.module_id
        and m.is_published = true
        and public.student_can_access_job_program(job_program_assignments.program_id)
    )
  );

-- ============================================================
-- 9. student_notifications CHECK widening (the one existing-schema change)
-- ============================================================
-- Additive to the allowed value sets only: `type` gains 'JOB_TRAINING',
-- `related_entity_type` gains 'JOB_TRAINING_ENROLLMENT'. Every existing
-- row still satisfies the widened constraints -> forward-only,
-- non-destructive. Exactly the DO-block name-resolution shape 051 used
-- (the 035 inline CHECKs are auto-named by Postgres, so the real
-- single-column constraint name is read from the catalog before swapping).
-- This phase wires NO notification producer -- the widening only makes the
-- enrollment entity referenceable by a later phase.
--
-- Ordering note: this section assumes migration 051 has already run (it is
-- lower-numbered, so a forward replay guarantees that). It re-adds the
-- same two constraint names 051 uses, extended by one value each; the
-- final value sets are the 051 sets PLUS the job-training value.

do $$
declare
  v_name text;
begin
  select con.conname into v_name
  from pg_constraint con
  join pg_attribute att
    on att.attrelid = con.conrelid and att.attnum = con.conkey[1]
  where con.conrelid = 'public.student_notifications'::regclass
    and con.contype = 'c'
    and array_length(con.conkey, 1) = 1
    and att.attname = 'type';

  if v_name is not null then
    execute format('alter table public.student_notifications drop constraint %I', v_name);
  end if;
end $$;

alter table public.student_notifications
  add constraint student_notifications_type_check
  check (type in (
    'APPLICATION_STATUS', 'INTERVIEW', 'ASSESSMENT', 'LEARNING',
    'MENTORSHIP', 'EVENT', 'SYSTEM', 'INTERNSHIP', 'JOB_TRAINING'
  ));

do $$
declare
  v_name text;
begin
  select con.conname into v_name
  from pg_constraint con
  join pg_attribute att
    on att.attrelid = con.conrelid and att.attnum = con.conkey[1]
  where con.conrelid = 'public.student_notifications'::regclass
    and con.contype = 'c'
    and array_length(con.conkey, 1) = 1
    and att.attname = 'related_entity_type';

  if v_name is not null then
    execute format('alter table public.student_notifications drop constraint %I', v_name);
  end if;
end $$;

alter table public.student_notifications
  add constraint student_notifications_related_entity_type_check
  check (related_entity_type in (
    'APPLICATION', 'INTERVIEW', 'ASSESSMENT', 'LEARNING_RESOURCE',
    'MENTORSHIP', 'EVENT', 'INTERNSHIP_WORKSPACE', 'JOB_TRAINING_ENROLLMENT'
  ));

-- ============================================================
-- Post-conditions (for a live check after `supabase db push`)
-- ============================================================
--   -- 6 new tables, RLS on:
--   select tablename, rowsecurity from pg_tables
--   where schemaname = 'public'
--     and tablename in ('job_programs','job_program_modules','job_program_items',
--                       'job_program_skills','job_program_assignments',
--                       'job_training_enrollments');
--
--   -- 1:1 program <-> job:
--   -- a second job_programs row for the same job_id fails with 23505
--   -- (job_programs_one_per_job).
--
--   -- the ABSOLUTE enrollment gate (as the owning industry, non-service_role):
--   --   * JOB + SELECTED   -> insert into job_training_enrollments succeeds.
--   --   * JOB + APPLIED / UNDER_REVIEW / SHORTLISTED / INTERVIEW_SCHEDULED /
--   --     REJECTED -> "... only be created for a SELECTED application."
--   --   * INTERNSHIP + SELECTED (or any status) -> "... only be created for
--   --     a JOB application."
--
--   -- identity immutability (as the owning industry, non-service_role):
--   -- update job_training_enrollments set student_id = '...'  ->  42501.
--
--   -- lifecycle guard:
--   -- update job_training_enrollments set enrollment_status = 'ACTIVE'
--   --   where enrollment_status = 'REVOKED'  ->  42501.
--   -- as the student: any enrollment_status change  ->  42501.
--
--   -- closed/archived job keeps student access:
--   -- set the job status to 'CLOSED', then re-run the student's select on
--   -- job_programs / job_program_modules  ->  still returns rows.
--
--   select tablename, cmd, policyname from pg_policies
--   where schemaname='public'
--     and tablename in ('job_programs','job_program_modules','job_program_items',
--                       'job_program_skills','job_program_assignments',
--                       'job_training_enrollments')
--   order by tablename, cmd;
--   -- expect: record tables  SELECT/INSERT/UPDATE (no DELETE);
--   --         job_program_skills alone shows ALL;
--   --         job_training_enrollments  SELECT/INSERT/UPDATE (no DELETE),
--   --         and no student UPDATE policy.
--
--   -- notification CHECK widening kept all originals:
--   select pg_get_constraintdef(oid) from pg_constraint
--   where conrelid = 'public.student_notifications'::regclass and contype = 'c';
--   -- -> type list still has APPLICATION_STATUS..INTERNSHIP, plus JOB_TRAINING;
--   --    related_entity_type list still has APPLICATION..INTERNSHIP_WORKSPACE,
--   --    plus JOB_TRAINING_ENROLLMENT; the *_paired 2-column check is untouched.
