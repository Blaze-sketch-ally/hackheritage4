-- Migration: 077_institution_events
-- Purpose: PHASE 10 -- lets an INSTITUTION organize its own event
-- (seminar, workshop, guest lecture, industry talk, training, FDP,
-- career session, placement orientation, ...), optionally featuring an
-- existing company, targeted at its own departments/batches. This
-- migration adds exactly ONE new table.
--
-- Audit finding this migration acts on: `industry_workshops`
-- (024_industry_workshops.sql) is the ONLY event-style entity anywhere
-- in this schema (confirmed by student_event_service.py's own docstring:
-- "There is no `events` table and none is introduced... a student-facing
-- 'event' is one PUBLISHED industry workshop"). It is INDUSTRY-owned --
-- RLS grants no INSTITUTION write path to it at all ("Industry can
-- manage their own workshops", auth.uid() = industry_id AND
-- is_industry(auth.uid())) -- and it has no department targeting, no
-- event-type taxonomy, and no concept of an institution-organized
-- session (a Placement Orientation or Career Session has no company
-- posting it to be). Reusing it for Institution's own events would
-- require either (a) widening its INSERT policy to a role it was never
-- designed for, silently changing who "owns" a workshop, or (b) misusing
-- REGISTERED-to-industry rows to represent institution-run sessions.
-- Neither is acceptable, so `industry_workshops` is left completely
-- untouched, and this migration adds the smallest new entity that
-- genuinely does not exist: an INSTITUTION-owned event record.
--
-- This is NOT a duplicate event system: `industry_workshops` remains
-- the one place a company posts its own workshop, still readable to
-- Institution/Students via its existing "PUBLISHED" policy and still
-- surfaced platform-wide on the Institution Events page (Part 4) --
-- this table is additive, for the institution's OWN organized sessions,
-- which may optionally reference an existing company (industry_id) for
-- context (e.g. "ABC Technologies" giving an Industry Talk) without
-- requiring that company to have published a matching industry_workshops
-- row. There is no registration/attendance table anywhere in this
-- schema (024's own header comment: "no application/registration table")
-- and none is invented here either -- see Part 11/12 of the phase task.
--
-- Same ownership/target reasoning as placement_drives (041):
--   institution_id references profiles(id), not institution_profiles(id).
--   industry_id (nullable) references profiles(id), validated to be a
--     real INDUSTRY account when set -- same pattern as
--     institution_industry_partners.industry_id (043) /
--     institution_industry_connections.industry_id (044).
--   target_department_ids is a uuid[], not a join table -- same
--     "simple scalar-list, only ever read/written atomically with the
--     parent row" reasoning as placement_drives.eligible_department_ids.
--   Empty target_department_ids AND empty target_batches means "all
--     students" -- the institution narrows the audience down, not up.
--   mode reuses the EXACT SAME vocabulary as jobs/internships/
--     placement_drives (ONSITE/REMOTE/HYBRID).
--   start_at/end_at are timestamptz (absolute instants), same reasoning
--     as interviews.scheduled_at (030): no separate date/time/timezone
--     columns are needed or wanted.

create table if not exists institution_events (
  id uuid primary key default gen_random_uuid(),
  institution_id uuid not null references profiles (id) on delete cascade,
  -- Optional featured company -- validated by the trigger below when set.
  -- Null means a purely institution-organized session (e.g. a Career
  -- Session or Placement Orientation with no company involved).
  industry_id uuid references profiles (id) on delete set null,

  title text not null,
  description text,
  event_type text not null default 'OTHER' check (
    event_type in (
      'SEMINAR', 'WORKSHOP', 'GUEST_LECTURE', 'INDUSTRY_TALK', 'TRAINING',
      'FDP', 'CAREER_SESSION', 'PLACEMENT_ORIENTATION', 'OTHER'
    )
  ),

  status text not null default 'DRAFT' check (
    status in ('DRAFT', 'PUBLISHED', 'ONGOING', 'COMPLETED', 'CANCELLED')
  ),

  mode text check (mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  venue text,
  start_at timestamptz,
  end_at timestamptz,
  constraint institution_events_end_after_start check (end_at is null or start_at is null or end_at >= start_at),
  -- Informational only -- there is no registration system to enforce
  -- this against (see the migration header comment).
  registration_deadline timestamptz,

  -- ---- Audience targeting (Part 9/10) -- descriptive metadata only,
  -- no registration/eligibility engine sits on top of it. ----
  target_department_ids uuid[] not null default '{}',
  target_batches int[] not null default '{}',
  includes_faculty boolean not null default false,

  instructions text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists institution_events_institution_id_idx on institution_events (institution_id);
create index if not exists institution_events_institution_status_idx on institution_events (institution_id, status);
create index if not exists institution_events_industry_id_idx on institution_events (industry_id) where industry_id is not null;

alter table institution_events enable row level security;

-- ============================================================
-- Triggers
-- ============================================================

create or replace function public.validate_institution_event_industry_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.industry_id is not null and not public.is_industry(new.industry_id) then
    raise exception 'institution_events.industry_id must reference an INDUSTRY account.' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke all on function public.validate_institution_event_industry_id() from public;

drop trigger if exists institution_events_validate_industry_id on institution_events;
create trigger institution_events_validate_industry_id
  before insert or update on institution_events
  for each row
  execute procedure public.validate_institution_event_industry_id();

-- Same shape as validate_placement_drive_departments (041) -- every id in
-- target_department_ids must be a department belonging to the SAME
-- institution as the event.
create or replace function public.validate_institution_event_departments()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  invalid_count int;
begin
  if new.target_department_ids is null or array_length(new.target_department_ids, 1) is null then
    return new;
  end if;

  select count(*) into invalid_count
  from unnest(new.target_department_ids) as dept_id
  where not exists (
    select 1 from public.departments d
    where d.id = dept_id and d.institution_id = new.institution_id
  );

  if invalid_count > 0 then
    raise exception 'All target departments must belong to your own institution.' using errcode = '23514';
  end if;

  return new;
end;
$$;

revoke all on function public.validate_institution_event_departments() from public;

drop trigger if exists institution_events_validate_departments on institution_events;
create trigger institution_events_validate_departments
  before insert or update on institution_events
  for each row
  execute procedure public.validate_institution_event_departments();

drop trigger if exists institution_events_set_updated_at on institution_events;
create trigger institution_events_set_updated_at
  before update on institution_events
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies -- INSTITUTION-owned, INSTITUTION-only. Split into
-- explicit SELECT / INSERT / UPDATE so DELETE is left with NO policy at
-- all -- same "CANCELLED is terminal, never hard-delete" convention as
-- placement_drives (041) and every other institution-owned table.
-- ============================================================

drop policy if exists "Institution can view their own events" on institution_events;
create policy "Institution can view their own events"
  on institution_events for select
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can create their own events" on institution_events;
create policy "Institution can create their own events"
  on institution_events for insert
  to authenticated
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can update their own events" on institution_events;
create policy "Institution can update their own events"
  on institution_events for update
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()))
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INSTITUTION: organize an event, optionally featuring
--   -- a real company, targeted at its own departments
--   insert into public.institution_events
--     (institution_id, title, event_type, industry_id, target_department_ids)
--     values (auth.uid(), 'Placement Orientation 2026', 'PLACEMENT_ORIENTATION', null, '{}');
--
--   -- industry_id referencing a STUDENT/FACULTY/non-industry account: rejected
--   -- (validate_institution_event_industry_id raises)
--
--   -- target_department_ids referencing another institution's department: rejected
--   -- (validate_institution_event_departments raises)
--
--   -- as a DIFFERENT institution: 0 rows, and inserting under someone
--   -- else's institution_id is rejected by the WITH CHECK
-- ============================================================
