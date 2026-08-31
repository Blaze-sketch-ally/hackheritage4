-- Migration: 019_jobs
-- Purpose: full-time job postings created by INDUSTRY users, plus the
-- normalized required-skills relationship for each posting. Application
-- tracking lives in 020_applications.sql, not here.
--
-- NOTE: 006_jobs.sql is an earlier, still-unimplemented placeholder for
-- this same feature area -- left untouched per explicit instruction. This
-- migration is the real schema, numbered after the current tip of the
-- migration sequence, not a replacement of 006.
--
-- Same ownership reasoning as internships (018_internships.sql):
-- industry_id references profiles(id), not industry_profiles(id).

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  industry_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text not null,
  location text,
  work_mode text check (work_mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  employment_type text check (employment_type in ('FULL_TIME', 'PART_TIME', 'CONTRACT')),
  salary_min numeric(12, 2) check (salary_min >= 0),
  salary_max numeric(12, 2) check (salary_max >= 0),
  constraint jobs_salary_range check (salary_min is null or salary_max is null or salary_max >= salary_min),
  salary_currency text not null default 'INR',
  experience_min_years numeric(3, 1) check (experience_min_years >= 0),
  openings int not null default 1 check (openings > 0),
  eligibility_criteria text,
  application_deadline date,
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists jobs_industry_id_idx on jobs (industry_id);
-- Partial index for the public "browse published jobs" query -- same
-- pattern as internships_published_idx (018_internships.sql).
create index if not exists jobs_published_idx on jobs (id) where status = 'PUBLISHED';

alter table jobs enable row level security;

drop policy if exists "Industry can manage their own jobs" on jobs;
create policy "Industry can manage their own jobs"
  on jobs for all
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Authenticated users can view published jobs" on jobs;
create policy "Authenticated users can view published jobs"
  on jobs for select
  to authenticated
  using (status = 'PUBLISHED');

drop trigger if exists jobs_set_updated_at on jobs;
create trigger jobs_set_updated_at
  before update on jobs
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- job_skills -- required skills + level + importance per posting. Same
-- shape as internship_skills / job_role_skills.
-- ============================================================

create table if not exists job_skills (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references jobs (id) on delete cascade,
  skill_id uuid not null references skills (id) on delete restrict,
  required_level text not null check (required_level in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),
  importance text not null default 'IMPORTANT' check (importance in ('CORE', 'IMPORTANT', 'OPTIONAL')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint job_skills_unique_per_job unique (job_id, skill_id)
);

create index if not exists job_skills_job_id_idx on job_skills (job_id);
create index if not exists job_skills_skill_id_idx on job_skills (skill_id);

alter table job_skills enable row level security;

drop policy if exists "Authenticated users can view skills for published jobs" on job_skills;
create policy "Authenticated users can view skills for published jobs"
  on job_skills for select
  to authenticated
  using (
    exists (
      select 1 from jobs j
      where j.id = job_skills.job_id
        and j.status = 'PUBLISHED'
    )
  );

drop policy if exists "Industry can manage skills for their own jobs" on job_skills;
create policy "Industry can manage skills for their own jobs"
  on job_skills for all
  to authenticated
  using (
    exists (
      select 1 from jobs j
      where j.id = job_skills.job_id
        and j.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  )
  with check (
    exists (
      select 1 from jobs j
      where j.id = job_skills.job_id
        and j.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

drop trigger if exists job_skills_set_updated_at on job_skills;
create trigger job_skills_set_updated_at
  before update on job_skills
  for each row
  execute procedure public.set_updated_at();
