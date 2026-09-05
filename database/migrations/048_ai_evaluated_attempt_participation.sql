-- Migration: 048_ai_evaluated_attempt_participation
-- Purpose: Phase F8.4.0 -- the narrow prerequisite the F8.4 architecture
-- audit identified before any human-evaluation score can ever be
-- integrated: an AI_EVALUATED question has never been selectable into a
-- live attempt at any point in this project's history, because
-- create_assessment_attempt()'s own selection query has always hard-
-- filtered scoring_method = 'OBJECTIVE'. This migration widens exactly
-- that one filter, and teaches score_assessment_attempt() to defer
-- (never auto-score) an AI_EVALUATED question rather than fail the
-- entire scoring transaction because one exists in the attempt.
--
-- This is F8.4.0 ONLY. No evaluation_status, no final_score/
-- final_total_marks/final_percentage, no finalization RPC, no
-- reconciliation -- those are later F8.4.x work per the approved F8.4
-- architecture audit. The existing score/total_marks/percentage columns
-- continue to represent ONLY the objective-scoring result, exactly as
-- they always have -- an AI_EVALUATED question's points are excluded
-- from that denominator entirely (see part 2 below), not included and
-- then silently unscored.
--
-- ============================================================
-- 1. create_assessment_attempt() -- CREATE OR REPLACE, not an edit to
--    015_question_bank_random_assessment.sql. The ONLY change from that
--    file's version: the eligible-question filter widens from
--    scoring_method = 'OBJECTIVE' to scoring_method in ('OBJECTIVE',
--    'AI_EVALUATED'). Every other line -- the attempt insert, the
--    per-difficulty-bucket pool/count logic, the insufficient-pool
--    failure, the persisted-selection insert loop -- is reproduced
--    completely unchanged.
--
--    The blueprint model (assessment_blueprint_rules) has no
--    scoring_method axis today -- it only ever specified difficulty and
--    count, deliberately indifferent to scoring_method (015's own
--    design). Widening this filter therefore means a difficulty
--    bucket's random draw can now include a mix of OBJECTIVE and
--    AI_EVALUATED questions -- this is a direct, expected consequence
--    of the existing blueprint design, not a new selection concept
--    introduced here. A future phase may add scoring_method-aware
--    blueprint rules if that granularity is ever actually needed; not
--    built here, not asked for.
-- ============================================================
create or replace function public.create_assessment_attempt(
  p_assessment_id uuid,
  p_student_id uuid
)
returns public.assessment_attempts
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_attempt public.assessment_attempts;
  v_rule record;
  v_bucket uuid[];
  v_selected uuid[] := array[]::uuid[];
  v_available int;
  v_order int := 0;
  v_question_id uuid;
begin
  if not exists (
    select 1 from public.assessments where id = p_assessment_id and is_active = true
  ) then
    raise exception 'Assessment not found or inactive.' using errcode = 'P0002';
  end if;

  if not exists (
    select 1 from public.assessment_blueprint_rules where assessment_id = p_assessment_id
  ) then
    raise exception 'Assessment has no blueprint configured.' using errcode = '55000';
  end if;

  insert into public.assessment_attempts (student_id, assessment_id, status)
  values (p_student_id, p_assessment_id, 'IN_PROGRESS')
  returning * into v_attempt;

  for v_rule in
    select difficulty, question_count
    from public.assessment_blueprint_rules
    where assessment_id = p_assessment_id
  loop
    select coalesce(array_agg(id), array[]::uuid[])
    into v_bucket
    from (
      select id
      from public.assessment_questions
      where assessment_id = p_assessment_id
        and review_status = 'APPROVED'
        and is_active = true
        and scoring_method in ('OBJECTIVE', 'AI_EVALUATED')
        and difficulty = v_rule.difficulty
      order by random()
      limit v_rule.question_count
    ) eligible;

    v_available := array_length(v_bucket, 1);
    v_available := coalesce(v_available, 0);

    if v_available < v_rule.question_count then
      raise exception 'Insufficient approved % questions for this assessment: need %, have %.',
        v_rule.difficulty, v_rule.question_count, v_available
        using errcode = '55000';
    end if;

    v_selected := v_selected || v_bucket;
  end loop;

  foreach v_question_id in array v_selected
  loop
    insert into public.assessment_attempt_questions (attempt_id, question_id, display_order)
    values (v_attempt.id, v_question_id, v_order);
    v_order := v_order + 1;
  end loop;

  return v_attempt;
end;
$$;

