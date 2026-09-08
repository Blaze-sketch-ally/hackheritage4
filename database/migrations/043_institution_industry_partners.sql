-- Migration: 043_institution_industry_partners
-- Purpose: PHASE 8 -- lets an INSTITUTION explicitly track its own
-- relationship with a company (industry account), independent of any
-- actual recruitment activity. This migration adds exactly ONE new
-- table. It does NOT create a second company entity:
--
--   - The canonical company identity remains `industry_profiles`
--     (017_industry_profiles.sql), already readable by any authenticated
--     user ("Authenticated users can view industry profiles",
--     using (true)) -- this migration references it, never duplicates it.
--   - `industry_collaborations` (026_industry_collaborations.sql) is a
--     DIFFERENT, pre-existing concept: an INDUSTRY-initiated, bilateral
--     collaboration PROPOSAL (workshops/mentorship/research-style
--     academic collaboration) with its own DRAFT->SENT->ACCEPTED/
--     REJECTED->ACTIVE->COMPLETED/CANCELLED lifecycle. An Institution
--     cannot create a row there (industry_id must be the inserting
--     INDUSTRY caller) -- it is the wrong shape and the wrong initiation
--     direction for "the TPO wants to privately track/tag a company as a
--     prospective or active recruiting partner", which is what this
--     table is for. The two are complementary, not competing: Company
--     Detail (Phase 8) shows a summary of `industry_collaborations` rows
--     alongside this table's own relationship_type/status, never
--     duplicating collaboration content.
--   - "Placed"/"selected" activity itself still means exactly what it
--     has meant since 037_institution_tenancy.sql: an `applications` row
--     with status = 'SELECTED'. This table carries no activity data of
--     its own (no job/internship/drive counts) -- those are always
--     computed live from the existing applications/placement_drives
--     tables by institution_industry_service.py, keyed by this
--     relationship's own industry_id.
--
-- Scope: INSTITUTION-private. There is no INDUSTRY-side visibility into
-- this table (a company is never notified "Institution X tagged you as
-- a PROSPECT") -- same "institution-only, not company-facing" privacy
-- boundary already established for placement_drives (041).
--
-- Ownership: institution_id references profiles(id), not
-- institution_profiles(id) -- same reasoning as every other
-- institution_id FK in this schema (037/038/040/041): a profiles row
-- exists for every user from signup, institution_profiles is created
-- lazily.

create table if not exists institution_industry_partners (
  id uuid primary key default gen_random_uuid(),

  institution_id uuid not null references profiles (id) on delete cascade,
  -- Must reference an actual INDUSTRY account -- enforced by the
  -- validate_partner_industry_id trigger below, not just documented.
  industry_id uuid not null references profiles (id) on delete cascade,

  relationship_type text not null default 'OTHER' check (
    relationship_type in ('RECRUITMENT', 'INTERNSHIP', 'INDUSTRY_INTERACTION', 'COLLABORATION', 'TRAINING', 'OTHER')
  ),
  relationship_status text not null default 'PROSPECT' check (
    relationship_status in ('PROSPECT', 'ACTIVE', 'INACTIVE')
  ),
  -- Private TPO notes about this company -- never shown to the company
  -- or any other institution.
  notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- One relationship row per (institution, company) -- re-tagging an
  -- already-tracked company is an UPDATE, not a second row.
  constraint institution_industry_partners_unique_pair unique (institution_id, industry_id)
);

create index if not exists institution_industry_partners_institution_id_idx
  on institution_industry_partners (institution_id);
create index if not exists institution_industry_partners_industry_id_idx
  on institution_industry_partners (industry_id);

alter table institution_industry_partners enable row level security;

-- ============================================================
-- Trigger: the referenced industry_id must be a real INDUSTRY account.
-- An Institution can never invent a fake company here -- company
-- selection is always constrained to the canonical industry_profiles/
-- profiles(role='INDUSTRY') identity, same "server-validates, never
-- trusts the client's target id" pattern as
-- validate_placement_drive_departments (041).
-- ============================================================

create or replace function public.validate_partner_industry_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.is_industry(new.industry_id) then
    raise exception 'institution_industry_partners.industry_id must reference an INDUSTRY account.' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke all on function public.validate_partner_industry_id() from public;

drop trigger if exists institution_industry_partners_validate_industry_id on institution_industry_partners;
create trigger institution_industry_partners_validate_industry_id
  before insert or update on institution_industry_partners
  for each row
  execute procedure public.validate_partner_industry_id();

drop trigger if exists institution_industry_partners_set_updated_at on institution_industry_partners;
create trigger institution_industry_partners_set_updated_at
  before update on institution_industry_partners
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies -- INSTITUTION-owned, INSTITUTION-only (see the "Scope"
-- note above: no company-facing visibility exists for this table).
--
-- Split into explicit SELECT / INSERT / UPDATE (rather than one FOR ALL)
-- so DELETE is left with NO policy at all -- same "deactivate, never
-- hard-delete" convention as every other institution-owned table in this
-- schema (departments' is_active, placement_drives' CANCELLED status):
-- "remove" a partner by setting relationship_status = 'INACTIVE', not by
-- deleting the row.
-- ============================================================

drop policy if exists "Institution can view their own industry partner relationships" on institution_industry_partners;
create policy "Institution can view their own industry partner relationships"
  on institution_industry_partners for select
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can create their own industry partner relationships" on institution_industry_partners;
create policy "Institution can create their own industry partner relationships"
  on institution_industry_partners for insert
  to authenticated
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can update their own industry partner relationships" on institution_industry_partners;
create policy "Institution can update their own industry partner relationships"
  on institution_industry_partners for update
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()))
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INSTITUTION: tag a real industry account as a partner
--   insert into public.institution_industry_partners (institution_id, industry_id, relationship_type, relationship_status)
--     values (auth.uid(), '<a real INDUSTRY profile id>'::uuid, 'RECRUITMENT', 'ACTIVE');
--
--   -- industry_id referencing a STUDENT/FACULTY/non-industry account: rejected
--   -- (validate_partner_industry_id raises)
--
--   -- as a DIFFERENT institution: 0 rows, and inserting under someone
--   -- else's institution_id is rejected by the WITH CHECK
--
--   -- re-tagging the same company: an UPDATE via the unique
--   -- (institution_id, industry_id) pair, never a duplicate row
-- ============================================================
