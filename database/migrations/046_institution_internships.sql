-- Migration: 046_institution_internships
-- Purpose: PHASE -- INSTITUTION-CURATED INTERNSHIPS. Replaces the
-- Institution Internship module's old "directory" definition (every
-- currently-PUBLISHED internship platform-wide, plus any internship one
-- of the institution's own students happened to apply to --
-- 042_institution_internship_visibility.sql) with an EXPLICIT
-- institution selection/curation model. This migration adds exactly ONE
-- new table. It does NOT create a second internship entity:
--
--   - The canonical internship identity/content remains `internships`
--     (018_internships.sql), owned and edited only by its Industry
--     account -- this migration never copies title/description/stipend/
--     work_mode/eligibility into the new table, and grants the
--     Institution no write path onto `internships` at all.
--   - "Selected" (a STUDENT being selected for an internship) still means
--     exactly what it has meant since 037_institution_tenancy.sql: an
--     `applications` row with opportunity_type = 'INTERNSHIP' and
--     status = 'SELECTED'. This table's own `status` column is a
--     DIFFERENT concept -- whether the INSTITUTION itself has curated
--     this internship -- and is never conflated with application status.
--   - This is the exact same "institution-private relationship tag on
--     top of an existing canonical entity" shape as
--     institution_industry_partners (043_institution_industry_partners.sql)
--     tags a company, and placement_drives (041) wraps a job -- same
--     ownership split, same naming convention (a `status` lifecycle,
--     `institution_id` + target-entity id, one row per pair).
--
-- Ownership split:
--   internships               -> canonical Industry-owned posting
--   institution_internships   -> the INSTITUTION's own selection of that
--                                 posting into its curated internship list
--
-- Scope: INSTITUTION-private, same as institution_industry_partners --
-- an Industry account is never notified "Institution X added your
-- internship", and no other institution can see this institution's
-- selection.
--
-- Ownership: institution_id references profiles(id), not
-- institution_profiles(id) -- same reasoning as every other
-- institution_id FK in this schema (037/038/040/041/043/044).
--
-- internship_id references internships(id) `on delete restrict`, NOT
-- cascade -- same choice, and the same reasoning, as placement_drives.
-- job_id (041): `internships` already has no DELETE policy at all
-- (028_forbid_internship_job_deletes.sql), so this is a defensive,
-- currently-unreachable safeguard, not a working deletion path this
-- migration expects to ever fire. A curated internship must never
-- silently disappear because its canonical row was removed out from
-- under it.
--
-- No `added_by` column: every institution account in this schema is a
-- single auth.uid() (there is no multi-staff-user-per-institution
-- concept anywhere yet), so `added_by` would always equal
-- `institution_id` -- an always-redundant column. institution_id alone
-- already answers "who added this", matching every other institution-
-- owned relationship table in this schema (043/044 carry no such column
-- either).
--
-- Lifecycle: ACTIVE / INACTIVE (not SELECTED/REMOVED) -- matches the
-- existing `relationship_status` vocabulary style used by
-- institution_industry_partners (043: PROSPECT/ACTIVE/INACTIVE). ACTIVE
-- means "currently part of this institution's curated internship list";
-- INACTIVE means the institution removed it -- soft-removal only, same
-- deactivate-don't-delete convention as every other institution-owned
-- table in this schema. Re-selecting a previously INACTIVE internship
-- reactivates the same row (status -> ACTIVE) rather than inserting a
-- second one, honoring the unique pair constraint below.

create table if not exists institution_internships (
  id uuid primary key default gen_random_uuid(),

  institution_id uuid not null references profiles (id) on delete cascade,
  internship_id uuid not null references internships (id) on delete restrict,

  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'INACTIVE')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- One association row per (institution, internship) ever -- removing
  -- and re-adding the same internship reactivates this row, never a
  -- second one.
  constraint institution_internships_unique_pair unique (institution_id, internship_id)
);

create index if not exists institution_internships_institution_id_idx
  on institution_internships (institution_id);
create index if not exists institution_internships_internship_id_idx
  on institution_internships (internship_id);
-- Serves the default "curated / ACTIVE" list view (the module's default
-- page load).
create index if not exists institution_internships_institution_status_idx
  on institution_internships (institution_id, status);

alter table institution_internships enable row level security;

