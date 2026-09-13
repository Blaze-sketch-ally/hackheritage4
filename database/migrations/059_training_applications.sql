-- Migration: 059_training_applications
-- Purpose: the missing application/enrollment table for Industry Training
-- (023_industry_training.sql), which was deliberately scoped to
-- postings-only ("no application/enrollment table" -- see that
-- migration's header) -- the same original state Workshops (024) and
-- Projects (022) were in before 056/057 added their pipelines. This adds
-- the equivalent pipeline for Training: a student registers for a
-- PUBLISHED training program, the owning Industry account reviews and
-- accepts/rejects, and a completion state can be recorded for an
-- accepted participant. Exact structural mirror of
-- 056_workshop_applications.sql -- see that migration for the full
-- reasoning (ownership/deletion strategy, trigger shapes, RLS policy
-- shapes); only table/column names differ (training_id, not
-- workshop_id).
--
-- Named `industry_training_applications` (not reusing `applications`) for
-- the same reason 056/057 avoided it: `applications` is the load-bearing,
-- unified INTERNSHIP/JOB recruitment table and is not widened into a
-- generic opportunities model.
--
-- Status lifecycle: APPLIED -> ACCEPTED | REJECTED | WITHDRAWN, and
-- ACCEPTED -> COMPLETED -- same five-value shape as
-- industry_workshop_applications. The product's "Registered/Applied,
-- Enrolled, Active if applicable, Completed" language maps ACCEPTED to
-- "Enrolled" in the UI only; no separate ACTIVE status is added to the
-- database for it (there is nothing an ACTIVE row would need to record
-- that ACCEPTED doesn't already capture, so a friendlier label is enough
-- -- no new enum value for the sake of wording).

create table if not exists industry_training_applications (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,
  -- Populated and validated server-side by the
  -- set_training_application_industry_id trigger below -- never trusted
  -- from client input.
  industry_id uuid not null references profiles (id) on delete restrict,
  training_id uuid not null references industry_training (id) on delete restrict,

  status text not null default 'APPLIED' check (
    status in ('APPLIED', 'ACCEPTED', 'REJECTED', 'WITHDRAWN', 'COMPLETED')
  ),

  applied_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists training_applications_unique_student_training_idx
  on industry_training_applications (student_id, training_id);

create index if not exists training_applications_student_id_idx
  on industry_training_applications (student_id);
create index if not exists training_applications_industry_id_status_idx
  on industry_training_applications (industry_id, status);
create index if not exists training_applications_training_id_idx
  on industry_training_applications (training_id);

alter table industry_training_applications enable row level security;

-- ============================================================
-- Helper triggers (mirrors 056_workshop_applications.sql exactly)
-- ============================================================

create or replace function public.set_training_application_industry_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  resolved_industry_id uuid;
begin
  select industry_id into resolved_industry_id
  from public.industry_training
  where id = new.training_id;

  if resolved_industry_id is null then
    raise exception 'Referenced training record does not exist.' using errcode = '23503';
  end if;

  if not public.is_industry(resolved_industry_id) then
    raise exception 'The training owner is not an INDUSTRY account.' using errcode = '42501';
  end if;

  new.industry_id := resolved_industry_id;
  return new;
end;
$$;

revoke all on function public.set_training_application_industry_id() from public;

drop trigger if exists training_applications_set_industry_id on industry_training_applications;
create trigger training_applications_set_industry_id
  before insert on industry_training_applications
  for each row
  execute procedure public.set_training_application_industry_id();

create or replace function public.prevent_training_application_identity_change()
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
    or new.training_id is distinct from old.training_id
  then
    raise exception 'Cannot change the student, training record, or industry owner of an existing application.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_training_application_identity_change() from public;

drop trigger if exists training_applications_prevent_identity_change on industry_training_applications;
create trigger training_applications_prevent_identity_change
  before update on industry_training_applications
  for each row
  execute procedure public.prevent_training_application_identity_change();

create or replace function public.prevent_training_student_status_override()
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

revoke all on function public.prevent_training_student_status_override() from public;

drop trigger if exists training_applications_prevent_student_status_override on industry_training_applications;
create trigger training_applications_prevent_student_status_override
  before update on industry_training_applications
  for each row
  execute procedure public.prevent_training_student_status_override();

drop trigger if exists training_applications_set_updated_at on industry_training_applications;
create trigger training_applications_set_updated_at
  before update on industry_training_applications
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies
-- ============================================================

drop policy if exists "Students can view their own training applications" on industry_training_applications;
create policy "Students can view their own training applications"
  on industry_training_applications for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can apply to published training" on industry_training_applications;
create policy "Students can apply to published training"
  on industry_training_applications for insert
  to authenticated
  with check (
    auth.uid() = student_id
    and public.is_student(auth.uid())
    and exists (
      select 1 from industry_training t where t.id = training_id and t.status = 'PUBLISHED'
    )
  );

drop policy if exists "Students can withdraw their own training applications" on industry_training_applications;
create policy "Students can withdraw their own training applications"
  on industry_training_applications for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Industry can view applications to their own training" on industry_training_applications;
create policy "Industry can view applications to their own training"
  on industry_training_applications for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update applications to their own training" on industry_training_applications;
create policy "Industry can update applications to their own training"
  on industry_training_applications for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No delete policy -- participation history is never removed via the app.

-- ============================================================
-- Applicant display helper (mirrors workshop_applicant_profiles /
-- project_applicant_profiles).
-- ============================================================

create or replace function public.training_applicant_profiles(application_ids uuid[])
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
  from public.industry_training_applications a
  join public.profiles p on p.id = a.student_id
  left join public.student_profiles sp on sp.id = a.student_id
  where a.id = any(application_ids)
    and a.industry_id = auth.uid()
    and public.is_industry(auth.uid());
$$;

revoke all on function public.training_applicant_profiles(uuid[]) from public;
revoke all on function public.training_applicant_profiles(uuid[]) from anon;
grant execute on function public.training_applicant_profiles(uuid[]) to authenticated;
