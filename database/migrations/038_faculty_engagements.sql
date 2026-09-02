-- Migration: 038_faculty_engagements
-- Purpose: Phase F4.1 -- the approved minimal successor to F3.4's
-- deliberately-terminal EOI ACCEPTED state. Introduces the relationship
-- created once an Industry or Institution accepts a Faculty expression of
-- interest: `faculty_engagements`. This is NOT an EOI, NOT an opportunity,
-- NOT industry_collaborations, and NOT a mentorship relationship -- those
-- remain fully distinct concepts (industry_collaborations especially:
-- untouched by this migration, no FK added from it, no lifecycle change).
--
-- ============================================================
-- SCHEMA CHOICE: ONE TABLE WITH A DISCRIMINATOR, NOT TWO ENGAGEMENT
-- TABLES, NOT A SHARED REGISTRY (Option A, chosen over B and C)
-- ============================================================
-- F3.4 chose two separate EOI tables (Option B, in that phase's own
-- terms) specifically because EOI rows are read AND written by TWO
-- different actors with different, non-trivial permitted-transition
-- rules each (Faculty submits/withdraws; the owning Industry/Institution
-- reviews/decides) -- splitting the table let each side's RLS/trigger
-- logic stay simple per table.
--
-- faculty_engagements has a fundamentally simpler write shape: Faculty is
-- read-only here (view own engagements; F4.1 does not grant Faculty any
-- lifecycle-mutating action, per the approved scope), and only ONE actor
-- (the owning organization) ever transitions status. There is no
-- two-party write dance to simplify by splitting the table. Given that,
-- splitting into faculty_industry_engagements / faculty_institution_
-- engagements would only add migration/RLS duplication for no
-- corresponding safety or clarity benefit, AND would force a
-- service-layer UNION for the one query Faculty actually needs most --
-- "show me all my engagements" -- that a single table answers directly
-- with one plain SELECT. That query-simplicity gain, plus materially
-- less migration code, is why Option A wins here even though F3.4 chose
-- differently for a structurally different write pattern.
--
-- This is explicitly NOT the rejected polymorphic source_type/source_id
-- pattern: `industry_eoi_id` and `institution_eoi_id` are each a real,
-- independently-enforced foreign key to a fixed, specific table -- not a
-- single ambiguous id column whose target table is decided by a string.
-- Postgres enforces both constraints unconditionally; the CHECK below
-- only additionally enforces that exactly one of the two is populated,
-- consistent with `source_kind`. This "exclusive arc" shape is a
-- standard, safe relational pattern -- not the anti-pattern being
-- avoided.
--
-- Option C (a shared Faculty Opportunity/EOI parent/registry that a
-- single Engagement FK could point at) was rejected again here for the
-- same reason F3.4 rejected it for EOI: it would introduce a new table
-- purely for theoretical normalization, solving a discovery-unification
-- problem this project already solves at the service layer (see
-- faculty_opportunity_service.py's / faculty_opportunity_expression_
-- service.py's existing Python-side union pattern).
--
-- `organization_id` is a plain FK to profiles(id) -- the exact same shape
-- industry_id/institution_id/faculty_id already use everywhere else in
-- this schema, NOT a polymorphic organization_type+organization_id pair.
-- It is never client-writable: faculty_engagements has NO user-facing
-- INSERT policy at all (mirroring 027_faculty_assessment_permissions.sql's
-- own "no user-facing write policy, RPC-only" precedent) -- the two
-- accept_* RPCs below are the exclusive creation path, and they derive
-- organization_id from the real opportunity-ownership row, never from a
-- request parameter. The CHECK constraint below independently guarantees
-- organization_id's role is at least self-consistent with source_kind
-- and the populated EOI reference; it does not (and, being a plain CHECK
-- with no subquery capability, cannot) re-verify organization_id against
-- the EOI's actual opportunity owner -- that guarantee comes entirely
-- from the RPCs' own correct server-side derivation, the same trust
-- model this project already applies to every other privileged RPC
-- (e.g. admin_grant_assessment_capability's granted_by).

create table if not exists faculty_engagements (
  id uuid primary key default gen_random_uuid(),

  source_kind text not null check (source_kind in ('INDUSTRY_EOI', 'INSTITUTION_EOI')),

  -- restrict, not cascade: an engagement is a historical record: its
  -- source EOI must never be deletable while an engagement references
  -- it. Exactly one of the two is populated, enforced by the CHECK below.
  industry_eoi_id uuid references faculty_industry_opportunity_expressions (id) on delete restrict,
  institution_eoi_id uuid references faculty_institution_opportunity_expressions (id) on delete restrict,

  -- Participant identity, derived and persisted once at creation by the
  -- accept_* RPCs below -- never updated afterward (enforced by the
  -- guard trigger further down), so the engagement's historical origin
  -- can never silently change even if the source opportunity is edited
  -- or closed later.
  faculty_id uuid not null references profiles (id) on delete cascade,
  organization_id uuid not null references profiles (id) on delete cascade,

  status text not null default 'PLANNED' check (status in ('PLANNED', 'ACTIVE', 'COMPLETED', 'CANCELLED')),

  start_date date,
  end_date date,
  notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint faculty_engagements_dates_check check (
    start_date is null or end_date is null or end_date >= start_date
  ),

  -- The exclusive-arc guarantee: source_kind and exactly one populated
  -- EOI reference must always agree.
  constraint faculty_engagements_source_kind_matches_eoi check (
    (source_kind = 'INDUSTRY_EOI' and industry_eoi_id is not null and institution_eoi_id is null)
    or
    (source_kind = 'INSTITUTION_EOI' and institution_eoi_id is not null and industry_eoi_id is null)
  ),

  -- THE idempotency guarantee (not an application-layer "if not exists"):
  -- Postgres treats each NULL as distinct for uniqueness purposes, so
  -- this allows unlimited rows with a NULL industry_eoi_id (i.e. every
  -- institution-sourced engagement) while still guaranteeing at most one
  -- engagement per actual industry EOI. Same reasoning mirrored for
  -- institution_eoi_id below.
  constraint faculty_engagements_unique_industry_eoi unique (industry_eoi_id),
  constraint faculty_engagements_unique_institution_eoi unique (institution_eoi_id)
);

create index if not exists faculty_engagements_faculty_id_idx on faculty_engagements (faculty_id);
create index if not exists faculty_engagements_organization_id_idx on faculty_engagements (organization_id);
create index if not exists faculty_engagements_status_idx on faculty_engagements (status);

alter table faculty_engagements enable row level security;

-- Faculty: view-only. F4.1's approved scope grants Faculty no
-- lifecycle-mutating action on an engagement -- "do not automatically
-- allow Faculty to activate/complete/cancel" -- so there is no Faculty
-- UPDATE policy at all, only SELECT.
create policy "Faculty can view their own engagements"
  on faculty_engagements for select
  to authenticated
  using (auth.uid() = faculty_id and public.is_faculty(auth.uid()));

-- Organization (Industry or Institution): view + lifecycle-transition
-- write, scoped to their own engagements only. organization_id is
-- compared directly to auth.uid() -- no join back to the source
-- opportunity table is needed for this check, since organization_id was
-- already derived from that exact ownership relationship at creation.
create policy "Organization can view their own engagements"
  on faculty_engagements for select
  to authenticated
  using (
    auth.uid() = organization_id
    and (
      (source_kind = 'INDUSTRY_EOI' and public.is_industry(auth.uid()))
      or (source_kind = 'INSTITUTION_EOI' and public.is_institution(auth.uid()))
    )
  );

create policy "Organization can update their own engagements"
  on faculty_engagements for update
  to authenticated
  using (
    auth.uid() = organization_id
    and (
      (source_kind = 'INDUSTRY_EOI' and public.is_industry(auth.uid()))
      or (source_kind = 'INSTITUTION_EOI' and public.is_institution(auth.uid()))
    )
  )
  with check (
    auth.uid() = organization_id
    and (
      (source_kind = 'INDUSTRY_EOI' and public.is_industry(auth.uid()))
      or (source_kind = 'INSTITUTION_EOI' and public.is_institution(auth.uid()))
    )
  );

-- No INSERT policy for any authenticated role, and no DELETE policy at
-- all -- creation is exclusively through the two SECURITY DEFINER RPCs
-- below (which run with the elevated privilege every other privileged
-- RPC in this project already relies on), and an engagement, once
-- created, is a historical record that is never deleted, only
-- transitioned to CANCELLED.

-- Precise transition control, same division of labor as every other
-- guarded table in this project: RLS (above) decides WHO may attempt to
-- touch a row; this trigger decides WHICH mutation is actually legal.
-- Simpler than the EOI guard triggers because there is only one writing
-- actor (the organization) -- no per-caller branching needed.
create or replace function public.guard_faculty_engagement_update()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.faculty_id is distinct from old.faculty_id
    or new.organization_id is distinct from old.organization_id
    or new.source_kind is distinct from old.source_kind
    or new.industry_eoi_id is distinct from old.industry_eoi_id
    or new.institution_eoi_id is distinct from old.institution_eoi_id
  then
    raise exception 'Cannot change an engagement''s participants or source.' using errcode = '42501';
  end if;

  if new.status is distinct from old.status
    and not (old.status = 'PLANNED' and new.status in ('ACTIVE', 'CANCELLED'))
    and not (old.status = 'ACTIVE' and new.status in ('COMPLETED', 'CANCELLED'))
  then
    raise exception 'Invalid engagement status transition: % -> %', old.status, new.status
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.guard_faculty_engagement_update() from public;

drop trigger if exists faculty_engagements_guard_update on faculty_engagements;
create trigger faculty_engagements_guard_update
  before update on faculty_engagements
  for each row
  execute procedure public.guard_faculty_engagement_update();

drop trigger if exists faculty_engagements_set_updated_at on faculty_engagements;
create trigger faculty_engagements_set_updated_at
  before update on faculty_engagements
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- accept_faculty_industry_expression(): the one atomic acceptance
-- operation for an Industry-sourced EOI.
-- ============================================================
-- Performs, in one transaction: ownership verification, the EOI's
-- UNDER_REVIEW -> ACCEPTED transition (via the existing table's own
-- guard_faculty_industry_eoi_update() trigger, which still fires for
-- this internal UPDATE and independently permits exactly this
-- transition when the acting auth.uid() is the opportunity's real
-- owner -- verified true here before this UPDATE ever runs), and the
-- Engagement's creation. Nothing here trusts a client-supplied
-- faculty_id, organization_id, or status; every value is derived from
-- the EOI/opportunity rows themselves.
create or replace function public.accept_faculty_industry_expression(target_eoi_id uuid)
returns faculty_engagements
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  v_eoi public.faculty_industry_opportunity_expressions;
  v_opportunity public.industry_faculty_opportunities;
  v_engagement public.faculty_engagements;
begin
  if caller_id is null then
    raise exception 'Authentication required.' using errcode = '28000';
  end if;

  if not public.is_industry(caller_id) then
    raise exception 'Only INDUSTRY accounts may accept an expression of interest.' using errcode = '42501';
  end if;

  select * into v_eoi from public.faculty_industry_opportunity_expressions where id = target_eoi_id;
  if v_eoi.id is null then
    raise exception 'Expression of interest not found.' using errcode = 'P0002';
  end if;

  select * into v_opportunity
  from public.industry_faculty_opportunities
  where id = v_eoi.opportunity_id;

  if v_opportunity.industry_id is distinct from caller_id then
    raise exception 'Not authorized to accept this expression of interest.' using errcode = '42501';
  end if;

  if v_eoi.status is distinct from 'UNDER_REVIEW' then
    raise exception 'Expression of interest must be UNDER_REVIEW before it can be accepted.'
      using errcode = '55000';
  end if;

  update public.faculty_industry_opportunity_expressions
  set status = 'ACCEPTED'
  where id = target_eoi_id;

  insert into public.faculty_engagements (
    source_kind, industry_eoi_id, faculty_id, organization_id, status
  ) values (
    'INDUSTRY_EOI', target_eoi_id, v_eoi.faculty_id, v_opportunity.industry_id, 'PLANNED'
  )
  returning * into v_engagement;

  return v_engagement;
end;
$$;

revoke all on function public.accept_faculty_industry_expression(uuid) from public;
revoke all on function public.accept_faculty_industry_expression(uuid) from anon;
grant execute on function public.accept_faculty_industry_expression(uuid) to authenticated;

-- ============================================================
-- accept_faculty_institution_expression(): structural twin, Institution side.
-- ============================================================
create or replace function public.accept_faculty_institution_expression(target_eoi_id uuid)
returns faculty_engagements
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  v_eoi public.faculty_institution_opportunity_expressions;
  v_opportunity public.institution_faculty_opportunities;
  v_engagement public.faculty_engagements;
begin
  if caller_id is null then
    raise exception 'Authentication required.' using errcode = '28000';
  end if;

  if not public.is_institution(caller_id) then
    raise exception 'Only INSTITUTION accounts may accept an expression of interest.' using errcode = '42501';
  end if;

  select * into v_eoi from public.faculty_institution_opportunity_expressions where id = target_eoi_id;
  if v_eoi.id is null then
    raise exception 'Expression of interest not found.' using errcode = 'P0002';
  end if;

  select * into v_opportunity
  from public.institution_faculty_opportunities
  where id = v_eoi.opportunity_id;

  if v_opportunity.institution_id is distinct from caller_id then
    raise exception 'Not authorized to accept this expression of interest.' using errcode = '42501';
  end if;

  if v_eoi.status is distinct from 'UNDER_REVIEW' then
    raise exception 'Expression of interest must be UNDER_REVIEW before it can be accepted.'
      using errcode = '55000';
  end if;

  update public.faculty_institution_opportunity_expressions
  set status = 'ACCEPTED'
  where id = target_eoi_id;

  insert into public.faculty_engagements (
    source_kind, institution_eoi_id, faculty_id, organization_id, status
  ) values (
    'INSTITUTION_EOI', target_eoi_id, v_eoi.faculty_id, v_opportunity.institution_id, 'PLANNED'
  )
  returning * into v_engagement;

  return v_engagement;
end;
$$;

revoke all on function public.accept_faculty_institution_expression(uuid) from public;
revoke all on function public.accept_faculty_institution_expression(uuid) from anon;
grant execute on function public.accept_faculty_institution_expression(uuid) to authenticated;

-- ============================================================
-- NOT DONE HERE (explicitly deferred, per the approved F4.1 scope)
-- ============================================================
-- Faculty->Student mentorship, Faculty<->Faculty mentorship, a
-- Mentorship-as-Engagement-type column, industry_collaborations
-- integration, calendar/messaging/notifications, any Admin/Student
-- access to faculty_engagements. See the F4 architecture audit for the
-- reasoning behind each.
