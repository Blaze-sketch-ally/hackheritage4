-- Migration: 014_score_assessment_attempt
-- Purpose: the ONE trusted, atomic operation that scores a submitted
-- assessment attempt and completes it -- Phase 1H.
--
-- Why this needs to be a database function, not a sequence of ordinary
-- REST calls from FastAPI: Supabase PostgREST does not expose
-- cross-statement transactions to an external client -- every
-- client.table(...).execute() is its own independent request and its own
-- independent Postgres transaction. Scoring touches many
-- assessment_answers rows AND assessment_attempts in one logical
-- operation; if that were done as N+1 separate REST calls and the process
-- crashed partway through, the database would be left with some answers
-- scored, others not, and the attempt still IN_PROGRESS -- a real,
-- observable inconsistency. A single PL/pgSQL function body executes as
-- one transaction: every statement inside it commits together, or (on any
-- raised exception) the entire function's effects roll back together,
-- automatically, with no explicit BEGIN/EXCEPTION block required for that
-- guarantee.
--
-- Callable ONLY via the backend's service-role client, after the backend
-- has already verified attempt ownership through the normal
-- RLS-respecting path (build_user_client() + the existing "Students can
-- view their own attempts" policy) -- see the REVOKE/GRANT at the bottom.
-- This function does not, and must not, replace that check: it exists to
-- perform the ONE class of write that RLS structurally forbids everyone
-- except service_role from making (see prevent_self_attempt_scoring and
-- prevent_self_answer_scoring in 004_assessments.sql), not to decide who
-- is allowed to trigger it. The p_student_id parameter is a second,
-- defense-in-depth ownership check inside the trusted function itself --
-- even though the FastAPI caller already verified ownership, this
-- function does not blindly trust that call site.
--
-- Scope: scores exactly the same eligible-question population Phase
-- 1D/1G already use (review_status = APPROVED, is_active = true,
-- scoring_method = OBJECTIVE, belonging to the attempt's own assessment).
-- AI_EVALUATED questions are never selected by this function's own query
-- -- there is no AI/LLM call anywhere here, and none is possible given
-- what this function reads.
--
-- Scoring rules implemented (approved product decisions, not derived
-- from the schema itself):
--   MCQ / MULTIPLE_SELECT: exact set equality between the student's
--     selected_option_ids and the answer key's correct_option_ids ->
--     full points, otherwise 0. Compared as sorted arrays so option
--     order never matters.
--   SHORT_ANSWER (only when scoring_method = OBJECTIVE, which is the
--     only way this function ever sees a SHORT_ANSWER question at all):
--     case-insensitive, trimmed exact text match -> full points,
--     otherwise 0.
--   CODE / SUBJECTIVE reaching this function at all would mean a
--     question was classified OBJECTIVE with a type this function has no
--     rule for -- treated as a data-integrity failure (raises, rolling
--     back everything), never silently scored as 0.
--   A missing answer-key row for an eligible question is likewise a
--     data-integrity failure, not a 0 -- see the approval report for why
--     silently awarding 0 for missing data was explicitly rejected.
--   An eligible question with no saved student answer at all IS a
--     legitimate, expected case (Phase 1G's completeness gate should
--     prevent this in normal operation, but this function does not trust
--     that either) -- scored as 0/incorrect, not an error. A row is
--     INSERTed for it (answer_text = null, selected_option_ids =
--     '{}'::uuid[] as an internal-only "unanswered" sentinel that a real
--     student answer can never produce, awarded_marks = 0, is_correct =
--     false) rather than leaving no trace, so that after this function
--     returns, every eligible question has exactly one assessment_answers
--     row -- making that table the complete, permanent historical record
--     of this attempt's scored population (see the Phase 1I results
--     endpoint, which depends on this invariant). That INSERT is
--     ON CONFLICT (attempt_id, question_id) DO NOTHING, followed by a
--     mandatory re-SELECT and a content-based (not found-based) check for
--     the placeholder shape -- see the concurrency note below and the
--     inline comments in the loop -- so a real student answer racing in
--     concurrently is scored normally, never overwritten, and never
--     silently treated as unanswered.
--
-- total_marks = sum(points) over the eligible question set.
-- score = sum(awarded_marks) over the same set.
-- percentage = round((score / total_marks) * 100, 2), except when
--   total_marks = 0 (an assessment with zero currently-eligible
--   questions -- Phase 1G's own completeness check already allows this
--   attempt to have been submitted at all), in which case percentage is
--   defined as 100 and score/total_marks both remain 0 -- an explicit
--   approved product decision, not a mathematical default.
--
-- Concurrency, two distinct races:
--   1. A second, genuinely concurrent call to SCORE the SAME attempt:
--      `select ... for update` locks the attempt row for the duration of
--      this function's transaction. The second call blocks until the
--      first commits, then re-reads the row, finds status = 'COMPLETED',
--      and raises the "not eligible" exception below -- a real,
--      race-safe rejection, not a best-effort check-then-act pattern.
--   2. A concurrent POST /attempts/{id}/answers for a question this
--      function is about to treat as unanswered: Phase 1G leaves
--      status = 'IN_PROGRESS' for this function's entire duration (only
--      the final UPDATE below sets COMPLETED), so a real student answer
--      can legally arrive and race against this function's own
--      unanswered-placeholder INSERT for the exact same
--      UNIQUE(attempt_id, question_id) key. Handled with
--      ON CONFLICT (attempt_id, question_id) DO NOTHING plus a mandatory
--      re-SELECT and content-based placeholder check inside the loop --
--      never a raised unique_violation aborting an otherwise-legitimate
--      scoring transaction, never a real answer silently scored as
--      unanswered, and never an overwrite of a real answer.

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
    select q.id, q.points, q.question_type
    from public.assessment_questions q
    where q.assessment_id = v_attempt.assessment_id
      and q.review_status = 'APPROVED'
      and q.is_active = true
      and q.scoring_method = 'OBJECTIVE'
  loop
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
      -- Eligible question with no saved student answer AT THE MOMENT OF
      -- THIS SELECT: a legitimate, expected case (see header comment),
      -- scored as 0/incorrect, not an error. A placeholder row is
      -- inserted so this question becomes part of the attempt's
      -- permanent historical record -- the Phase 1I results endpoint
      -- reconstructs its question population entirely from
      -- assessment_answers, so an eligible question that never got a
      -- row would otherwise be unreconstructable after the fact (e.g.
      -- if it's later deactivated).
      --
      -- ON CONFLICT DO NOTHING (not a plain INSERT): Phase 1G leaves
      -- status = 'IN_PROGRESS' for this attempt's ENTIRE duration --
      -- only the final UPDATE below ever sets COMPLETED -- so
      -- POST /attempts/{id}/answers for this exact question can still
      -- legally land concurrently with this exact statement, racing
      -- against this placeholder INSERT for the same
      -- UNIQUE(attempt_id, question_id) key. A plain INSERT would raise
      -- unique_violation and abort this entire, otherwise-legitimate
      -- scoring transaction. ON CONFLICT DO NOTHING instead makes our
      -- INSERT a silent no-op whenever a real answer already exists or
      -- wins the race -- it NEVER overwrites, and can never overwrite,
      -- an existing row (there is no DO UPDATE clause at all).
      insert into public.assessment_answers (
        attempt_id, question_id, answer_text, selected_option_ids, awarded_marks, is_correct
      ) values (
        p_attempt_id, v_question.id, null, '{}'::uuid[], 0, false
      )
      on conflict (attempt_id, question_id) do nothing;

      -- Re-read is required, not optional: after the statement above,
      -- UNIQUE(attempt_id, question_id) guarantees exactly one row now
      -- exists for this pair -- either the placeholder this statement
      -- just inserted, or a real answer that raced in and won (our
      -- INSERT silently did nothing in that case). Scoring must judge
      -- which one it is from this fresh row's actual CONTENT, not from
      -- the fact that the FIRST select above found nothing -- that
      -- information is now stale and must not be trusted.
      select *
      into v_answer
      from public.assessment_answers
      where attempt_id = p_attempt_id
        and question_id = v_question.id;
    end if;

    -- v_answer is now always populated: either found by the first
    -- SELECT (the ordinary case, unchanged from before), or resolved by
    -- the insert-or-reread above. Distinguish the internal
    -- unanswered-placeholder sentinel from a genuine student answer BY
    -- CONTENT: answer_text IS NULL AND selected_option_ids = '{}'::uuid[]
    -- is a shape the public answer-saving API can never produce
    -- (AssessmentAnswerRequest's model_validator always rejects an empty
    -- selected_option_ids array, and always requires at least one of
    -- answer_text/selected_option_ids), so it unambiguously identifies
    -- "no answer was ever submitted" regardless of whether this
    -- iteration's own INSERT created that row or it already existed. A
    -- real answer that won the race above is therefore scored normally
    -- here, exactly like any other answered question -- never silently
    -- treated as unanswered, and never overwritten by the placeholder.
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

-- Explicitly close off the default PUBLIC execute privilege Postgres
-- grants on new functions, then grant ONLY to service_role -- this
-- function performs privileged writes that bypass RLS and the
-- prevent_self_*_scoring triggers by design; it must never be directly
-- callable by anon or authenticated, only by the trusted backend.
revoke all on function public.score_assessment_attempt(uuid, uuid) from public;
revoke all on function public.score_assessment_attempt(uuid, uuid) from anon;
revoke all on function public.score_assessment_attempt(uuid, uuid) from authenticated;
grant execute on function public.score_assessment_attempt(uuid, uuid) to service_role;
