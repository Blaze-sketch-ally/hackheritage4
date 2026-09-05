-- Migration: 049_evaluation_status_and_final_score
-- Purpose: Phase F8.4.1 -- per the approved F8.4 architecture audit's
-- recommendation (§G/§J), adds an ORTHOGONAL evaluation-completeness
-- axis to assessment_attempts, plus additive stored final-result
-- columns, plus the ONE trusted transactional operation that computes
-- them. This migration does NOT wire anything to call that operation
-- automatically -- that is F8.4.2. It also does NOT touch
-- score_assessment_attempt()/create_assessment_attempt() at all.
--
-- assessment_attempts.status (IN_PROGRESS/COMPLETED/ABANDONED) keeps
-- meaning exactly what it always has -- "the objective-scoring portion
-- is done." score/total_marks/percentage keep meaning exactly what they
-- always have -- the objective-only result. Nothing here repurposes or
-- reinterprets any of those five things.
--
-- ============================================================
-- 1. assessment_attempts -- four new, fully additive columns.
-- ============================================================
-- evaluation_status: NOT NULL DEFAULT 'NOT_REQUIRED' -- every existing
-- historical row (all of them objective-only, since AI_EVALUATED
-- questions could never enter an attempt before F8.4.0's
-- 048_ai_evaluated_attempt_participation.sql) is correctly backfilled by
-- this default alone, with no separate UPDATE/backfill script needed --
-- NOT_REQUIRED is the factually correct value for every row that
-- predates this migration. A newly-created mixed attempt also starts at
-- NOT_REQUIRED (the column default) until the fold-in RPC below is
-- first invoked against it -- F8.4.1 deliberately does not wire that
-- invocation yet (F8.4.2), so a freshly-created mixed attempt's
-- evaluation_status stays at this default, technically stale, until
-- something calls fold_in_attempt_evaluation() -- exactly the state the
-- F8.4.1 brief itself anticipates and accepts.
--
-- final_score/final_total_marks/final_percentage: nullable, no default.
-- Populated ONLY by fold_in_attempt_evaluation() below, and ONLY when it
-- determines evaluation_status = COMPLETE -- enforced by the new CHECK
-- constraint below, not merely by application convention.
alter table assessment_attempts
  add column if not exists evaluation_status text not null default 'NOT_REQUIRED'
    check (evaluation_status in ('NOT_REQUIRED', 'PENDING', 'PARTIAL', 'COMPLETE', 'NEEDS_RECONCILIATION')),
  add column if not exists final_score numeric(6, 2) check (final_score >= 0),
  add column if not exists final_total_marks numeric(6, 2) check (final_total_marks >= 0),
  add column if not exists final_percentage numeric(5, 2) check (final_percentage >= 0 and final_percentage <= 100);

-- Belt-and-suspenders DB-level guarantee (not just an RPC-internal
-- convention): the three final_* columns are populated together, if
-- and only if evaluation_status = 'COMPLETE'. No other status may ever
-- carry a "final result" -- including a stale one left over from a
-- prior COMPLETE state that a later re-run (e.g. after a new,
-- conflicting FINALIZED evaluation appears) has since invalidated; the
-- fold-in RPC's own every-branch design (part 2 below) explicitly nulls
-- these fields out whenever the recomputed outcome is not COMPLETE, and
-- this constraint is what makes that a guarantee, not merely a promise.
alter table assessment_attempts
  add constraint assessment_attempts_final_score_consistency check (
    (evaluation_status = 'COMPLETE')
    = (final_score is not null and final_total_marks is not null and final_percentage is not null)
  );

