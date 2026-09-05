-- Migration: 043_question_authoring_metadata
-- Purpose: Phase F6.1-F6.3 -- the first controlled Question Authoring
-- extension slice, per the approved F6 architecture audit. Two pieces:
--
--   1. Two small, additive, nullable metadata columns on
--      assessment_questions (learning_objective, estimated_time_minutes),
--      with the EXISTING approved-question immutability trigger
--      (prevent_unauthorized_question_review, 015) extended to cover
--      them -- so the project's central historical-integrity guarantee
--      ("an approved question's content can never change, so a completed
--      attempt can never retroactively diverge from what a student
--      actually saw") is preserved for these new fields exactly as it
--      already is for question_text/points/etc.
--
--   2. A database-side guard, inside the EXISTING review_question() RPC
--      (016, hardened by 041), that blocks a question from reaching
--      review_status = 'APPROVED' unless it is actually structurally
--      scoreable by the existing score_assessment_attempt() function
--      (015). The F6 audit (Sections 6/16/31) found this was previously
--      possible: an OBJECTIVE MCQ/MULTIPLE_SELECT question with no answer
--      key, or with correct_option_ids referencing an option that doesn't
--      belong to it, or with fewer than 2 options, or a SHORT_ANSWER
--      question with no correct_answer_text, could all be approved and
--      then hard-fail scoring (an unhandled 'XX000' exception) the first
--      time a student's attempt actually reached them. A CODE/SUBJECTIVE
--      question marked OBJECTIVE (a combination the scoring function has
--      never supported, and no UI has ever offered, but the schema's own
--      CHECK constraint never blocked) had the same failure mode. This
--      migration closes that gap AT THE ONLY POINT the audit identified
--      as safe to enforce it: approval time, not creation/edit time --
--      review_question() already has the complete, current row (question
--      + its options + its answer key) in hand, so this is a single
--      additional set of checks immediately before its existing UPDATE,
--      not a new lifecycle state and not a constraint on ordinary
--      PENDING-question PATCH/draft-saving, which remains exactly as
--      permissive as before (see the header of 015 for why partial-draft
--      saving is intentional).
--
-- ============================================================
-- WHY NO `domain` COLUMN IN THIS MIGRATION
-- ============================================================
-- The F6 implementation brief allowed `domain` only if the existing
-- skills/skill_categories taxonomy (003_skills.sql) "clearly supports a
-- safe FK/reference" at the QUESTION level, and required deferring it
-- with an explicit report otherwise. Re-inspected here: skill_categories
-- is a broad, evolving lookup table (e.g. "Programming Languages") that
-- already applies to a question's parent skill via
-- assessment_questions -> assessments.skill_id -> skills.category_id --
-- a working, if indirect, path already exists. Adding a SEPARATE,
-- independently-settable assessment_questions.category_id (or a new
-- `domain` text/FK column) would create a second, question-level source
-- of truth for a concept the assessment's own skill already carries, with
-- no mechanism to keep the two in sync and no traced product requirement
-- (in the audit's own words) for a question to ever belong to a
-- DIFFERENT domain than its parent assessment's skill. This is exactly
-- the "ambiguous -- stop and report rather than invent architecture"
-- case the brief anticipated. DEFERRED, not implemented -- see the F6.1-
-- F6.3 implementation report for the explicit writeup.
--
-- ============================================================
-- 1. assessment_questions: two additive, nullable metadata columns
-- ============================================================
-- Nullable, no default requiring backfill -- existing rows (and every
-- question created before this migration is applied) remain completely
-- valid with both columns NULL, exactly the same "safe to add, safe to
-- ignore" shape as generation_source/generation_model/generated_at in
-- 004_assessments.sql.
--
-- learning_objective: free text, same type/nullability convention as
-- assessments.description (004) -- a short, unconstrained prose field,
-- not a controlled vocabulary.
--
-- estimated_time_minutes: MINUTES, explicitly named as such (unlike the
-- ambiguous generic "estimated_time" the brief used) to avoid exactly the
-- unit ambiguity the brief warned about. Same int + `> 0` CHECK + nullable
-- shape as the existing assessments.duration_minutes (004) -- the one
-- existing per-item duration field in this schema -- reused verbatim
-- rather than inventing a new numeric convention.
alter table assessment_questions
  add column if not exists learning_objective text,
  add column if not exists estimated_time_minutes int check (estimated_time_minutes > 0);

-- ============================================================
-- 2. Extend the EXISTING approved-question immutability trigger (015) to
--    cover both new columns. CREATE OR REPLACE, not an edit to 015's own
--    file -- same precedent as 041 replacing this same function to add no
--    new comparisons (041 only added the capability check to the
--    review_question RPC, not this trigger) -- and as 016/041 replacing
--    review_question() itself. Every existing comparison in both branches
--    (the APPROVED-immutable branch, and the reviewer-may-only-touch-
--    review_status branch) is reproduced completely unchanged below --
--    only the two new field comparisons are added, one line each, to each
--    branch's list.
-- ============================================================
create or replace function public.prevent_unauthorized_question_review()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if old.review_status = 'APPROVED' then
    -- Approved questions are content-immutable. is_active is the one
    -- exception -- retiring a flawed approved question from future
    -- selection must not rewrite history for attempts that already used
    -- it (see assessment_attempt_questions and score_assessment_attempt(),
    -- neither of which re-checks is_active once a question has been
    -- persisted to an attempt).
    if new.question_text is distinct from old.question_text
      or new.question_type is distinct from old.question_type
      or new.scoring_method is distinct from old.scoring_method
      or new.difficulty is distinct from old.difficulty
      or new.points is distinct from old.points
      or new.display_order is distinct from old.display_order
      or new.review_status is distinct from old.review_status
      or new.created_by is distinct from old.created_by
      or new.learning_objective is distinct from old.learning_objective
      or new.estimated_time_minutes is distinct from old.estimated_time_minutes
    then
      raise exception 'Cannot modify an approved question, other than deactivating it.'
        using errcode = '42501';
    end if;
    return new;
  end if;

  if new.created_by = auth.uid() then
    -- The question's own setter may edit its content freely while it is
    -- not yet approved (including moving a REJECTED question back to
    -- PENDING after revising it) but may never approve or reject their
    -- own question.
    if new.review_status is distinct from old.review_status
      and new.review_status in ('APPROVED', 'REJECTED')
    then
      raise exception 'Cannot review your own question.' using errcode = '42501';
    end if;
  else
    -- A reviewer (any other faculty member, RLS already confirmed the row
    -- was PENDING) may only ever change review_status -- never the
    -- question's actual content, including the two new metadata fields.
    if new.question_text is distinct from old.question_text
      or new.question_type is distinct from old.question_type
      or new.scoring_method is distinct from old.scoring_method
      or new.difficulty is distinct from old.difficulty
      or new.points is distinct from old.points
      or new.display_order is distinct from old.display_order
      or new.is_active is distinct from old.is_active
      or new.created_by is distinct from old.created_by
      or new.learning_objective is distinct from old.learning_objective
      or new.estimated_time_minutes is distinct from old.estimated_time_minutes
    then
      raise exception 'Reviewers may only change review_status.' using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_unauthorized_question_review() from public;

-- ============================================================
-- 3. review_question(): add the approval-readiness guard. CREATE OR
--    REPLACE over 041's version -- every existing check (decision-value
--    validity, FACULTY role, row lookup/lock, self-review block,
--    PENDING-only, and the F5A assessment_reviewer capability check) is
--    reproduced completely unchanged, in the same order, with the new
--    scoreability guard inserted immediately before the existing final
--    UPDATE, and ONLY when p_decision = 'APPROVED' (a REJECTED decision
--    never needs a scoreable question -- rejecting a broken draft must
--    always remain possible). The trigger this RPC's internal UPDATE
--    still fires (prevent_unauthorized_question_review, above) is
--    completely unaffected by this addition.
--
--    Scope of the guard, deliberately minimal (see this migration's
--    header comment and the F6.1-F6.3 implementation report for the full
--    reasoning):
--      - Applies ONLY when scoring_method = 'OBJECTIVE' -- an
--        AI_EVALUATED question is never selected by create_assessment_
--        attempt() (015 filters scoring_method = 'OBJECTIVE' only), so it
--        can never reach score_assessment_attempt() at all; guarding its
--        approval here would be enforcing a rule with no corresponding
--        failure mode to prevent, and would risk inventing scoring
--        semantics for a method this project has never implemented --
--        explicitly out of scope.
--      - question_type must be one of the three types
--        score_assessment_attempt() actually implements
--        (MCQ/MULTIPLE_SELECT/SHORT_ANSWER, 015) -- blocks the confirmed
--        CODE/SUBJECTIVE + OBJECTIVE latent-failure combination from ever
--        reaching APPROVED, without adding any new scoring capability for
--        either type.
--      - MCQ/MULTIPLE_SELECT: an answer key row must exist, its
--        correct_option_ids must be non-null and non-empty, every id in
--        it must belong to this question's own assessment_question_options
--        (closing the "stale/foreign reference silently never matches at
--        scoring time" gap the audit flagged), the question must have at
--        least 2 options (matching the frontend's own existing minimum,
--        now DB-enforced at the one point that matters), and MCQ
--        specifically must have EXACTLY one correct option (matching the
--        existing, documented MCQ semantics -- MULTIPLE_SELECT allows one
--        or more).
--      - SHORT_ANSWER: an answer key row must exist with a non-null,
--        non-blank correct_answer_text.
--
--    Deliberately NOT enforced here (out of scope for F6.1-F6.3, per the
--    brief): fuzzy/partial-credit matching semantics, any check on
--    explanation, any AI_EVALUATED/rubric concept, any change to how
--    score_assessment_attempt() itself reads these rows.
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
  v_answer_key public.assessment_question_answers;
  v_option_count int;
  v_valid_correct_count int;
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

  if p_decision = 'APPROVED' and v_question.scoring_method = 'OBJECTIVE' then
    if v_question.question_type not in ('MCQ', 'MULTIPLE_SELECT', 'SHORT_ANSWER') then
      raise exception
        'Cannot approve question %: OBJECTIVE scoring is not implemented for question_type %.',
        v_question.id, v_question.question_type
        using errcode = '55001';
    end if;

    select *
    into v_answer_key
    from public.assessment_question_answers
    where question_id = v_question.id;

    if not found then
      raise exception 'Cannot approve question %: no answer key exists.', v_question.id
        using errcode = '55001';
    end if;

    if v_question.question_type in ('MCQ', 'MULTIPLE_SELECT') then
      if v_answer_key.correct_option_ids is null
        or array_length(v_answer_key.correct_option_ids, 1) is null
      then
        raise exception 'Cannot approve question %: no correct option(s) specified.', v_question.id
          using errcode = '55001';
      end if;

      if v_question.question_type = 'MCQ' and array_length(v_answer_key.correct_option_ids, 1) <> 1 then
        raise exception
          'Cannot approve MCQ question %: exactly one correct option is required, found %.',
          v_question.id, array_length(v_answer_key.correct_option_ids, 1)
          using errcode = '55001';
      end if;

      select count(*)
      into v_option_count
      from public.assessment_question_options
      where question_id = v_question.id;

      if v_option_count < 2 then
        raise exception 'Cannot approve question %: at least 2 options are required, found %.',
          v_question.id, v_option_count
          using errcode = '55001';
      end if;

      select count(*)
      into v_valid_correct_count
      from public.assessment_question_options o
      where o.question_id = v_question.id
        and o.id = any (v_answer_key.correct_option_ids);

      if v_valid_correct_count <> array_length(v_answer_key.correct_option_ids, 1) then
        raise exception
          'Cannot approve question %: correct_option_ids references an option that does not belong to this question.',
          v_question.id
          using errcode = '55001';
      end if;
    elsif v_question.question_type = 'SHORT_ANSWER' then
      if v_answer_key.correct_answer_text is null or length(trim(v_answer_key.correct_answer_text)) = 0 then
        raise exception
          'Cannot approve question %: correct_answer_text is required for SHORT_ANSWER questions.',
          v_question.id
          using errcode = '55001';
      end if;
    end if;
  end if;

  -- Fires prevent_unauthorized_question_review same as any other UPDATE
  -- to this table -- that trigger independently re-confirms "only
  -- review_status changed" and "caller is not the creator," so this
  -- function's own checks above (including the new scoreability guard)
  -- are defense in depth for a database-side invariant, not application
  -- logic standing in for it.
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

