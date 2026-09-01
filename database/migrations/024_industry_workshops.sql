-- Migration: 024_industry_workshops
-- Purpose: Phase 10C -- workshops posted by INDUSTRY users (short,
-- event-style sessions offered to students), independent of the
-- internship/job/application pipeline (018/019/020) and independent of
-- Phase 9 matching (021). Same standalone-entity precedent as
-- industry_projects (022) / industry_training (023): no
-- application/registration table, no skills subtable, no certificate
-- infrastructure -- none of that is established anywhere else in this
-- repository, so none of it is invented here.
--
-- Named `industry_workshops` (not `workshop`/`workshops`) for the same
-- reason industry_projects/industry_training avoided their generic
-- names: 009_collaboration.sql already reserves "workshops" as part of a
-- separate, unimplemented academia-industry Collaboration feature
-- (mentorship pairings + workshops + research/consultancy engagements)
-- -- a different, broader concept from this Industry-owned posting.
-- This naming leaves that placeholder's namespace untouched.
--
-- Duration is `duration_days` (1-365), not `duration_months` like
-- internships/industry_projects/industry_training: those model
-- long-running engagements, but a workshop is a short event, and forcing
-- it into month-granularity would misrepresent a 1-3 day workshop as "1
-- month" -- a deliberate, approved deviation from otherwise-identical
-- schema parity with 022/023.
--
-- Same ownership reasoning as internships/jobs/projects/training:
-- industry_id references profiles(id), not industry_profiles(id).

create table if not exists industry_workshops (
  id uuid primary key default gen_random_uuid(),
  industry_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text not null,
  location text,
  work_mode text check (work_mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  duration_days int check (duration_days between 1 and 365),
  capacity int check (capacity > 0),
  eligibility_criteria text,
  application_deadline date,
  start_date date,
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists industry_workshops_industry_id_idx on industry_workshops (industry_id);
-- Partial index for the public "browse published workshops" query -- same
-- pattern as internships_published_idx / jobs_published_idx /
-- industry_projects_published_idx / industry_training_published_idx.
create index if not exists industry_workshops_published_idx on industry_workshops (id) where status = 'PUBLISHED';

alter table industry_workshops enable row level security;

-- "for all" covers select/insert/update/delete for the owner, regardless
-- of status (a DRAFT/CLOSED/ARCHIVED workshop is still visible/editable
-- to its own industry owner) -- the public policy below only adds
-- PUBLISHED visibility for everyone else.
drop policy if exists "Industry can manage their own workshops" on industry_workshops;
create policy "Industry can manage their own workshops"
  on industry_workshops for all
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Authenticated users can view published workshops" on industry_workshops;
create policy "Authenticated users can view published workshops"
  on industry_workshops for select
  to authenticated
  using (status = 'PUBLISHED');

drop trigger if exists industry_workshops_set_updated_at on industry_workshops;
create trigger industry_workshops_set_updated_at
  before update on industry_workshops
  for each row
  execute procedure public.set_updated_at();
