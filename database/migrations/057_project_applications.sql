-- Migration: 057_project_applications
-- Purpose: the missing application/selection table for Industry Projects
-- (022_industry_projects.sql), deliberately scoped to postings-only by
-- that migration ("Projects do not participate in the applications table
-- ... that wiring is explicitly out of scope for this phase"). This adds
-- that pipeline: a student applies to a PUBLISHED project, the owning
-- Industry account reviews, shortlists, selects (no interview stage --
-- Projects intentionally do not reuse the Internship/Job interview
-- workflow), and can mark a selected student's participation ACTIVE and
-- later COMPLETED.
--
-- Named `industry_project_applications` for the same reason
-- `industry_workshop_applications` (056) is separate from `applications`
-- (020): `applications` is the load-bearing, unified INTERNSHIP/JOB
-- recruitment table and is not widened into a generic opportunities
-- model. Same ownership/deletion strategy as 020/056:
--   * student_id  -> profiles(id) ON DELETE CASCADE
--   * industry_id -> profiles(id) ON DELETE RESTRICT
--   * project_id  -> industry_projects(id) ON DELETE RESTRICT
--
-- Status lifecycle: APPLIED -> SHORTLISTED -> SELECTED -> ACTIVE ->
-- COMPLETED, with REJECTED reachable from APPLIED/SHORTLISTED and
-- WITHDRAWN owned by the student. The CHECK constraint allows the seven
-- values; the transition graph is enforced in
-- backend/app/services/industry_project_application_service.py.

create table if not exists industry_project_applications (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,
  industry_id uuid not null references profiles (id) on delete restrict,
  project_id uuid not null references industry_projects (id) on delete restrict,

  status text not null default 'APPLIED' check (
    status in ('APPLIED', 'SHORTLISTED', 'SELECTED', 'ACTIVE', 'REJECTED', 'WITHDRAWN', 'COMPLETED')
  ),

  applied_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists project_applications_unique_student_project_idx
  on industry_project_applications (student_id, project_id);

create index if not exists project_applications_student_id_idx
  on industry_project_applications (student_id);
create index if not exists project_applications_industry_id_status_idx
  on industry_project_applications (industry_id, status);
create index if not exists project_applications_project_id_idx
  on industry_project_applications (project_id);

alter table industry_project_applications enable row level security;

-- ============================================================
-- Helper triggers (same pattern as 020_applications.sql / 056)
-- ============================================================

create or replace function public.set_project_application_industry_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  resolved_industry_id uuid;
begin
  select industry_id into resolved_industry_id
  from public.industry_projects
  where id = new.project_id;

  if resolved_industry_id is null then
    raise exception 'Referenced project does not exist.' using errcode = '23503';
  end if;

  if not public.is_industry(resolved_industry_id) then
    raise exception 'The project owner is not an INDUSTRY account.' using errcode = '42501';
  end if;

  new.industry_id := resolved_industry_id;
  return new;
end;
$$;

revoke all on function public.set_project_application_industry_id() from public;

drop trigger if exists project_applications_set_industry_id on industry_project_applications;
create trigger project_applications_set_industry_id
  before insert on industry_project_applications
  for each row
  execute procedure public.set_project_application_industry_id();

create or replace function public.prevent_project_application_identity_change()
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
    or new.project_id is distinct from old.project_id
  then
    raise exception 'Cannot change the student, project, or industry owner of an existing application.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_project_application_identity_change() from public;

drop trigger if exists project_applications_prevent_identity_change on industry_project_applications;
create trigger project_applications_prevent_identity_change
  before update on industry_project_applications
  for each row
  execute procedure public.prevent_project_application_identity_change();

create or replace function public.prevent_project_student_status_override()
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

revoke all on function public.prevent_project_student_status_override() from public;

drop trigger if exists project_applications_prevent_student_status_override on industry_project_applications;
create trigger project_applications_prevent_student_status_override
  before update on industry_project_applications
  for each row
  execute procedure public.prevent_project_student_status_override();

drop trigger if exists project_applications_set_updated_at on industry_project_applications;
create trigger project_applications_set_updated_at
  before update on industry_project_applications
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies
-- ============================================================

drop policy if exists "Students can view their own project applications" on industry_project_applications;
create policy "Students can view their own project applications"
  on industry_project_applications for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can apply to published projects" on industry_project_applications;
create policy "Students can apply to published projects"
  on industry_project_applications for insert
  to authenticated
  with check (
    auth.uid() = student_id
    and public.is_student(auth.uid())
    and exists (
      select 1 from industry_projects pr where pr.id = project_id and pr.status = 'PUBLISHED'
    )
  );

drop policy if exists "Students can withdraw their own project applications" on industry_project_applications;
create policy "Students can withdraw their own project applications"
  on industry_project_applications for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Industry can view applications to their own projects" on industry_project_applications;
create policy "Industry can view applications to their own projects"
  on industry_project_applications for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update applications to their own projects" on industry_project_applications;
create policy "Industry can update applications to their own projects"
  on industry_project_applications for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No delete policy -- participation history is never removed via the app.

-- ============================================================
-- Applicant display helper (same pattern as
-- workshop_applicant_profiles / 036_application_applicant_names.sql).
-- ============================================================

create or replace function public.project_applicant_profiles(application_ids uuid[])
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
  from public.industry_project_applications a
  join public.profiles p on p.id = a.student_id
  left join public.student_profiles sp on sp.id = a.student_id
  where a.id = any(application_ids)
    and a.industry_id = auth.uid()
    and public.is_industry(auth.uid());
$$;

revoke all on function public.project_applicant_profiles(uuid[]) from public;
revoke all on function public.project_applicant_profiles(uuid[]) from anon;
grant execute on function public.project_applicant_profiles(uuid[]) to authenticated;
