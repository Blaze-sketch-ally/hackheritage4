-- Migration: 038_institution_link_requests
-- Purpose: the STUDENT <-> INSTITUTION LINKING WORKFLOW -- the missing
-- piece from 037_institution_tenancy.sql, which added
-- student_profiles.institution_id but no safe way to populate it. Every
-- existing student got institution_id = NULL from 037 (no backfill was
-- performed -- see that migration's own comment); this migration is how
-- a student and an institution can legitimately become linked from here
-- on, with no auto-assignment and no student able to write an arbitrary
-- institution_id directly.
--
-- Modeled on industry_collaborations (026_industry_collaborations.sql):
-- a bilateral relationship row between an initiator (STUDENT here,
-- INDUSTRY there) and an approver (INSTITUTION here, FACULTY/INSTITUTION
-- there), with the identity-immutable / role-restricted-transition /
-- security-definer-derivation pattern reused wholesale, not reinvented.
--
-- Direction is deliberately STUDENT-initiates, INSTITUTION-approves --
-- not the other way around. An institution searching/browsing all
-- students to "invite" one would need either a global student list (an
-- information-disclosure risk explicitly ruled out by the task this
-- migration was written for) or the student's exact username already
-- known to the institution (no worse than this direction, but no better
-- either) -- so the safer, simpler direction is implemented: a student
-- who already knows their own institution's username requests to join
-- it, and the institution -- who can already see exactly who is asking --
-- approves or rejects.
--
-- Lifecycle:
--   PENDING -> APPROVED   (institution accepts -- sets student_profiles.institution_id)
--   PENDING -> REJECTED   (institution declines -- no student_profiles change)
--   PENDING -> CANCELLED  (student withdraws their own request)
--   APPROVED -> REMOVED   (institution unlinks a previously-approved student --
--                          clears student_profiles.institution_id)
-- REJECTED/CANCELLED/REMOVED are terminal for that row; a student may
-- always submit a brand-new PENDING request afterward (to the same or a
-- different institution) -- the partial unique index below only forbids
-- having more than one LIVE (PENDING or APPROVED) request at a time,
-- matching student_profiles.institution_id being a single column (one
-- institution per student), not a set.

create table if not exists institution_link_requests (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,
  -- Validated (never derived/overwritten) by validate_link_request_institution
  -- below -- unlike industry_collaborations' recipient_type, there is only
  -- one valid target role here (INSTITUTION), so there is nothing to
  -- derive into a second column; the FK + trigger together are the whole
  -- guarantee.
  institution_id uuid not null references profiles (id) on delete cascade,

  status text not null default 'PENDING' check (
    status in ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'REMOVED')
  ),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists institution_link_requests_student_id_idx on institution_link_requests (student_id);
create index if not exists institution_link_requests_institution_id_idx on institution_link_requests (institution_id);
-- At most one LIVE request per student at a time -- see the migration
-- header comment. Mirrors student_target_job_role_one_per_student
-- (016_skill_gap.sql) and interviews_one_live_per_application_idx
-- (030_industry_interviews.sql) for the same "at most one active X"
-- shape, via a partial index rather than a CHECK (which cannot reference
-- other rows).
create unique index if not exists institution_link_requests_one_live_per_student_idx
  on institution_link_requests (student_id) where status in ('PENDING', 'APPROVED');
-- Serves the institution-side "incoming" query (status filter + recency).
create index if not exists institution_link_requests_incoming_idx
  on institution_link_requests (institution_id, status);

alter table institution_link_requests enable row level security;

-- ============================================================
-- Resolution (student-side create form): find an institution by
-- username. Same shape and safety properties as
-- resolve_collaboration_recipient (026_industry_collaborations.sql) --
-- returns a row ONLY when the match is role = 'INSTITUTION', so a
-- STUDENT/INDUSTRY/FACULTY/ADMIN username resolves to no rows,
-- indistinguishable from a username that doesn't exist (no
-- account-existence or role leak). This is a single exact-identifier
-- lookup, never a browsable list -- it cannot be used to enumerate
-- institutions or students.
-- ============================================================

create or replace function public.resolve_institution_by_username(identifier text)
returns table (id uuid, full_name text)
language sql
security definer
set search_path = ''
stable
as $$
  select p.id, p.full_name
  from public.profiles p
  where lower(p.username) = lower(identifier)
    and p.role = 'INSTITUTION'
  limit 1;
$$;

revoke all on function public.resolve_institution_by_username(text) from public;
revoke all on function public.resolve_institution_by_username(text) from anon;
grant execute on function public.resolve_institution_by_username(text) to authenticated;

-- ============================================================
-- Display-name resolution (institution-side incoming list): same wall
-- and same fix as application_applicant_names (036) /
-- collaboration_counterparty_names (029) -- profiles' own SELECT policy
-- is ownership-only, so an Institution's user-scoped client cannot join
-- to a requesting student's profiles.full_name directly. Re-derives the
-- exact same authorization the table's own SELECT policy grants
-- (institution_id = auth.uid()), so this can never name a student for a
-- request the caller could not already see through the API. Exposes
-- full_name + username only -- no email, phone, or any other column.
-- ============================================================

create or replace function public.institution_link_request_student_names(request_ids uuid[])
returns table (request_id uuid, student_name text, student_username text)
language sql
security definer
set search_path = ''
stable
as $$
  select r.id, p.full_name, p.username
  from public.institution_link_requests r
  join public.profiles p on p.id = r.student_id
  where r.id = any(request_ids)
    and r.institution_id = auth.uid()
    and public.is_institution(auth.uid());
$$;

