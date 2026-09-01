-- Migration: 022_industry_projects
-- Purpose: Phase 10A -- collaborative projects posted by INDUSTRY users
-- (e.g. real-world problem statements offered to students), independent
-- of the internship/job/application pipeline (018/019/020). Projects do
-- not participate in the `applications` table or Phase 9 matching --
-- that wiring is explicitly out of scope for this phase.
--
-- Named `industry_projects` (not `projects`) to avoid colliding with the
-- still-unbuilt Student Portfolio "projects" feature referenced by
-- 008_portfolio.sql and the generic backend/app/schemas/project.py +
-- backend/app/api/projects.py stubs, which are a distinct, unrelated
-- feature area reserved for whoever builds that later.
--
-- Same ownership reasoning as internships/jobs: industry_id references
-- profiles(id), not industry_profiles(id) -- an industry user must be
-- able to post before ever touching their company profile form.
--
-- No skills subtable: unlike internships/jobs, Projects has no
-- application/matching flow yet this phase, so a required-skills
-- relationship would have nothing to consume it.

create table if not exists industry_projects (
  id uuid primary key default gen_random_uuid(),
  industry_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text not null,
  location text,
  work_mode text check (work_mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  duration_months int check (duration_months between 1 and 24),
  team_size int check (team_size > 0),
  eligibility_criteria text,
  application_deadline date,
  start_date date,
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists industry_projects_industry_id_idx on industry_projects (industry_id);
-- Partial index for the public "browse published projects" query -- same
-- pattern as internships_published_idx / jobs_published_idx.
create index if not exists industry_projects_published_idx on industry_projects (id) where status = 'PUBLISHED';

alter table industry_projects enable row level security;

-- "for all" covers select/insert/update/delete for the owner, regardless
-- of status (a DRAFT/CLOSED/ARCHIVED project is still visible/editable to
-- its own industry owner) -- the public policy below only adds PUBLISHED
-- visibility for everyone else.
drop policy if exists "Industry can manage their own projects" on industry_projects;
create policy "Industry can manage their own projects"
  on industry_projects for all
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Authenticated users can view published projects" on industry_projects;
create policy "Authenticated users can view published projects"
  on industry_projects for select
  to authenticated
  using (status = 'PUBLISHED');

drop trigger if exists industry_projects_set_updated_at on industry_projects;
create trigger industry_projects_set_updated_at
  before update on industry_projects
  for each row
  execute procedure public.set_updated_at();
