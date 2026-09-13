-- Migration: 067_skill_verification_fold_in_fix
-- Purpose: fix a real bug in the skill-verification fold-in step of
-- public.score_assessment_attempt() (originally 014_score_assessment_attempt.sql,
-- CREATE OR REPLACEd by 015_assessment_verification.sql). Forward migration
-- in this branch's own numbering -- no historical migration file is
-- edited, and 015's own body (reproduced in full below, per that file's
-- own "historical migrations are never edited" convention for this exact
-- function) is otherwise untouched.
--
-- ============================================================
-- The bug
-- ============================================================
-- 015's verification step (its own comment, reproduced verbatim, said so
-- explicitly):
--
--   "if no student_skills row exists for this exact (skill_id,
--   proficiency_level) pair, this UPDATE simply matches zero rows and
--   changes nothing."
--
-- That is not a hypothetical -- it is the normal case whenever a student
-- takes an assessment whose difficulty does not exactly equal their
-- CURRENT self-reported student_skills.proficiency_level at the moment
-- scoring runs. Nothing prevents this:
--   * GET /assessments (assessment_service.list_assessments_for_student)
--     returns EVERY active assessment for a selected skill_id, at every
--     difficulty tier -- not filtered to the student's current
--     proficiency_level.
--   * POST /assessments/{id}/attempts (assessment_service.student_has_skill)
--     only requires the student to have added the skill AT SOME level --
--     not the level matching this specific assessment's difficulty.
--   * The Student Skills page's own "matching assessment" lookup
--     (frontend/components/student/skills/student-skills-view.tsx,
--     keyFor(skill_id, proficiency_level)) only ever shows the ONE
--     assessment matching the CURRENTLY DECLARED level -- but a student
--     can still reach and pass a different-difficulty assessment for the
--     same skill via the general Assessments list, entirely legitimately
--     (e.g. attempting a harder tier to advance).
--
-- Result (the exact reported symptom): a student takes an assessment,
-- passes it, POST /attempts/{id}/score correctly returns passed=true, and
-- score_assessment_attempt() completes the attempt -- but the
-- student_skills UPDATE silently matches zero rows because
-- proficiency_level ('Beginner', say) does not equal the assessment's
-- difficulty ('Advanced', say). is_verified stays false forever, with no
-- error anywhere, and the Student Skills page correctly (the frontend has
-- no bug -- audited: it reads is_verified end-to-end, no field-name
-- mismatch anywhere in this codebase) shows "Not Verified" for a skill the
-- student just proved they have.
--
-- ============================================================
-- Fix
-- ============================================================
-- Extend the SAME function (CREATE OR REPLACE, same signature): on a
-- passing attempt, instead of one exact-match UPDATE, resolve the
-- student's existing student_skills row for (student_id, skill_id) --
-- canonical FK columns, never name-matched -- and rank the assessment's
-- difficulty against that row's CURRENT proficiency_level on the same
-- fixed 'Beginner' < 'Intermediate' < 'Advanced' < 'Expert' scale already
-- shared by both columns (004_assessments.sql's own stated reason for
-- reusing that exact scale):
--
--   * No row exists at all for (student_id, skill_id) (e.g. the student
--     removed the skill from their profile after starting the attempt but
--     before it was scored -- the only way this can happen, since
--     student_has_skill already required the row to exist at attempt
--     creation): INSERT one, at the assessment's own difficulty, verified.
--     This is the "safely create if the row is missing" behavior the
--     schema's existing design calls for -- never a silent no-op.
--   * A row exists and its proficiency_level ranks AT OR BELOW the
--     assessment's difficulty (the normal case, including the pre-existing
--     exact-match case): the row is brought up to (or confirmed at) the
--     assessment's difficulty and marked verified. A student who passes a
--     HIGHER-or-equal-difficulty assessment than they had declared has
--     directly earned verification at that level -- withholding it, as
--     before, was the bug.
--   * A row exists and its proficiency_level ranks ABOVE the assessment's
--     difficulty: left completely untouched. Passing a lower-tier
--     assessment must never verify (or otherwise touch) a higher,
--     self-declared-but-unproven level -- doing so would fabricate
--     verification for a level never actually attempted, exactly the kind
--     of readiness inflation 031_verified_skill_proficiency_integrity.sql
--     was written to prevent from the opposite direction (self-editing
--     proficiency_level upward while keeping an old verified badge). This
--     also means an already-verified higher-level skill can never be
--     downgraded by a later lower-tier attempt, passing or failing.
--
-- The UPDATE branch's WHERE clause additionally only fires when something
-- would actually change (proficiency_level differs, or is_verified is
-- currently false) -- re-scoring physically cannot happen (an attempt
-- transitions to COMPLETED and score_attempt() is re-entered only via the
-- documented, harmless "lost the race, sees COMPLETED, 409s" path with no
-- second write attempt), but this keeps the write a true no-op, not just a
-- value-identical one, if it is ever reached twice for the same state.
--
-- ============================================================
-- What is deliberately NOT changed
-- ============================================================
-- * Every other line of scoring logic (question loop, answer comparison,
--   totals, the COMPLETED transition, the PASS/FAIL threshold itself --
--   still the single v_assessment.passing_percentage, compared with the
--   exact same v_percentage used for the attempt's own passed/fail
--   outcome) is byte-for-byte unchanged from 015_assessment_verification.sql.
-- * No new column, no new table, no new verification field. Still exactly
--   student_skills.is_verified / verified_at, the pair 015 established.
-- * No change to prevent_self_skill_verification() (003_skills.sql,
--   CREATE OR REPLACEd by 015 and again by 031) -- this function still
--   runs entirely as service_role, which that trigger already steps aside
--   for unconditionally.
-- * No change to create_assessment_attempt(), the blueprint/question
--   selection, or anything AI_EVALUATED/SUBJECTIVE-related -- confirmed
--   during this fix's audit that no AI_EVALUATED/faculty-evaluation
--   scoring path exists anywhere in the backend (SUBJECTIVE/AI_EVALUATED
--   are schema-only enum values with zero implementing logic today), so
--   there is nothing else to route through this fold-in.
-- * assessments.skill_id is singular (one assessment = one skill; see
--   004_assessments.sql's own "One assessment belongs to exactly one
--   skill" comment) -- there is no multi-skill-per-assessment case to
--   handle here.
-- * The revoke/grant footer is identical to 015's.

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
  v_assessment public.assessments;
  v_total_marks numeric(6, 2) := 0;
  v_score numeric(6, 2) := 0;
  v_percentage numeric(5, 2);
  v_question record;
  v_key record;
  v_answer record;
  v_is_correct boolean;
  v_awarded numeric(6, 2);
  v_skill public.student_skills;
  v_new_rank int;
  v_existing_rank int;
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

  select * into v_assessment from public.assessments where id = v_attempt.assessment_id;

  for v_question in
    select q.id, q.points, q.question_type
    from public.assessment_attempt_questions aq
    join public.assessment_questions q on q.id = aq.question_id
    where aq.attempt_id = p_attempt_id
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

  -- Skill verification fold-in -- fixed in 067_skill_verification_fold_in_fix.sql
  -- (see that migration's header for the full root-cause writeup). Never
  -- downgrades: a row ranked ABOVE the assessment's own difficulty is left
  -- untouched; a missing row is created rather than silently skipped; an
  -- at-or-below row is brought up to this difficulty and verified. Uses
  -- canonical skill_id (never a name match) throughout.
  if v_percentage >= v_assessment.passing_percentage then
    v_new_rank := case v_assessment.difficulty
      when 'Beginner' then 1
      when 'Intermediate' then 2
      when 'Advanced' then 3
      when 'Expert' then 4
    end;

    select *
    into v_skill
    from public.student_skills
    where student_id = p_student_id
      and skill_id = v_assessment.skill_id
    for update;

    if not found then
      -- The row that authorized this attempt's creation (student_has_skill)
      -- no longer exists -- the student removed the skill after starting
      -- the attempt but before it was scored. Create it rather than
      -- silently losing a genuine pass.
      insert into public.student_skills (
        student_id, skill_id, proficiency_level, is_verified, verified_at
      ) values (
        p_student_id, v_assessment.skill_id, v_assessment.difficulty, true, now()
      )
      on conflict (student_id, skill_id) do nothing;
    else
      v_existing_rank := case v_skill.proficiency_level
        when 'Beginner' then 1
        when 'Intermediate' then 2
        when 'Advanced' then 3
        when 'Expert' then 4
      end;

      if v_new_rank >= v_existing_rank then
        update public.student_skills
        set proficiency_level = v_assessment.difficulty,
            is_verified = true,
            verified_at = now()
        where id = v_skill.id
          and (
            proficiency_level is distinct from v_assessment.difficulty
            or not is_verified
          );
      end if;
      -- else: the student passed a LOWER-difficulty assessment than their
      -- already-declared level -- leave the row untouched. Never fabricate
      -- verification for a higher level never actually attempted.
    end if;
  end if;

  return v_attempt;
end;
$$;

revoke all on function public.score_assessment_attempt(uuid, uuid) from public;
revoke all on function public.score_assessment_attempt(uuid, uuid) from anon;
revoke all on function public.score_assessment_attempt(uuid, uuid) from authenticated;
grant execute on function public.score_assessment_attempt(uuid, uuid) to service_role;
