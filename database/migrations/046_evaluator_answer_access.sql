-- Migration: 046_evaluator_answer_access
-- Purpose: Phase F8.2 -- the dedicated security phase for the F8
-- Evaluation & Rubrics roadmap. This is the FIRST migration in this
-- project's history that grants any Faculty role read access to
-- assessment_answers (student-submitted answer content) or
-- assessment_attempts beyond the existing mentor summary-only policy
-- (040_faculty_student_mentorships.sql). Per the approved F8.2 audit,
-- access is granted ONLY through an explicit, exact-scope evaluator
-- assignment (045_evaluation_foundation.sql's evaluator_assignments) --
-- never through the assessment_evaluator capability alone.
--
-- Approved architectural decisions this migration encodes (settled by
-- the user ahead of implementation, per the F8.2 audit's own "Open
-- Architectural Decisions" section):
--   A. Co-evaluation is ALLOWED. Multiple different evaluators may hold
--      simultaneous ACTIVE assignments to the same (attempt_id,
--      question_id) -- 045's own uniqueness model (partial unique index
--      scoped to (evaluator_id, attempt_id, question_id)) already
--      permits this and is NOT changed here. Every policy below scopes
--      strictly to auth.uid()'s OWN assignment(s), so co-evaluation
--      requires no special-casing: two evaluators each independently
--      satisfy the same EXISTS clause with two different rows.
--   B. Student identity IS visible to the explicitly assigned evaluator
--      (via assessment_attempts.student_id, on an attempt they are
--      actually assigned to) -- but this migration adds NO policy to
--      `profiles` of any kind. An evaluator learns a uuid, not a
--      browsable identity -- resolving that uuid to a name/profile is
--      explicitly out of scope here (see the header comment on why
--      003_skills.sql-style "no broad Faculty profile access" is
--      preserved).
--   C. Evaluators get NO access to assessment_question_answers (the
--      answer key). The rubric (045) is the authoritative grading
--      criteria for human evaluation -- the answer key remains exactly
--      as protected as it was before this migration, for every role.
--   D. Evaluators get NO access to assessment_attempt_questions. Nothing
--      an evaluator needs is missing without it: their own
--      evaluator_assignments row already carries attempt_id/question_id,
--      and assessment_answers already carries both directly.
--   E/F. assessment_evaluator (027) is reused exactly as-is -- no new
--      permission table, no new capability. has_assessment_capability()
--      is untouched and remains the sole source of truth for whether a
--      capability is currently GRANTED and unexpired; every policy below
--      calls it live, so a SUSPENDED/EXPIRED/REVOKED capability removes
--      access on the very next query, automatically, with nothing here
--      needing to know about status transitions.
--   G. A REVOKED evaluator_assignments row grants nothing under any
--      policy below (all require status = 'ACTIVE'), while the row
--      itself, evaluation_history, and any FINALIZED evaluations remain
--      exactly as queryable/immutable as 045 already made them -- this
--      migration does not touch evaluator_assignments, evaluations, or
--      evaluation_history at all.
--
-- Nothing in this migration is a write policy. F8.2 is answer/attempt/
-- rubric VISIBILITY only -- assessment_answers' existing student
-- INSERT/UPDATE policies and prevent_self_answer_scoring trigger
-- (004_assessments.sql) are completely untouched, so an evaluator gains
-- no new way to write anything, anywhere, through this migration.
--
-- ============================================================
-- 1. has_active_evaluator_assignment() -- the one new helper, reused by
--    the assessment_answers policy below. Deliberately narrow: derives
--    the evaluator's identity from auth.uid() only (never a parameter --
--    an evaluator_id argument here would be an unnecessary privilege-
--    escalation surface, letting one authenticated caller probe another
--    evaluator's assignments), and checks nothing about capability/role
--    -- those stay as separate, visible top-level conjuncts in every
--    consuming policy (matching this project's own established idiom --
--    is_faculty()/has_mentor_capability()/EXISTS(...) as three distinct
--    conjuncts in 040, never folded into one opaque check) rather than
--    being hidden inside this helper.
--
--    SECURITY DEFINER + search_path='' so it can read evaluator_
--    assignments directly without depending on -- or being redundantly
--    re-gated by -- that table's own RLS (which would still be correct
--    either way, since the policy's own USING clause already matches;
--    SECURITY DEFINER just avoids a pointless double RLS pass, the same
--    reasoning has_mentor_capability()/has_assessment_capability() apply
--    to their own permission tables).
-- ============================================================
create or replace function public.has_active_evaluator_assignment(
  p_attempt_id uuid,
  p_question_id uuid
)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.evaluator_assignments ea
    where ea.evaluator_id = auth.uid()
      and ea.attempt_id = p_attempt_id
      and ea.question_id = p_question_id
      and ea.status = 'ACTIVE'
  );
