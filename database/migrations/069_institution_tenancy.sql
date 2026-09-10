-- Migration: 069_institution_tenancy
-- Purpose: the INSTITUTION TENANCY FOUNDATION -- establishes a real,
-- FK-backed relationship between an INSTITUTION account and the students
-- who belong to it, plus the minimum RLS an Institution/TPO dashboard
-- needs to read its own students' data. Nothing in this migration touches
-- Student/Industry/Faculty write access or existing policies -- every
-- change here is either a new table or a new, additive SELECT policy.
--
-- Prior state (see the 2026-09-04 architecture-discovery audit): an
-- INSTITUTION account had NO way to determine "which students are mine".
-- `student_profiles.institution_name` (012_student_profiles.sql) is
-- free text, entered by the student, with no foreign key to any account
-- -- it is explicitly NOT used as the tenancy mechanism here (a text
-- match is unenforceable and can silently leak or omit rows). This
-- migration adds a real `institution_id` column instead and leaves
-- `institution_name` untouched, in place, for whatever the student
-- profile UI currently uses it for.
--
-- ============================================================
-- institution_profiles -- the Institution entity.
--
-- Same 1:1-with-profiles pattern as student_profiles (012) and
-- industry_profiles (017): id references profiles(id), created lazily
-- (no row required to exist for an INSTITUTION account to already be a
-- valid FK target for student_profiles.institution_id below -- an
-- institution must be linkable before it has ever filled in this
-- profile, exactly like industry_id on internships/jobs referencing
-- profiles(id) rather than industry_profiles(id)).
-- ============================================================

create table if not exists institution_profiles (
  id uuid primary key references profiles (id) on delete cascade,

  institution_name text,
  institution_type text,
  location text,
  website_url text,
  contact_phone text,
  constraint institution_profiles_phone_format check (contact_phone ~ '^[0-9+\-\s()]{7,20}$'),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table institution_profiles enable row level security;

-- Ownership policies, same shape as industry_profiles' own policies in
-- 017_industry_profiles.sql. is_institution() already exists
-- (026_industry_collaborations.sql) -- reused, not redefined.
drop policy if exists "Institution can view their own institution profile" on institution_profiles;
create policy "Institution can view their own institution profile"
  on institution_profiles for select
  to authenticated
  using (auth.uid() = id and public.is_institution(auth.uid()));

drop policy if exists "Institution can insert their own institution profile" on institution_profiles;
create policy "Institution can insert their own institution profile"
  on institution_profiles for insert
  to authenticated
  with check (auth.uid() = id and public.is_institution(auth.uid()));

drop policy if exists "Institution can update their own institution profile" on institution_profiles;
create policy "Institution can update their own institution profile"
  on institution_profiles for update
  to authenticated
  using (auth.uid() = id and public.is_institution(auth.uid()))
  with check (auth.uid() = id and public.is_institution(auth.uid()));

-- Same reasoning as "Authenticated users can view industry profiles"
-- (017_industry_profiles.sql): institution display info (name/location/
-- website) is non-sensitive and needs to be readable by any signed-in
-- user -- e.g. a future student-facing "select your institution" picker,
-- or a company viewing which institution it is collaborating with. No
-- delete policy, matching student_profiles/industry_profiles.
drop policy if exists "Authenticated users can view institution profiles" on institution_profiles;
create policy "Authenticated users can view institution profiles"
  on institution_profiles for select
  to authenticated
  using (true);

drop trigger if exists institution_profiles_set_updated_at on institution_profiles;
create trigger institution_profiles_set_updated_at
  before update on institution_profiles
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- student_profiles.institution_id -- the tenancy link.
--
-- Nullable: every existing student_profiles row gets institution_id =
-- NULL on this migration (the column is new, so there is nothing to
-- backfill it from). See this migration's approval report for why no
-- automatic backfill from institution_name is performed -- free-text
-- values ("CSE", "XYZ College", "xyz college", typos, abbreviations)
-- cannot be safely resolved to a specific institution ACCOUNT (a name
-- string, however normalized, is not proof of affiliation with that
-- account) without a human-reviewed confirmation step, which is a
-- separate, explicitly-approved onboarding/linking feature -- not part
-- of this schema migration. Every existing student is reported as
-- "unmapped" by this migration; none are guessed into place.
--
-- References profiles(id), not institution_profiles(id) -- same
-- reasoning as industry_id throughout this schema: an institution
-- account is a valid link target from the moment it signs up, whether or
-- not it has ever saved an institution_profiles row.
--
-- ON DELETE SET NULL (not CASCADE, not RESTRICT): a student's own record
-- must survive their institution's account being removed -- unlike an
-- industry's recruitment history (which the schema protects with
-- RESTRICT because deleting it would destroy applicant history), a
-- student losing their institution link is a benign, recoverable state
-- (nullable, can be re-linked), not data that must never be lost.
-- ============================================================

