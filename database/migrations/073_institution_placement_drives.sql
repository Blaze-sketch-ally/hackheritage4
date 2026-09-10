-- Migration: 073_institution_placement_drives
-- Purpose: lets an INSTITUTION coordinate its own students' participation
-- in an EXISTING company job posting, without creating any parallel
-- recruitment system. This migration adds exactly one new table
-- (`placement_drives`) plus the minimum read-visibility fix historical
-- drives need -- it does NOT create institution_jobs,
-- institution_applications, institution_interviews, or a second
-- placement-status concept. "Placed" still means exactly what it has
-- meant since 069_institution_tenancy.sql: an application row with
-- status = 'SELECTED'.
--
-- The real recruitment pipeline this migration coordinates, unchanged:
--   jobs (018/019)  ->  applications (020)  ->  interviews (030)
-- A placement_drives row is a thin INSTITUTION-owned wrapper around one
-- existing `jobs` row -- "this institution is coordinating its students'
-- participation in this company's job" -- plus institution-defined
-- eligibility criteria that have never existed anywhere in this schema
-- before now. It never duplicates the job's own title/description/
-- company/salary data, and it never touches `applications` ownership,
-- `jobs` ownership, or `interviews` ownership -- Industry still owns the
-- job and the hiring decision; the Institution only coordinates.
--
-- ============================================================
-- placement_drives
-- ============================================================
--
-- Eligibility criteria are arrays, not join tables -- consistent with
-- this project's own precedent for simple scalar-list fields
-- (student_profiles.preferred_roles/preferred_locations/interests, all
-- text[]), and simpler than three new join tables + their own RLS for
-- data that is only ever read/written as one atomic unit alongside the
-- drive itself (never independently listed, paginated, or CRUD'd on its
-- own). An empty array means "no restriction on this criterion" -- a
-- freshly created DRAFT drive with no criteria set yet is maximally
-- eligible, which is the correct default (the institution narrows
-- eligibility down, not up).
--
-- `mode` reuses the EXACT SAME vocabulary as jobs.work_mode / 018/019
-- (ONSITE/REMOTE/HYBRID) rather than inventing ONLINE/OFFLINE -- one
-- vocabulary for "how does this happen" across the schema.
--
-- `job_id references jobs(id) on delete restrict`: jobs already have no
-- delete policy at all (028_forbid_internship_job_deletes.sql) -- this
-- is a defensive, currently-unreachable safeguard, not a working
-- deletion path this migration expects to ever fire.

create table if not exists placement_drives (
  id uuid primary key default gen_random_uuid(),
  institution_id uuid not null references profiles (id) on delete cascade,
  job_id uuid not null references jobs (id) on delete restrict,

  title text not null,
  description text,

  status text not null default 'DRAFT' check (
    status in ('DRAFT', 'OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
  ),

  application_deadline date,
  drive_date date,
  mode text check (mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  venue text,
  instructions text,

  -- ---- Eligibility criteria (Part 7) ----
  -- Only criteria the existing student schema can actually evaluate.
  -- Deliberately NOT included: backlogs, attendance, age -- none of
  -- these exist anywhere on student_profiles or elsewhere in this schema.
  eligible_department_ids uuid[] not null default '{}',
  eligible_batches int[] not null default '{}',
  minimum_cgpa numeric(4, 2) check (minimum_cgpa is null or (minimum_cgpa >= 0 and minimum_cgpa <= 10)),
  eligible_skill_ids uuid[] not null default '{}',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint placement_drives_title_not_blank check (length(trim(title)) > 0)
);

create index if not exists placement_drives_institution_id_idx on placement_drives (institution_id);
create index if not exists placement_drives_job_id_idx on placement_drives (job_id);
-- Serves the default "active drives" view (list page default filter).
create index if not exists placement_drives_institution_status_idx on placement_drives (institution_id, status);

alter table placement_drives enable row level security;

drop policy if exists "Institution can view their own placement drives" on placement_drives;
create policy "Institution can view their own placement drives"
  on placement_drives for select
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can create their own placement drives" on placement_drives;
create policy "Institution can create their own placement drives"
  on placement_drives for insert
  to authenticated
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can update their own placement drives" on placement_drives;
create policy "Institution can update their own placement drives"
  on placement_drives for update
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()))
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

