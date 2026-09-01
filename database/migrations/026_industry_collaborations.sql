-- Migration: 026_industry_collaborations
-- Purpose: Phase 10E -- an actual academia-industry collaboration
-- proposal/relationship system between an INDUSTRY account (initiator)
-- and a FACULTY or INSTITUTION account (recipient). Unlike
-- industry_projects/industry_training/industry_workshops/industry_mentorship
-- (022-025), this is NOT a posting entity: it is a bilateral relationship
-- with an approval workflow, modeled after the two-party read/write shape
-- of applications (020_applications.sql), which is used here only as a
-- conceptual RLS precedent -- this migration does not touch or extend
-- that table in any way.
--
-- Named `industry_collaborations` (not `collaboration`/`collaborations`)
-- to avoid colliding with the still-unimplemented, ambiguous generic
-- stubs (backend/app/api/collaborations.py,
-- backend/app/schemas/collaboration.py) and with
-- 009_collaboration.sql's own broader, unimplemented "academia-industry
-- collaboration" scope (mentorship pairings/workshops/research/
-- consultancy) -- both of which are left completely untouched. Two of
-- 009's originally-named concepts ("mentorship pairings", "workshops")
-- were already independently built as pure Industry->Student postings in
-- 023/024 -- this migration does not revisit that.
--
-- Lifecycle (approved product decision, distinct from every posting
-- module's DRAFT/PUBLISHED/CLOSED/ARCHIVED):
--   DRAFT -> SENT -> ACCEPTED/REJECTED -> ACTIVE -> COMPLETED/CANCELLED
-- ACCEPTED means "the recipient has agreed"; ACTIVE means "the industry
-- has formally started the collaboration" -- a distinct, explicit,
-- industry-only transition, not automatic.
--
-- Same ownership reasoning as every other Industry module: industry_id
-- references profiles(id), not industry_profiles(id). recipient_id also
-- references profiles(id) directly -- there is no faculty_profiles or
-- institution_profiles table in this repository, and none is created
-- here.

create table if not exists industry_collaborations (
  id uuid primary key default gen_random_uuid(),
  industry_id uuid not null references profiles (id) on delete cascade,
  -- Populated and validated server-side by the
  -- set_collaboration_recipient_type trigger below -- a client-supplied
  -- value is never trusted, and identity is immutable after insert (see
  -- prevent_collaboration_identity_change).
  recipient_id uuid not null references profiles (id) on delete cascade,
  recipient_type text not null check (recipient_type in ('FACULTY', 'INSTITUTION')),

  title text not null,
  description text not null,

  status text not null default 'DRAFT' check (
    status in ('DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'ACTIVE', 'COMPLETED', 'CANCELLED')
  ),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists industry_collaborations_industry_id_idx on industry_collaborations (industry_id);
create index if not exists industry_collaborations_recipient_id_idx on industry_collaborations (recipient_id);
-- Partial index for the recipient's "incoming" query, which always
-- excludes DRAFT rows -- same pattern as the *_published_idx indexes on
-- the posting modules (018-025), narrowed to the exact query this table
-- actually serves.
create index if not exists industry_collaborations_incoming_idx on industry_collaborations (recipient_id) where status <> 'DRAFT';

alter table industry_collaborations enable row level security;

-- ============================================================
-- Role-check helpers
-- ============================================================
-- Neither is_faculty nor is_institution existed before this migration
-- (only is_student/012+013 and is_industry/017 do). Both are genuinely
-- required here, not added merely for symmetry:
--   1. Every existing owner-policy in this schema pairs an ownership
--      match with a role-check (is_student/is_industry) -- omitting one
--      for the recipient side would be the first inconsistency in that
--      pattern.
--   2. set_collaboration_recipient_type (below) must authoritatively
--      read an arbitrary OTHER user's role to validate/derive
--      recipient_type -- the base profiles table's own RLS
--      ("Users can view their own profile", auth.uid() = id) does not
--      allow that from a normal user-scoped query, exactly the same
--      problem is_student/is_industry solve for their own callers.
-- Hardened from creation exactly like is_industry (017): EXECUTE granted
-- to `authenticated` only, explicitly revoked from `public` and `anon`
-- up front -- no is_student-style follow-up hardening migration needed.

create or replace function public.is_faculty(profile_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.profiles where id = profile_id and role = 'FACULTY'
  );
$$;

revoke all on function public.is_faculty(uuid) from public;
revoke all on function public.is_faculty(uuid) from anon;
grant execute on function public.is_faculty(uuid) to authenticated;

create or replace function public.is_institution(profile_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.profiles where id = profile_id and role = 'INSTITUTION'
  );
$$;

revoke all on function public.is_institution(uuid) from public;
revoke all on function public.is_institution(uuid) from anon;
grant execute on function public.is_institution(uuid) to authenticated;

-- ============================================================
-- Recipient resolution (for the Industry-side create form)
-- ============================================================
-- Resolves a username to the minimum data needed to target a
-- collaboration recipient -- id, role, full_name only. Deliberately
-- excludes email/phone/any other profile column. Only ever returns a
-- row when the matched account's role is FACULTY or INSTITUTION -- a
-- STUDENT/INDUSTRY/ADMIN username resolves to no rows, indistinguishable
-- from a username that doesn't exist at all (no account-existence or
-- role leak). SECURITY DEFINER for the same reason as
-- get_email_for_identifier (001_profiles.sql): the base profiles SELECT
-- policy would otherwise block this lookup entirely. Granted to
-- `authenticated` only (unlike get_email_for_identifier, this has no
-- pre-login use case, so `anon` is not granted).
create or replace function public.resolve_collaboration_recipient(identifier text)
returns table (id uuid, role text, full_name text)
language sql
security definer
set search_path = ''
stable
as $$
  select p.id, p.role, p.full_name
  from public.profiles p
  where lower(p.username) = lower(identifier)
    and p.role in ('FACULTY', 'INSTITUTION')
  limit 1;
$$;

revoke all on function public.resolve_collaboration_recipient(text) from public;
revoke all on function public.resolve_collaboration_recipient(text) from anon;
grant execute on function public.resolve_collaboration_recipient(text) to authenticated;

-- ============================================================
-- Triggers
-- ============================================================

-- Derives (and OVERWRITES) recipient_type from the referenced profile's
-- real role at insert time -- any client-supplied value is ignored.
-- Rejects any recipient whose role is not FACULTY/INSTITUTION. Same
-- "resolve authoritative value server-side" pattern as
-- set_application_industry_id (020_applications.sql).
create or replace function public.set_collaboration_recipient_type()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  resolved_role text;
begin
  select role into resolved_role from public.profiles where id = new.recipient_id;

  if resolved_role is null then
    raise exception 'Recipient profile does not exist.' using errcode = '23503';
  end if;

  if resolved_role not in ('FACULTY', 'INSTITUTION') then
    raise exception 'Collaboration recipient must be a FACULTY or INSTITUTION account.' using errcode = '42501';
  end if;

  new.recipient_type := resolved_role;
  return new;
end;
$$;

revoke all on function public.set_collaboration_recipient_type() from public;

drop trigger if exists industry_collaborations_set_recipient_type on industry_collaborations;
create trigger industry_collaborations_set_recipient_type
  before insert on industry_collaborations
  for each row
  execute procedure public.set_collaboration_recipient_type();

-- Blocks changes to the columns that define WHICH collaboration this is
-- -- industry_id, recipient_id, recipient_type -- after creation, for
-- every ordinary RLS-governed caller (industry or recipient alike). Same
-- OLD vs NEW / service_role-steps-aside pattern as
-- prevent_application_identity_change (020_applications.sql).
create or replace function public.prevent_collaboration_identity_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.industry_id is distinct from old.industry_id
    or new.recipient_id is distinct from old.recipient_id
    or new.recipient_type is distinct from old.recipient_type
  then
    raise exception 'Cannot change the industry, recipient, or recipient type of an existing collaboration.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_collaboration_identity_change() from public;

drop trigger if exists industry_collaborations_prevent_identity_change on industry_collaborations;
create trigger industry_collaborations_prevent_identity_change
  before update on industry_collaborations
  for each row
  execute procedure public.prevent_collaboration_identity_change();

-- Restricts a RECIPIENT caller to exactly one kind of change: moving
-- status from SENT to ACCEPTED or REJECTED, nothing else. Postgres RLS
-- has no native column-level restriction, so -- same reasoning as
-- prevent_student_status_override (020_applications.sql) -- this trigger
-- is what actually enforces "the recipient cannot touch proposal
-- content, only respond to it", on top of the identity-change guard
-- above (which already blocks industry_id/recipient_id/recipient_type
-- for the recipient too).
create or replace function public.restrict_recipient_collaboration_updates()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if auth.uid() = old.recipient_id then
    if new.title is distinct from old.title
      or new.description is distinct from old.description
      or new.created_at is distinct from old.created_at
    then
      raise exception 'Recipients may only change the status of a collaboration, nothing else.' using errcode = '42501';
    end if;

    if new.status is distinct from old.status
      and not (old.status = 'SENT' and new.status in ('ACCEPTED', 'REJECTED'))
    then
      raise exception 'Recipients may only accept or reject a sent proposal.' using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.restrict_recipient_collaboration_updates() from public;

drop trigger if exists industry_collaborations_restrict_recipient_updates on industry_collaborations;
create trigger industry_collaborations_restrict_recipient_updates
  before update on industry_collaborations
  for each row
  execute procedure public.restrict_recipient_collaboration_updates();

drop trigger if exists industry_collaborations_set_updated_at on industry_collaborations;
create trigger industry_collaborations_set_updated_at
  before update on industry_collaborations
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies
-- ============================================================

-- ---- Industry policies ----

drop policy if exists "Industry can manage their own collaborations" on industry_collaborations;
create policy "Industry can manage their own collaborations"
  on industry_collaborations for all
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- ---- Recipient policies ----

-- DRAFT rows are excluded -- a proposal not yet sent has not been
-- "addressed to" its recipient in any meaningful sense yet.
drop policy if exists "Recipients can view collaborations addressed to them" on industry_collaborations;
create policy "Recipients can view collaborations addressed to them"
  on industry_collaborations for select
  to authenticated
  using (
    auth.uid() = recipient_id
    and status <> 'DRAFT'
    and (
      (recipient_type = 'FACULTY' and public.is_faculty(auth.uid()))
      or (recipient_type = 'INSTITUTION' and public.is_institution(auth.uid()))
    )
  );

-- The USING/WITH CHECK here only scopes WHICH rows a recipient may
-- attempt to update -- restrict_recipient_collaboration_updates (above)
-- is what actually limits WHAT they may change within that row.
drop policy if exists "Recipients can respond to their own sent proposals" on industry_collaborations;
create policy "Recipients can respond to their own sent proposals"
  on industry_collaborations for update
  to authenticated
  using (
    auth.uid() = recipient_id
    and status <> 'DRAFT'
    and (
      (recipient_type = 'FACULTY' and public.is_faculty(auth.uid()))
      or (recipient_type = 'INSTITUTION' and public.is_institution(auth.uid()))
    )
  )
  with check (
    auth.uid() = recipient_id
    and (
      (recipient_type = 'FACULTY' and public.is_faculty(auth.uid()))
      or (recipient_type = 'INSTITUTION' and public.is_institution(auth.uid()))
    )
  );

-- No delete policy for either party -- collaborations are historical
-- records; cancellation is a status (CANCELLED), never a row deletion.
