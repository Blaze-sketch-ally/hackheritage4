-- Migration: 080_institution_skill_gap
-- Purpose: the ONE narrowly-scoped data path an INSTITUTION needs to power
-- an application-specific Skill Gap Analysis for its OWN linked students --
-- "for student X's application to opportunity Y, how do their skills
-- compare to what Y requires". This migration adds exactly ONE function.
-- It does NOT create a new skill table, a new matching algorithm, or a new
-- assessment system -- the deterministic scoring itself stays entirely in
-- app.services.match_service.compute_match (Phase 9), the SAME function
-- Industry's own GET /applications/{id}/match already uses. This function
-- only supplies that function's input rows, scoped by institution tenancy
-- instead of posting ownership.
--
-- Same wall, same fix, as public.application_skill_match
-- (021_application_skill_match.sql): institution has no RLS path to
-- another account's `internship_skills` / `job_skills` requirements
-- joined against a specific student's `student_skills` in one shot, and
-- broadening the existing per-table SELECT policies to do that join
-- client-side would leak more than intended (e.g. every skill the
-- posting owner never asked about). Instead, a SECURITY DEFINER READ
-- HELPER, exactly like application_skill_match itself and the
-- institution_visible_* functions already established in
-- 071/073/074_institution_*.sql.
--
-- Ownership gate (re-derived from auth.uid() on every call, never trusted
-- from the input): the caller must be an INSTITUTION account, and each
-- requested application's student must be one of the caller's own linked
-- students (student_profiles.institution_id = auth.uid()) -- the EXACT
-- same predicate as "Institution can view applications from their own
-- students" (069_institution_tenancy.sql). An application belonging to a
-- different institution's student -- or no institution at all -- yields
-- zero rows for that application_id, indistinguishable from a
-- non-existent id.
--
-- Accepts an ARRAY of application ids (not a single id, unlike
-- application_skill_match) so the Institution Skill Gap LIST page can
-- resolve every visible application's skill match in one round trip
-- instead of one RPC call per row -- the detail page simply calls this
-- with a one-element array. Grouping the result rows by application_id
-- happens in Python (app.services.institution_skill_gap_service), not here.
--
-- What this function discloses, and ONLY this, and ONLY for an
-- application whose student belongs to the CALLER's own institution --
-- for each skill the application's own posting requires:
--     application_id, skill_id, skill_name, required_level, importance,
--     candidate_has, candidate_level, candidate_verified
--
-- No profiles / student_profiles column, no skill outside what the
-- specific posting requires, and no other institution's data can ever
-- appear -- same disclosure discipline as application_skill_match's own
-- header comment.

create or replace function public.institution_visible_application_skill_match(p_application_ids uuid[])
returns table (
  application_id uuid,
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
  with owned_applications as (
    -- Ownership gate. The caller must be an INSTITUTION account AND the
    -- application's student must be linked to that same institution.
    -- Fails for a given application_id -> zero rows for it below.
    select
      a.id as application_id,
      a.student_id,
      a.opportunity_type,
      a.internship_id,
      a.job_id
    from public.applications a
    join public.student_profiles sp on sp.id = a.student_id
    where a.id = any(p_application_ids)
      and sp.institution_id = auth.uid()
      and public.is_institution(auth.uid())
  ),
  requirements as (
    -- Exactly one branch fires per application (opportunity_type is
    -- INTERNSHIP xor JOB, enforced by applications_opportunity_matches_type,
    -- 020_applications.sql). internship_skills / job_skills each have a
    -- unique (posting, skill_id) constraint, so this yields at most one
    -- row per (application_id, skill_id); UNION (not UNION ALL) is
    -- belt-and-suspenders against future schema drift, matching
    -- application_skill_match's own convention.
    select oa.application_id, oa.student_id, isk.skill_id, isk.required_level, isk.importance
    from owned_applications oa
    join public.internship_skills isk
      on oa.opportunity_type = 'INTERNSHIP'
     and isk.internship_id = oa.internship_id
    union
    select oa.application_id, oa.student_id, jsk.skill_id, jsk.required_level, jsk.importance
    from owned_applications oa
    join public.job_skills jsk
      on oa.opportunity_type = 'JOB'
     and jsk.job_id = oa.job_id
  )
  select
    r.application_id,
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
   and ss.student_id = r.student_id;
$$;

-- Close off PUBLIC's default EXECUTE, then grant to authenticated only --
-- same hardening as application_skill_match and every institution_visible_*
-- function before it.
revoke all on function public.institution_visible_application_skill_match(uuid[]) from public;
revoke all on function public.institution_visible_application_skill_match(uuid[]) from anon;
grant execute on function public.institution_visible_application_skill_match(uuid[]) to authenticated;

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INSTITUTION: skill-match rows for one of its own
--   -- linked student's applications
--   select * from public.institution_visible_application_skill_match(
--     array(
--       select a.id from public.applications a
--       join public.student_profiles sp on sp.id = a.student_id
--       where sp.institution_id = auth.uid()
--     )
--   );
--
--   -- as a DIFFERENT institution, passing the same application ids: 0 rows
--
--   -- as a STUDENT or INDUSTRY caller: 0 rows -- requires
--   -- is_institution(auth.uid()), which is false for either
-- ============================================================
