-- Migration: 025_industry_mentorship
-- Purpose: Phase 10D -- mentorship opportunities posted by INDUSTRY users
-- (e.g. multi-month mentoring engagements offered to students),
-- independent of the internship/job/application pipeline (018/019/020)
-- and independent of Phase 9 matching (021). Same standalone-entity
-- precedent as industry_projects (022) / industry_training (023) /
-- industry_workshops (024): no mentor<->mentee pairing table, no
-- request/enrollment table, no skills/expertise subtable, no
-- certificate infrastructure -- none of that is established anywhere
-- else in this repository, so none of it is invented here. Phase 10D is
-- deliberately scoped to the Industry-side posting only (Model C, per
-- product decision): a future Student/Collaboration phase owns any
-- request/pairing workflow.
--
-- Named `industry_mentorship` (not `mentorship`/`mentorships`) for the
-- same reason industry_projects/industry_training/industry_workshops
-- avoided their generic names: `backend/app/api/mentorship.py` is a
-- dead, unregistered generic stub that a future Student or Collaboration
-- feature may still claim, and 009_collaboration.sql already reserves
-- "mentorship pairings" as part of a separate, unimplemented
-- academia-industry Collaboration feature. This naming leaves both of
-- those namespaces untouched.
--
-- Unlike 022/023/024, `location`, `work_mode`, `duration_months`, and
-- `capacity` are NOT NULL here per explicit product decision -- a
-- mentorship opportunity must specify these at creation time, not only
-- before publish. `duration_months` (not `duration_days` like
-- industry_workshops) follows the long-running-engagement pattern of
-- industry_projects/industry_training, since a mentorship is a
-- multi-month relationship, not a short event. `application_deadline`
-- is TIMESTAMPTZ (not DATE like 022/023/024) per explicit product
-- decision.
--
-- Same ownership reasoning as internships/jobs/projects/training/workshops:
-- industry_id references profiles(id), not industry_profiles(id).

create table if not exists industry_mentorship (
  id uuid primary key default gen_random_uuid(),
  industry_id uuid not null references public.profiles (id) on delete cascade,

  title text not null,
  description text not null,
  location text not null,
  work_mode text not null check (work_mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  duration_months int not null check (duration_months between 1 and 24),
  capacity int not null check (capacity > 0),
  eligibility_criteria text,
  application_deadline timestamptz,
  start_date date,
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists industry_mentorship_industry_id_idx on industry_mentorship (industry_id);
-- Partial index for the public "browse published mentorship opportunities"
-- query -- same pattern as internships_published_idx / jobs_published_idx
-- / industry_projects_published_idx / industry_training_published_idx /
-- industry_workshops_published_idx.
create index if not exists industry_mentorship_published_idx on industry_mentorship (id) where status = 'PUBLISHED';

alter table industry_mentorship enable row level security;

-- "for all" covers select/insert/update/delete for the owner, regardless
-- of status (a DRAFT/CLOSED/ARCHIVED mentorship opportunity is still
-- visible/editable to its own industry owner) -- the public policy below
-- only adds PUBLISHED visibility for everyone else.
drop policy if exists "Industry can manage their own mentorship opportunities" on industry_mentorship;
create policy "Industry can manage their own mentorship opportunities"
  on industry_mentorship for all
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Authenticated users can view published mentorship opportunities" on industry_mentorship;
create policy "Authenticated users can view published mentorship opportunities"
  on industry_mentorship for select
  to authenticated
  using (status = 'PUBLISHED');

drop trigger if exists industry_mentorship_set_updated_at on industry_mentorship;
create trigger industry_mentorship_set_updated_at
  before update on industry_mentorship
  for each row
  execute procedure public.set_updated_at();
