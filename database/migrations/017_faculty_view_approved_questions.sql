-- Migration: 017_faculty_view_approved_questions
-- Purpose: fixes a second real bug found during Phase 1K real-Supabase QA
-- verification (immediately after 016 fixed the approve/reject write
-- path) -- once a faculty member reviews (approves) another setter's
-- question, that REVIEWING faculty member immediately loses SELECT
-- visibility into the very question they just approved, along with its
-- options and answer key.
--
-- Root cause: 015's three faculty SELECT policies
-- ("Faculty can view their own or pending questions" and the analogous
-- policies on assessment_question_options/assessment_question_answers)
-- only ever covered two cases -- the caller's OWN question (any
-- review_status) or ANY question that is still PENDING. The moment
-- review_status becomes APPROVED, a non-owner faculty caller matches
-- neither condition. The existing "Students can view approved active
-- questions" policy (and its options/answer_key equivalents) doesn't
-- help either -- confirmed live via `select * from pg_policies` that
-- these are gated by is_student(auth.uid()), which is false for faculty.
-- Net effect: GET /questions/{id} (and the list) 404s for a faculty
-- member immediately after they approve someone else's question, and any
-- endpoint response that re-reads the row post-approval (approve_question
-- itself, in this codebase) fails the same way.
--
-- Fix: widen the same three faculty SELECT policies to also cover
-- APPROVED questions from ANY setter, not just the caller's own or
-- PENDING ones. This is a deliberate widening, not a workaround --
-- approved, active questions are already effectively public content
-- (any STUDENT can already read them, including their options; the
-- answer key is student-readable too, just gated on the student's own
-- completed attempt rather than unconditionally). There is no
-- confidentiality reason to hide an approved question's content from
-- OTHER faculty members once it has already cleared review -- REJECTED
-- and PENDING questions remain visible only to their own creator (never
-- to a third, uninvolved faculty member) and to whichever faculty member
-- is actively reviewing a PENDING one, exactly as 015 already intended.
--
-- Each policy is dropped and recreated under the SAME name (not just
-- ALTERed, since PostgreSQL has no ALTER POLICY ... USING that changes a
-- SELECT policy's qual in place while preserving the name in one
-- statement in a way older/newer servers agree on -- drop+create is the
-- unambiguous, portable way to widen an existing policy's condition).
-- Nothing else about 015/016 changes: the write-side policies (INSERT/
-- UPDATE/DELETE on all three tables), review_question() (016), and every
-- trigger are untouched.

drop policy if exists "Faculty can view their own or pending questions" on assessment_questions;

create policy "Faculty can view their own, pending, or approved questions"
  on assessment_questions for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and (created_by = auth.uid() or review_status in ('PENDING', 'APPROVED'))
  );

drop policy if exists "Faculty can view options for their own or pending questions" on assessment_question_options;

create policy "Faculty can view options for their own, pending, or approved questions"
  on assessment_question_options for select
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and public.is_faculty(auth.uid())
        and (q.created_by = auth.uid() or q.review_status in ('PENDING', 'APPROVED'))
    )
  );

drop policy if exists "Faculty can view answer keys for their own or pending questions" on assessment_question_answers;

create policy "Faculty can view answer keys for their own, pending, or approved questions"
  on assessment_question_answers for select
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_answers.question_id
        and public.is_faculty(auth.uid())
        and (q.created_by = auth.uid() or q.review_status in ('PENDING', 'APPROVED'))
    )
  );