-- ============================================================
-- Trigger: on INSERT only, the referenced internship must currently be
-- PUBLISHED -- an Institution can only curate a genuinely available
-- posting, never a DRAFT (not even visible to it), CLOSED, or ARCHIVED
-- one. This is a database-level backstop behind the service-layer check
-- (institution_internship_service.select_internship reads the internship
-- through the institution's own RLS-scoped client first, which already
-- returns nothing for a non-PUBLISHED posting it doesn't own) -- same
-- "server validates, never trusts the client's target id" shape as
-- validate_partner_industry_id (043) and
-- validate_placement_drive_departments (041).
--
-- Deliberately NOT re-checked on UPDATE: once curated, a posting may
-- later be legitimately CLOSED/ARCHIVED by its owner while remaining a
-- valid piece of the institution's OWN historical curated list (same
-- "the institution's own record stays readable after the underlying
-- posting's status moves on" principle as placement_drives/
-- institution_visible_job_details, 041). Only the institution's own
-- `status` column (ACTIVE/INACTIVE) is meant to change after insert.
-- ============================================================

create or replace function public.validate_internship_selection()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (
    select 1 from public.internships i
    where i.id = new.internship_id and i.status = 'PUBLISHED'
  ) then
    raise exception 'institution_internships.internship_id must reference a currently PUBLISHED internship.' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke all on function public.validate_internship_selection() from public;

drop trigger if exists institution_internships_validate_selection on institution_internships;
create trigger institution_internships_validate_selection
  before insert on institution_internships
  for each row
  execute procedure public.validate_internship_selection();

drop trigger if exists institution_internships_set_updated_at on institution_internships;
create trigger institution_internships_set_updated_at
  before update on institution_internships
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies -- INSTITUTION-owned, INSTITUTION-only. Split into
-- explicit SELECT / INSERT / UPDATE so DELETE is left with NO policy at
-- all -- same "deactivate via status, never hard-delete" convention as
-- institution_industry_partners (043) and every other institution-owned
-- table in this schema.
-- ============================================================

drop policy if exists "Institution can view their own curated internships" on institution_internships;
create policy "Institution can view their own curated internships"
  on institution_internships for select
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can create their own curated internships" on institution_internships;
create policy "Institution can create their own curated internships"
  on institution_internships for insert
  to authenticated
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can update their own curated internships" on institution_internships;
create policy "Institution can update their own curated internships"
  on institution_internships for update
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()))
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

-- ============================================================
-- institution_curated_internship_details -- same "historical visibility"
-- fix as institution_visible_internship_details (042), but keyed by
-- CURATION (this institution's own institution_internships row) instead
-- of by a student application. Needed because `internships` is only
-- readable to a non-owner while status = 'PUBLISHED' (018) -- once a
-- company closes/archives an internship the institution already curated,
-- the curated list/detail page would otherwise go blind to its own
-- title/description/stipend/etc. 042's own function is left completely
-- untouched (still used nowhere by this migration, superseded for the
-- curated-list purpose it used to partially serve, but harmless and not
-- retroactively edited -- this project never rewrites a past migration).
-- Returns full display fields, but ONLY for an internship THIS
-- institution has curated (any association status) -- never a general
-- posting lookup.
-- ============================================================

create or replace function public.institution_curated_internship_details(internship_ids uuid[])
returns table (
  id uuid,
  title text,
  description text,
  location text,
  work_mode text,
  duration_months int,
  stipend_amount numeric,
  stipend_currency text,
  eligibility_criteria text,
  application_deadline date,
  start_date date,
  status text,
  industry_id uuid
)
language sql
security definer
set search_path = ''
stable
as $$
  select i.id, i.title, i.description, i.location, i.work_mode, i.duration_months,
         i.stipend_amount, i.stipend_currency, i.eligibility_criteria,
         i.application_deadline, i.start_date, i.status, i.industry_id
  from public.internships i
  where i.id = any(internship_ids)
    and public.is_institution(auth.uid())
    and exists (
      select 1
      from public.institution_internships ii
      where ii.internship_id = i.id
        and ii.institution_id = auth.uid()
    );
$$;

revoke all on function public.institution_curated_internship_details(uuid[]) from public;
revoke all on function public.institution_curated_internship_details(uuid[]) from anon;
grant execute on function public.institution_curated_internship_details(uuid[]) to authenticated;

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INSTITUTION: curate a real PUBLISHED internship
--   insert into public.institution_internships (institution_id, internship_id)
--     values (auth.uid(), '<a PUBLISHED internship id>'::uuid);
--   select * from public.institution_internships where institution_id = auth.uid();
--
--   -- internship_id referencing a DRAFT/CLOSED/ARCHIVED internship: rejected
--   -- (validate_internship_selection raises)
--
--   -- as a DIFFERENT institution: 0 rows, and inserting under someone
--   -- else's institution_id is rejected by the WITH CHECK
--
--   -- re-curating the same internship after removal: an UPDATE via the
--   -- unique (institution_id, internship_id) pair (status ACTIVE ->
--   -- INACTIVE -> ACTIVE again), never a duplicate row
--
--   -- institution_curated_internship_details for an internship this
--   -- institution never curated: 0 rows, even if PUBLISHED (use the
--   -- ordinary internships table read for that case instead)
-- ============================================================
