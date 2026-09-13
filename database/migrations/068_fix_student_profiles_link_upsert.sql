-- Migration: 068_fix_student_profiles_link_upsert
-- Purpose: fix a real bug in apply_link_request_status_change()
-- (038_institution_link_requests.sql) -- the trigger that is supposed to
-- be THE ONE place that writes student_profiles.institution_id on
-- approval/removal of an institution_link_requests row. Forward migration
-- in this branch's own numbering -- no historical migration file is
-- edited.
--
-- ============================================================
-- The bug
-- ============================================================
-- On APPROVED, the trigger has always done:
--
--   update public.student_profiles
--      set institution_id = new.institution_id
--    where id = new.student_id;
--
-- student_profiles rows are created LAZILY (012_student_profiles.sql --
-- "unlike `profiles`, there is no trigger auto-creating a [student_profiles]
-- row"; a row only exists once a student saves their Student Profile
-- form). A student who requests and gets approved by an institution
-- BEFORE ever saving that form has no student_profiles row yet, so the
-- UPDATE above matches zero rows and silently does nothing --
-- institution_link_requests.status correctly becomes 'APPROVED', but
-- student_profiles.institution_id (the canonical Student<->Institution
-- relationship -- student_institution_service.py's own docstring: "the
-- ONE source of truth ... set/cleared ONLY by [this] trigger") is never
-- set. Every institution-curated placement drive / internship / event
-- the student should now see depends on that same column, so this is a
-- real, silent data-loss bug, not just a display issue -- confirmed
-- during the Student Dashboard "My Institution" card investigation (see
-- that task's VERIFIED_AWAITING_SYNC frontend defensive state, which
-- stays in place after this fix as protection against any future/
-- transient inconsistency, not a substitute for it).
--
-- ============================================================
-- Confirmed safe before writing this migration (not assumed)
-- ============================================================
-- Every student_profiles column except `id` (the PK) is either NULLABLE
-- or has a DEFAULT (012_student_profiles.sql: preferred_roles/
-- preferred_locations/interests all `not null default '{}'`, created_at/
-- updated_at both `not null default now()`; 037_institution_tenancy.sql's
-- institution_id and 040_institution_departments.sql's department_id are
-- both plain nullable columns). So `insert into student_profiles (id,
-- institution_id) values (...)` is valid against the CURRENT schema with
-- no invented values for any other column.
--
-- student_profiles_validate_institution_id (037) is BEFORE INSERT OR
-- UPDATE and re-checks is_institution(new.institution_id) -- satisfied
-- here regardless, since institution_link_requests.institution_id is
-- already validated as a real INSTITUTION account by
-- validate_link_request_institution (038) on that table. No conflict.
--
-- institution_link_requests_one_live_per_student_idx (038) is a unique
-- index on (student_id) where status in ('PENDING', 'APPROVED') -- this
-- guarantees AT MOST ONE live (PENDING or APPROVED) request can ever
-- exist for a given student at a time. There is therefore no possible
-- ambiguity for the backfill below: a student with an APPROVED row has
-- exactly one, never two competing ones.
--
-- ============================================================
-- Fix (CREATE OR REPLACE, same signature/security properties)
-- ============================================================
-- APPROVED now performs an atomic UPSERT instead of a bare UPDATE:
-- creates the minimum valid student_profiles row (id, institution_id --
-- every other column takes its own default/NULL, matching what a
-- lazily-created row would already look like) if one doesn't exist yet,
-- or updates institution_id on the existing row otherwise. The WHERE
-- guard on the UPDATE arm makes a repeat/no-op call a true no-op (no
-- spurious updated_at bump), matching this codebase's existing
-- idempotency convention (e.g. 067's own verification UPDATE).
--
-- REMOVED is UNCHANGED: still a bare UPDATE, still guarded by
-- `and institution_id = new.institution_id` so it can never clear a
-- newer/different institution relationship the student has since
-- established -- there is nothing to upsert here (unlinking a student
-- with no student_profiles row is already correctly a no-op, and
-- REMOVED should never itself bring a row into existence).
--
-- Same SECURITY DEFINER + set search_path = '' as the original -- no
-- privilege broadened. Still fires only from an already-RLS-checked
-- UPDATE on institution_link_requests (restrict_link_request_transitions,
-- 038), the same "narrowly-scoped SECURITY DEFINER write gated by an
-- already-RLS-checked update on this table" pattern documented in 038's
-- own header.

create or replace function public.apply_link_request_status_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.status = 'APPROVED' and old.status is distinct from 'APPROVED' then
    insert into public.student_profiles (id, institution_id)
    values (new.student_id, new.institution_id)
    on conflict (id) do update
      set institution_id = excluded.institution_id
      where student_profiles.institution_id is distinct from excluded.institution_id;
  elsif new.status = 'REMOVED' and old.status = 'APPROVED' then
    -- The `and institution_id = new.institution_id` guard means this can
    -- never clear a link the student has since re-established elsewhere
    -- -- though the one-live-request-per-student index means that could
    -- only happen after this same REMOVED transition already ran.
    update public.student_profiles
       set institution_id = null
     where id = new.student_id
       and institution_id = new.institution_id;
  end if;

  return new;
end;
$$;

revoke all on function public.apply_link_request_status_change() from public;

-- Trigger definition itself is unchanged (same name, same timing, same
-- procedure) -- CREATE OR REPLACE FUNCTION above already updates its
-- behavior without needing to touch the trigger attachment at all. Kept
-- here (drop + recreate) only to match this codebase's existing
-- convention of making every migration that touches a trigger function
-- fully self-contained and safe to re-run on its own.
drop trigger if exists institution_link_requests_apply_status_change on institution_link_requests;
create trigger institution_link_requests_apply_status_change
  after update on institution_link_requests
  for each row
  execute procedure public.apply_link_request_status_change();

-- ============================================================
-- Backfill: repair existing APPROVED links broken by the bug above
-- ============================================================
-- Scoped strictly to institution_link_requests rows that are CURRENTLY
-- 'APPROVED' -- never REJECTED/CANCELLED/REMOVED/PENDING. Safe and
-- unambiguous per the one-live-request-per-student index confirmed
-- above: at most one APPROVED row can exist per student, so there is
-- exactly one correct institution_id to backfill, never a choice between
-- competing candidates. Idempotent: a student_profiles row that already
-- has the correct institution_id is left untouched (ON CONFLICT ... WHERE
-- guard below); running this migration twice changes nothing the second
-- time.
insert into public.student_profiles (id, institution_id)
select ilr.student_id, ilr.institution_id
from public.institution_link_requests ilr
where ilr.status = 'APPROVED'
on conflict (id) do update
  set institution_id = excluded.institution_id
  where student_profiles.institution_id is distinct from excluded.institution_id;
