-- Migration: 020_applications
-- Purpose: ONE unified table for both internship and job applications, so
-- the industry recruitment pipeline (applicants / shortlisted / interviews
-- / selected) can query a single table instead of unioning two. Depends on
-- 018_internships.sql and 019_jobs.sql (industry_id resolution below reads
-- both).
--
-- NOTE: 007_learning.sql is the current tip-adjacent unimplemented
-- placeholder in this numeric range (applications was never its own
-- placeholder file) -- nothing existing is modified by this migration.
--
-- FIX (this revision): a prior run of this migration -- or an earlier,
-- differently-shaped draft of it -- already created an `applications`
-- table in the database. Because the original version of this file used
-- `create table if not exists`, that re-run silently no-op'd on table
-- creation, leaving the OLD column set in place, and the
-- `applications_unique_student_internship_idx` index then failed with
-- `column "internship_id" does not exist`. This revision drops any
-- stale `applications` table before recreating it, and uses a plain
-- `create table` (no `if not exists`) so any future schema drift fails
-- loudly here instead of silently no-op'ing again. If you have real
-- recruitment data in the existing table, do NOT run this as-is --
-- migrate that data first, since the drop below is destructive.
--
-- Deletion strategy (deliberate, per explicit product requirement):
--   - student_id  -> profiles(id) ON DELETE CASCADE. Matches the existing
--     convention for every other student_id FK in this schema
--     (student_skills, assessment attempts, student_target_job_role): a
--     student is allowed to take their own rows with them when their
--     account is deleted.
--   - industry_id -> profiles(id) ON DELETE RESTRICT. Deliberately NOT
--     cascaded -- recruitment history must survive even if the posting
--     industry account is later deleted. RESTRICT blocks that deletion
--     outright (the delete fails) rather than silently orphaning or
--     destroying application rows. An industry account with real
--     recruitment history cannot be hard-deleted at the database level;
--     account deactivation (a future feature) is the correct path, not
--     row deletion.
--   - internship_id / job_id -> internships(id) / jobs(id) ON DELETE
--     RESTRICT. Same reasoning -- closing or archiving a posting (the
--     status column already supports this) is the intended way to stop
--     new applications; deleting a posting that already has applications
--     is blocked by this restrict, not silently destructive.

drop table if exists applications cascade;

create table applications (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,
  -- Populated and validated server-side by the
  -- applications_set_industry_id trigger below -- never trusted from
  -- client input. See that function for why.
  industry_id uuid not null references profiles (id) on delete restrict,

  opportunity_type text not null check (opportunity_type in ('INTERNSHIP', 'JOB')),
  internship_id uuid references internships (id) on delete restrict,
  job_id uuid references jobs (id) on delete restrict,

  status text not null default 'APPLIED' check (
    status in ('APPLIED', 'UNDER_REVIEW', 'SHORTLISTED', 'INTERVIEW_SCHEDULED', 'SELECTED', 'REJECTED', 'WITHDRAWN')
  ),
  cover_note text,
  -- Filled later by the AI matching service (not part of this migration).
  match_score numeric(5, 2) check (match_score >= 0 and match_score <= 100),

  applied_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint applications_opportunity_matches_type check (
    (opportunity_type = 'INTERNSHIP' and internship_id is not null and job_id is null)
    or
    (opportunity_type = 'JOB' and job_id is not null and internship_id is null)
  )
);

-- Prevent duplicate applications: one application per student per
-- posting. Partial (not a plain multi-column unique) because internship_id
-- / job_id are each null on the "other" opportunity type's rows. These
-- also serve as the lookup indexes for "all applications for posting X"
-- (internship_id / job_id / status lookups) -- a non-null internship_id
-- already implies opportunity_type = 'INTERNSHIP' for that row, so no
-- separate plain index is needed on top of these. "Published opportunity"
-- lookups are served by internships_published_idx / jobs_published_idx
-- (018_internships.sql / 019_jobs.sql) -- publication state lives there,
-- not on this table.
create unique index if not exists applications_unique_student_internship_idx
  on applications (student_id, internship_id) where internship_id is not null;
create unique index if not exists applications_unique_student_job_idx
  on applications (student_id, job_id) where job_id is not null;

create index if not exists applications_student_id_idx on applications (student_id);
-- Drives the industry-side recruitment pipeline views -- applicants /
-- shortlisted / interviews / selected all filter by industry_id + status.
create index if not exists applications_industry_id_status_idx on applications (industry_id, status);

alter table applications enable row level security;

-- ============================================================
-- Helper triggers
-- ============================================================

