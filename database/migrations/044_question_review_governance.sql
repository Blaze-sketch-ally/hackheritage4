-- Migration: 044_question_review_governance
-- Purpose: Phase F7.1 -- the database foundation for the approved F7
-- "Review Governance & History" scope, per the F7 architecture audit.
-- Adds the minimal additive model the audit concluded was justified:
--
--   assessment_questions.reviewed_by  -- who made the CURRENT review
--                                        decision (server-controlled)
--   assessment_questions.review_note  -- their optional note/reason
--
-- This is deliberately a LATEST-REVIEW-STATE model, not a review-history
-- table. The F7 audit explicitly found no justification for a
-- `question_reviews` table yet (nothing in the authoritative spec or the
-- current UX gap asks "show me every past decision across every
-- resubmission" -- only "who decided this, and why, right now"). If that
-- ever becomes a real requirement, this project already has a proven,
-- reusable append-only-audit-table pattern
-- (faculty_assessment_permission_audit, 027) to apply -- not invented
-- here, not needed yet.
--
-- Three pieces, all additive, none touching migrations 001-043:
--
--   1. Two nullable columns on assessment_questions, reusing this
--      project's own established precedent for exactly this shape
--      (037_faculty_opportunities_and_expressions.sql's
--      reviewed_by/reviewer_note on faculty_industry_opportunity_
--      expressions and its Institution counterpart) rather than
--      inventing a new column-naming/typing convention.
--
--   2. review_question() gains an optional third parameter (p_note),
--      via DROP + CREATE (a parameter-list change is a new overload in
--      Postgres, not something CREATE OR REPLACE can express) with a
--      DEFAULT of NULL -- the existing backend caller
--      (question_bank_service.py's set_review_status(), which calls
--      client.rpc("review_question", {"p_question_id":...,
--      "p_decision":...}) with exactly those two named parameters) is
--      completely unaffected: PostgREST resolves the missing p_note to
--      its default, identically to before this migration. No backend
--      or frontend file needs to change for F7.1.
--
--   3. prevent_unauthorized_question_review() is extended to cover the
--      two new fields under the EXACT SAME immutability guarantee as
--      every other content field -- once APPROVED, neither can ever
--      change again -- plus new, narrow rules specific to review
--      governance (see part 3 below for the full reasoning).
--
-- ============================================================
-- 1. assessment_questions: two additive, nullable columns
-- ============================================================
-- Same FK/nullability shape as assessment_questions.created_by (015)
-- and as 037's reviewed_by precedent: nullable, ON DELETE SET NULL (a
-- deleted reviewer account must not block or cascade-delete the
-- question they once reviewed), no default, no backfill -- every
-- existing question (PENDING, APPROVED, or REJECTED) remains completely
-- valid with both columns NULL. An existing APPROVED question simply
-- has no recorded reviewer identity for the decision that already
-- happened before this migration existed -- exactly as F6's own two
-- metadata columns launched NULL for every pre-existing row.
alter table assessment_questions
  add column if not exists reviewed_by uuid references profiles (id) on delete set null,
  add column if not exists review_note text;

