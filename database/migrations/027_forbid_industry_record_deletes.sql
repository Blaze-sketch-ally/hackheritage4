-- Migration: 027_forbid_industry_record_deletes
-- Purpose: close a hard-delete gap found during the Phase 10 Industry
-- portal hardening audit, per an explicit product decision:
--
--     HARD DELETE MUST NOT BE POSSIBLE FOR INDUSTRY RECORDS.
--
-- The five Phase 10 Industry resource tables (022-026) each grant their
-- owner a single `for all` policy:
--
--     create policy "Industry can manage their own <X>"
--       on <table> for all
--       to authenticated
--       using      (auth.uid() = industry_id and public.is_industry(auth.uid()))
--       with check (auth.uid() = industry_id and public.is_industry(auth.uid()));
--
-- `for all` covers SELECT/INSERT/UPDATE **and DELETE**. The application
-- never exposes deletion -- there is no DELETE API route, the service
-- layer only ever calls .insert()/.update() on these tables, and the
-- documented lifecycle is status-only (DRAFT -> PUBLISHED -> CLOSED ->
-- ARCHIVED for the postings; DRAFT -> SENT -> ACCEPTED/REJECTED ->
-- ACTIVE -> COMPLETED, plus CANCELLED, for collaborations). Every
-- archive helper's own docstring calls ARCHIVE "the closest thing to a
-- delete -- rows are never physically removed", and
-- 026_industry_collaborations.sql states outright that "collaborations
-- are historical records; cancellation is a status (CANCELLED), never a
-- row deletion". But the `for all` policy still lets an owner issue a
-- direct `DELETE FROM ...` against Supabase's REST endpoint with their
-- own JWT and permanently destroy their own row.
--
-- Fix: replace each single `for all` owner policy with three explicit
-- per-command policies -- SELECT, INSERT, UPDATE -- carrying the exact
-- same ownership predicate. With no DELETE policy present and RLS
-- enabled, DELETE is denied for every RLS-governed caller. This is the
-- same shape already used by public.applications (020_applications.sql:
-- separate "view" / "apply" / "withdraw" / "update" policies, "No delete
-- policy for either role -- applications are recruitment history") and by
-- public.industry_profiles (017_industry_profiles.sql: separate
-- view/insert/update, "No delete policy -- matches student_profiles").
--
-- Behaviour preserved exactly:
--   * SELECT/INSERT/UPDATE for the owner are byte-identical predicates
--     to the dropped `for all` policy, so create / edit / publish /
--     close / archive / cancel / send / activate / complete all keep
--     working unchanged.
--   * The public "view published" policies on 022-025 are untouched.
--   * All three recipient policies and all three identity/response
--     triggers on industry_collaborations (026) are untouched.
--   * service_role continues to bypass RLS entirely (BYPASSRLS) -- any
--     future privileged/GDPR-style deletion path is unaffected.
--
-- Deliberately OUT OF SCOPE (no change here):
--   * internships / jobs (018_internships.sql, 019_jobs.sql) carry the
--     identical `for all` owner policy and the same latent DELETE
--     exposure. They are Phase 9 recruitment surface, were not part of
--     this audit's stated scope (022-026), and internship_skills /
--     job_skills legitimately depend on owner DELETE (the service layer's
--     _replace_skills() does `DELETE FROM <x>_skills WHERE ...` on every
--     skill-list edit). Extending the same treatment to the postings
--     (but NOT their _skills child tables) is a recommended follow-up,
--     tracked separately.
--   * industry_profiles already has no delete policy (017) -- nothing to do.
--   * Analytics (011_analytics.sql) -- untouched.
--
-- Idempotent: every statement is `drop policy if exists` + `create
-- policy`, matching the convention used throughout migrations 001-026.

-- ============================================================
-- 022_industry_projects -- public.industry_projects
-- ============================================================

drop policy if exists "Industry can manage their own projects" on industry_projects;

drop policy if exists "Industry can view their own projects" on industry_projects;
create policy "Industry can view their own projects"
  on industry_projects for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can insert their own projects" on industry_projects;
create policy "Industry can insert their own projects"
  on industry_projects for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update their own projects" on industry_projects;
create policy "Industry can update their own projects"
  on industry_projects for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- ============================================================
-- 023_industry_training -- public.industry_training
-- ============================================================

drop policy if exists "Industry can manage their own training" on industry_training;

drop policy if exists "Industry can view their own training" on industry_training;
create policy "Industry can view their own training"
  on industry_training for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can insert their own training" on industry_training;
create policy "Industry can insert their own training"
  on industry_training for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update their own training" on industry_training;
create policy "Industry can update their own training"
  on industry_training for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- ============================================================
-- 024_industry_workshops -- public.industry_workshops
-- ============================================================

drop policy if exists "Industry can manage their own workshops" on industry_workshops;

drop policy if exists "Industry can view their own workshops" on industry_workshops;
create policy "Industry can view their own workshops"
  on industry_workshops for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can insert their own workshops" on industry_workshops;
create policy "Industry can insert their own workshops"
  on industry_workshops for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update their own workshops" on industry_workshops;
create policy "Industry can update their own workshops"
  on industry_workshops for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- ============================================================
-- 025_industry_mentorship -- public.industry_mentorship
-- ============================================================

drop policy if exists "Industry can manage their own mentorship opportunities" on industry_mentorship;

drop policy if exists "Industry can view their own mentorship opportunities" on industry_mentorship;
create policy "Industry can view their own mentorship opportunities"
  on industry_mentorship for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can insert their own mentorship opportunities" on industry_mentorship;
create policy "Industry can insert their own mentorship opportunities"
  on industry_mentorship for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update their own mentorship opportunities" on industry_mentorship;
create policy "Industry can update their own mentorship opportunities"
  on industry_mentorship for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- ============================================================
-- 026_industry_collaborations -- public.industry_collaborations
--
-- Only the Industry-owner policy is split here. The recipient policies
-- ("Recipients can view collaborations addressed to them",
-- "Recipients can respond to their own sent proposals") are already
-- SELECT-only / UPDATE-only and are left exactly as 026 defined them.
-- ============================================================

drop policy if exists "Industry can manage their own collaborations" on industry_collaborations;

drop policy if exists "Industry can view their own collaborations" on industry_collaborations;
create policy "Industry can view their own collaborations"
  on industry_collaborations for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can insert their own collaborations" on industry_collaborations;
create policy "Industry can insert their own collaborations"
  on industry_collaborations for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update their own collaborations" on industry_collaborations;
create policy "Industry can update their own collaborations"
  on industry_collaborations for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   select tablename, policyname, cmd
--   from pg_policies
--   where schemaname = 'public'
--     and tablename in ('industry_projects','industry_training',
--                       'industry_workshops','industry_mentorship',
--                       'industry_collaborations')
--   order by tablename, cmd, policyname;
--
-- Expect: for every table above, cmd values are only SELECT / INSERT /
-- UPDATE (plus the pre-existing public "view published" SELECT on
-- 022-025 and the recipient SELECT/UPDATE on collaborations). There must
-- be NO policy with cmd = 'DELETE' or cmd = 'ALL' on any of them, so a
-- DELETE by any `authenticated` caller returns 0 rows / is denied.
-- ============================================================