-- Derives (and OVERWRITES) applications.industry_id from the referenced
-- internship/job at insert time -- any client-supplied value is ignored.
-- This is what makes "industry_id must correspond to an INDUSTRY profile"
-- and "must match the posting's real owner" actual database-enforced
-- guarantees rather than client-side promises: even a maliciously crafted
-- insert (e.g. a direct REST call bypassing the UI) ends up with the
-- correct industry_id, because it is computed server-side from the
-- referenced posting, then independently re-validated by the INSERT
-- policy's WITH CHECK below. SECURITY DEFINER + pinned empty search_path,
-- same pattern as is_student/is_industry -- avoids any RLS-recursion risk
-- and resolves correctly regardless of the caller's own visibility into
-- internships/jobs.
create or replace function public.set_application_industry_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  resolved_industry_id uuid;
begin
  if new.opportunity_type = 'INTERNSHIP' then
    select industry_id into resolved_industry_id
    from public.internships
    where id = new.internship_id;
  elsif new.opportunity_type = 'JOB' then
    select industry_id into resolved_industry_id
    from public.jobs
    where id = new.job_id;
  end if;

  if resolved_industry_id is null then
    raise exception 'Referenced internship/job does not exist.' using errcode = '23503';
  end if;

  if not public.is_industry(resolved_industry_id) then
    raise exception 'The posting owner is not an INDUSTRY account.' using errcode = '42501';
  end if;

  new.industry_id := resolved_industry_id;
  return new;
end;
$$;

revoke all on function public.set_application_industry_id() from public;

drop trigger if exists applications_set_industry_id on applications;
create trigger applications_set_industry_id
  before insert on applications
  for each row
  execute procedure public.set_application_industry_id();

-- Blocks changes to the columns that define WHICH application this is --
-- student_id, industry_id, opportunity_type, internship_id, job_id --
-- after creation. Same OLD vs NEW comparison pattern as
-- prevent_self_admin_promotion (002_protect_admin_role.sql): service_role
-- steps aside entirely, every ordinary RLS-governed caller (student or
-- industry) is blocked from re-pointing an application at a different
-- student, a different posting, or a different industry account.
create or replace function public.prevent_application_identity_change()
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
    or new.opportunity_type is distinct from old.opportunity_type
    or new.internship_id is distinct from old.internship_id
    or new.job_id is distinct from old.job_id
  then
    raise exception 'Cannot change the student, posting, or industry owner of an existing application.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_application_identity_change() from public;

drop trigger if exists applications_prevent_identity_change on applications;
create trigger applications_prevent_identity_change
  before update on applications
  for each row
  execute procedure public.prevent_application_identity_change();

-- Restricts a STUDENT caller to exactly one status transition on their own
-- application: withdrawing it. Every other status value (SHORTLISTED,
-- INTERVIEW_SCHEDULED, SELECTED, REJECTED, ...) is a recruitment decision
-- that only the owning INDUSTRY account may set -- enforced here because
-- the "Students can withdraw their own applications" UPDATE policy below
-- is ownership-only and would otherwise let a student set ANY status on
-- their own row, not just WITHDRAWN.
create or replace function public.prevent_student_status_override()
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

revoke all on function public.prevent_student_status_override() from public;

drop trigger if exists applications_prevent_student_status_override on applications;
create trigger applications_prevent_student_status_override
  before update on applications
  for each row
  execute procedure public.prevent_student_status_override();

drop trigger if exists applications_set_updated_at on applications;
create trigger applications_set_updated_at
  before update on applications
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies
-- ============================================================

-- ---- Student policies ----

drop policy if exists "Students can view their own applications" on applications;
create policy "Students can view their own applications"
  on applications for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

-- industry_id is deliberately NOT checked here -- it does not exist yet
-- at the time this policy evaluates the incoming row's client-supplied
-- value; it is populated by the applications_set_industry_id trigger
-- (which runs BEFORE this check, since BEFORE ROW triggers execute before
-- RLS WITH CHECK is evaluated against the resulting row). Ownership of
-- the caller as the applicant, and the referenced posting actually being
-- PUBLISHED, are what this check enforces.
drop policy if exists "Students can apply to published opportunities" on applications;
create policy "Students can apply to published opportunities"
  on applications for insert
  to authenticated
  with check (
    auth.uid() = student_id
    and public.is_student(auth.uid())
    and (
      (opportunity_type = 'INTERNSHIP' and exists (
        select 1 from internships i where i.id = internship_id and i.status = 'PUBLISHED'
      ))
      or
      (opportunity_type = 'JOB' and exists (
        select 1 from jobs j where j.id = job_id and j.status = 'PUBLISHED'
      ))
    )
  );

drop policy if exists "Students can withdraw their own applications" on applications;
create policy "Students can withdraw their own applications"
  on applications for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

-- ---- Industry policies ----

drop policy if exists "Industry can view applications to their own postings" on applications;
create policy "Industry can view applications to their own postings"
  on applications for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update applications to their own postings" on applications;
create policy "Industry can update applications to their own postings"
  on applications for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No delete policy for either role -- applications are recruitment
-- history and are never removed via the app, only via status transitions
-- (WITHDRAWN / REJECTED / etc.).