$$;

revoke all on function public.has_active_evaluator_assignment(uuid, uuid) from public;
revoke all on function public.has_active_evaluator_assignment(uuid, uuid) from anon;
grant execute on function public.has_active_evaluator_assignment(uuid, uuid) to authenticated;

-- ============================================================
-- 2. assessment_answers -- the primary deliverable of F8.2. Exact-scope
--    only: an evaluator sees a row if and only if their OWN ACTIVE
--    assignment names that row's exact (attempt_id, question_id) pair.
--    Every existing policy on this table (student INSERT/SELECT/UPDATE,
--    004_assessments.sql) and its scoring-immutability trigger
--    (prevent_self_answer_scoring) are completely untouched -- this is a
--    purely additive SELECT policy, evaluated as an OR alongside the
--    existing student policy by Postgres RLS (permissive by default),
--    never a replacement for it.
-- ============================================================
create policy "Evaluators can view answers for their active assignment"
  on assessment_answers for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
    and public.has_active_evaluator_assignment(
      assessment_answers.attempt_id,
      assessment_answers.question_id
    )
  );

-- ============================================================
-- 3. assessment_attempts -- scoped to "any ACTIVE assignment exists for
--    this attempt", not tied to a single question column the way
--    assessment_answers is (an attempt has no question_id of its own).
--    A direct EXISTS, not the helper above -- the helper's signature is
--    specifically the two-column (attempt_id, question_id) shape
--    assessment_answers needs; reusing it here with a placeholder
--    question_id would be the wrong tool, not a shortcut.
-- ============================================================
create policy "Evaluators can view attempts they have an active assignment for"
  on assessment_attempts for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
    and exists (
      select 1 from public.evaluator_assignments ea
      where ea.attempt_id = assessment_attempts.id
        and ea.evaluator_id = auth.uid()
        and ea.status = 'ACTIVE'
    )
  );

-- ============================================================
-- 4. rubrics / rubric_criteria -- F8.1 left these fully closed to
--    `authenticated`. This migration opens the narrowest possible slice:
--    the rubric (and its criteria) actually attached to one of the
--    evaluator's own evaluations, via an ACTIVE assignment -- never a
--    blanket "any evaluator can read any rubric" grant. Who may CREATE a
--    rubric remains undecided and unopened here (F8.3's concern, per
--    045's own header) -- this is read-only, and only for rubrics
--    already in active use by the reading evaluator's own work.
-- ============================================================
create policy "Evaluators can view the rubric attached to their own evaluation"
  on rubrics for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
    and exists (
      select 1
      from public.evaluations e
      join public.evaluator_assignments ea on ea.id = e.assignment_id
      where e.rubric_id = rubrics.id
        and ea.evaluator_id = auth.uid()
        and ea.status = 'ACTIVE'
    )
  );

create policy "Evaluators can view criteria for their own evaluation's rubric"
  on rubric_criteria for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
    and exists (
      select 1
      from public.evaluations e
      join public.evaluator_assignments ea on ea.id = e.assignment_id
      where e.rubric_id = rubric_criteria.rubric_id
        and ea.evaluator_id = auth.uid()
        and ea.status = 'ACTIVE'
    )
  );

-- ============================================================
-- NOT DONE HERE (explicitly, per F8.2's own scope boundary)
-- ============================================================
-- - No policy of any kind on assessment_question_answers (the answer
--   key), assessment_attempt_questions, or profiles/student_profiles.
-- - No INSERT/UPDATE/DELETE policy anywhere in this migration -- F8.2 is
--   read access only.
-- - No change to create_assessment_attempt()/score_assessment_attempt(),
--   evaluator_assignments/evaluations/evaluation_history (045), or any
--   mentorship policy (040).
-- - No FastAPI route, no service, no frontend component -- F8.3.
