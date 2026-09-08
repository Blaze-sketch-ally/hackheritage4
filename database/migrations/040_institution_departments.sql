-- Migration: 040_institution_departments
-- Purpose: a real Department entity, owned by an INSTITUTION account, to
-- replace the free-text `student_profiles.department` string as the
-- authoritative grouping for the Institution Dashboard's "Department
-- Performance", the Student Directory's department filter, and the new
-- /institution/departments module.
--
-- Does NOT touch `student_profiles.department` (still there, still
-- whatever the student's own profile form writes to it) or
-- `student_profiles.institution_name` -- both are left exactly as they
-- are. `department_id` is additive: NULL for every existing student
-- (see the "no fuzzy migration" section below), and becomes the
-- authoritative Institution-portal relationship going forward only once
-- an institution explicitly assigns it.
--
-- Ownership convention: departments.institution_id references
-- profiles(id), NOT institution_profiles(id) -- same reasoning as every
-- other Institution/Industry-owned entity in this schema
-- (student_profiles.institution_id, industry_collaborations.industry_id,
-- internships.industry_id, ...): an institution account is a valid owner
-- from the moment it signs up, whether or not it has ever saved an
-- institution_profiles row.
--
-- ============================================================
-- No automatic data migration.
-- ============================================================
-- student_profiles.department is free text entered by students
-- ("CSE", "Computer Science", "Computer Science & Engineering", typos,
-- ...). This migration does NOT attempt to resolve that text into a
-- department row for any institution -- a name match is not proof of
-- which institution's "CSE" a given student meant, and guessing risks
-- silently attaching a student to the wrong department (or the wrong
-- institution's department entirely, which 037/038's whole tenancy model
-- exists to prevent). Every student's department_id starts NULL. An
-- institution creates its own departments and assigns students to them
-- explicitly (institution_department_service.assign_student_department)
-- -- see this migration's approval report for the exact "how existing
-- students become organized" answer.

-- ============================================================
-- departments
-- ============================================================

create table if not exists departments (
  id uuid primary key default gen_random_uuid(),
  institution_id uuid not null references profiles (id) on delete cascade,

  name text not null,
  code text,
  description text,
  is_active boolean not null default true,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint departments_name_not_blank check (length(trim(name)) > 0),
  constraint departments_code_not_blank check (code is null or length(trim(code)) > 0)
);

-- Case-insensitive uniqueness PER INSTITUTION -- same "lower(x)" pattern
-- as profiles.username / skills.name throughout this schema. Two
-- different institutions may both have a "CSE" department; the same
-- institution may not have "CSE" and "cse" as two different rows.
create unique index if not exists departments_institution_name_lower_idx
  on departments (institution_id, lower(name));
-- Partial: code is optional, so uniqueness only applies when it's set.
create unique index if not exists departments_institution_code_lower_idx
  on departments (institution_id, lower(code)) where code is not null;

create index if not exists departments_institution_id_idx on departments (institution_id);
-- Serves the "browse active departments" query (the department selector,
-- the default Departments page filter) -- same partial-index shape as
-- job_roles_active_idx / internships_published_idx elsewhere.
create index if not exists departments_institution_active_idx
  on departments (institution_id) where is_active = true;

alter table departments enable row level security;

drop policy if exists "Institution can view their own departments" on departments;
create policy "Institution can view their own departments"
  on departments for select
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can create their own departments" on departments;
create policy "Institution can create their own departments"
  on departments for insert
  to authenticated
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can update their own departments" on departments;
create policy "Institution can update their own departments"
  on departments for update
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()))
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

-- No delete policy -- matches the "forbid hard delete of owned records"
-- convention already established for Industry postings
-- (027_forbid_industry_record_deletes.sql / 028_forbid_internship_job_deletes.sql).
-- Deactivation is `is_active = false` via the update policy above; a
-- deactivated department's existing student assignments and historical
-- placement data are never touched by this migration or by the service
-- layer built on top of it.

drop trigger if exists departments_set_updated_at on departments;
create trigger departments_set_updated_at
  before update on departments
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- student_profiles.department_id -- the authoritative Institution-portal
-- department relationship. Nullable, additive; `department` (free text)
-- is untouched.
-- ============================================================

alter table student_profiles
  add column if not exists department_id uuid references departments (id) on delete set null;

create index if not exists student_profiles_department_id_idx on student_profiles (department_id);

