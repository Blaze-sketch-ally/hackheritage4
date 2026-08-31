-- Migration: 017_industry_profiles
-- Purpose: extends the shared `profiles` identity row (001_profiles.sql)
-- with INDUSTRY-specific company data. One row per INDUSTRY user, keyed
-- 1-to-1 by `id = profiles.id = auth.users.id`.
--
-- The row is created lazily by the app the first time an industry user
-- saves their company profile -- same pattern as student_profiles
-- (012_student_profiles.sql): not every `profiles` row belongs to an
-- industry account, and a brand-new user has nothing to store here yet.
--
-- Deliberately NOT included here:
--   - company_name is NOT a duplicate of profiles.full_name -- the person
--     who signs up has a name on profiles; the company they represent is
--     separate data, kept only here.
--   - Logo/document file storage -- no Supabase Storage bucket exists yet
--     (same limitation 012_student_profiles.sql documents for resumes).
--     logo_url is a plain text URL column, exactly like profiles.avatar_url.

create table if not exists industry_profiles (
  id uuid primary key references profiles (id) on delete cascade,

  company_name text,
  industry_sector text,
  -- Small, stable bucket scale -- same "short stable scale -> CHECK
  -- constraint" convention as profiles.role / student_skills.proficiency_level.
  company_size text check (company_size in ('1-10', '11-50', '51-200', '201-500', '501-1000', '1000+')),
  website_url text,
  company_description text,
  headquarters_location text,
  founded_year int check (founded_year between 1800 and 2100),
  -- Same phone format already used by student_profiles.phone.
  contact_phone text,
  constraint industry_profiles_phone_format check (contact_phone ~ '^[0-9+\-\s()]{7,20}$'),
  linkedin_url text,
  logo_url text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table industry_profiles enable row level security;

-- Role-check helper mirroring public.is_student(uuid) (012_student_profiles.sql,
-- hardened in 013_harden_is_student.sql) -- SECURITY DEFINER + pinned empty
-- search_path so this reads `profiles` directly, bypassing profiles' own
-- RLS for this one check. Same pattern used throughout this project
-- (get_email_for_identifier, prevent_self_admin_promotion, is_student).
--
-- Hardened from creation, unlike is_student (which needed the follow-up
-- 013_harden_is_student.sql to close a gap where `anon` picked up EXECUTE
-- via Supabase's project-level default privileges): EXECUTE is granted to
-- `authenticated` only here, and explicitly revoked from both `public` and
-- `anon` up front, so no equivalent follow-up migration is needed.
create or replace function public.is_industry(profile_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.profiles where id = profile_id and role = 'INDUSTRY'
  );
$$;

revoke all on function public.is_industry(uuid) from public;
revoke all on function public.is_industry(uuid) from anon;
grant execute on function public.is_industry(uuid) to authenticated;

-- Ownership policies, same shape as student_profiles' own policies in
-- 012_student_profiles.sql.
drop policy if exists "Industry can view their own industry profile" on industry_profiles;
create policy "Industry can view their own industry profile"
  on industry_profiles for select
  to authenticated
  using (auth.uid() = id and public.is_industry(auth.uid()));

drop policy if exists "Industry can insert their own industry profile" on industry_profiles;
create policy "Industry can insert their own industry profile"
  on industry_profiles for insert
  to authenticated
  with check (auth.uid() = id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update their own industry profile" on industry_profiles;
create policy "Industry can update their own industry profile"
  on industry_profiles for update
  to authenticated
  using (auth.uid() = id and public.is_industry(auth.uid()))
  with check (auth.uid() = id and public.is_industry(auth.uid()));

-- Company display info (name/description/logo/etc.) must be readable by
-- any signed-in user -- students and institutions need it to show "posted
-- by <company>" on internship/job listings (018_internships.sql,
-- 019_jobs.sql) without duplicating these columns onto every posting row.
-- Scoped `to authenticated` only -- no `anon`/public policy, per the
-- approved plan.
drop policy if exists "Authenticated users can view industry profiles" on industry_profiles;
create policy "Authenticated users can view industry profiles"
  on industry_profiles for select
  to authenticated
  using (true);

-- No delete policy -- matches student_profiles (no delete policy either).

drop trigger if exists industry_profiles_set_updated_at on industry_profiles;

create trigger industry_profiles_set_updated_at
  before update on industry_profiles
  for each row
  execute procedure public.set_updated_at();
