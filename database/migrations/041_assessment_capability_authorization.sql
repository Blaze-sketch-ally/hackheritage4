-- Migration: 041_assessment_capability_authorization
-- Purpose: Phase F5A -- activates the F2 capability model
-- (027_faculty_assessment_permissions.sql) on the question-bank/
-- blueprint/review surface it was always meant to govern, but never
-- actually wired into. Confirmed by the F5 readiness audit: every one of
-- the five capabilities (assessment_author/reviewer/evaluator/moderator/
-- lead) has been grantable and self-readable since 027/035, but zero RLS
-- policy and zero backend route referenced any of them until now -- the
-- entire question-bank/review/blueprint surface has been gated by the
-- bare FACULTY role only (is_faculty(auth.uid()), 015/017/018/019).
--
-- This migration activates exactly TWO of the five: assessment_author
-- and assessment_reviewer. assessment_evaluator/moderator/lead remain
-- completely untouched and dormant -- they belong to later phases (F8
-- evaluation, F10 governance) per the approved roadmap, not F5A.
--
-- ============================================================
-- WHAT THIS DOES NOT CHANGE
-- ============================================================
-- - The question lifecycle (PENDING -> APPROVED | REJECTED) is unchanged.
-- - Ownership rules are unchanged: a question's own creator (created_by)
--   still has all their existing rights over their own non-approved
--   content; a reviewer still can only ever change review_status, never
--   content (prevent_unauthorized_question_review, 015, untouched).
-- - Self-review is still blocked (015's trigger + 016's RPC, untouched).
-- - Approved-question content immutability is untouched.
-- - assessment_attempt_questions, assessment_attempts,
--   assessment_answers, and every historical-integrity guarantee (023)
--   are completely untouched -- this migration touches only the
--   AUTHORING/REVIEW surface (assessment_questions, its options, its
--   answer keys, assessment_blueprint_rules) and the review_question()
--   RPC. Nothing here can retroactively alter a completed attempt.
-- - F4.2's mentor-visibility policy on assessment_attempts (040) is a
--   completely different table and is not referenced anywhere below.
--   Mentorship remains structurally incapable of reaching answer keys.
--
-- ============================================================
-- THE ONE BEHAVIOR CHANGE: narrower answer-key/question/option READ
-- ============================================================
-- 018_faculty_view_all_questions.sql made three SELECT policies
-- unconditionally `using (is_faculty(auth.uid()))` -- ANY Faculty account
-- could read ANY question, its options, and its answer key, regardless
-- of capability. The F5 audit flagged this as broader than the target
-- architecture: a plain FACULTY account with no assessment capability at
-- all should not be able to read answer keys.
--
-- Replacement rule for all three tables: a Faculty caller may read a
-- question/its options/its answer key if EITHER:
--   (a) they created it themselves (created_by = auth.uid()) -- you can
--       always see your own work, regardless of your current capability
--       status; capability governs creating NEW content and reviewing
--       OTHERS' content, not revoking your view of your own history, or
--   (b) they currently hold assessment_reviewer -- reviewers are trusted
--       peers who need full-bank visibility to review any PENDING
--       question and to retain visibility into what they already
--       reviewed (this preserves exactly the behavior 017/018 were
--       written to fix: a reviewer losing sight of a question the
--       instant their own decision took effect).
--
-- A plain FACULTY account holding neither assessment_author nor
-- assessment_reviewer sees nothing here at all (own questions: none,
-- since they never created any without author capability -- see the
-- INSERT policy below). This is intentionally the exact target-state
-- security property named in section 5 of the F5A brief.

drop policy if exists "Faculty can view any question" on assessment_questions;

create policy "Faculty can view their own questions or any question as a reviewer"
  on assessment_questions for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and (
      created_by = auth.uid()
      or public.has_assessment_capability(auth.uid(), 'assessment_reviewer')
    )
  );

drop policy if exists "Faculty can view options for any question" on assessment_question_options;

create policy "Faculty can view options for their own questions or any as a reviewer"
  on assessment_question_options for select
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and public.is_faculty(auth.uid())
        and (
          q.created_by = auth.uid()
          or public.has_assessment_capability(auth.uid(), 'assessment_reviewer')
        )
    )
  );

