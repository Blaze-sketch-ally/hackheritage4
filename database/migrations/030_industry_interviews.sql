-- Migration: 030_industry_interviews
-- Purpose: Interview Scheduling for the Industry recruitment pipeline.
-- Until now "Interviews" was only an application STATUS
-- (applications.status = 'INTERVIEW_SCHEDULED', migration 020) with no
-- date, time, mode, location, or notes -- app/industry/interviews was a
-- filtered candidate list, not a scheduler. This migration adds the one
-- table that turns that stage into an actual scheduled event.
--
-- An interview always hangs off an existing `applications` row (020):
-- that row already carries the authoritative student <-> industry <->
-- posting relationship, server-derived and immutable. This table does
-- not re-derive or duplicate any of that from the client -- industry_id
-- and student_id are copied from the referenced application by a
-- BEFORE INSERT trigger, exactly like set_application_industry_id in 020.
--
-- Scope: INDUSTRY-side only. There is no Student-facing interview view in
-- this repository yet, so there is deliberately no student SELECT policy
-- here (add one in a later migration when that view is built). Nothing in
-- the existing Student / Faculty / Institution / Admin surface is touched.
--
-- Lifecycle (approved scope expansion, deliberately minimal):
--   SCHEDULED -> COMPLETED
--   SCHEDULED -> CANCELLED
-- Rescheduling is an EDIT of scheduled_at/duration/mode/location/notes on
-- a still-SCHEDULED interview -- NOT a separate status. A single-row model
-- cannot honestly carry "was rescheduled from X to Y" history, so it does
-- not pretend to (same philosophy as 026: cancellation is a status, an
-- edit is an edit). COMPLETED and CANCELLED are terminal.
--
-- Timezone: `scheduled_at` is `timestamptz` -- it stores an absolute UTC
-- instant. The client sends an ISO-8601 string with offset; the UI renders
-- it back in the viewer's own locale. No separate date / time / timezone
-- columns are needed or wanted.

create table if not exists interviews (
  id uuid primary key default gen_random_uuid(),

  application_id uuid not null references applications (id) on delete cascade,

  -- Both are populated and OVERWRITTEN server-side by the
  -- set_interview_derived_ids BEFORE INSERT trigger from the referenced
  -- application -- a client-supplied value is ignored, and both are
  -- immutable after insert (prevent_interview_identity_change). Mirrors
  -- applications.industry_id (020): ON DELETE RESTRICT so interview
  -- history survives even if the posting industry account is later
  -- removed; student_id ON DELETE CASCADE matching every other student_id
  -- FK convention in this schema.
  industry_id uuid not null references profiles (id) on delete restrict,
  student_id uuid not null references profiles (id) on delete cascade,

  scheduled_at timestamptz not null,
  duration_minutes int not null default 30 check (duration_minutes between 5 and 480),

  -- ONLINE: `location` holds the meeting URL. ONSITE: `location` holds the
  -- address. PHONE: `location` optionally holds a number. One field,
  -- semantics by mode -- no separate meeting_url / address / phone columns.
  mode text not null check (mode in ('ONLINE', 'PHONE', 'ONSITE')),
  location text,

  -- Industry-private preparation notes. Never exposed to any other role
  -- (there is no policy that would let another role read this row at all).
  notes text,

  status text not null default 'SCHEDULED' check (status in ('SCHEDULED', 'COMPLETED', 'CANCELLED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- At most ONE live (SCHEDULED) interview per application. A COMPLETED or
-- CANCELLED interview may coexist with a fresh SCHEDULED one (reschedule
-- after cancellation), but two simultaneously-live interviews for the
-- same application can never exist. Partial index -- the "duplicate
-- interview" guard the scheduler needs.
create unique index if not exists interviews_one_live_per_application_idx
  on interviews (application_id) where status = 'SCHEDULED';

create index if not exists interviews_application_id_idx on interviews (application_id);
-- Drives the industry-side list (ordered by date) and the overlap check
-- the service runs before scheduling a new one.
create index if not exists interviews_industry_scheduled_idx on interviews (industry_id, scheduled_at);

alter table interviews enable row level security;

-- ============================================================
-- Triggers
-- ============================================================

-- Derives (and OVERWRITES) industry_id + student_id from the referenced
-- application at insert time -- any client-supplied value is ignored.
-- This is what makes "an interview belongs to the same industry and
-- student as its application" a database-enforced guarantee rather than a
-- client-side promise, even for a direct REST call bypassing the API.
-- SECURITY DEFINER + pinned empty search_path, same pattern as
-- set_application_industry_id (020_applications.sql).
create or replace function public.set_interview_derived_ids()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  app record;
begin
  select industry_id, student_id, status
    into app
    from public.applications
   where id = new.application_id;

  if app.industry_id is null then
    raise exception 'Referenced application does not exist.' using errcode = '23503';
  end if;

  -- An interview only makes sense for a candidate who is at (or past) the
  -- shortlist stage. This mirrors the intent of the applications status
  -- pipeline (020): SHORTLISTED -> INTERVIEW_SCHEDULED. The service layer
  -- re-checks this too, but the trigger is the authoritative backstop.
  if app.status not in ('SHORTLISTED', 'INTERVIEW_SCHEDULED') then
    raise exception 'An interview can only be scheduled for a shortlisted application.' using errcode = '42501';
  end if;

  new.industry_id := app.industry_id;
  new.student_id := app.student_id;
  return new;
end;
$$;

revoke all on function public.set_interview_derived_ids() from public;

drop trigger if exists interviews_set_derived_ids on interviews;
create trigger interviews_set_derived_ids
  before insert on interviews
  for each row
  execute procedure public.set_interview_derived_ids();

-- Blocks changes to the columns that define WHICH interview this is --
-- application_id, industry_id, student_id -- after creation, for every
-- ordinary RLS-governed caller. Same OLD vs NEW / service_role-steps-aside
-- pattern as prevent_application_identity_change (020_applications.sql).
create or replace function public.prevent_interview_identity_change()
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
    or new.industry_id is distinct from old.industry_id
    or new.student_id is distinct from old.student_id
  then
    raise exception 'Cannot change the application, industry, or student of an existing interview.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_interview_identity_change() from public;

drop trigger if exists interviews_prevent_identity_change on interviews;
create trigger interviews_prevent_identity_change
  before update on interviews
  for each row
  execute procedure public.prevent_interview_identity_change();

drop trigger if exists interviews_set_updated_at on interviews;
create trigger interviews_set_updated_at
  before update on interviews
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies -- INDUSTRY only
-- ============================================================
-- Split into explicit SELECT / INSERT / UPDATE (rather than one FOR ALL)
-- so that DELETE is left with NO policy at all: an interview is
-- recruitment history and is never hard-deleted through the app --
-- cancellation is a status (CANCELLED), matching 020/026/027/028.

drop policy if exists "Industry can view interviews for their own postings" on interviews;
create policy "Industry can view interviews for their own postings"
  on interviews for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- industry_id is set by the set_interview_derived_ids trigger (which runs
-- BEFORE this WITH CHECK is evaluated) from the referenced application, so
-- `auth.uid() = industry_id` here confirms the derived owner -- and
-- therefore the application's real owner -- is the caller.
drop policy if exists "Industry can schedule interviews for their own applications" on interviews;
create policy "Industry can schedule interviews for their own applications"
  on interviews for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update interviews for their own postings" on interviews;
create policy "Industry can update interviews for their own postings"
  on interviews for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No DELETE policy for any role -- see the note above.
