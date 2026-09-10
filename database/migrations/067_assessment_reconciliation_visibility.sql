-- Migration: 067_assessment_reconciliation_visibility
-- Purpose: Faculty Assessment Governance audit -- READ-ONLY visibility
-- for assessment_moderator into NEEDS_RECONCILIATION cases. This
-- migration deliberately does NOT implement a resolution/decision
-- mechanism -- see the audit report (Faculty Assessment Governance
-- phase) for why: fold_in_attempt_evaluation() (049) is the ONLY
-- existing path that ever computes evaluation_status/final_*, it is
-- service-role-only and unreachable by any authenticated caller, it
-- ALWAYS recomputes from scratch from FINALIZED evaluations (never an
-- override, never an average, never a chosen evaluator), and a
-- FINALIZED evaluation's awarded_marks/status are permanently immutable
-- (045's prevent_unauthorized_evaluation_change trigger, no transition
-- FROM FINALIZED exists in evaluation_service._TRANSITIONS_FROM). There
-- is therefore no existing mechanism, at any layer, that lets ANY actor
-- change the outcome of a NEEDS_RECONCILIATION case -- deciding how one
-- should be introduced is a genuine, unresolved product decision (three
-- concrete options are documented in the audit report), not something
-- this migration invents. What this migration DOES add is the one part
-- of the Moderator capability's candidate responsibilities (F2's own
-- list: "view assigned reconciliation cases... inspect evaluator
-- submissions... compare conflicting marks") that requires NO decision
-- on the write/resolution model at all -- pure visibility.
--
-- ============================================================
-- WHY TWO NEW RPCS, NOT A NEW RLS POLICY ON evaluations/
-- evaluator_assignments/rubrics
-- ============================================================
-- Every existing SELECT policy on those three tables is scoped strictly
-- to "the caller's own" (evaluator_id = auth.uid(), 045). Broadening
-- that RLS to also admit assessment_moderator callers would require
-- expressing "...OR (this row belongs to an attempt currently
-- NEEDS_RECONCILIATION AND the caller holds assessment_moderator)" as a
-- policy predicate independently on THREE different tables, each
-- re-executing an equivalent join back to assessment_attempts on every
-- row check -- both a correctness risk (three policies must agree
-- exactly) and a broadening of an RLS surface that has been strict since
-- 045. This project's own established alternative for "a different
-- capability needs a narrow, conditional, cross-table read" is a tightly
-- scoped SECURITY DEFINER RPC (e.g. review_question(), 016/044;
-- admin_list_attempts_for_assignment-style reads) -- chosen here for the
-- same reason: the capability check and the NEEDS_RECONCILIATION
-- condition are enforced ONCE, in one audited place, and the underlying
-- RLS on evaluations/evaluator_assignments/rubrics remains completely
-- untouched and exactly as strict as it was in 045.
--
-- ============================================================
-- Privacy: student identifier
-- ============================================================
-- Mirrors admin_list_attempts_for_assignment's own existing convention
-- (app.services.evaluation_service.admin_list_attempts_for_assignment,
-- Phase 2) exactly: a short, truncated `student_label` derived from the
-- attempt/student id, never the student's email/name/profile. No new
-- privacy posture is invented here -- this reuses the one this project
-- already established and audited for the exact same "Faculty governance
-- view sees student identity" situation.
--
-- ============================================================
-- list_reconciliation_cases()
-- ============================================================
-- One row per (attempt, question) that is CURRENTLY part of a
-- NEEDS_RECONCILIATION attempt with a genuine, still-live disagreement
-- on that question (recomputed the same way fold_in_attempt_evaluation()
-- itself defines a conflict: >1 DISTINCT eligible FINALIZED awarded_marks
-- value, eligible meaning rubric.max_marks = question.points -- this
-- RPC does not invent a second definition of "conflict", it reads the
-- identical condition). authenticated-callable; internally requires
-- has_assessment_capability(auth.uid(), 'assessment_moderator') or
-- raises 42501 -- same pattern as review_question()'s own self-review
-- check. Read-only: selects only, never inserts/updates/deletes.
create or replace function public.list_reconciliation_cases()
returns table (
  attempt_id uuid,
  assessment_id uuid,
  assessment_title text,
  student_label text,
  question_id uuid,
  question_text text,
  points numeric(6, 2)
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.has_assessment_capability(auth.uid(), 'assessment_moderator') then
    raise exception 'Only an assessment_moderator may view reconciliation cases.'
      using errcode = '42501';
  end if;

  return query
  select
    aa.id as attempt_id,
    a.id as assessment_id,
    a.title as assessment_title,
    'Student ' || left(aa.student_id::text, 8) as student_label,
    q.id as question_id,
    q.question_text,
    q.points
  from public.assessment_attempts aa
  join public.assessments a on a.id = aa.assessment_id
  join public.assessment_attempt_questions aq on aq.attempt_id = aa.id
  join public.assessment_questions q on q.id = aq.question_id and q.scoring_method = 'AI_EVALUATED'
  where aa.evaluation_status = 'NEEDS_RECONCILIATION'
    and (
      select count(distinct e.awarded_marks)
      from public.evaluations e
      join public.evaluator_assignments ea on ea.id = e.assignment_id
      join public.rubrics r on r.id = e.rubric_id
      where ea.attempt_id = aa.id
        and ea.question_id = q.id
        and e.status = 'FINALIZED'
        and r.max_marks = q.points
    ) > 1
  order by aa.updated_at desc, q.display_order;
end;
$$;

revoke all on function public.list_reconciliation_cases() from public;
revoke all on function public.list_reconciliation_cases() from anon;
grant execute on function public.list_reconciliation_cases() to authenticated;

-- ============================================================
-- get_reconciliation_case(p_attempt_id)
-- ============================================================
-- The detail view for one attempt: every FINALIZED, eligible evaluation
-- on every conflicting question, so a moderator can compare them --
-- "evaluator A / evaluator A's marks / evaluator B / evaluator B's
-- marks" from the audit's own UI requirement. Same capability check as
-- above. Raises P0002 if the attempt doesn't exist or is not currently
-- NEEDS_RECONCILIATION (never silently returns an empty/misleading
-- result for a case that isn't genuinely in this state) -- callers
-- should turn that into 404, matching this project's own
-- "not found vs not visible are indistinguishable" convention
-- (get_student_skill_scores, get_notification, etc.).
create or replace function public.get_reconciliation_case(p_attempt_id uuid)
returns table (
  question_id uuid,
  question_text text,
  points numeric(6, 2),
  evaluator_id uuid,
  awarded_marks numeric(6, 2),
  feedback text,
  rubric_id uuid,
  rubric_name text,
  finalized_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_attempt public.assessment_attempts;
begin
  if not public.has_assessment_capability(auth.uid(), 'assessment_moderator') then
    raise exception 'Only an assessment_moderator may view reconciliation cases.'
      using errcode = '42501';
  end if;

  select * into v_attempt from public.assessment_attempts where id = p_attempt_id;

  if not found or v_attempt.evaluation_status <> 'NEEDS_RECONCILIATION' then
    raise exception 'This attempt is not a current reconciliation case.' using errcode = 'P0002';
  end if;

  return query
  select
    q.id as question_id,
    q.question_text,
    q.points,
    e.evaluator_id,
    e.awarded_marks,
    e.feedback,
    r.id as rubric_id,
    r.name as rubric_name,
    e.finalized_at
  from public.assessment_attempt_questions aq
  join public.assessment_questions q on q.id = aq.question_id and q.scoring_method = 'AI_EVALUATED'
  join public.evaluator_assignments ea on ea.attempt_id = aq.attempt_id and ea.question_id = q.id
  join public.evaluations e on e.assignment_id = ea.id and e.status = 'FINALIZED'
  join public.rubrics r on r.id = e.rubric_id and r.max_marks = q.points
  where aq.attempt_id = p_attempt_id
  order by q.display_order, e.finalized_at;
end;
$$;

revoke all on function public.get_reconciliation_case(uuid) from public;
revoke all on function public.get_reconciliation_case(uuid) from anon;
grant execute on function public.get_reconciliation_case(uuid) to authenticated;

-- ============================================================
-- NOT DONE HERE (explicitly, per the audit's own product-decision gate)
-- ============================================================
-- - No resolution/decision endpoint, table, or column of any kind.
-- - No change to fold_in_attempt_evaluation(), evaluations,
--   evaluator_assignments, or any existing RLS policy.
-- - No moderator-assignment mechanism (every current
--   assessment_moderator can see every current case -- an explicit,
--   documented interim default, not a final assignment model; see the
--   audit report's Section 15 options).
-- - No assessment_lead activation of any kind -- Lead remains
--   completely dormant, exactly as every prior phase left it.
-- - No new notification type -- there is no defined resolution event
--   to notify about yet.