-- ============================================================
-- 2. fold_in_attempt_evaluation() -- the ONE new trusted operation.
--    service_role-only, exactly like create_assessment_attempt()/
--    score_assessment_attempt() (015_question_bank_random_assessment.
--    sql) -- same REVOKE/GRANT pattern, same SELECT ... FOR UPDATE
--    row-locking discipline, same "recompute from stored historical
--    facts, never trust anything mutable" philosophy. NOT exposed
--    through any FastAPI route in this phase -- F8.4.2 decides who/what
--    calls it and when.
--
--    WHAT COUNTS AS "REQUIRED": every question persisted into THIS
--    attempt's own assessment_attempt_questions whose
--    assessment_questions.scoring_method = 'AI_EVALUATED', full stop.
--    The current schema has no other opt-out signal anywhere (no flag
--    on assessment_questions, assessment_attempt_questions, or
--    evaluator_assignments marking a question as "AI_EVALUATED but
--    evaluation not actually required for this attempt") -- so this is
--    the only correct, and only possible, definition given what is
--    actually persisted today. If a future product need ever
--    introduces such a signal, this function's single WHERE clause is
--    the one place that would need to change.
--
--    THE RUBRIC/POINTS RULE, ENFORCED HERE, AT THE POINT OF USE: a
--    FINALIZED evaluation only ever contributes to the per-question
--    resolution below if its OWN attached rubric's max_marks exactly
--    equals the question's own points -- enforced by an INNER JOIN
--    (rubrics r on r.id = e.rubric_id where r.max_marks =
--    v_question.points), which naturally also excludes a FINALIZED
--    evaluation with NO rubric attached at all (rubric_id is nullable,
--    045_evaluation_foundation.sql) -- no rubric to compare against
--    means no basis to trust the marks are on the right scale, so it is
--    excluded identically to a mismatched one. This is chosen over a
--    CHECK constraint or trigger on evaluations/rubrics themselves
--    (which would have to live in 045's own migration territory, or a
--    new one touching that table's write path -- out of F8.4.1's scope,
--    which only asked to keep an ineligible evaluation out of the FINAL
--    SCORE, not to prevent it from being saved/attached in the first
--    place, a separate, not-yet-decided product question). Marks are
--    NEVER scaled -- an evaluation whose rubric doesn't match is simply
--    treated as if it does not exist for fold-in purposes; the question
--    remains unresolved (PENDING/PARTIAL), never silently rescaled.
--
--    CO-EVALUATION, PER QUESTION: zero eligible FINALIZED evaluations ->
--    unresolved. Exactly one DISTINCT eligible awarded_marks value
--    (whether from one evaluator or several who happened to agree) ->
--    resolved, that value counts. More than one DISTINCT eligible value
--    -> conflict, the WHOLE ATTEMPT (not just this question) becomes
--    NEEDS_RECONCILIATION and no final_* value is ever computed --
--    never an average, never latest/first-wins, never a silently
--    chosen evaluator. This phase builds no reconciliation authority at
--    all, per the approved F8.4 architecture audit's own explicit
--    deferral.
--
--    IDEMPOTENCY: every branch always RECOMPUTES from scratch (the
--    FINALIZED evaluations it reads, and the already-stored
--    v_attempt.score/total_marks), never incrementally adjusts prior
--    state -- calling this twice on an unchanged attempt writes the
--    identical values both times; calling it again after a genuinely
--    new conflicting FINALIZED evaluation appears correctly transitions
--    COMPLETE -> NEEDS_RECONCILIATION and clears the now-invalid final_*
--    values, rather than leaving a stale, no-longer-trustworthy result
--    in place.
--
--    CONCURRENCY: `select ... for update` on the attempt row, taken
--    FIRST, serializes any two concurrent fold-in attempts for the same
--    attempt_id exactly the way score_assessment_attempt() already
--    serializes concurrent scoring attempts -- the second caller simply
--    waits for the lock, then recomputes against whatever the first
--    caller's transaction actually committed. No application-level
--    locking of any kind.
-- ============================================================
create or replace function public.fold_in_attempt_evaluation(
  p_attempt_id uuid
)
returns public.assessment_attempts
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_attempt public.assessment_attempts;
  v_question record;
  v_required_count int := 0;
  v_resolved_count int := 0;
  v_has_conflict boolean := false;
  v_has_unresolved boolean := false;
  v_human_score numeric(6, 2) := 0;
  v_human_total numeric(6, 2) := 0;
  v_eligible_marks numeric(6, 2)[];
  v_distinct_count int;
  v_final_score numeric(6, 2);
  v_final_total numeric(6, 2);
  v_final_percentage numeric(5, 2);
begin
  select *
  into v_attempt
  from public.assessment_attempts
  where id = p_attempt_id
  for update;

  if not found then
    raise exception 'Attempt not found.' using errcode = 'P0002';
  end if;

  if v_attempt.status <> 'COMPLETED' then
    raise exception 'Attempt is not eligible for evaluation fold-in.' using errcode = '55000';
  end if;

  for v_question in
    select q.id as question_id, q.points
    from public.assessment_attempt_questions aq
    join public.assessment_questions q on q.id = aq.question_id
    where aq.attempt_id = p_attempt_id
      and q.scoring_method = 'AI_EVALUATED'
  loop
    v_required_count := v_required_count + 1;

    select array_agg(distinct e.awarded_marks)
    into v_eligible_marks
    from public.evaluations e
    join public.evaluator_assignments ea on ea.id = e.assignment_id
    join public.rubrics r on r.id = e.rubric_id
    where ea.attempt_id = p_attempt_id
      and ea.question_id = v_question.question_id
      and e.status = 'FINALIZED'
      and r.max_marks = v_question.points;

    v_distinct_count := coalesce(array_length(v_eligible_marks, 1), 0);

    if v_distinct_count = 0 then
      v_has_unresolved := true;
    elsif v_distinct_count = 1 then
      v_resolved_count := v_resolved_count + 1;
      v_human_score := v_human_score + v_eligible_marks[1];
      v_human_total := v_human_total + v_question.points;
    else
      v_has_conflict := true;
    end if;
  end loop;

  if v_required_count = 0 then
    update public.assessment_attempts
    set evaluation_status = 'NOT_REQUIRED',
        final_score = null,
        final_total_marks = null,
        final_percentage = null
    where id = p_attempt_id
    returning * into v_attempt;
    return v_attempt;
  end if;

  if v_has_conflict then
    update public.assessment_attempts
    set evaluation_status = 'NEEDS_RECONCILIATION',
        final_score = null,
        final_total_marks = null,
        final_percentage = null
    where id = p_attempt_id
    returning * into v_attempt;
    return v_attempt;
  end if;

  if v_has_unresolved then
    update public.assessment_attempts
    set evaluation_status = case when v_resolved_count > 0 then 'PARTIAL' else 'PENDING' end,
        final_score = null,
        final_total_marks = null,
        final_percentage = null
    where id = p_attempt_id
    returning * into v_attempt;
    return v_attempt;
  end if;

  -- Every required question resolved, no conflicts -- fold the
  -- objective portion (already computed and stored, trusted as-is, by
  -- the completely unmodified score_assessment_attempt()) together with
  -- the human portion computed above. Exact numeric arithmetic
  -- throughout -- every variable involved is numeric(p,s), never float.
  v_final_score := coalesce(v_attempt.score, 0) + v_human_score;
  v_final_total := coalesce(v_attempt.total_marks, 0) + v_human_total;

  if v_final_total = 0 then
    v_final_percentage := 100;
  else
    v_final_percentage := round((v_final_score / v_final_total) * 100, 2);
  end if;

  update public.assessment_attempts
  set evaluation_status = 'COMPLETE',
      final_score = v_final_score,
      final_total_marks = v_final_total,
      final_percentage = v_final_percentage
  where id = p_attempt_id
  returning * into v_attempt;

  return v_attempt;
end;
$$;

revoke all on function public.fold_in_attempt_evaluation(uuid) from public;
revoke all on function public.fold_in_attempt_evaluation(uuid) from anon;
revoke all on function public.fold_in_attempt_evaluation(uuid) from authenticated;
grant execute on function public.fold_in_attempt_evaluation(uuid) to service_role;

-- ============================================================
-- NOT DONE HERE (explicitly, per F8.4.1's own scope boundary)
-- ============================================================
-- - No automatic invocation of fold_in_attempt_evaluation() from
--   anywhere -- evaluation_service.py's finalize-status-transition is
--   completely untouched. F8.4.2 wires this.
-- - No new FastAPI route -- this RPC is not reachable by any
--   authenticated caller, evaluator or otherwise.
-- - No RLS change of any kind, on any table.
-- - No reconciliation authority, no moderator/lead activation.
-- - No change to score_assessment_attempt()/create_assessment_attempt().
-- - No student-facing exposure of evaluation_status/final_* anywhere.

