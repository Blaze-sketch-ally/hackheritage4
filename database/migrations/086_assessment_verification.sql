-- Migration: 086_assessment_verification
-- Purpose: build the "an assessment pass verifies the matching skill"
-- feature that 004_assessments.sql's own header comment deferred as a
-- FUTURE INTEGRATION POINT, and that 014_score_assessment_attempt.sql /
-- 015_question_bank_random_assessment.sql never wired up -- student_skills
-- .is_verified has been permanently false on this branch until now.
--
-- Ported and adapted from a collaborator's parallel migration lineage
-- (their 015_assessment_verification.sql built the same feature against
-- their own, simpler scoring RPC), combined with their own follow-up fix
-- (031_verified_skill_proficiency_integrity.sql) from day one -- since
-- this feature has never been live on this branch, there is no historical
-- exposure window to patch separately; the trigger below is written
-- correctly the first time.
--
-- ============================================================
-- 1. assessments.passing_percentage -- the threshold PASS/FAIL and skill
--    verification are now computed against. Genuinely per-assessment, not
--    a global constant; existing rows get a documented default rather
--    than being left with an undefined threshold.
-- ============================================================
alter table assessments
  add column if not exists passing_percentage numeric(5, 2) not null default 70
    check (passing_percentage >= 0 and passing_percentage <= 100);

-- ============================================================
-- 2. student_skills.verified_at -- timestamp companion to the existing
--    is_verified boolean (003_skills.sql). Set only alongside
--    is_verified = true, by service_role, from inside
--    score_assessment_attempt() / fold_in_attempt_evaluation() below.
-- ============================================================
alter table student_skills
  add column if not exists verified_at timestamptz;

-- ============================================================
-- 3. prevent_self_skill_verification() -- CREATE OR REPLACE of the exact
--    same function/trigger from 003_skills.sql. Written in its final,
--    correct shape directly (see this migration's own header): blocks a
--    non-service_role caller from ever setting is_verified false -> true
--    or verified_at to a non-null value directly, but auto-clears an
--    existing verification (is_verified := false, verified_at := null)
--    when the student revises the self-reported proficiency_level /
--    proficiency_score it was earned against -- the verification was
--    earned against the OLD level and does not carry over. A student may
--    also voluntarily move is_verified true -> false themselves (that can
--    only lower their own standing, never inflate it).
-- ============================================================
create or replace function public.prevent_self_skill_verification()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if old.is_verified
    and (
      new.proficiency_level is distinct from old.proficiency_level
      or new.proficiency_score is distinct from old.proficiency_score
    )
  then
    new.is_verified := false;
    new.verified_at := null;
  end if;

  if old.is_verified and not new.is_verified then
    new.verified_at := null;
  end if;

  if new.is_verified and not old.is_verified then
    raise exception 'Cannot change skill verification status directly.' using errcode = '42501';
  end if;

  if new.verified_at is distinct from old.verified_at and new.verified_at is not null then
    raise exception 'Cannot change skill verification status directly.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_self_skill_verification() from public;

-- ============================================================
-- 4. score_assessment_attempt() -- CREATE OR REPLACE of the current
--    (048_ai_evaluated_attempt_participation.sql) definition, unchanged
--    except for the addition at the very end: when this attempt required
--    NO AI_EVALUATED questions (so v_percentage IS the final,
--    authoritative result -- evaluation_status will resolve to
--    NOT_REQUIRED) and it meets the assessment's passing_percentage,
--    verify the student's matching (skill_id, proficiency_level) row.
--
--    Deliberately does NOT verify here when the attempt DOES contain
--    AI_EVALUATED questions -- v_percentage/v_score only reflect the
--    objective portion in that case (see 048's own header), which is not
--    the true final result. That case is instead handled by
--    fold_in_attempt_evaluation() below, at the point it resolves to
--    evaluation_status = 'COMPLETE' and computes the real
--    final_percentage.
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
  v_requires_evaluation boolean := false;
  v_assessment record;
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
      v_requires_evaluation := true;

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

  if not v_requires_evaluation then
    select skill_id, difficulty, passing_percentage
    into v_assessment
    from public.assessments
    where id = v_attempt.assessment_id;

    if v_percentage >= v_assessment.passing_percentage then
      update public.student_skills
      set is_verified = true,
          verified_at = now()
      where student_id = p_student_id
        and skill_id = v_assessment.skill_id
        and proficiency_level = v_assessment.difficulty
        and is_verified = false;
    end if;
  end if;

  return v_attempt;
end;
$$;

revoke all on function public.score_assessment_attempt(uuid, uuid) from public;
revoke all on function public.score_assessment_attempt(uuid, uuid) from anon;
revoke all on function public.score_assessment_attempt(uuid, uuid) from authenticated;
grant execute on function public.score_assessment_attempt(uuid, uuid) to service_role;

-- ============================================================
-- 5. fold_in_attempt_evaluation() -- CREATE OR REPLACE of the current
--    (049_evaluation_status_and_final_score.sql) definition, unchanged
--    except for the addition in the final COMPLETE branch: once every
--    AI_EVALUATED question is resolved with no conflicts and
--    final_percentage is computed, verify the student's matching skill
--    the same way score_assessment_attempt() does for a NOT_REQUIRED
--    attempt -- this is the counterpart path for a mixed/AI-evaluated
--    attempt, using final_percentage (the true authoritative result for
--    that case) rather than the objective-only percentage.
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
  v_assessment record;
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

  select skill_id, difficulty, passing_percentage
  into v_assessment
  from public.assessments
  where id = v_attempt.assessment_id;

  if v_final_percentage >= v_assessment.passing_percentage then
    update public.student_skills
    set is_verified = true,
        verified_at = now()
    where student_id = v_attempt.student_id
      and skill_id = v_assessment.skill_id
      and proficiency_level = v_assessment.difficulty
      and is_verified = false;
  end if;

  return v_attempt;
end;
$$;

revoke all on function public.fold_in_attempt_evaluation(uuid) from public;
revoke all on function public.fold_in_attempt_evaluation(uuid) from anon;
revoke all on function public.fold_in_attempt_evaluation(uuid) from authenticated;
grant execute on function public.fold_in_attempt_evaluation(uuid) to service_role;
