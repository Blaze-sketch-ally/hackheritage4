-- Migration: 039_institution_student_directory
-- Purpose: the minimum additional read access an INSTITUTION account
-- needs to power a real Student Directory (list + detail) for its OWN
-- linked students (student_profiles.institution_id = auth.uid(), from
-- 037_institution_tenancy.sql / 038_institution_link_requests.sql).
-- Nothing here changes STUDENT/INDUSTRY write access, and nothing here
-- is a service_role bypass -- every read added below is either a new,
-- narrowly-scoped SELECT policy or a SECURITY DEFINER function that
-- re-derives the exact same institution-ownership predicate already
-- established in 037.
--
-- Two distinct walls this migration climbs, both already-seen shapes in
-- this schema:
--
-- 1. `profiles` has no institution-facing SELECT policy at all (only
--    "Users can view their own profile"), so an institution-scoped
--    client cannot read a linked student's full_name/username/avatar_url
--    via any join. Same wall application_applicant_names (036) and
--    collaboration_counterparty_names (029) already climb for Industry
--    -- institution_student_names() is that same fix, scoped by
--    student_profiles.institution_id instead of applications.industry_id.
--
-- 2. internships/jobs are only readable to a non-owner while
--    status = 'PUBLISHED' (018/019). An institution's own student may
--    have applied to a posting that has since been CLOSED/ARCHIVED, which
--    would silently make that application's opportunity title
--    unreadable through the ordinary RLS-scoped path.
--    institution_visible_opportunity_titles() resolves the title
--    regardless of current publish status, but ONLY for a posting one of
--    the institution's own linked students has actually applied to --
--    never a general "read any posting" escape hatch.
--
-- ============================================================
-- Institution-scoped SELECT policies (additive, read-only)
-- ============================================================

-- ---- Portfolio (student_projects / student_certifications / student_achievements) ----
-- All three are otherwise owner-only (034_student_portfolio.sql). These
-- are read-only additions -- no institution insert/update/delete policy
-- is added on any of them; an institution can view but never edit a
-- student's portfolio.

drop policy if exists "Institution can view their own students' projects" on student_projects;
create policy "Institution can view their own students' projects"
  on student_projects for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and exists (
      select 1 from student_profiles sp
      where sp.id = student_projects.student_id
        and sp.institution_id = auth.uid()
    )
  );

drop policy if exists "Institution can view skills on their own students' projects" on student_project_skills;
create policy "Institution can view skills on their own students' projects"
  on student_project_skills for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and exists (
      select 1 from student_projects p
      join student_profiles sp on sp.id = p.student_id
      where p.id = student_project_skills.project_id
        and sp.institution_id = auth.uid()
    )
  );

drop policy if exists "Institution can view their own students' certifications" on student_certifications;
create policy "Institution can view their own students' certifications"
  on student_certifications for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and exists (
      select 1 from student_profiles sp
      where sp.id = student_certifications.student_id
        and sp.institution_id = auth.uid()
    )
  );

drop policy if exists "Institution can view their own students' achievements" on student_achievements;
create policy "Institution can view their own students' achievements"
  on student_achievements for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and exists (
      select 1 from student_profiles sp
      where sp.id = student_achievements.student_id
        and sp.institution_id = auth.uid()
    )
  );

-- ---- assessments (title/skill/difficulty metadata only) ----
-- Deliberately NOT a blanket "institution can view all assessments"
-- policy (that would hand over the whole curated catalog) -- scoped to
-- only assessments one of the institution's own linked students has
-- actually attempted. assessment_questions / assessment_question_options
-- / assessment_question_answers are UNTOUCHED by this migration -- no
-- question content or answer key becomes visible to any new caller.
drop policy if exists "Institution can view assessments taken by their own students" on assessments;
create policy "Institution can view assessments taken by their own students"
  on assessments for select
  to authenticated
  using (
    public.is_institution(auth.uid())
    and exists (
      select 1 from assessment_attempts aa
      join student_profiles sp on sp.id = aa.student_id
      where aa.assessment_id = assessments.id
        and sp.institution_id = auth.uid()
    )
  );

-- ============================================================
-- institution_student_names -- display identity for the Student
-- Directory list/detail. Exposes full_name, username, avatar_url ONLY --
-- no email, phone, or any other profiles column. Matches the
-- "full_name only" austerity of application_applicant_names (036); adds
-- username + avatar_url on top only because the directory UI needs a
-- profile picture and an unambiguous handle, not because more profile
-- data is safe to expose by default. A caller is only ever returned rows
-- for student ids that are ALREADY linked to them -- re-derived here,
-- not trusted from the input array.
-- ============================================================

create or replace function public.institution_student_names(student_ids uuid[])
returns table (student_id uuid, full_name text, username text, avatar_url text)
language sql
security definer
set search_path = ''
stable
as $$
  select p.id, p.full_name, p.username, p.avatar_url
  from public.profiles p
  join public.student_profiles sp on sp.id = p.id
  where p.id = any(student_ids)
    and sp.institution_id = auth.uid()
    and public.is_institution(auth.uid());
$$;

revoke all on function public.institution_student_names(uuid[]) from public;
revoke all on function public.institution_student_names(uuid[]) from anon;
grant execute on function public.institution_student_names(uuid[]) to authenticated;

-- ============================================================
-- institution_visible_opportunity_titles -- see the migration header
-- comment (wall #2). Returns a title for an internship/job ONLY when the
-- caller is the institution of a student who has an application
-- referencing it -- never a general posting lookup.
-- ============================================================

create or replace function public.institution_visible_opportunity_titles(
  internship_ids uuid[],
  job_ids uuid[]
)
returns table (id uuid, opportunity_type text, title text)
language sql
security definer
set search_path = ''
stable
as $$
  select i.id, 'INTERNSHIP', i.title
  from public.internships i
  where i.id = any(internship_ids)
    and public.is_institution(auth.uid())
    and exists (
      select 1
      from public.applications a
      join public.student_profiles sp on sp.id = a.student_id
      where a.internship_id = i.id
        and sp.institution_id = auth.uid()
    )
  union all
  select j.id, 'JOB', j.title
  from public.jobs j
  where j.id = any(job_ids)
    and public.is_institution(auth.uid())
    and exists (
      select 1
      from public.applications a
      join public.student_profiles sp on sp.id = a.student_id
      where a.job_id = j.id
        and sp.institution_id = auth.uid()
    );
$$;

revoke all on function public.institution_visible_opportunity_titles(uuid[], uuid[]) from public;
revoke all on function public.institution_visible_opportunity_titles(uuid[], uuid[]) from anon;
grant execute on function public.institution_visible_opportunity_titles(uuid[], uuid[]) to authenticated;

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INSTITUTION account: names for its own linked students
--   select * from public.institution_student_names(
--     array(select id from public.student_profiles where institution_id = auth.uid())
--   );
--
--   -- as any caller, for a student id NOT linked to them: 0 rows
--   select * from public.institution_student_names(array['<other-institution-student-id>'::uuid]);
--
--   -- as a STUDENT: 0 rows from either function -- both require
--   -- is_institution(auth.uid()), which is false for a STUDENT caller
-- ============================================================
