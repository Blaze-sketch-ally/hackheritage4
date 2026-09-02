-- Migration: 037_faculty_opportunities_and_expressions
-- Purpose: Phase F3.4 -- the corrected Faculty opportunity architecture
-- from the approved design checkpoint. Introduces the missing two lanes
-- of the four-quadrant opportunity model (Industry->Faculty,
-- Institution->Faculty) plus the Faculty EOI layer, while leaving the
-- Student lanes (024_opportunities_and_applications.sql) and the four
-- existing Industry->Student posting tables (028-031) completely
-- untouched -- this migration adds new tables only, and does not ALTER
-- any of them.
--
-- ============================================================
-- WHY TWO NEW POSTING TABLES, NOT A REUSE OF 028-031
-- ============================================================
-- 028_industry_projects.sql / 029_industry_training.sql /
-- 030_industry_workshops.sql / 031_industry_mentorship.sql each say, in
-- their own header, that they are postings "offered to students". Their
-- RLS technically has no role check on the read side ("Authenticated
-- users can view published X" -- any role, confirmed by direct
-- inspection), but the documented PRODUCT meaning of every row in those
-- four tables is Student-facing. Attaching a Faculty
-- expression-of-interest concept to them would silently redefine what
-- those tables mean to the Industry accounts that already post to them,
-- without changing a single existing column -- exactly the kind of
-- silent semantic drift the architecture review this migration
-- implements was commissioned to prevent. `industry_faculty_opportunities`
-- is therefore a genuinely new, fifth Industry posting table, scoped to
-- Faculty from its own first line -- not a repurposing of anything that
-- exists. `institution_faculty_opportunities` is its Institution-owned
-- twin -- Institution has never been a content-owner anywhere in this
-- schema before now (it only ever appears as industry_collaborations'
-- recipient_type), so this is Institution's first posting entity,
-- deliberately given the same shape as the Industry one rather than
-- inventing a different shape for no reason evidenced by the repository.
--
-- ============================================================
-- WHY TWO EOI TABLES, NOT A POLYMORPHIC FK OR A SHARED REGISTRY
-- ============================================================
-- A single faculty_opportunity_expressions table referencing "whichever
-- opportunity table opportunity_type names" would be a polymorphic
-- source_type/source_id pair -- Postgres cannot enforce a real foreign
-- key against a column-selected table, only application logic or a
-- trigger re-checking existence on every write, which is strictly weaker
-- than a real FK (no cascade, no index-backed constraint, silently rots
-- if a row is ever removed by a path the trigger doesn't anticipate).
-- A shared `faculty_opportunities` base/registry table with Industry/
-- Institution subtype tables underneath it was also considered and
-- rejected for this phase: the only reason such a registry would earn
-- its keep is unifying Faculty *discovery* across both source tables in
-- one SQL-level read, and that problem is already solved, without a new
-- table, by 038's own service-layer union pattern (see
-- app/services/faculty_opportunity_service.py's existing precedent from
-- Phase F3.2, which already unions four different posting tables into
-- one API response purely in Python). Building a registry table now
-- would duplicate a solved problem for a payoff nothing currently needs,
-- at the cost of an extra table that must be kept in sync with its
-- sources. Two small typed EOI tables, each with one plain NOT NULL FK
-- to its own opportunity table, is the simplest design that is fully
-- relationally enforced -- exactly this project's own stated preference
-- (see opportunity_skill_requirements.opportunity_id -> opportunities(id)
-- for the precedent this mirrors).
--
-- is_industry()/is_faculty()/is_institution() are reused unchanged from
-- 024/015/032 respectively -- none is redefined here.