drop policy if exists "Faculty can view answer keys for any question" on assessment_question_answers;

create policy "Faculty can view answer keys for their own questions or any as a reviewer"
  on assessment_question_answers for select
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_answers.question_id
        and public.is_faculty(auth.uid())
        and (
          q.created_by = auth.uid()
          or public.has_assessment_capability(auth.uid(), 'assessment_reviewer')
        )
    )
  );

-- ============================================================
-- WRITE ACCESS: capability-gate creation/authoring, unchanged ownership
-- ============================================================
-- Every write policy below keeps its EXACT existing ownership/status
-- condition (created_by = auth.uid(), review_status <> 'APPROVED', etc)
-- and adds exactly one extra condition: the caller must additionally
-- hold assessment_author. Nothing about WHO may edit WHAT changes --
-- only "must this Faculty member also hold the author capability" is
-- added on top.

drop policy if exists "Faculty can create their own questions" on assessment_questions;

create policy "Faculty authors can create their own questions"
  on assessment_questions for insert
  to authenticated
  with check (
    created_by = auth.uid()
    and public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_author')
    and review_status = 'PENDING'
  );

-- The UPDATE policy is split into its two pre-existing branches (own-
-- edit vs. reviewer-touching-a-pending-row) exactly as the
-- prevent_unauthorized_question_review trigger (015) already
-- distinguishes them -- each branch now requires the matching
-- capability. Note: in practice, the actual approve/reject transition
-- goes through review_question() (016), a SECURITY DEFINER function
-- that bypasses this table's RLS entirely for its own internal UPDATE
-- (see that migration's own header) -- that RPC is hardened separately,
-- below. This policy's "reviewer" branch is hardened here anyway, as
-- defence in depth, so a hypothetical direct-PostgREST UPDATE attempt at
-- a review transition is *also* capability-gated, not just role-gated,
-- even though the real, working review path never reaches it.
drop policy if exists "Faculty can update their own or review pending questions" on assessment_questions;

create policy "Faculty authors can edit their own questions, reviewers can touch pending ones"
  on assessment_questions for update
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and (
      (created_by = auth.uid() and public.has_assessment_capability(auth.uid(), 'assessment_author'))
      or (review_status = 'PENDING' and public.has_assessment_capability(auth.uid(), 'assessment_reviewer'))
    )
  )
  with check (
    public.is_faculty(auth.uid())
    and (
      (created_by = auth.uid() and public.has_assessment_capability(auth.uid(), 'assessment_author'))
      or public.has_assessment_capability(auth.uid(), 'assessment_reviewer')
    )
  );

drop policy if exists "Faculty can create options for their own non-approved questions" on assessment_question_options;

create policy "Faculty authors can create options for their own non-approved questions"
  on assessment_question_options for insert
  to authenticated
  with check (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
        and public.has_assessment_capability(auth.uid(), 'assessment_author')
    )
  );

drop policy if exists "Faculty can update options for their own non-approved questions" on assessment_question_options;

create policy "Faculty authors can update options for their own non-approved questions"
  on assessment_question_options for update
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
        and public.has_assessment_capability(auth.uid(), 'assessment_author')
    )
  )
  with check (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
        and public.has_assessment_capability(auth.uid(), 'assessment_author')
    )
  );

drop policy if exists "Faculty can delete options for their own non-approved questions" on assessment_question_options;

create policy "Faculty authors can delete options for their own non-approved questions"
  on assessment_question_options for delete
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
        and public.has_assessment_capability(auth.uid(), 'assessment_author')
    )
  );

drop policy if exists "Faculty can create answer keys for their own non-approved questions" on assessment_question_answers;

create policy "Faculty authors can create answer keys for their own non-approved questions"
  on assessment_question_answers for insert
  to authenticated
  with check (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_answers.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
        and public.has_assessment_capability(auth.uid(), 'assessment_author')
    )
  );

drop policy if exists "Faculty can update answer keys for their own non-approved questions" on assessment_question_answers;

create policy "Faculty authors can update answer keys for their own non-approved questions"
  on assessment_question_answers for update
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_answers.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
        and public.has_assessment_capability(auth.uid(), 'assessment_author')
    )
  )
  with check (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_answers.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
        and public.has_assessment_capability(auth.uid(), 'assessment_author')
    )
  );

