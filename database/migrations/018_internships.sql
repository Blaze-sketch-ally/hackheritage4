-- Migration: 018_internships
-- Purpose: internship postings created by INDUSTRY users, plus the
-- normalized required-skills relationship for each posting. Application
-- tracking lives in 020_applications.sql, not here.
--
-- NOTE: 005_internships.sql is an earlier, still-unimplemented placeholder
-- for this same feature area -- left untouched per explicit instruction.
-- This migration is the real schema, numbered after the current tip of
-- the migration sequence (016), not a replacement of 005.
--
-- industry_id references profiles(id), NOT industry_profiles(id): a
-- profiles row exists for every user from signup, but industry_profiles
-- (017_industry_profiles.sql) is created lazily -- same reasoning already
-- applied to student_skills.student_id (003_skills.sql) and
-- student_target_job_role.student_id (016_skill_gap.sql). An industry
-- user must be able to post before ever touching their company profile
-- form.

create table if not exists internships (
  id uuid primary key default gen_random_uuid(),
  industry_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text not null,
  location text,
  work_mode text check (work_mode in ('ONSITE', 'REMOTE', 'HYBRID')),
  duration_months int check (duration_months between 1 and 24),
  stipend_amount numeric(10, 2) check (stipend_amount >= 0),
  stipend_currency text not null default 'INR',
  openings int not null default 1 check (openings > 0),
  eligibility_criteria text,
  application_deadline date,
  start_date date,
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'CLOSED', 'ARCHIVED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists internships_industry_id_idx on internships (industry_id);
-- Partial index for the public "browse published internships" query --
-- same pattern as job_roles_active_idx (016_skill_gap.sql).
create index if not exists internships_published_idx on internships (id) where status = 'PUBLISHED';

alter table internships enable row level security;

-- "for all" covers select/insert/update/delete for the owner, regardless
-- of status (a DRAFT/CLOSED/ARCHIVED posting is still visible/editable to
-- its own industry owner) -- the public policy below only adds PUBLISHED
-- visibility for everyone else.
drop policy if exists "Industry can manage their own internships" on internships;
create policy "Industry can manage their own internships"
  on internships for all
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Authenticated users can view published internships" on internships;
create policy "Authenticated users can view published internships"
  on internships for select
  to authenticated
  using (status = 'PUBLISHED');

drop trigger if exists internships_set_updated_at on internships;
create trigger internships_set_updated_at
  before update on internships
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- internship_skills -- required skills + level + importance per posting.
-- Same shape as job_role_skills (016_skill_gap.sql).
-- ============================================================

create table if not exists internship_skills (
  id uuid primary key default gen_random_uuid(),
  internship_id uuid not null references internships (id) on delete cascade,
  -- restrict, not cascade: a skill referenced by a real posting
  -- requirement is protected content -- same reasoning as
  -- job_role_skills.skill_id / student_skills.skill_id.
  skill_id uuid not null references skills (id) on delete restrict,
  required_level text not null check (required_level in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),
  importance text not null default 'IMPORTANT' check (importance in ('CORE', 'IMPORTANT', 'OPTIONAL')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint internship_skills_unique_per_internship unique (internship_id, skill_id)
);

create index if not exists internship_skills_internship_id_idx on internship_skills (internship_id);
create index if not exists internship_skills_skill_id_idx on internship_skills (skill_id);

alter table internship_skills enable row level security;

drop policy if exists "Authenticated users can view skills for published internships" on internship_skills;
create policy "Authenticated users can view skills for published internships"
  on internship_skills for select
  to authenticated
  using (
    exists (
      select 1 from internships i
      where i.id = internship_skills.internship_id
        and i.status = 'PUBLISHED'
    )
  );

drop policy if exists "Industry can manage skills for their own internships" on internship_skills;
create policy "Industry can manage skills for their own internships"
  on internship_skills for all
  to authenticated
  using (
    exists (
      select 1 from internships i
      where i.id = internship_skills.internship_id
        and i.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  )
  with check (
    exists (
      select 1 from internships i
      where i.id = internship_skills.internship_id
        and i.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

drop trigger if exists internship_skills_set_updated_at on internship_skills;
create trigger internship_skills_set_updated_at
  before update on internship_skills
  for each row
  execute procedure public.set_updated_at();
