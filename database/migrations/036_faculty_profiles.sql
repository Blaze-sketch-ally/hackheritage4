-- Migration: 036_faculty_profiles
-- Purpose: Phase F3 subphase 1 -- extends the shared `profiles` identity
-- row (001_profiles.sql) with FACULTY-specific academic profile data. One
-- row per FACULTY user, keyed 1-to-1 by `id = profiles.id = auth.users.id`.
-- Same lazy-creation, same-shape pattern as student_profiles
-- (012_student_profiles.sql) and industry_profiles (026_industry_profiles.sql,
-- itself untracked/local but already merged into this branch): the row is
-- created by the app the first time a Faculty member saves their profile,
-- not by a signup trigger -- not every `profiles` row is FACULTY, and a
-- brand-new Faculty account has nothing to store here yet.
--
-- Deliberately NOT included in this migration (F3 subphase 1 is a
-- foundation, not the full target Faculty-profile spec):
--   - full_name, email, username, role -- already live on `profiles`; not
--     duplicated here, and this table has no role column, so it cannot be
--     used to change a user's role.
--   - A normalized skills structure (a future faculty_skills table with
--     its own catalog, mirroring student_skills) -- no such catalog-linked
--     structure exists for Faculty yet; a flat array here couldn't be
--     matched/deduplicated against anything, same reasoning
--     012_student_profiles.sql already gives for omitting technical_skills.
--   - Publications, certifications, structured industry-experience
--     history -- no existing structure to extend, out of scope for this
--     subphase; may land with a later Faculty phase if the product
--     actually needs them.
--   - Profile photo / file storage -- no Supabase Storage bucket exists
--     yet, same limitation 012_student_profiles.sql documents.
--   - profile_completion -- deliberately NOT a stored column: it's fully
--     derivable from which fields are non-null, so storing it would just
--     be denormalized state that could drift from the real data for no
--     benefit. Computed by the API/frontend instead.
--   - assessment_capability data (027/035) -- entirely separate from this
--     table; a Faculty member's capabilities are not part of their
--     academic profile.

create table if not exists faculty_profiles (
  id uuid primary key references profiles (id) on delete cascade,

  -- Academic identity (full_name and email already live on profiles)
  designation text,
  department text,
  institution_name text,

  -- Contact (phone format mirrors student_profiles/industry_profiles exactly)
  phone text,
  constraint faculty_profiles_phone_format check (phone ~ '^[0-9+\-\s()]{7,20}$'),

  -- Professional
  bio text,
  expertise_areas text[] not null default '{}',
  -- Single scalar field for "industry exposure" rather than a structured
  -- history table -- same "don't overbuild ahead of a real requirement"
  -- reasoning as the exclusions above.
  years_of_experience int check (years_of_experience >= 0 and years_of_experience <= 60),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table faculty_profiles enable row level security;

-- Restricts faculty_profiles access to callers whose OWN profiles.role is
-- 'FACULTY' -- same defence-in-depth reasoning as student_profiles'
-- equivalent policies: without the is_faculty() check, a non-Faculty
-- account would still pass the bare `auth.uid() = id` ownership check.
-- Deliberately self-only for this subphase: no policy yet grants any
-- other role (student, industry, institution, admin) visibility into a
-- Faculty profile -- broader read access (e.g. for a future mentorship
-- directory) is an additive policy for whichever later phase actually
-- needs it, not something to pre-build speculatively here.
create policy "Faculty can view their own faculty profile"
  on faculty_profiles for select
  to authenticated
  using (auth.uid() = id and public.is_faculty(auth.uid()));

create policy "Faculty can insert their own faculty profile"
  on faculty_profiles for insert
  to authenticated
  with check (auth.uid() = id and public.is_faculty(auth.uid()));

create policy "Faculty can update their own faculty profile"
  on faculty_profiles for update
  to authenticated
  using (auth.uid() = id and public.is_faculty(auth.uid()))
  with check (auth.uid() = id and public.is_faculty(auth.uid()));

-- No delete policy -- matches student_profiles/industry_profiles (neither
-- has one either).

-- Reuses the generic set_updated_at() trigger function already defined in
-- 012_student_profiles.sql -- not redefined here.
drop trigger if exists faculty_profiles_set_updated_at on faculty_profiles;

create trigger faculty_profiles_set_updated_at
  before update on faculty_profiles
  for each row
  execute procedure public.set_updated_at();
