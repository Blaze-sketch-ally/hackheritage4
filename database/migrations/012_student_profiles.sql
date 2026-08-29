-- Migration: 012_student_profiles
-- Purpose: extends the shared `profiles` identity row (001_profiles.sql)
-- with STUDENT-specific personal, education, and career-preference data.
-- One row per STUDENT user, keyed 1-to-1 by `id = profiles.id =
-- auth.users.id`.
--
-- The row is created lazily by the app the first time a student saves
-- their profile — unlike `profiles`, there is no trigger auto-creating a
-- row here on signup, because not every `profiles` row belongs to a
-- student and a brand-new user has nothing to store here yet.
--
-- Deliberately NOT included in this migration:
--   - full_name, email, username, role — already live on `profiles`;
--     not duplicated here, and this table has no role column at all, so
--     it cannot be used to change a user's role.
--   - technical_skills, soft_skills, programming_languages, tools,
--     domain_knowledge — these need a normalized, queryable structure (a
--     future student_skills table with its own skill catalog), not a
--     flat array that can't be deduplicated or matched against postings.
--   - Resume/file storage — no Supabase Storage bucket exists yet.
--   - LinkedIn/GitHub/portfolio links, academic_year, profile_completion
--     — out of scope for this migration; may land with later features.

create table if not exists student_profiles (
  id uuid primary key references profiles (id) on delete cascade,

  -- Personal (full_name and email already live on profiles — not duplicated here)
  phone text,
  -- Not-in-the-future validation is done at the application layer, not
  -- here — deliberately no `check (date_of_birth <= current_date)`.
  date_of_birth date,
  gender text,
  location text,
  constraint phone_format check (phone ~ '^[0-9+\-\s()]{7,20}$'),

  -- Education
  institution_name text,
  department text,
  degree text,
  graduation_year int check (graduation_year between 2000 and 2100),
  -- Kept as two separate nullable fields rather than one generic column:
  -- institutions grade on CGPA (0-10) or percentage/marks (0-100), and a
  -- student only ever fills in whichever one applies to them.
  cgpa numeric(4, 2) check (cgpa >= 0 and cgpa <= 10),
  percentage numeric(5, 2) check (percentage >= 0 and percentage <= 100),

  -- Career
  career_goals text,
  preferred_roles text[] not null default '{}',
  preferred_locations text[] not null default '{}',
  interests text[] not null default '{}',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table student_profiles enable row level security;

-- Restricts student_profiles access to callers whose OWN profiles.role is
-- 'STUDENT' — a FACULTY/INDUSTRY/INSTITUTION/ADMIN user, or a user who
-- hasn't picked a role yet, cannot create or see a student_profiles row
-- for themselves, even though they'd otherwise pass the `auth.uid() = id`
-- ownership check.
--
-- SECURITY DEFINER + a pinned empty search_path so this function reads
-- `profiles` directly, bypassing profiles' own RLS policies for this one
-- read, rather than having student_profiles' policy indirectly trigger
-- profiles' policy evaluation. This is the same pattern already used by
-- get_email_for_identifier and prevent_self_admin_promotion in this
-- project — it avoids any risk of RLS-policy recursion by construction,
-- since the check never re-enters a policy-evaluated query.
create or replace function public.is_student(profile_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.profiles where id = profile_id and role = 'STUDENT'
  );
$$;

-- Explicitly close off the default PUBLIC execute privilege Postgres
-- grants on new functions, then grant only to authenticated — this is a
-- role-check helper, not something anon or unintended callers should be
-- able to invoke.
revoke all on function public.is_student(uuid) from public;
grant execute on function public.is_student(uuid) to authenticated;

create policy "Students can view their own student profile"
  on student_profiles for select
  to authenticated
  using (auth.uid() = id and public.is_student(auth.uid()));

create policy "Students can insert their own student profile"
  on student_profiles for insert
  to authenticated
  with check (auth.uid() = id and public.is_student(auth.uid()));

create policy "Students can update their own student profile"
  on student_profiles for update
  to authenticated
  using (auth.uid() = id and public.is_student(auth.uid()))
  with check (auth.uid() = id and public.is_student(auth.uid()));

-- Generic updated_at-maintenance trigger function. No equivalent exists
-- yet anywhere in this project (profiles.updated_at is set once at insert
-- and never auto-maintained) — named generically, not
-- student_profiles-specific, so later migrations (student_skills,
-- assessments, etc.) can attach the same function instead of redefining
-- it.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Trigger execution doesn't require EXECUTE privilege on the trigger
-- function for the invoking role (Postgres calls it internally as part
-- of the DML statement) — revoking PUBLIC access here doesn't affect the
-- trigger below, it just closes off direct invocation as a normal call.
revoke all on function public.set_updated_at() from public;

drop trigger if exists student_profiles_set_updated_at on student_profiles;

create trigger student_profiles_set_updated_at
  before update on student_profiles
  for each row
  execute procedure public.set_updated_at();