alter table student_profiles
  add column if not exists institution_id uuid references profiles (id) on delete set null;

create index if not exists student_profiles_institution_id_idx on student_profiles (institution_id);

-- Validates (never derives) institution_id: a student -- or whatever
-- future onboarding flow sets this column -- may only link to a real
-- INSTITUTION-role account. Unlike set_application_industry_id /
-- set_collaboration_recipient_type (which OVERWRITE a derived value),
-- this only guards a value the caller supplies directly, because
-- student_profiles has no "referenced entity" to derive it from the way
-- an application derives industry_id from its posting. Security
-- boundary, not overwritten silently -- a bad value must fail loudly,
-- not resolve to something the caller didn't intend.
create or replace function public.validate_student_institution_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.institution_id is not null and not public.is_institution(new.institution_id) then
    raise exception 'institution_id must reference an INSTITUTION account.' using errcode = '23514';
  end if;

  return new;
end;
$$;

revoke all on function public.validate_student_institution_id() from public;

drop trigger if exists student_profiles_validate_institution_id on student_profiles;
create trigger student_profiles_validate_institution_id
  before insert or update on student_profiles
  for each row
  execute procedure public.validate_student_institution_id();

-- ============================================================
-- Institution-scoped RLS -- additive SELECT-only policies.
--
-- Every policy below follows the exact same shape:
--   public.is_institution(auth.uid())            <- caller is a real Institution
--   and exists (... student_profiles sp
--               where sp.id = <table>.student_id
--                 and sp.institution_id = auth.uid())   <- row belongs to MY students
--
-- None of these broaden STUDENT or INDUSTRY access at all -- they are new
-- policies alongside the existing ones (Postgres RLS policies are OR'd
-- together), and none use `using (true)` on student- or application-level
-- data. A student with institution_id = NULL (the default for every
-- existing row until explicitly linked) is invisible to every policy
-- here, for every institution -- exactly the safe default this migration
-- is designed to produce.
-- ============================================================

-- ---- student_profiles ----

drop policy if exists "Institution can view their own students' profiles" on student_profiles;
create policy "Institution can view their own students' profiles"
  on student_profiles for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and institution_id = auth.uid()
  );

-- ---- applications ----
-- Read-only. Institution can never see applications for students it is
-- not linked to, nor influence the applications in any way (no
-- insert/update/delete policy is added here).

drop policy if exists "Institution can view applications from their own students" on applications;
create policy "Institution can view applications from their own students"
  on applications for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and exists (
      select 1 from student_profiles sp
      where sp.id = applications.student_id
        and sp.institution_id = auth.uid()
    )
  );

-- ---- student_skills ----
-- Supports institution-level skill distribution / skill-gap insight.

drop policy if exists "Institution can view their own students' skills" on student_skills;
create policy "Institution can view their own students' skills"
  on student_skills for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and exists (
      select 1 from student_profiles sp
      where sp.id = student_skills.student_id
        and sp.institution_id = auth.uid()
    )
  );

-- ---- assessment_attempts ----
-- Supports an institution-level assessment-participation/performance
-- insight. Deliberately does NOT touch assessment_questions /
-- assessment_question_answers -- the protected answer key remains exactly
-- as locked down as it already is; only the attempt's own score/status is
-- ever institution-readable, never question content or correct answers.

drop policy if exists "Institution can view their own students' assessment attempts" on assessment_attempts;
create policy "Institution can view their own students' assessment attempts"
  on assessment_attempts for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and exists (
      select 1 from student_profiles sp
      where sp.id = assessment_attempts.student_id
        and sp.institution_id = auth.uid()
    )
  );

-- ---- interviews ----
-- Supports an "upcoming interviews for your students" action item.

drop policy if exists "Institution can view interviews for their own students" on interviews;
create policy "Institution can view interviews for their own students"
  on interviews for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and exists (
      select 1 from student_profiles sp
      where sp.id = interviews.student_id
        and sp.institution_id = auth.uid()
    )
  );