-- ============================================================
-- 2. review_question(): gain an optional review note, via DROP + CREATE
--    (changing the parameter list requires this -- CREATE OR REPLACE
--    cannot alter a function's signature). Every existing check
--    (decision-value validity, FACULTY role, row lookup/lock,
--    self-review block, PENDING-only, the assessment_reviewer
--    capability check, and the F6.3 approval-readiness guard) is
--    reproduced completely unchanged, in the same order. The only
--    change is the final UPDATE statement, which now also sets
--    reviewed_by = auth.uid() and review_note = p_note.
--
--    reviewed_by is set here for clarity at the call site (matching
--    this migration's own header framing of "conceptually p_question_id,
--    p_decision, p_note"), but per part 3 below, prevent_unauthorized_
--    question_review() independently re-verifies (and would correct)
--    this value regardless of what this function -- or any other caller
--    reaching this table's UPDATE policy directly -- sends. That trigger,
--    not this RPC, is the actual security boundary for "reviewed_by can
--    never be spoofed," exactly as it already is for every other
--    ownership/content rule in this table (see 015's own header comment
--    on why the trigger, not RLS or this RPC alone, is authoritative).
-- ============================================================
drop function if exists public.review_question(uuid, text);

create or replace function public.review_question(
  p_question_id uuid,
  p_decision text,
  p_note text default null
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
  -- review_status/reviewed_by/review_note changed," "reviewed_by equals
  -- the acting caller," and "caller is not the creator," so this
  -- function's own checks above (including reviewed_by/review_note here)
  -- are defense in depth for a database-side invariant, not application
  -- logic standing in for it.
  update public.assessment_questions
  set review_status = p_decision,
      reviewed_by = auth.uid(),
      review_note = p_note
  where id = p_question_id
  returning * into v_question;

  return v_question;
end;
$$;

revoke all on function public.review_question(uuid, text, text) from public;
revoke all on function public.review_question(uuid, text, text) from anon;
grant execute on function public.review_question(uuid, text, text) to authenticated;

-- ============================================================
-- 3. Extend prevent_unauthorized_question_review() for review governance.
--    CREATE OR REPLACE, not an edit to 015/043's own files -- same
--    precedent those two migrations themselves already established for
--    this exact function. Every existing comparison in every existing
--    branch is reproduced completely unchanged; only the additions below
--    (marked F7.1) are new.
--
--    Three distinct new rules, matching the F7.1 brief's own three
--    sub-questions:
--
--    a) APPROVED-immutable branch: reviewed_by/review_note join the
--       existing content-immutability list. Once APPROVED, a client can
--       no more rewrite who reviewed a question, or why, than it can
--       rewrite the question's own text -- this is the same historical-
--       integrity guarantee F6 already extended once for its two fields,
--       applied identically here.
--
--    b) Reviewer branch (caller is not the question's own creator): the
--       set of fields a reviewer may touch grows from {review_status} to
--       {review_status, reviewed_by, review_note} -- and nothing else;
--       every other existing comparison in this branch (question_text,
--       question_type, ..., learning_objective, estimated_time_minutes)
--       is untouched, so a reviewer still cannot touch question content.
--       Critically, reviewed_by is not simply added to the "allowed to
--       change" set -- it is independently constrained to equal
--       auth.uid() whenever it changes. This is what actually closes the
--       direct-PostgREST bypass case: 041's own UPDATE policy already
--       permits a reviewer to UPDATE a PENDING row they don't own
--       (review_question() exists precisely because RLS alone was never
--       sufficient here -- see 016's header), so without this check nothing
--       would stop `PATCH .../assessment_questions?id=eq.X` with an
--       arbitrary reviewed_by from succeeding outside review_question()
--       entirely. Mirrors this project's own existing precedent for the
--       identical concern (037's guard_faculty_industry_eoi_update:
--       "reviewed_by is always the acting reviewer, never client-
--       supplied").
--
--    c) Owner (author) branch: an author must never be able to set
--       reviewed_by/review_note to an arbitrary value -- these fields
--       describe a reviewer's decision, never the author's own. The ONE
--       legitimate way they change under the author's own hand is
--       resubmission (REJECTED -> PENDING, or more generally any
--       author-driven transition INTO PENDING): F7 is explicitly a
--       latest-review-state model, not a history table, so once a
--       question is back under active authorship review, a stale
--       reviewed_by/review_note from the PRIOR (no-longer-current)
--       decision must not go on misleadingly describing content that
--       hasn't been reviewed yet. That transition therefore forces both
--       fields to NULL -- never to any author-supplied value -- as a
--       side effect, exactly as the brief required: "a subsequent review
--       overwrites reviewed_by/review_note... no fake multi-cycle
--       history should be implied." Any OTHER attempt by the owner to
--       touch these two fields (an ordinary edit that does not resubmit,
--       e.g. fixing a typo while a REJECTED question still shows why it
--       was rejected) is rejected outright -- exactly the same shape as
--       the pre-existing self-review-transition check immediately above
--       it in this same branch.
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
      -- F7.1: the reviewer's identity and note are part of the same
      -- historical-integrity guarantee as every other content field.
      or new.reviewed_by is distinct from old.reviewed_by
      or new.review_note is distinct from old.review_note
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

    -- F7.1: resubmission always clears the previous review's identity/
    -- note -- F7 is a latest-review-state model, not a history table, so
    -- once the question is back under active authorship review these
    -- fields must not go on describing a decision that no longer applies
    -- to the (unreviewed) content the author is now resubmitting. This is
    -- the ONLY way these two fields may change under the author's own
    -- hand, and it always clears to NULL -- never to an author-supplied
    -- value.
    if new.review_status is distinct from old.review_status and new.review_status = 'PENDING' then
      new.reviewed_by := null;
      new.review_note := null;
    elsif new.reviewed_by is distinct from old.reviewed_by
      or new.review_note is distinct from old.review_note
    then
      raise exception 'Only a reviewer may set reviewed_by/review_note.' using errcode = '42501';
    end if;
  else
    -- A reviewer (any other faculty member, RLS already confirmed the row
    -- was PENDING) may only ever change review_status, reviewed_by, and
    -- review_note -- never the question's actual content, including the
    -- F6 metadata fields.
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
      raise exception 'Reviewers may only change review_status, reviewed_by, and review_note.'
        using errcode = '42501';
    end if;

    -- F7.1: reviewed_by, whenever it changes, must equal the acting
    -- caller's own identity -- never trust a client-supplied value, even
    -- one arriving through review_question() itself, and especially not
    -- one arriving through a direct PostgREST UPDATE that never called
    -- that RPC at all (041's own UPDATE policy permits a reviewer to
    -- UPDATE a PENDING row they don't own -- this check, not that policy,
    -- is what actually prevents identity spoofing on that path).
    if new.reviewed_by is distinct from old.reviewed_by and new.reviewed_by is distinct from auth.uid() then
      raise exception 'reviewed_by must be the acting reviewer.' using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_unauthorized_question_review() from public;