-- Note: assessment_question_answers has never had a DELETE policy for
-- `authenticated` at all (verified: neither 015 nor any later migration
-- ever added one) -- app.services.question_bank_service.clear_answer_key
-- already relies on this pre-existing state and is unaffected either
-- way. Not introduced or changed here -- out of F5A's scope.

-- ============================================================
-- BLUEPRINT AUTHORIZATION: assessment_author is the least-privilege fit
-- ============================================================
-- Per the F5A brief: "determine which existing Faculty capability should
-- authorize blueprint management... use the least-privilege capability
-- that fits the current behavior." Blueprint configuration (which
-- questions, how many, per difficulty) is assessment CONFIGURATION --
-- the same class of activity as authoring a question, not reviewing one.
-- assessment_reviewer's entire purpose is judging PEER-SUBMITTED
-- content; a blueprint rule has no "submitter" and nothing to peer
-- review, so gating it on assessment_reviewer would be a semantic
-- mismatch, not a security improvement. assessment_author is the
-- correct, minimal fit. assessments themselves still have no
-- owner/creator column (unchanged, and explicitly NOT introduced by
-- F5A) -- blueprint management remains a shared FACULTY-author
-- capability, not scoped to an individual setter, exactly matching how
-- blueprint configuration has always worked.
drop policy if exists "Faculty can create blueprint rules" on assessment_blueprint_rules;

create policy "Faculty authors can create blueprint rules"
  on assessment_blueprint_rules for insert
  to authenticated
  with check (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_author')
  );

drop policy if exists "Faculty can update blueprint rules" on assessment_blueprint_rules;

create policy "Faculty authors can update blueprint rules"
  on assessment_blueprint_rules for update
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_author')
  )
  with check (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_author')
  );

drop policy if exists "Faculty can delete blueprint rules" on assessment_blueprint_rules;

create policy "Faculty authors can delete blueprint rules"
  on assessment_blueprint_rules for delete
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_author')
  );

-- ============================================================
-- REVIEW RPC: the actual working approve/reject path (016) hardened
-- with the reviewer capability, as its own internal check -- the RLS
-- policy above never actually governs this transition (SECURITY
-- DEFINER bypasses it, per 016's own header), so this is where the real
-- enforcement for "reviewing requires assessment_reviewer" lives.
-- CREATE OR REPLACE, not an edit to 016_review_question_rpc.sql itself
-- -- same precedent as 015 replacing 014's score_assessment_attempt().
-- Every existing check (role, self-review, PENDING-only) is unchanged
-- and unreordered relative to before; the capability check is added
-- alongside them, and the trigger this RPC's internal UPDATE still
-- fires (prevent_unauthorized_question_review, 015) is completely
-- untouched.
-- ============================================================

create or replace function public.review_question(
  p_question_id uuid,
  p_decision text
)
returns public.assessment_questions
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_question public.assessment_questions;
begin
  if p_decision not in ('APPROVED', 'REJECTED') then
    raise exception 'Invalid review decision: %.', p_decision using errcode = '22023';
  end if;

  if not public.is_faculty(auth.uid()) then
    raise exception 'This action requires the FACULTY role.' using errcode = '42501';
  end if;

  if not public.has_assessment_capability(auth.uid(), 'assessment_reviewer') then
    raise exception 'This action requires the assessment_reviewer capability.'
      using errcode = '42501';
  end if;

  select *
  into v_question
  from public.assessment_questions
  where id = p_question_id
  for update;

  if not found then
    raise exception 'Question not found.' using errcode = 'P0002';
  end if;

  if v_question.created_by = auth.uid() then
    raise exception 'Cannot review your own question.' using errcode = '42501';
  end if;

  if v_question.review_status <> 'PENDING' then
    raise exception 'Question is not pending review.' using errcode = '55000';
  end if;

  update public.assessment_questions
  set review_status = p_decision
  where id = p_question_id
  returning * into v_question;

  return v_question;
end;
$$;

revoke all on function public.review_question(uuid, text) from public;
revoke all on function public.review_question(uuid, text) from anon;
grant execute on function public.review_question(uuid, text) to authenticated;