-- Validates (auto-clears, never hard-fails) that department_id -- if set
-- -- belongs to the SAME institution as the student's own institution_id.
-- Auto-clear rather than raise is deliberate: this trigger also fires for
-- the trusted institution-unlink path (apply_link_request_status_change,
-- 038_institution_link_requests.sql, sets institution_id = NULL on
-- REMOVED), which must succeed, not abort, when a department was
-- assigned. The institution-facing REJECTION of an invalid *assignment
-- attempt* (Part 14 of this phase) happens one layer up, in
-- institution_department_service.assign_student_department, before this
-- trigger ever sees the write -- this is the last-resort data-integrity
-- backstop, same role as every other validate_* trigger in this schema.
create or replace function public.validate_student_department_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  dept_institution_id uuid;
begin
  if new.department_id is null then
    return new;
  end if;

  select institution_id into dept_institution_id
  from public.departments
  where id = new.department_id;

  if dept_institution_id is null or new.institution_id is null or dept_institution_id <> new.institution_id then
    new.department_id := null;
  end if;

  return new;
end;
$$;

revoke all on function public.validate_student_department_id() from public;

drop trigger if exists student_profiles_validate_department_id on student_profiles;
create trigger student_profiles_validate_department_id
  before insert or update on student_profiles
  for each row
  execute procedure public.validate_student_department_id();

-- ============================================================
-- Institution write access to student_profiles (department assignment
-- only). No such policy existed before this migration -- 037 only added
-- an institution SELECT policy on student_profiles. This is the first
-- institution WRITE path onto a table it does not own, so it is paired
-- immediately with a column-restriction trigger: Postgres RLS can only
-- gate WHICH ROWS an UPDATE may touch, never WHICH COLUMNS, so without
-- the trigger below this policy would let an institution edit a linked
-- student's cgpa, career_goals, etc. -- not just department_id.
-- ============================================================

drop policy if exists "Institution can update department assignment for their own students" on student_profiles;
create policy "Institution can update department assignment for their own students"
  on student_profiles for update
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()))
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

-- Restricts an INSTITUTION-context update (auth.uid() = the row's OWN
-- institution_id, i.e. reached only through the policy above) to
-- changing department_id and nothing else. Deliberately does NOT include
-- institution_id in the guarded column list: institution_id changes on
-- this table are made exclusively by apply_link_request_status_change
-- (038), a SECURITY DEFINER function that runs with elevated privilege
-- (bypassing RLS entirely, same as every other trusted cross-table write
-- in this schema) -- this trigger still fires for that write (BEFORE ROW
-- triggers always fire regardless of the RLS path taken), and on unlink
-- old.institution_id = auth.uid() (the unlinking institution) while
-- institution_id itself is legitimately changing to NULL. The
-- policy's own WITH CHECK (institution_id = auth.uid()) already prevents
-- an institution from changing institution_id to anything but its own id
-- via THIS ordinary RLS-scoped policy, so no additional trigger guard is
-- needed for that column specifically.
create or replace function public.restrict_institution_student_profile_updates()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if auth.uid() = old.institution_id and public.is_institution(auth.uid()) then
    if new.phone is distinct from old.phone
      or new.date_of_birth is distinct from old.date_of_birth
      or new.gender is distinct from old.gender
      or new.location is distinct from old.location
      or new.institution_name is distinct from old.institution_name
      or new.department is distinct from old.department
      or new.degree is distinct from old.degree
      or new.graduation_year is distinct from old.graduation_year
      or new.cgpa is distinct from old.cgpa
      or new.percentage is distinct from old.percentage
      or new.career_goals is distinct from old.career_goals
      or new.preferred_roles is distinct from old.preferred_roles
      or new.preferred_locations is distinct from old.preferred_locations
      or new.interests is distinct from old.interests
    then
      raise exception 'An institution may only change a linked student''s department assignment.' using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.restrict_institution_student_profile_updates() from public;

drop trigger if exists student_profiles_restrict_institution_updates on student_profiles;
create trigger student_profiles_restrict_institution_updates
  before update on student_profiles
  for each row
  execute procedure public.restrict_institution_student_profile_updates();

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INSTITUTION: create/list/update its own departments
--   insert into public.departments (institution_id, name, code)
--     values (auth.uid(), 'Computer Science & Engineering', 'CSE');
--   select * from public.departments where institution_id = auth.uid();
--
--   -- as any OTHER institution: 0 rows, insert under someone else's
--   -- institution_id is rejected by the WITH CHECK
--
--   -- assigning a department belonging to a different institution:
--   -- the UPDATE succeeds (RLS allows updating your own linked student),
--   -- but validate_student_department_id silently clears department_id
--   -- back to NULL -- the service layer is expected to reject this
--   -- attempt before it ever reaches this point.
-- ============================================================