-- No delete policy -- a drive is historical record once created (Part 27:
-- "do not destroy historical drive data"). CANCELLED is the terminal
-- status for a drive that needs to stop, matching the
-- deactivate-don't-delete convention already used for departments (040)
-- and every Industry posting module (027/028).

drop trigger if exists placement_drives_set_updated_at on placement_drives;
create trigger placement_drives_set_updated_at
  before update on placement_drives
  for each row
  execute procedure public.set_updated_at();

-- Database-level integrity backstop (Part 26): every id in
-- eligible_department_ids must be a department belonging to the SAME
-- institution as the drive. Unlike validate_student_department_id (040),
-- which silently clears an invalid value because it must also tolerate a
-- trusted system-driven write, there is no such system-driven path here
-- -- every write to this table is a direct institution action through
-- its own RLS-scoped client, so an invalid value is a real integrity
-- violation and RAISES rather than silently correcting itself.
create or replace function public.validate_placement_drive_departments()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  invalid_count int;
begin
  if new.eligible_department_ids is null or array_length(new.eligible_department_ids, 1) is null then
    return new;
  end if;

  select count(*) into invalid_count
  from unnest(new.eligible_department_ids) as dept_id
  where not exists (
    select 1 from public.departments d
    where d.id = dept_id and d.institution_id = new.institution_id
  );

  if invalid_count > 0 then
    raise exception 'All eligible departments must belong to your own institution.' using errcode = '23514';
  end if;

  return new;
end;
$$;

revoke all on function public.validate_placement_drive_departments() from public;

drop trigger if exists placement_drives_validate_departments on placement_drives;
create trigger placement_drives_validate_departments
  before insert or update on placement_drives
  for each row
  execute procedure public.validate_placement_drive_departments();

-- ============================================================
-- institution_visible_job_details -- same wall, same fix, as
-- institution_visible_opportunity_titles (071_institution_student_directory.sql):
-- `jobs` is only readable to a non-owner while status = 'PUBLISHED'
-- (019_jobs.sql). Once a company closes/archives a job that already has
-- a placement drive, the drive would otherwise go blind to its own
-- job's title/description/salary/location -- breaking Part 27's
-- "the Placement Drive should remain readable for historical reporting".
-- Returns full display fields, but ONLY for a job one of the caller's
-- OWN placement drives references -- never a general posting lookup,
-- and never anything beyond what a published job already shows any
-- authenticated user.
-- ============================================================

create or replace function public.institution_visible_job_details(job_ids uuid[])
returns table (
  id uuid,
  title text,
  description text,
  location text,
  work_mode text,
  employment_type text,
  salary_min numeric,
  salary_max numeric,
  salary_currency text,
  experience_min_years numeric,
  status text,
  industry_id uuid
)
language sql
security definer
set search_path = ''
stable
as $$
  select j.id, j.title, j.description, j.location, j.work_mode, j.employment_type,
         j.salary_min, j.salary_max, j.salary_currency, j.experience_min_years,
         j.status, j.industry_id
  from public.jobs j
  where j.id = any(job_ids)
    and public.is_institution(auth.uid())
    and exists (
      select 1 from public.placement_drives pd
      where pd.job_id = j.id
        and pd.institution_id = auth.uid()
    );
$$;

revoke all on function public.institution_visible_job_details(uuid[]) from public;
revoke all on function public.institution_visible_job_details(uuid[]) from anon;
grant execute on function public.institution_visible_job_details(uuid[]) to authenticated;

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INSTITUTION: create/list/update its own drives
--   insert into public.placement_drives (institution_id, job_id, title)
--     values (auth.uid(), '<a PUBLISHED job id>'::uuid, 'Campus Drive 2026');
--   select * from public.placement_drives where institution_id = auth.uid();
--
--   -- eligible_department_ids referencing another institution's department: rejected
--   -- (validate_placement_drive_departments raises)
--
--   -- as a DIFFERENT institution: 0 rows, and inserting under someone
--   -- else's institution_id is rejected by the WITH CHECK
--
--   -- institution_visible_job_details for a job with no drive owned by
--   -- the caller: 0 rows, even if the job is PUBLISHED (use the ordinary
--   -- jobs table read for that case instead -- this function is only for
--   -- the historical-visibility gap)
-- ============================================================
