-- Migration: 028_forbid_internship_job_deletes
-- Purpose: extend the hard-delete lockdown from
-- 027_forbid_industry_record_deletes.sql to the two Phase 9 Industry
-- posting tables that carry the identical exposure -- `internships`
-- (018_internships.sql) and `jobs` (019_jobs.sql) -- under the same
-- product decision:
--
--     HARD DELETE MUST NOT BE POSSIBLE FOR INDUSTRY RECORDS.
--
-- Both tables currently grant their owner one `for all` policy
-- ("Industry can manage their own internships" / "... jobs"), and
-- `for all` includes DELETE. As with the Phase 10 tables, the
-- application never deletes a posting: internship_service /
-- job_service only ever call .insert()/.update() on `internships` /
-- `jobs`, there is no DELETE API route, and the lifecycle is
-- status-only (DRAFT -> PUBLISHED -> CLOSED -> ARCHIVED). Both archive
-- helpers' docstrings say so outright -- "This is the closest thing to
-- a delete -- rows are never physically removed (018's FKs from
-- applications are ON DELETE RESTRICT, and recruitment history must
-- survive)". But the `for all` policy still lets an owner issue a
-- direct `DELETE FROM internships WHERE ...` against Supabase's REST
-- endpoint with their own JWT.
--
-- Fix (identical shape to migration 027): replace each single `for all`
-- owner policy with three per-command policies -- SELECT, INSERT,
-- UPDATE -- carrying the exact same ownership predicate. With no DELETE
-- policy present and RLS enabled, DELETE is denied for every
-- RLS-governed caller.
--
-- Behaviour preserved exactly:
--   * SELECT/INSERT/UPDATE for the owner use byte-identical predicates
--     to the dropped `for all` policy -- create / edit / publish /
--     close / archive all keep working unchanged.
--   * The public "Authenticated users can view published internships"
--     / "... jobs" SELECT policies are untouched.
--   * service_role continues to bypass RLS entirely (BYPASSRLS).
--
-- Deliberately OUT OF SCOPE (no change here) -- repository evidence
-- proves DELETE is REQUIRED on these:
--   * internship_skills (018) and job_skills (019) keep their existing
--     `for all` owner policies ("Industry can manage skills for their
--     own internships" / "... jobs"). internship_service._replace_skills
--     and job_service._replace_skills legitimately run
--     `client.table("<x>_skills").delete().eq("<x>_id", ...)` on every
--     skill-list edit, then re-insert. Removing DELETE there would break
--     editing a posting's required skills. Those child rows are not
--     "the record" -- they are mutable content of a draft/live posting,
--     and are also `on delete cascade` from their parent (which itself
--     can no longer be deleted after this migration).
--   * jobs / internships FKs, triggers, indexes, and the published-view
--     policies -- untouched.
--   * Recruitment (020_applications.sql), Analytics, and
--     Student/Faculty/Institution RLS -- untouched.
--
-- Idempotent: every statement is `drop policy if exists` + `create
-- policy`, matching migrations 001-027.

-- ============================================================
-- 018_internships -- public.internships
-- ============================================================

drop policy if exists "Industry can manage their own internships" on internships;

drop policy if exists "Industry can view their own internships" on internships;
create policy "Industry can view their own internships"
  on internships for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can insert their own internships" on internships;
create policy "Industry can insert their own internships"
  on internships for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update their own internships" on internships;
create policy "Industry can update their own internships"
  on internships for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- ============================================================
-- 019_jobs -- public.jobs
-- ============================================================

drop policy if exists "Industry can manage their own jobs" on jobs;

drop policy if exists "Industry can view their own jobs" on jobs;
create policy "Industry can view their own jobs"
  on jobs for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can insert their own jobs" on jobs;
create policy "Industry can insert their own jobs"
  on jobs for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update their own jobs" on jobs;
create policy "Industry can update their own jobs"
  on jobs for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   select tablename, policyname, cmd
--   from pg_policies
--   where schemaname = 'public'
--     and tablename in ('internships', 'jobs')
--   order by tablename, cmd, policyname;
--
-- Expect: for `internships` and `jobs`, cmd values are only SELECT /
-- INSERT / UPDATE (owner + the pre-existing public "view published"
-- SELECT). There must be NO policy with cmd = 'DELETE' or cmd = 'ALL'
-- on either table, so a DELETE by any `authenticated` caller returns
-- 0 rows / is denied.
--
-- internship_skills / job_skills are intentionally unchanged and still
-- show cmd = 'ALL' for their owner policy -- that is required by
-- _replace_skills().
-- ============================================================
