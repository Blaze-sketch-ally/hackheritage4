-- Migration: 058_fix_portfolio_industry_view_after_applications_migration
-- Purpose: fixes a genuine live bug found during the cross-branch
-- integration pass -- 025_portfolio_projects_and_certifications.sql's
-- "Industry can view projects/certifications of their own applicants"
-- policies join `applications a join opportunities o on o.id =
-- a.opportunity_id`. That column/relationship no longer exists:
-- 055_applications.sql replaced `applications` with an
-- internship_id/job_id-keyed schema (the one already live in production
-- -- see that migration's own header for the full history). Any SELECT
-- against portfolio_projects/portfolio_certifications by an INDUSTRY
-- caller fails outright (the policy's own query references a column that
-- doesn't exist), not merely returns zero rows -- this has been broken
-- since 055 (or whatever migration originally introduced that schema on
-- the live project) was applied, independent of anything else in this
-- integration pass.
--
-- Fix: re-point both policies at the surviving schema -- an application
-- now references EITHER an internship OR a job (never both,
-- applications_opportunity_matches_type), each with its own industry_id.
-- The replacement mirrors that OR directly rather than introducing a new
-- view/helper -- same shape as this migration's own sibling checks
-- throughout 055_applications.sql.
--
-- Also extends both policies to student_achievements
-- (052_student_achievements.sql) for consistency: that table shipped
-- later, in this same integration pass, and (per its own migration
-- header) deliberately had NO industry-view policy at all yet. Since an
-- applicant's portfolio view (GET /applications/{id}/portfolio) now
-- returns achievements too (see app.services.portfolio_service.
-- get_student_portfolio), the RLS policy is added here so that read
-- isn't silently empty for achievements specifically.

drop policy if exists "Industry can view projects of their own applicants" on portfolio_projects;
create policy "Industry can view projects of their own applicants"
  on portfolio_projects for select
  to authenticated
  using (
    public.is_industry(auth.uid())
    and exists (
      select 1
      from applications a
      left join internships i on i.id = a.internship_id
      left join jobs j on j.id = a.job_id
      where a.student_id = portfolio_projects.student_id
        and (i.industry_id = auth.uid() or j.industry_id = auth.uid())
    )
  );

drop policy if exists "Industry can view certifications of their own applicants" on portfolio_certifications;
create policy "Industry can view certifications of their own applicants"
  on portfolio_certifications for select
  to authenticated
  using (
    public.is_industry(auth.uid())
    and exists (
      select 1
      from applications a
      left join internships i on i.id = a.internship_id
      left join jobs j on j.id = a.job_id
      where a.student_id = portfolio_certifications.student_id
        and (i.industry_id = auth.uid() or j.industry_id = auth.uid())
    )
  );

drop policy if exists "Industry can view achievements of their own applicants" on student_achievements;
create policy "Industry can view achievements of their own applicants"
  on student_achievements for select
  to authenticated
  using (
    public.is_industry(auth.uid())
    and exists (
      select 1
      from applications a
      left join internships i on i.id = a.internship_id
      left join jobs j on j.id = a.job_id
      where a.student_id = student_achievements.student_id
        and (i.industry_id = auth.uid() or j.industry_id = auth.uid())
    )
  );