revoke all on function public.institution_link_request_student_names(uuid[]) from public;
revoke all on function public.institution_link_request_student_names(uuid[]) from anon;
grant execute on function public.institution_link_request_student_names(uuid[]) to authenticated;

-- ============================================================
-- Triggers
-- ============================================================

-- Validates (does not derive -- there is nowhere else to derive it from,
-- unlike set_application_industry_id/set_collaboration_recipient_type)
-- that institution_id is a real INSTITUTION account. student_id needs no
-- equivalent check here: the INSERT policy below already requires
-- auth.uid() = student_id AND is_student(auth.uid()), which is strictly
-- stronger than validating an arbitrary column value after the fact.
create or replace function public.validate_link_request_institution()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.is_institution(new.institution_id) then
    raise exception 'institution_id must reference an INSTITUTION account.' using errcode = '23514';
  end if;

  return new;
end;
$$;

revoke all on function public.validate_link_request_institution() from public;

drop trigger if exists institution_link_requests_validate_institution on institution_link_requests;
create trigger institution_link_requests_validate_institution
  before insert on institution_link_requests
  for each row
  execute procedure public.validate_link_request_institution();

-- Blocks changes to WHICH request this is -- student_id, institution_id
-- -- after creation, for every ordinary RLS-governed caller. Same
-- OLD-vs-NEW / service_role-steps-aside pattern as
-- prevent_collaboration_identity_change (026).
create or replace function public.prevent_link_request_identity_change()
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
    or new.institution_id is distinct from old.institution_id
  then
    raise exception 'Cannot change the student or institution of an existing link request.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_link_request_identity_change() from public;

drop trigger if exists institution_link_requests_prevent_identity_change on institution_link_requests;
create trigger institution_link_requests_prevent_identity_change
  before update on institution_link_requests
  for each row
  execute procedure public.prevent_link_request_identity_change();

-- Postgres RLS has no native column/value-transition restriction -- this
-- is the authoritative backstop (same role as
-- restrict_recipient_collaboration_updates, 026) limiting each party to
-- exactly the transitions the lifecycle allows, regardless of what the
-- UPDATE policies' USING clauses would otherwise structurally permit.
create or replace function public.restrict_link_request_transitions()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.status is distinct from old.status then
    if auth.uid() = old.student_id then
      if not (old.status = 'PENDING' and new.status = 'CANCELLED') then
        raise exception 'A student may only cancel their own pending request.' using errcode = '42501';
      end if;
    elsif auth.uid() = old.institution_id then
      if not (
        (old.status = 'PENDING' and new.status in ('APPROVED', 'REJECTED'))
        or (old.status = 'APPROVED' and new.status = 'REMOVED')
      ) then
        raise exception 'Invalid status transition for an institution.' using errcode = '42501';
      end if;
    else
      raise exception 'Not authorized to change this request.' using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.restrict_link_request_transitions() from public;

drop trigger if exists institution_link_requests_restrict_transitions on institution_link_requests;
create trigger institution_link_requests_restrict_transitions
  before update on institution_link_requests
  for each row
  execute procedure public.restrict_link_request_transitions();

-- THE cross-table write: applies an approval/unlink decision to
-- student_profiles.institution_id. SECURITY DEFINER so it can write a
-- row the caller (the institution) has no direct UPDATE access to at
-- all -- but the ONLY way to reach this code is by successfully updating
-- an institution_link_requests row the caller owns as the institution
-- party, which restrict_link_request_transitions above has already
-- confirmed is a legal APPROVED or REMOVED transition. This is not a
-- service_role bypass: it is the same "narrowly-scoped SECURITY DEFINER
-- write, gated entirely by an already-RLS-checked update on this table"
-- pattern used throughout this schema (e.g. set_application_industry_id
-- deriving a value across the internships/jobs boundary at insert time)
-- extended to an UPDATE-time, cross-table effect.
create or replace function public.apply_link_request_status_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.status = 'APPROVED' and old.status is distinct from 'APPROVED' then
    update public.student_profiles
       set institution_id = new.institution_id
     where id = new.student_id;
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

drop trigger if exists institution_link_requests_apply_status_change on institution_link_requests;
create trigger institution_link_requests_apply_status_change
  after update on institution_link_requests
  for each row
  execute procedure public.apply_link_request_status_change();

drop trigger if exists institution_link_requests_set_updated_at on institution_link_requests;
create trigger institution_link_requests_set_updated_at
  before update on institution_link_requests
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies
-- ============================================================

-- ---- Student (initiator) ----

drop policy if exists "Students can view their own link requests" on institution_link_requests;
create policy "Students can view their own link requests"
  on institution_link_requests for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can request to join an institution" on institution_link_requests;
create policy "Students can request to join an institution"
  on institution_link_requests for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()) and status = 'PENDING');

drop policy if exists "Students can cancel their own pending request" on institution_link_requests;
create policy "Students can cancel their own pending request"
  on institution_link_requests for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

-- ---- Institution (approver) ----

drop policy if exists "Institution can view requests addressed to it" on institution_link_requests;
create policy "Institution can view requests addressed to it"
  on institution_link_requests for select
  to authenticated
  using (auth.uid() = institution_id and public.is_institution(auth.uid()));

drop policy if exists "Institution can respond to requests addressed to it" on institution_link_requests;
create policy "Institution can respond to requests addressed to it"
  on institution_link_requests for update
  to authenticated
  using (auth.uid() = institution_id and public.is_institution(auth.uid()))
  with check (auth.uid() = institution_id and public.is_institution(auth.uid()));

-- No delete policy for either party -- link history (who requested,
-- who approved/rejected/removed, and when) is kept, matching every
-- other bilateral-relationship table in this schema.