-- ============================================================
-- industry_faculty_opportunities
-- ============================================================
-- An opportunity created by an INDUSTRY account specifically for Faculty
-- participation. Same shape and conventions as industry_projects/
-- industry_training/industry_workshops (028-030): owner-managed lifecycle,
-- broad "authenticated can view published" read policy. Deliberately NOT
-- given a duration_months/duration_days column like those four tables --
-- the approved design's minimum field list omits it, and it can be added
-- additively later if a real need appears. No transition-lock trigger
-- (unlike 024_opportunities_and_applications.sql's opportunities table):
-- 028-031 establish that a plain status CHECK constraint, without a
-- transition trigger, is this project's own precedent for an
-- Industry-owned posting table; this table follows that lighter
-- precedent, not the heavier one.

create table if not exists industry_faculty_opportunities (
  id uuid primary key default gen_random_uuid(),
  industry_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text not null,
  location text,
  work_mode text check (work_mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  capacity int check (capacity > 0),
  eligibility_criteria text,
  application_deadline date,
  start_date date,
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'CLOSED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists industry_faculty_opportunities_industry_id_idx
  on industry_faculty_opportunities (industry_id);
create index if not exists industry_faculty_opportunities_status_idx
  on industry_faculty_opportunities (status);

alter table industry_faculty_opportunities enable row level security;

-- Split into SELECT/INSERT/UPDATE from the start (no DELETE policy at
-- all) -- 033_forbid_industry_record_deletes.sql already had to correct
-- a `for all` owner policy on 028-031 into exactly this split after
-- discovering it silently permitted owner self-DELETE; this table starts
-- with the corrected shape directly rather than repeating that mistake.
create policy "Industry can view their own faculty opportunities"
  on industry_faculty_opportunities for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

create policy "Industry can insert their own faculty opportunities"
  on industry_faculty_opportunities for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

create policy "Industry can update their own faculty opportunities"
  on industry_faculty_opportunities for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

create policy "Authenticated users can view published industry faculty opportunities"
  on industry_faculty_opportunities for select
  to authenticated
  using (status = 'PUBLISHED');

drop trigger if exists industry_faculty_opportunities_set_updated_at on industry_faculty_opportunities;
create trigger industry_faculty_opportunities_set_updated_at
  before update on industry_faculty_opportunities
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- institution_faculty_opportunities
-- ============================================================
-- Institution's own twin of the table above. Institution has no separate
-- identity table anywhere in this repository (confirmed:
-- 032_industry_collaborations.sql's own header states "[no]
-- institution_profiles table in this repository, and none is created
-- [there]" -- an INSTITUTION account is just a `profiles` row with
-- role='INSTITUTION') -- so institution_id references profiles(id)
-- directly, exactly the same shape industry_id already uses, and exactly
-- how industry_collaborations.recipient_id already treats an INSTITUTION
-- recipient. No new Institution identity concept is introduced.

create table if not exists institution_faculty_opportunities (
  id uuid primary key default gen_random_uuid(),
  institution_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text not null,
  location text,
  work_mode text check (work_mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  capacity int check (capacity > 0),
  eligibility_criteria text,
  application_deadline date,
  start_date date,
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'CLOSED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists institution_faculty_opportunities_institution_id_idx
  on institution_faculty_opportunities (institution_id);
create index if not exists institution_faculty_opportunities_status_idx
  on institution_faculty_opportunities (status);

alter table institution_faculty_opportunities enable row level security;

create policy "Institution can view their own faculty opportunities"
  on institution_faculty_opportunities for select
  to authenticated
  using (auth.uid() = institution_id and public.is_institution(auth.uid()));

create policy "Institution can insert their own faculty opportunities"
  on institution_faculty_opportunities for insert
  to authenticated
  with check (auth.uid() = institution_id and public.is_institution(auth.uid()));

create policy "Institution can update their own faculty opportunities"
  on institution_faculty_opportunities for update
  to authenticated
  using (auth.uid() = institution_id and public.is_institution(auth.uid()))
  with check (auth.uid() = institution_id and public.is_institution(auth.uid()));

create policy "Authenticated users can view published institution faculty opportunities"
  on institution_faculty_opportunities for select
  to authenticated
  using (status = 'PUBLISHED');

drop trigger if exists institution_faculty_opportunities_set_updated_at on institution_faculty_opportunities;
create trigger institution_faculty_opportunities_set_updated_at
  before update on institution_faculty_opportunities
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- faculty_industry_opportunity_expressions ("EOI", Industry-sourced)
-- ============================================================
-- Faculty-initiated expression of interest against one
-- industry_faculty_opportunities posting. Deliberately separate from
-- industry_collaborations (032): a collaboration is Industry-initiated,
-- addressed directly at one named Faculty/Institution account, with no
-- discoverable listing involved at all; this is the reverse direction --
-- Faculty discovers a public listing and initiates interest in it. The
-- two are not merged, per the approved architecture.

create table if not exists faculty_industry_opportunity_expressions (
  id uuid primary key default gen_random_uuid(),

  faculty_id uuid not null references profiles (id) on delete cascade,

  -- restrict, not cascade: an EOI is a historical record of Faculty
  -- interest, same reasoning as applications.opportunity_id -- in
  -- practice postings are never hard-deleted (CLOSED is the retirement
  -- path), so this should never actually fire, but the guarantee is
  -- stated explicitly anyway, mirroring 024's own precedent.
  opportunity_id uuid not null references industry_faculty_opportunities (id) on delete restrict,

  status text not null default 'DRAFT'
    check (status in ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'ACCEPTED', 'REJECTED', 'WITHDRAWN')),

  message text,
  reviewed_by uuid references profiles (id) on delete set null,
  reviewer_note text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Mirrors applications_unique_per_opportunity_student: one Faculty
  -- member may express interest in one opportunity at most once.
  constraint faculty_industry_eoi_unique_per_opportunity_faculty unique (faculty_id, opportunity_id)
);

create index if not exists faculty_industry_eoi_faculty_id_idx
  on faculty_industry_opportunity_expressions (faculty_id);
create index if not exists faculty_industry_eoi_opportunity_id_idx
  on faculty_industry_opportunity_expressions (opportunity_id);
create index if not exists faculty_industry_eoi_status_idx
  on faculty_industry_opportunity_expressions (status);

alter table faculty_industry_opportunity_expressions enable row level security;

create policy "Faculty can view their own industry-sourced EOIs"
  on faculty_industry_opportunity_expressions for select
  to authenticated
  using (auth.uid() = faculty_id and public.is_faculty(auth.uid()));

-- Mirrors "Industry can create their own opportunities" (024): only as a
-- fresh DRAFT -- a client can never insert an already-SUBMITTED/decided row.
create policy "Faculty can create their own industry-sourced EOIs"
  on faculty_industry_opportunity_expressions for insert
  to authenticated
  with check (auth.uid() = faculty_id and public.is_faculty(auth.uid()) and status = 'DRAFT');

create policy "Faculty can update their own industry-sourced EOIs"
  on faculty_industry_opportunity_expressions for update
  to authenticated
  using (auth.uid() = faculty_id and public.is_faculty(auth.uid()))
  with check (auth.uid() = faculty_id and public.is_faculty(auth.uid()));

-- Join-through-ownership-chain read, same pattern as
-- opportunity_skill_requirements' / applications' own owner-side SELECT.
create policy "Industry can view EOIs for their own faculty opportunities"
  on faculty_industry_opportunity_expressions for select
  to authenticated
  using (
    exists (
      select 1 from industry_faculty_opportunities o
      where o.id = faculty_industry_opportunity_expressions.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

create policy "Industry can review EOIs for their own faculty opportunities"
  on faculty_industry_opportunity_expressions for update
  to authenticated
  using (
    exists (
      select 1 from industry_faculty_opportunities o
      where o.id = faculty_industry_opportunity_expressions.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  )
  with check (
    exists (
      select 1 from industry_faculty_opportunities o
      where o.id = faculty_industry_opportunity_expressions.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

-- No DELETE policy for any role -- withdrawal is a status (WITHDRAWN),
-- not a deletion, matching this project's general preference for status
-- transitions over hard deletes.

-- Precise transition control -- RLS alone can gate WHO may attempt to
-- touch a row, but not WHICH transition is legal; this project's own
-- precedent for that second layer is a BEFORE UPDATE trigger
-- (024's prevent_invalid_opportunity_transition / prevent_unauthorized_
-- application_change, 032's restrict_recipient_collaboration_updates).
-- This trigger plays exactly that role for the two-party (Faculty +
-- owning Industry) update shape, the same two-party shape 032 already
-- uses successfully.
create or replace function public.guard_faculty_industry_eoi_update()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  caller_is_owner boolean;
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.faculty_id is distinct from old.faculty_id
    or new.opportunity_id is distinct from old.opportunity_id
  then
    raise exception 'Cannot reassign an expression of interest to a different Faculty member or opportunity.'
      using errcode = '42501';
  end if;

  select exists (
    select 1 from public.industry_faculty_opportunities o
    where o.id = old.opportunity_id and o.industry_id = caller_id
  ) into caller_is_owner;

  if caller_id = old.faculty_id then
    if new.reviewed_by is distinct from old.reviewed_by
      or new.reviewer_note is distinct from old.reviewer_note
    then
      raise exception 'Faculty cannot set review fields on their own expression of interest.'
        using errcode = '42501';
    end if;
    if old.status <> 'DRAFT' and new.message is distinct from old.message then
      raise exception 'Cannot edit the message after submission.' using errcode = '42501';
    end if;
    if new.status is distinct from old.status
      and not (old.status = 'DRAFT' and new.status = 'SUBMITTED')
      and not (old.status in ('SUBMITTED', 'UNDER_REVIEW') and new.status = 'WITHDRAWN')
    then
      raise exception 'Faculty may only submit a draft or withdraw a pending expression of interest.'
        using errcode = '42501';
    end if;
  elsif caller_is_owner then
    if new.message is distinct from old.message then
      raise exception 'Reviewers cannot modify the applicant''s message.' using errcode = '42501';
    end if;
    if new.status is distinct from old.status
      and not (old.status = 'SUBMITTED' and new.status = 'UNDER_REVIEW')
      and not (old.status = 'UNDER_REVIEW' and new.status in ('ACCEPTED', 'REJECTED'))
    then
      raise exception 'Invalid expression-of-interest status transition: % -> %', old.status, new.status
        using errcode = '42501';
    end if;
    -- reviewed_by is always the acting reviewer, never client-supplied.
    new.reviewed_by = caller_id;
  else
    raise exception 'Not authorized to modify this expression of interest.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.guard_faculty_industry_eoi_update() from public;

drop trigger if exists faculty_industry_eoi_guard_update on faculty_industry_opportunity_expressions;
create trigger faculty_industry_eoi_guard_update
  before update on faculty_industry_opportunity_expressions
  for each row
  execute procedure public.guard_faculty_industry_eoi_update();

drop trigger if exists faculty_industry_eoi_set_updated_at on faculty_industry_opportunity_expressions;
create trigger faculty_industry_eoi_set_updated_at
  before update on faculty_industry_opportunity_expressions
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- faculty_institution_opportunity_expressions ("EOI", Institution-sourced)
-- ============================================================
-- Exact structural twin of the table above, targeting
-- institution_faculty_opportunities instead. Kept as a fully separate
-- table rather than parameterized/shared, for the same reason the two
-- opportunity tables are separate: no dynamic-table-target trigger/RLS
-- exists safely in Postgres without dynamic SQL, and this project avoids
-- dynamic SQL. Explicit duplication here is the safe choice, not an
-- oversight.

create table if not exists faculty_institution_opportunity_expressions (
  id uuid primary key default gen_random_uuid(),

  faculty_id uuid not null references profiles (id) on delete cascade,
  opportunity_id uuid not null references institution_faculty_opportunities (id) on delete restrict,

  status text not null default 'DRAFT'
    check (status in ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'ACCEPTED', 'REJECTED', 'WITHDRAWN')),

  message text,
  reviewed_by uuid references profiles (id) on delete set null,
  reviewer_note text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint faculty_institution_eoi_unique_per_opportunity_faculty unique (faculty_id, opportunity_id)
);

create index if not exists faculty_institution_eoi_faculty_id_idx
  on faculty_institution_opportunity_expressions (faculty_id);
create index if not exists faculty_institution_eoi_opportunity_id_idx
  on faculty_institution_opportunity_expressions (opportunity_id);
create index if not exists faculty_institution_eoi_status_idx
  on faculty_institution_opportunity_expressions (status);

alter table faculty_institution_opportunity_expressions enable row level security;

create policy "Faculty can view their own institution-sourced EOIs"
  on faculty_institution_opportunity_expressions for select
  to authenticated
  using (auth.uid() = faculty_id and public.is_faculty(auth.uid()));

create policy "Faculty can create their own institution-sourced EOIs"
  on faculty_institution_opportunity_expressions for insert
  to authenticated
  with check (auth.uid() = faculty_id and public.is_faculty(auth.uid()) and status = 'DRAFT');

create policy "Faculty can update their own institution-sourced EOIs"
  on faculty_institution_opportunity_expressions for update
  to authenticated
  using (auth.uid() = faculty_id and public.is_faculty(auth.uid()))
  with check (auth.uid() = faculty_id and public.is_faculty(auth.uid()));

create policy "Institution can view EOIs for their own faculty opportunities"
  on faculty_institution_opportunity_expressions for select
  to authenticated
  using (
    exists (
      select 1 from institution_faculty_opportunities o
      where o.id = faculty_institution_opportunity_expressions.opportunity_id
        and o.institution_id = auth.uid()
        and public.is_institution(auth.uid())
    )
  );

create policy "Institution can review EOIs for their own faculty opportunities"
  on faculty_institution_opportunity_expressions for update
  to authenticated
  using (
    exists (
      select 1 from institution_faculty_opportunities o
      where o.id = faculty_institution_opportunity_expressions.opportunity_id
        and o.institution_id = auth.uid()
        and public.is_institution(auth.uid())
    )
  )
  with check (
    exists (
      select 1 from institution_faculty_opportunities o
      where o.id = faculty_institution_opportunity_expressions.opportunity_id
        and o.institution_id = auth.uid()
        and public.is_institution(auth.uid())
    )
  );

create or replace function public.guard_faculty_institution_eoi_update()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  caller_is_owner boolean;
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.faculty_id is distinct from old.faculty_id
    or new.opportunity_id is distinct from old.opportunity_id
  then
    raise exception 'Cannot reassign an expression of interest to a different Faculty member or opportunity.'
      using errcode = '42501';
  end if;

  select exists (
    select 1 from public.institution_faculty_opportunities o
    where o.id = old.opportunity_id and o.institution_id = caller_id
  ) into caller_is_owner;

  if caller_id = old.faculty_id then
    if new.reviewed_by is distinct from old.reviewed_by
      or new.reviewer_note is distinct from old.reviewer_note
    then
      raise exception 'Faculty cannot set review fields on their own expression of interest.'
        using errcode = '42501';
    end if;
    if old.status <> 'DRAFT' and new.message is distinct from old.message then
      raise exception 'Cannot edit the message after submission.' using errcode = '42501';
    end if;
    if new.status is distinct from old.status
      and not (old.status = 'DRAFT' and new.status = 'SUBMITTED')
      and not (old.status in ('SUBMITTED', 'UNDER_REVIEW') and new.status = 'WITHDRAWN')
    then
      raise exception 'Faculty may only submit a draft or withdraw a pending expression of interest.'
        using errcode = '42501';
    end if;
  elsif caller_is_owner then
    if new.message is distinct from old.message then
      raise exception 'Reviewers cannot modify the applicant''s message.' using errcode = '42501';
    end if;
    if new.status is distinct from old.status
      and not (old.status = 'SUBMITTED' and new.status = 'UNDER_REVIEW')
      and not (old.status = 'UNDER_REVIEW' and new.status in ('ACCEPTED', 'REJECTED'))
    then
      raise exception 'Invalid expression-of-interest status transition: % -> %', old.status, new.status
        using errcode = '42501';
    end if;
    new.reviewed_by = caller_id;
  else
    raise exception 'Not authorized to modify this expression of interest.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.guard_faculty_institution_eoi_update() from public;

drop trigger if exists faculty_institution_eoi_guard_update on faculty_institution_opportunity_expressions;
create trigger faculty_institution_eoi_guard_update
  before update on faculty_institution_opportunity_expressions
  for each row
  execute procedure public.guard_faculty_institution_eoi_update();

drop trigger if exists faculty_institution_eoi_set_updated_at on faculty_institution_opportunity_expressions;
create trigger faculty_institution_eoi_set_updated_at
  before update on faculty_institution_opportunity_expressions
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- FUTURE INTEGRATION POINTS (explicitly NOT built in this migration)
-- ============================================================
-- faculty_engagements: deliberately not created here. An ACCEPTED EOI is
-- a terminal lifecycle state for now; a later phase may introduce a
-- separate engagement table keyed off (eoi table, eoi id) once that
-- design is approved -- not assumed or scaffolded here.
--
-- Research/Consultancy/FDP/Faculty-Workshop domain entities: still
-- product-decision gaps per the F3.3 architecture discovery and the
-- approved design checkpoint. Nothing here should be read as answering
-- those questions -- industry_faculty_opportunities/
-- institution_faculty_opportunities are generic "Faculty opportunity"
-- postings, not a Research/Consultancy/FDP/Workshop-specific schema.
