-- Migration: 056_workshop_applications
-- Purpose: the missing application/registration table for Industry
-- Workshops (024_industry_workshops.sql), which was deliberately scoped
-- to postings-only ("no application/registration table" -- see that
-- migration's header). This is the pipeline that phase adds: a student
-- registers interest in a PUBLISHED workshop, the owning Industry account
-- reviews and accepts/rejects, and a completion state can be recorded for
-- an accepted participant.
--
-- Named `industry_workshop_applications` (not reusing `applications`,
-- 020_applications.sql) per explicit product direction: `applications` is
-- the load-bearing, unified INTERNSHIP/JOB recruitment table and is not to
-- be widened into a generic opportunities model. Workshops (and Projects,
-- 057) get their own small, independent application tables -- the same
-- "standalone entity" precedent industry_workshops itself already set
-- relative to internships/jobs.
--
-- Ownership / deletion strategy mirrors 020_applications.sql exactly:
--   * student_id  -> profiles(id) ON DELETE CASCADE (a student may take
--     their own rows with them).
--   * industry_id -> profiles(id) ON DELETE RESTRICT (participation
--     history survives even if the posting account is later deleted).
--   * workshop_id -> industry_workshops(id) ON DELETE RESTRICT (a workshop
--     with real applications cannot be hard-deleted; archiving, which
--     024 already supports, is the intended path).
--
-- Status lifecycle: APPLIED -> ACCEPTED | REJECTED | WITHDRAWN, and
-- ACCEPTED -> COMPLETED. The CHECK constraint allows the five values; the
-- transition graph itself is enforced in
-- backend/app/services/industry_workshop_application_service.py (same
-- split as `applications`, whose CHECK also doesn't encode the graph).

create table if not exists industry_workshop_applications (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,
  -- Populated and validated server-side by the
  -- set_workshop_application_industry_id trigger below -- never trusted
  -- from client input, same reasoning as applications_set_industry_id.
  industry_id uuid not null references profiles (id) on delete restrict,
  workshop_id uuid not null references industry_workshops (id) on delete restrict,

  status text not null default 'APPLIED' check (
    status in ('APPLIED', 'ACCEPTED', 'REJECTED', 'WITHDRAWN', 'COMPLETED')
  ),

  applied_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Prevent duplicate applications: one per student per workshop.
create unique index if not exists workshop_applications_unique_student_workshop_idx
  on industry_workshop_applications (student_id, workshop_id);

create index if not exists workshop_applications_student_id_idx
  on industry_workshop_applications (student_id);
-- Drives the Industry-side applicants view -- filters by industry_id +
-- status, and by workshop_id for one workshop's own applicant list.
create index if not exists workshop_applications_industry_id_status_idx
  on industry_workshop_applications (industry_id, status);
create index if not exists workshop_applications_workshop_id_idx
  on industry_workshop_applications (workshop_id);

alter table industry_workshop_applications enable row level security;

-- ============================================================
-- Helper triggers (same pattern as 020_applications.sql)
-- ============================================================

create or replace function public.set_workshop_application_industry_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  resolved_industry_id uuid;
begin
  select industry_id into resolved_industry_id
  from public.industry_workshops
  where id = new.workshop_id;

  if resolved_industry_id is null then
    raise exception 'Referenced workshop does not exist.' using errcode = '23503';
  end if;

  if not public.is_industry(resolved_industry_id) then
    raise exception 'The workshop owner is not an INDUSTRY account.' using errcode = '42501';
  end if;

  new.industry_id := resolved_industry_id;
  return new;
end;
$$;

revoke all on function public.set_workshop_application_industry_id() from public;

drop trigger if exists workshop_applications_set_industry_id on industry_workshop_applications;
create trigger workshop_applications_set_industry_id
  before insert on industry_workshop_applications
  for each row
  execute procedure public.set_workshop_application_industry_id();

create or replace function public.prevent_workshop_application_identity_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.student_id is distinct from old.student_id
    or new.industry_id is distinct from old.industry_id
    or new.workshop_id is distinct from old.workshop_id
  then
    raise exception 'Cannot change the student, workshop, or industry owner of an existing application.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_workshop_application_identity_change() from public;

drop trigger if exists workshop_applications_prevent_identity_change on industry_workshop_applications;
create trigger workshop_applications_prevent_identity_change
  before update on industry_workshop_applications
  for each row
  execute procedure public.prevent_workshop_application_identity_change();

-- Restricts a STUDENT caller to exactly one status transition on their own
-- application: withdrawing it. Every other status (ACCEPTED, REJECTED,
-- COMPLETED) is an Industry decision.
create or replace function public.prevent_workshop_student_status_override()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if auth.uid() = old.student_id and new.status is distinct from old.status and new.status <> 'WITHDRAWN' then
    raise exception 'Students may only withdraw an application, not set any other status.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_workshop_student_status_override() from public;

drop trigger if exists workshop_applications_prevent_student_status_override on industry_workshop_applications;
create trigger workshop_applications_prevent_student_status_override
  before update on industry_workshop_applications
  for each row
  execute procedure public.prevent_workshop_student_status_override();

drop trigger if exists workshop_applications_set_updated_at on industry_workshop_applications;
create trigger workshop_applications_set_updated_at
  before update on industry_workshop_applications
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies
-- ============================================================

drop policy if exists "Students can view their own workshop applications" on industry_workshop_applications;
create policy "Students can view their own workshop applications"
  on industry_workshop_applications for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can apply to published workshops" on industry_workshop_applications;
create policy "Students can apply to published workshops"
  on industry_workshop_applications for insert
  to authenticated
  with check (
    auth.uid() = student_id
    and public.is_student(auth.uid())
    and exists (
      select 1 from industry_workshops w where w.id = workshop_id and w.status = 'PUBLISHED'
    )
  );

drop policy if exists "Students can withdraw their own workshop applications" on industry_workshop_applications;
create policy "Students can withdraw their own workshop applications"
  on industry_workshop_applications for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Industry can view applications to their own workshops" on industry_workshop_applications;
create policy "Industry can view applications to their own workshops"
  on industry_workshop_applications for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update applications to their own workshops" on industry_workshop_applications;
create policy "Industry can update applications to their own workshops"
  on industry_workshop_applications for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No delete policy for either role -- participation history is never
-- removed via the app, only via status transitions.

-- ============================================================
-- Applicant display helper (same pattern as
-- 036_application_applicant_names.sql), scoped to this table's own
-- Industry-ownership predicate. Returns the minimal human-readable
-- identity an Applicants view needs: name, institution, department,
-- graduation year, and a short skill-name list -- never a raw student_id.
-- ============================================================

create or replace function public.workshop_applicant_profiles(application_ids uuid[])
returns table (
  application_id uuid,
  student_name text,
  institution_name text,
  department text,
  graduation_year int,
  skills text[]
)
language sql
security definer
set search_path = ''
stable
as $$
  select
    a.id,
    p.full_name,
    sp.institution_name,
    sp.department,
    sp.graduation_year,
    (
      select array_agg(sk.name order by sk.name)
      from public.student_skills ss
      join public.skills sk on sk.id = ss.skill_id
      where ss.student_id = a.student_id
    )
  from public.industry_workshop_applications a
  join public.profiles p on p.id = a.student_id
  left join public.student_profiles sp on sp.id = a.student_id
  where a.id = any(application_ids)
    and a.industry_id = auth.uid()
    and public.is_industry(auth.uid());
$$;

revoke all on function public.workshop_applicant_profiles(uuid[]) from public;
revoke all on function public.workshop_applicant_profiles(uuid[]) from anon;
grant execute on function public.workshop_applicant_profiles(uuid[]) to authenticated;
