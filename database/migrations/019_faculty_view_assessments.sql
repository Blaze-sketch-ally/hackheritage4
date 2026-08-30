-- Migration: 019_faculty_view_assessments
-- Purpose: fixes a pre-existing (not Phase-1K-introduced) live-database
-- condition found during Phase 1K real-Supabase QA verification --
-- `assessments`' own SELECT policy currently requires
-- is_student(auth.uid()), confirmed directly (`select ... from
-- assessments` returns zero rows for a FACULTY session, non-zero for a
-- STUDENT session on an is_active=true row). This isn't what
-- 004_assessments.sql's own file text shows (a plain
-- `to authenticated using (is_active = true)`, no role check at all) --
-- the live database has diverged from the migration file at some point
-- before this session, the same kind of drift already found and worked
-- around on assessment_questions/options/answer_keys.
--
-- This condition blocks Phase 1K's faculty-facing UI entirely: faculty
-- cannot browse assessments to pick one for question authoring or
-- blueprint configuration, and assessment_blueprint_rules' own SELECT
-- policy (015) depends on an EXISTS subquery against `assessments`,
-- so faculty could not even read a blueprint they had (successfully, at
-- the database level) written.
--
-- The exact live policy name is unknown from this codebase alone (it
-- differs from the file's original name, exactly like the drift already
-- found on assessment_questions) -- this migration drops every name this
-- policy might plausibly be under, all IF EXISTS (a no-op for whichever
-- names don't match), then creates one fresh, clearly-named policy.
--
-- Deliberately conservative: rather than reverting all the way back to
-- 004's original "any authenticated user" text (unknown why the live
-- database narrowed this to students only -- could be an intentional
-- decision this session has no record of), this ADDS faculty alongside
-- the existing student restriction rather than removing it. Widening
-- SELECT to FACULTY is safe either way: assessment title/description/
-- difficulty/duration/question_count carry no sensitive information --
-- every STUDENT can already read any active assessment unconditionally.
-- This migration touches SELECT only; no INSERT/UPDATE/DELETE policy is
-- added or changed here, and assessments still has no write policy for
-- `authenticated` at all (unchanged from 004 -- creating an assessment
-- remains a service_role-only operation, out of Phase 1K's scope).

drop policy if exists "Authenticated users can view active assessments" on assessments;
drop policy if exists "Students can view active assessments" on assessments;

create policy "Students and faculty can view active assessments"
  on assessments for select
  to authenticated
  using (is_active = true and (public.is_student(auth.uid()) or public.is_faculty(auth.uid())));
