-- Migration: 020_student_view_own_attempt_questions
-- Purpose: Phase 1K final hardening -- completes the fix started by the
-- is_question_in_attempt() application-code change (save_answer no
-- longer live-gates on is_active/review_status). That change alone was
-- not sufficient: `GET /attempts/{id}/questions` still could not RENDER
-- a persisted-but-deactivated question's content at all, because the
-- existing student-facing SELECT policies on assessment_questions and
-- assessment_question_options ("Students can view approved active
-- questions" / "...options for visible questions") both require
-- is_active = true and review_status = 'APPROVED' unconditionally --
-- there was no path for a student to see a question that WAS approved
-- and active at attempt-creation time but has since been deactivated,
-- even though that question legitimately remains part of their own
-- persisted attempt.
--
-- This is the exact same class of gap 017/018 already fixed for
-- FACULTY visibility of the question bank -- resolved the same way:
-- widen SELECT (never touch any write policy), scoped narrowly this
-- time to "a question is part of one of MY OWN attempts," not opened
-- broadly. A student can never see a question this way that wasn't
-- legitimately selected into one of their own attempts by the trusted
-- create_assessment_attempt() RPC -- and that RPC only ever selects
-- APPROVED + active + OBJECTIVE questions at selection time, so nothing
-- a student was never meant to see becomes visible; only ALREADY-SEEN
-- content stays visible after a later deactivation.
--
-- Does not touch assessment_question_answers (the answer key) at all --
-- "Students can view answer keys for their own completed attempts"
-- already scopes to attempt.status = 'COMPLETED', independent of
-- question is_active, and answer keys must never be visible before
-- completion regardless of this fix.
--
-- Additive only: these are NEW, separate permissive policies alongside
-- the existing "approved active" ones (Postgres OR's multiple permissive
-- SELECT policies together) -- nothing existing is dropped or narrowed.

create policy "Students can view questions in their own attempts"
  on assessment_questions for select
  to authenticated
  using (
    exists (
      select 1
      from assessment_attempt_questions aq
      join assessment_attempts aa on aa.id = aq.attempt_id
      where aq.question_id = assessment_questions.id
        and aa.student_id = auth.uid()
    )
  );

create policy "Students can view options for questions in their own attempts"
  on assessment_question_options for select
  to authenticated
  using (
    exists (
      select 1
      from assessment_attempt_questions aq
      join assessment_attempts aa on aa.id = aq.attempt_id
      where aq.question_id = assessment_question_options.question_id
        and aa.student_id = auth.uid()
    )
  );
