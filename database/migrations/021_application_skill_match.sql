-- Migration: 021_application_skill_match
-- Purpose: the ONE narrowly-scoped data path that lets an INDUSTRY user
-- obtain the job-relevant skill overlap for an application submitted to a
-- posting THEY OWN -- the input to deterministic candidate/opportunity
-- matching (Phase 9). Nothing else about the applicant is exposed.
--
-- Background: Industry has no RLS path to student_skills / student_profiles
-- / profiles (001_profiles.sql, 003_skills.sql, 012_student_profiles.sql) --
-- deliberately. Rather than add a broad "Industry can read student skills"
-- policy (which would leak the applicant's whole skill inventory), this
-- migration follows the project's existing pattern of a SECURITY DEFINER
-- READ HELPER granted to `authenticated`, scoped entirely by the function's
-- own logic -- exactly like public.get_email_for_identifier (001_profiles.sql)
-- and public.is_student / public.is_industry.
--
-- What this function discloses, and ONLY this, and ONLY for an application
-- whose posting the CALLER owns -- for each skill the caller's own posting
-- requires:
--     skill_id, skill_name, required_level, importance,
--     candidate_has, candidate_level, candidate_verified
--
-- The row source is the requirements table (internship_skills / job_skills)
-- LEFT JOIN student_skills, so:
--   * a student_skill the posting does not require can never appear;
--   * the applicant's total skill count / breadth is never revealed;
--   * no profiles / student_profiles / assessment column is referenced;
--   * another company's application returns zero rows (the ownership CTE
--     is empty -> the requirements CTE is empty -> the result is empty).
--
-- No existing RLS policy is modified. RLS stays enabled everywhere. The
-- backend calls this through build_user_client(access_token) (Postgres
-- role `authenticated`) -- never service_role. auth.uid() inside a
-- SECURITY DEFINER function is still the CALLING user's id (it reads the
-- request JWT), so swapping in another company's application UUID yields
-- no rows -- same guarantee public.prevent_student_status_override and
-- public.set_application_industry_id rely on (020_applications.sql).

create or replace function public.application_skill_match(p_application_id uuid)
returns table (
  skill_id uuid,
  skill_name text,
  required_level text,
  importance text,
  candidate_has boolean,
  candidate_level text,
  candidate_verified boolean
)
language sql
security definer
set search_path = ''
stable
as $$
  with owned_application as (
    -- Ownership gate. The caller must be an INDUSTRY account AND the
    -- posting owner of this exact application. Fails -> zero rows below.
    select
      a.student_id,
      a.opportunity_type,
      a.internship_id,
      a.job_id
    from public.applications a
    where a.id = p_application_id
      and a.industry_id = auth.uid()
      and public.is_industry(auth.uid())
  ),
  requirements as (
    -- Exactly one branch fires per application (opportunity_type is
    -- INTERNSHIP xor JOB, enforced by applications_opportunity_matches_type).
    -- internship_skills / job_skills each have a unique (posting, skill_id)
    -- constraint, so this yields at most one row per skill_id; UNION (not
    -- UNION ALL) is belt-and-suspenders against future schema drift.
    select isk.skill_id, isk.required_level, isk.importance
    from owned_application oa
    join public.internship_skills isk
      on oa.opportunity_type = 'INTERNSHIP'
     and isk.internship_id = oa.internship_id
    union
    select jsk.skill_id, jsk.required_level, jsk.importance
    from owned_application oa
    join public.job_skills jsk
      on oa.opportunity_type = 'JOB'
     and jsk.job_id = oa.job_id
  )
  select
    r.skill_id,
    s.name as skill_name,
    r.required_level,
    r.importance,
    (ss.skill_id is not null) as candidate_has,
    ss.proficiency_level as candidate_level,
    coalesce(ss.is_verified, false) as candidate_verified
  from requirements r
  join public.skills s on s.id = r.skill_id
  left join public.student_skills ss
    on ss.skill_id = r.skill_id
   and ss.student_id = (select oa.student_id from owned_application oa);
$$;

-- Close off PUBLIC's default EXECUTE, then grant to authenticated only --
-- same hardening as public.is_industry (017_industry_profiles.sql).
revoke all on function public.application_skill_match(uuid) from public;
revoke all on function public.application_skill_match(uuid) from anon;
grant execute on function public.application_skill_match(uuid) to authenticated;
