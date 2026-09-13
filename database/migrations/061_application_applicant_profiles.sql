-- Migration: 061_application_applicant_profiles
-- Purpose: close the same "raw student_id as identity" gap
-- 036_application_applicant_names.sql closed for `student_name` alone --
-- the Job/Internship Applicants view (application_service.py) currently
-- shows name only, never institution/department/graduation year/skills,
-- unlike the richer per-application profile the Workshop/Project/Training
-- Applicants views already get from workshop_applicant_profiles (056) /
-- project_applicant_profiles (057) / training_applicant_profiles (059).
-- This is that same helper, for `applications` (020).
--
-- Exact same SECURITY DEFINER / ownership-predicate pattern as those three
-- (and as 036 itself, whose ownership check this mirrors verbatim):
-- scoped to "a.industry_id = auth.uid() and is_industry(auth.uid())" --
-- the identical predicate as the applications RLS SELECT policy, so this
-- can never name/profile an applicant for an application the caller does
-- not already own.
--
-- Additive only: no table changed, no existing function replaced (036
-- stays as-is and is still used where only a name is needed, e.g.
-- internship_workspace_service's workspace roster). This is a second,
-- richer alternative for the Applicants view specifically.

create or replace function public.application_applicant_profiles(application_ids uuid[])
returns table (
  application_id uuid,
  student_name text,
  institution_name text,
  department text,
  graduation_year int,
  skills text[]
)
language sql
security definer
set search_path = ''
stable
as $$
  select
    a.id,
    p.full_name,
    sp.institution_name,
    sp.department,
    sp.graduation_year,
    (
      select array_agg(sk.name order by sk.name)
      from public.student_skills ss
      join public.skills sk on sk.id = ss.skill_id
      where ss.student_id = a.student_id
    )
  from public.applications a
  join public.profiles p on p.id = a.student_id
  left join public.student_profiles sp on sp.id = a.student_id
  where a.id = any(application_ids)
    and a.industry_id = auth.uid()
    and public.is_industry(auth.uid());
$$;

revoke all on function public.application_applicant_profiles(uuid[]) from public;
revoke all on function public.application_applicant_profiles(uuid[]) from anon;
grant execute on function public.application_applicant_profiles(uuid[]) to authenticated;
