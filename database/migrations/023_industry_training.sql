-- Migration: 023_industry_training
-- Purpose: Phase 10B -- training programs posted by INDUSTRY users (e.g.
-- upskilling/bootcamp-style programs offered to students), independent of
-- the internship/job/application pipeline (018/019/020) and independent
-- of Phase 9 matching (021). Same standalone-entity precedent as
-- industry_projects (022): no application/enrollment table, no skills
-- subtable, no certificate infrastructure -- none of that is established
-- anywhere else in this repository, so none of it is invented here.
--
-- Named `industry_training` (not `training`/`trainings`) for the same
-- reason industry_projects avoided the generic `project`/`projects`
-- names: Faculty has its own unimplemented, unrelated "FDP" (Faculty
-- Development Programs) placeholder (frontend/app/faculty/fdps) that is
-- also training-shaped -- this naming leaves that room free for whoever
-- builds it later.
--
-- Same ownership reasoning as internships/jobs/projects: industry_id
-- references profiles(id), not industry_profiles(id).

create table if not exists industry_training (
  id uuid primary key default gen_random_uuid(),
  industry_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text not null,
  location text,
  work_mode text check (work_mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  duration_months int check (duration_months between 1 and 24),
  capacity int check (capacity > 0),
  eligibility_criteria text,
  application_deadline date,
  start_date date,
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists industry_training_industry_id_idx on industry_training (industry_id);
-- Partial index for the public "browse published training" query -- same
-- pattern as internships_published_idx / jobs_published_idx / industry_projects_published_idx.
create index if not exists industry_training_published_idx on industry_training (id) where status = 'PUBLISHED';

alter table industry_training enable row level security;

-- "for all" covers select/insert/update/delete for the owner, regardless
-- of status (a DRAFT/CLOSED/ARCHIVED training record is still
-- visible/editable to its own industry owner) -- the public policy below
-- only adds PUBLISHED visibility for everyone else.
drop policy if exists "Industry can manage their own training" on industry_training;
create policy "Industry can manage their own training"
  on industry_training for all
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Authenticated users can view published training" on industry_training;
create policy "Authenticated users can view published training"
  on industry_training for select
  to authenticated
  using (status = 'PUBLISHED');

drop trigger if exists industry_training_set_updated_at on industry_training;
create trigger industry_training_set_updated_at
  before update on industry_training
  for each row
  execute procedure public.set_updated_at();
