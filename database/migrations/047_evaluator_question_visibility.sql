-- Migration: 047_evaluator_question_visibility
-- Purpose: Phase F8.2.1 -- closes a real RLS gap discovered during F8.3
-- live verification: a Faculty account holding only assessment_evaluator
-- (and a real, ACTIVE evaluator_assignments row) could not read
-- assessment_questions or assessment_question_options at all.
--
-- Root cause (confirmed live, not just from file text -- see the
-- F8.2.1 audit): 041_assessment_capability_authorization.sql's own
-- SELECT policies on these two tables grant Faculty visibility only to
-- (a) a question's own creator, or (b) a Faculty member currently
-- holding assessment_reviewer. assessment_evaluator did not exist as a
-- meaningful capability when 041 was written (F8 didn't exist yet), so
-- it was never added to that condition list -- not a bug in 041 at the
-- time, just a capability nobody had reason to reference yet.
--
-- This migration does NOT touch 041's own policies at all -- see that
-- file's own comment on why a plain FACULTY account with no capability
-- must see nothing, which remains completely true after this migration.
-- It ADDS two new, separate PERMISSIVE SELECT policies (Postgres ORs
-- multiple permissive policies together), giving an evaluator a THIRD
-- way to see a question/its options -- own / reviewer / assigned-
-- evaluator -- without altering the other two paths in any way.
--
-- ============================================================
-- WHY ASSIGNMENT-SCOPED (045's evaluator_assignments), NOT A BLANKET
-- "assessment_evaluator -> any question" GRANT
-- ============================================================
-- The F8.2.1 audit considered and rejected mirroring 041's reviewer
-- clause exactly (`... or has_assessment_capability(auth.uid(),
-- 'assessment_evaluator')`) -- that would let any evaluator browse
-- every question in the bank, which is correct for a reviewer (whose
-- job is to browse the PENDING pool) but not for an evaluator, whose
-- entire F8.1/F8.2 design is deliberately assignment-scoped, never
-- capability-alone (see 046_evaluator_answer_access.sql's own header,
-- and the F8.2 audit's explicit rejection of "capability alone is
-- never sufficient"). Scoping through an ACTIVE evaluator_assignments
-- row is the narrowest grant that still lets an evaluator see what
-- they're actually assigned to evaluate, and is exactly the same shape
-- 046 already used for assessment_answers/assessment_attempts/rubrics/
-- rubric_criteria -- reused here, not a new pattern.
--
-- ============================================================
-- WHY NO review_status = 'APPROVED' / is_active = true CONDITION
-- ============================================================
-- A question reachable via an evaluator_assignments row was, by
-- construction, APPROVED + is_active = true + scoring_method =
-- 'OBJECTIVE' at the moment create_assessment_attempt() selected it
-- into assessment_attempt_questions (015) -- create_evaluator_
-- assignment() (045) requires that exact membership to exist before an
-- assignment can even be created. Re-checking CURRENT review_status/
-- is_active here would reintroduce, for evaluators, the exact historical-
-- integrity bug 020_student_view_own_attempt_questions.sql already fixed
-- for students: a question deactivated after being selected into a
-- persisted attempt must not become invisible to that attempt's
-- legitimate participant. An evaluator assigned to grade a since-
-- deactivated question must still be able to see what they're grading.
--
-- ============================================================
-- WHY NOT assessment_question_answers
-- ============================================================
-- No policy is added here, deliberately. The rubric (045) is the
-- authoritative evaluation criteria for human evaluation; the answer
-- key remains exactly as protected as it was before this migration, for
-- every role, matching the F8.2 audit's own decision C.

create policy "Evaluators can view questions for their active assignment"
  on assessment_questions for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
    and exists (
      select 1 from public.evaluator_assignments ea
      where ea.question_id = assessment_questions.id
        and ea.evaluator_id = auth.uid()
        and ea.status = 'ACTIVE'
    )
  );

create policy "Evaluators can view options for their active assignment's question"
  on assessment_question_options for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
    and exists (
      select 1 from public.evaluator_assignments ea
      where ea.question_id = assessment_question_options.question_id
        and ea.evaluator_id = auth.uid()
        and ea.status = 'ACTIVE'
    )
  );

-- ============================================================
-- NOT DONE HERE (explicitly, per F8.2.1's own scope boundary)
-- ============================================================
-- - No policy of any kind on assessment_question_answers.
-- - No INSERT/UPDATE/DELETE policy for evaluators on either table --
--   read-only, exactly like every other evaluator-facing policy so far.
-- - No change to 041's existing author/reviewer policies, or to any
--   other migration.
-- - No change to assessment_answers/assessment_attempts (046),
--   evaluator_assignments/evaluations/evaluation_history (045), or any
--   mentorship policy (040).
