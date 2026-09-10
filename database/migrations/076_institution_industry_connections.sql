-- Migration: 076_institution_industry_connections
-- Purpose: PHASE 9 -- lets an INSTITUTION keep its own record of NAMED
-- contact people at a company (recruiter, HR lead, alumni relations,
-- etc.), independent of the company's own public profile. This
-- migration adds exactly ONE new table. It does NOT create a second
-- company entity and does NOT touch `industry_collaborations` (026) --
-- that bilateral proposal workflow is unchanged by this migration.
--
-- Audit finding this migration acts on: `industry_profiles`
-- (017_industry_profiles.sql) already has a single COMPANY-level
-- `contact_phone` column -- one phone number for the whole company,
-- owned and edited only by the Industry account itself. It has no
-- concept of a named person, a designation, a contact "type"
-- (recruitment vs academic vs internship...), or anything
-- institution-specific. That is a genuinely different, and genuinely
-- missing, piece of data -- reusing industry_profiles.contact_phone for
-- it would conflate "the company's own public contact number" with "who
-- my TPO office happens to talk to there", so it is not reused; a new,
-- small, institution-owned table is the smallest correct fix.
--
-- Ownership split (same shape as institution_industry_partners, 043):
--   industry_profiles        -> canonical company identity, Industry-owned
--   institution_industry_connections -> the INSTITUTION's own private
--                                        record of a contact person at
--                                        that company. Never visible to
--                                        the company or any other
--                                        institution.
--
-- Multiple contacts per company are expected (a placement office may
-- know both an HR recruiter and an alumni-relations contact at the same
-- company) -- unlike institution_industry_partners (043), there is
-- deliberately NO unique(institution_id, industry_id) constraint here.
--
-- Ownership: institution_id references profiles(id), not
-- institution_profiles(id) -- same reasoning as every other
-- institution_id FK in this schema (037/038/040/041/043).

create table if not exists institution_industry_connections (
  id uuid primary key default gen_random_uuid(),

  institution_id uuid not null references profiles (id) on delete cascade,
  -- Must reference an actual INDUSTRY account -- enforced by the
  -- validate_connection_industry_id trigger below, not just documented.
  industry_id uuid not null references profiles (id) on delete cascade,

  contact_name text not null,
  designation text,
  contact_type text not null default 'OTHER' check (
    contact_type in ('RECRUITMENT', 'ACADEMIC', 'INTERNSHIP', 'PARTNERSHIP', 'TRAINING', 'OTHER')
  ),
  -- The institution's own record of how to reach this person -- not
  -- synced from, and never written back to, industry_profiles.
  email text,
  phone text,
  constraint institution_industry_connections_phone_format check (
    phone is null or phone ~ '^[0-9+\-\s()]{7,20}$'
  ),
  notes text,

  -- Soft-remove flag -- see the "no delete policy" note below. A
  -- deactivated connection is a former contact, not erased history.
  is_active boolean not null default true,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint institution_industry_connections_name_not_blank check (length(btrim(contact_name)) > 0)
);

create index if not exists institution_industry_connections_institution_id_idx
  on institution_industry_connections (institution_id);
create index if not exists institution_industry_connections_industry_id_idx
  on institution_industry_connections (industry_id);

alter table institution_industry_connections enable row level security;

-- ============================================================
-- Trigger: the referenced industry_id must be a real INDUSTRY account.
-- Same "server-validates, never trusts the client's target id" pattern
-- as validate_partner_industry_id (075_institution_industry_partners.sql).
-- ============================================================

create or replace function public.validate_connection_industry_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.is_industry(new.industry_id) then
    raise exception 'institution_industry_connections.industry_id must reference an INDUSTRY account.' using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke all on function public.validate_connection_industry_id() from public;

drop trigger if exists institution_industry_connections_validate_industry_id on institution_industry_connections;
create trigger institution_industry_connections_validate_industry_id
  before insert or update on institution_industry_connections
  for each row
  execute procedure public.validate_connection_industry_id();

drop trigger if exists institution_industry_connections_set_updated_at on institution_industry_connections;
create trigger institution_industry_connections_set_updated_at
  before update on institution_industry_connections
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- RLS policies -- INSTITUTION-owned, INSTITUTION-only. Split into
-- explicit SELECT / INSERT / UPDATE so DELETE is left with NO policy at
-- all -- same "deactivate via is_active, never hard-delete" convention
-- as institution_industry_partners (043) and every other institution-
-- owned table in this schema.
-- ============================================================

drop policy if exists "Institution can view their own industry connections" on institution_industry_connections;
create policy "Institution can view their own industry connections"
  on institution_industry_connections for select
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can create their own industry connections" on institution_industry_connections;
create policy "Institution can create their own industry connections"
  on institution_industry_connections for insert
  to authenticated
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

drop policy if exists "Institution can update their own industry connections" on institution_industry_connections;
create policy "Institution can update their own industry connections"
  on institution_industry_connections for update
  to authenticated
  using (institution_id = auth.uid() and public.is_institution(auth.uid()))
  with check (institution_id = auth.uid() and public.is_institution(auth.uid()));

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INSTITUTION: record a contact at a real company
--   insert into public.institution_industry_connections
--     (institution_id, industry_id, contact_name, designation, contact_type)
--     values (auth.uid(), '<a real INDUSTRY profile id>'::uuid, 'Priya Sharma', 'HR Manager', 'RECRUITMENT');
--
--   -- industry_id referencing a STUDENT/FACULTY/non-industry account: rejected
--   -- (validate_connection_industry_id raises)
--
--   -- as a DIFFERENT institution: 0 rows, and inserting under someone
--   -- else's institution_id is rejected by the WITH CHECK
--
--   -- as the INDUSTRY account itself, or any other role: 0 rows, no
--   -- policy grants any visibility outside the owning institution
-- ============================================================