revoke all on function public.create_assessment_attempt(uuid, uuid) from public;
revoke all on function public.create_assessment_attempt(uuid, uuid) from anon;
revoke all on function public.create_assessment_attempt(uuid, uuid) from authenticated;
grant execute on function public.create_assessment_attempt(uuid, uuid) to service_role;

-- ============================================================
-- 2. score_assessment_attempt() -- CREATE OR REPLACE, not an edit to
--    014_score_assessment_attempt.sql/015. Every existing line for an
--    OBJECTIVE question -- the answer-key requirement, the unanswered-
--    placeholder insert-or-reread, the MCQ/MULTIPLE_SELECT/SHORT_ANSWER
--    comparison, the hard failure on a genuinely unsupported OBJECTIVE
--    question_type -- is reproduced completely unchanged, in the same
--    order, for the same inputs. The ONLY change: one new branch, taken
--    FIRST, purely on scoring_method = 'AI_EVALUATED' (never on
--    question_type -- an AI_EVALUATED question is deferred regardless
--    of whether it's MCQ/SUBJECTIVE/CODE/etc., per the F8.4.0 brief's
--    own explicit instruction not to assume AI_EVALUATED implies
--    SUBJECTIVE).
--
--    WHY THIS DISTINGUISHES "INTENTIONALLY DEFERRED" FROM "GENUINELY
--    UNSUPPORTED", RATHER THAN BROADLY SKIPPING EVERY UNKNOWN COMBINATION:
--    the new branch is gated on scoring_method alone, checked BEFORE
--    question_type is ever inspected -- so it catches every AI_EVALUATED
--    question (a real, intentional, schema-declared category) and
--    nothing else. The pre-existing `else raise 'Unsupported OBJECTIVE
--    question_type %'` branch is completely untouched, still reachable,
--    and still fires for exactly what it always fired for: an
--    OBJECTIVE-scored question whose question_type is neither MCQ,
--    MULTIPLE_SELECT, nor SHORT_ANSWER (a CODE/SUBJECTIVE question
--    incorrectly marked OBJECTIVE) -- which review_question()'s own
--    F6.3 approval-readiness guard (043_question_authoring_metadata.sql)
--    is supposed to make impossible to ever reach APPROVED, so hitting
--    it remains a genuine data-integrity anomaly worth a hard XX000
--    failure, not something silently skipped.
--
--    AI_EVALUATED handling, exactly:
--      - NOT added to v_total_marks/v_score -- the existing score/
--        total_marks/percentage columns represent ONLY the objective-
--        scoring result (F8.4.0's own explicit requirement -- final,
--        evaluation-inclusive totals are F8.4.1+ work, not built here).
--      - NO answer-key lookup, no XX000 on a missing one -- unlike
--        OBJECTIVE questions, an AI_EVALUATED question was never
--        required to have an assessment_question_answers row at
--        approval time (043's own guard only applies when
--        scoring_method = 'OBJECTIVE'; 004's own header documents a
--        SUBJECTIVE question's answer-key row as optional, "rubric-style
--        guidance... or none at all").
--      - An assessment_answers row is still ensured to exist even if the
--        student never answered -- same reasoning as the existing
--        OBJECTIVE placeholder (get_attempt_result_rows()'s own
--        invariant: every historically-scored question has exactly one
--        assessment_answers row) and so F8.3's evaluator workflow always
--        has a real row to resolve (even an empty one) once an evaluator
--        is assigned -- but with awarded_marks/is_correct left NULL, not
--        0/false: an AI_EVALUATED question must never receive an
--        automatic score, including the "unanswered" case -- that
--        judgment belongs to a human evaluator, not this function.
--      - If the student DID already answer (a real assessment_answers
--        row already exists, inserted by the unmodified save_answer()
--        path, which itself already requires awarded_marks/is_correct
--        to be null at insert time), this branch does not touch that row
--        at all -- nothing to score, nothing to overwrite.
-- ============================================================

create or replace function public.score_assessment_attempt(
  p_attempt_id uuid,
  p_student_id uuid
)
returns public.assessment_attempts
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_attempt public.assessment_attempts;
  v_total_marks numeric(6, 2) := 0;
  v_score numeric(6, 2) := 0;
  v_percentage numeric(5, 2);
  v_question record;
  v_key record;
  v_answer record;
  v_is_correct boolean;
  v_awarded numeric(6, 2);
begin
  select *
  into v_attempt
  from public.assessment_attempts
  where id = p_attempt_id
    and student_id = p_student_id
  for update;

  if not found then
    raise exception 'Attempt not found.' using errcode = 'P0002';
  end if;

  if v_attempt.status <> 'IN_PROGRESS' or v_attempt.submitted_at is null then
    raise exception 'Attempt is not eligible for scoring.' using errcode = '55000';
  end if;

  for v_question in
    select q.id, q.points, q.question_type, q.scoring_method
    from public.assessment_attempt_questions aq
    join public.assessment_questions q on q.id = aq.question_id
    where aq.attempt_id = p_attempt_id
  loop
    if v_question.scoring_method = 'AI_EVALUATED' then
      -- Deferred to human evaluation -- see the migration header for
      -- the complete reasoning. Not counted toward v_total_marks/
      -- v_score. Ensure a row exists for the evaluator workflow, but
      -- never set awarded_marks/is_correct here.
      insert into public.assessment_answers (
        attempt_id, question_id, answer_text, selected_option_ids, awarded_marks, is_correct
      ) values (
        p_attempt_id, v_question.id, null, '{}'::uuid[], null, null
      )
      on conflict (attempt_id, question_id) do nothing;

      continue;
    end if;

    v_total_marks := v_total_marks + v_question.points;

    select *
    into v_key
    from public.assessment_question_answers
    where question_id = v_question.id;

    if not found then
      raise exception 'Missing answer key for question %.', v_question.id
        using errcode = 'XX000';
    end if;

    select *
    into v_answer
    from public.assessment_answers
    where attempt_id = p_attempt_id
      and question_id = v_question.id;

    if not found then
      insert into public.assessment_answers (
        attempt_id, question_id, answer_text, selected_option_ids, awarded_marks, is_correct
      ) values (
        p_attempt_id, v_question.id, null, '{}'::uuid[], 0, false
      )
      on conflict (attempt_id, question_id) do nothing;

      select *
      into v_answer
      from public.assessment_answers
      where attempt_id = p_attempt_id
        and question_id = v_question.id;
    end if;

    if v_answer.answer_text is null and v_answer.selected_option_ids = '{}'::uuid[] then
      v_is_correct := false;
      v_awarded := 0;
    else
      if v_question.question_type in ('MCQ', 'MULTIPLE_SELECT') then
        v_is_correct := (
          v_answer.selected_option_ids is not null
          and v_key.correct_option_ids is not null
          and (select array_agg(x order by x) from unnest(v_answer.selected_option_ids) x)
            = (select array_agg(x order by x) from unnest(v_key.correct_option_ids) x)
        );
        v_awarded := case when v_is_correct then v_question.points else 0 end;
      elsif v_question.question_type = 'SHORT_ANSWER' then
        v_is_correct := (
          v_answer.answer_text is not null
          and v_key.correct_answer_text is not null
          and lower(trim(v_answer.answer_text)) = lower(trim(v_key.correct_answer_text))
        );
        v_awarded := case when v_is_correct then v_question.points else 0 end;
      else
        raise exception 'Unsupported OBJECTIVE question_type % for question %.',
          v_question.question_type, v_question.id using errcode = 'XX000';
      end if;

      update public.assessment_answers
      set awarded_marks = v_awarded,
          is_correct = v_is_correct
      where id = v_answer.id;
    end if;

    v_score := v_score + v_awarded;
  end loop;

  if v_total_marks = 0 then
    v_percentage := 100;
  else
    v_percentage := round((v_score / v_total_marks) * 100, 2);
  end if;

  update public.assessment_attempts
  set status = 'COMPLETED',
      score = v_score,
      total_marks = v_total_marks,
      percentage = v_percentage
  where id = p_attempt_id
  returning * into v_attempt;

  return v_attempt;
end;
$$;

revoke all on function public.score_assessment_attempt(uuid, uuid) from public;
revoke all on function public.score_assessment_attempt(uuid, uuid) from anon;
revoke all on function public.score_assessment_attempt(uuid, uuid) from authenticated;
grant execute on function public.score_assessment_attempt(uuid, uuid) to service_role;

-- ============================================================
-- NOT DONE HERE (explicitly, per F8.4.0's own scope boundary)
-- ============================================================
-- - No new column anywhere (evaluation_status/final_score/
--   final_total_marks/final_percentage) -- F8.4.1+.
-- - No finalization/reconciliation RPC -- F8.4.1+.
-- - No change to assessment_answers/assessment_questions/evaluator_
--   assignments/evaluations/evaluation_history RLS -- F8.2/F8.2.1/F8.1
--   already established the correct boundary; nothing here needed it
--   to change.
-- - No change to save_answer()/mark_attempt_submitted() or any other
--   backend Python function -- an AI_EVALUATED question's answer is
--   already storable exactly as-is, through the completely unmodified
--   existing path (is_question_in_attempt() only checks
--   assessment_attempt_questions membership, never scoring_method).
