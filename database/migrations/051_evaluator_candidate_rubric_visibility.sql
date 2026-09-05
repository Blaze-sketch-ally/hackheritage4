-- Migration: 051_evaluator_candidate_rubric_visibility
-- Purpose: Phase 2 (Evaluator Assignment + Real Evaluation Workspace) --
-- fixes a real, pre-existing gap this phase's own audit surfaced:
-- rubrics/rubric_criteria (045_evaluation_foundation.sql) have never had
-- any policy letting an evaluator discover a candidate rubric BEFORE
-- picking one. The only SELECT policy that exists
-- (046_evaluator_answer_access.sql, "Evaluators can view the rubric
-- attached to their own evaluation") is keyed on
-- evaluations.rubric_id = rubrics.id -- which only ever matches AFTER a
-- rubric has already been saved onto the evaluation via
-- PATCH /faculty/evaluations/{id}. Before that first save, an evaluator
-- has no way to see ANY rubric for their assigned question at all, so
-- SaveEvaluationRequest.rubric_id can never be meaningfully populated
-- through the real product -- only via a direct service-role insert (as
-- this project's own live test suites do).
--
-- This migration adds exactly the missing half: read-only visibility of
-- a rubric (and its criteria) scoped to the evaluator's own ACTIVE
-- assignment on that rubric's question -- the same evaluator-assignment-
-- scoped shape 047_evaluator_question_visibility.sql already established
-- for assessment_questions/assessment_question_options, applied here to
-- rubrics/rubric_criteria instead. Postgres RLS policies for the same
-- command are OR'd together, so this is purely additive: 046's own
-- "attached to my evaluation" policy is untouched and still applies
-- (e.g. after revocation removes assignment-scoped visibility, a
-- FINALIZED evaluation's own already-attached rubric position is a
-- separate question this migration does not touch -- see that policy's
-- own history for why it stays as-is).
--
-- NOT DONE HERE: rubric AUTHORING. Who may create a rubric remains
-- exactly as undecided as 045 left it -- INSERT/UPDATE/DELETE on
-- rubrics/rubric_criteria stay service_role-only, unchanged. This
-- migration is read-only visibility, nothing else. A rubric must still
-- be seeded by an administrator/service-role process before any
-- evaluator can see or select it -- this is a known, reported gap (see
-- the Phase 2 implementation report), not solved by this migration.
create policy "Evaluators can view candidate rubrics for their assigned question"
  on rubrics for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
    and exists (
      select 1 from public.evaluator_assignments ea
      where ea.question_id = rubrics.question_id
        and ea.evaluator_id = auth.uid()
        and ea.status = 'ACTIVE'
    )
  );

create policy "Evaluators can view criteria for their assigned question's candidate rubrics"
  on rubric_criteria for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
    and exists (
      select 1
      from public.rubrics r
      join public.evaluator_assignments ea on ea.question_id = r.question_id
      where r.id = rubric_criteria.rubric_id
        and ea.evaluator_id = auth.uid()
        and ea.status = 'ACTIVE'
    )
  );
