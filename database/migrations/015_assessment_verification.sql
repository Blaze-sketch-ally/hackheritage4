-- Migration: 015_assessment_verification
-- Purpose: connects the existing Skill (003_skills.sql) and Assessment
-- (004_assessments.sql / 014_score_assessment_attempt.sql) foundations
-- into one working "declare a skill -> take its assessment -> get
-- verified" flow, and replaces "the whole live question pool is the
-- exam" with "the backend randomly selects and permanently freezes N
-- questions per attempt."
--
-- NAMING NOTE: the product spec that produced this migration describes
-- assessment/question difficulty tiers as BASIC / INTERMEDIATE / ADVANCED.
-- This schema already has a 4-value scale for exactly this concept --
-- assessments.difficulty and assessment_questions.difficulty
-- (004_assessments.sql), and student_skills.proficiency_level
-- (003_skills.sql) -- all three using ('Beginner', 'Intermediate',
-- 'Advanced', 'Expert'). Reusing that existing scale rather than adding a
-- second, parallel 'Basic'/'Beginner' enum for the same concept: "BASIC"
-- in product language IS "Beginner" in this schema. No new enum value is
-- introduced by this migration.
--
-- Two independent pieces, ported vs. new:
--
-- PORTED (adapted from the unmerged feature/question-bank-random-
-- assessment branch's own 015/020 migrations, which were independently
-- verified against a real Supabase project -- see that branch's
-- docs/architecture/assessment-lifecycle.md). Only the parts needed for
-- server-side randomized question selection are ported. Deliberately
-- EXCLUDED: created_by, is_faculty(), the peer-review workflow/trigger,
-- and every faculty-facing RLS policy from that branch -- none of it is
-- needed here, since this phase's question bank is populated directly by
-- service_role (curated/seeded), exactly like assessments and
-- assessment_questions already are today. Nothing here forecloses adding
-- that workflow later; assessment_questions.review_status/is_active
-- already support it unchanged.
--   - assessment_blueprint_rules: per-assessment, per-difficulty question
--     COUNT configuration (no content, no answer keys -- just how many
--     questions of which difficulty an attempt should draw).
--   - assessment_attempt_questions: the immutable, per-attempt persisted
--     random selection. Once written, never updated -- see the header
--     comment on the table itself.
--   - create_assessment_attempt(): the one atomic, service_role-only
--     operation that starts an attempt AND persists its random question
--     selection in the same transaction.
--   - score_assessment_attempt(): CREATE OR REPLACE, not an edit to
--     014_score_assessment_attempt.sql (historical migrations are never
--     rewritten). Reads the attempt's own persisted selection instead of
--     live-querying by assessment_id; every other line of scoring logic
--     is unchanged from 014.
--   - Two additive SELECT-only RLS policies so a student can still see a
--     question/option that was legitimately part of one of their own
--     attempts even if it is later deactivated -- otherwise
--     GET /attempts/{id}/questions could break for reasons entirely
--     outside the student's control.
--
-- CORRECTION vs. the branch this was ported from: that branch's own
-- 015/020 migrations left assessment_question_answers' "own completed
-- attempt" SELECT policy (004_assessments.sql) untouched, on the theory
-- that it "already has no is_active dependency and must never be
-- widened by anything pre-completion." That reasoning does not survive
-- this migration's own change: the 004-era policy grants access to the
-- answer key for every question belonging to the SAME ASSESSMENT as a
-- completed attempt (it joins assessment_questions.assessment_id =
-- assessment_attempts.assessment_id). That was correct back when "the
-- whole live question pool is the exam" -- every approved question WAS
-- part of every attempt. It is a straight answer-key leak now that an
-- attempt only ever contains a random N-question subset
-- (assessment_attempt_questions): as soon as a student completes ONE
-- attempt on an assessment, the old policy hands them the answer key for
-- every OTHER question in that assessment's bank too, including ones
-- never shown to them. Verified against a live Postgres instance: with
-- the 004-era policy in place, a student whose completed attempt froze
-- only questions Q1/Q3 out of a Q1/Q2/Q3 pool could still SELECT the
-- answer key row for Q2. This migration therefore replaces that policy
-- (DROP + CREATE -- Postgres has no CREATE OR REPLACE POLICY) with one
-- scoped through assessment_attempt_questions, so only the questions
-- actually frozen into the student's own completed attempt(s) are ever
-- exposed. Re-verified after the fix: the same student now sees only
-- Q1/Q3.
--
-- IDEMPOTENCY: every create table/index/trigger in this file already
-- tolerates a retried or repeated run (if not exists / drop trigger if
-- exists). The plain `create policy` statements did not -- Postgres has
-- no CREATE POLICY IF NOT EXISTS -- so retrying this file after any
-- partial failure (or simply re-applying it) would fail with 42710
-- "policy ... already exists" on whichever policy succeeded last time.
-- Every create policy below is now preceded by a matching drop policy
-- if exists, for the same reason the trigger below already has one.
--
-- NEW (not present on any branch -- the actual gap this task exists to
-- close, per 004_assessments.sql's own "FUTURE INTEGRATION POINTS"
-- comment, which explicitly deferred this):
--   - assessments.passing_percentage: the threshold score_assessment_
--     attempt() now uses to decide PASS/FAIL. Every assessment needs one
--     to be verifiable at all; existing rows get a documented default
--     (see the column comment) rather than being left unusable.
--   - student_skills.verified_at: timestamp companion to the existing
--     is_verified boolean (003_skills.sql) -- was always trigger-
--     protected from student writes via prevent_self_skill_verification,
--     but that trigger predates this column and only guarded is_verified;
--     extended below (CREATE OR REPLACE, same function name, same
--     trigger) to guard verified_at identically.
--   - The actual verification write, appended as the final step inside
--     score_assessment_attempt(): EXACT match only
--     (assessment.skill_id = student_skills.skill_id AND
--      assessment.difficulty = student_skills.proficiency_level), and
--     ONLY sets is_verified = true (never false, never touched on a
--     failing score) -- a student's declared proficiency_level is never
--     downgraded by this or any other path. If the student never
--     declared that exact skill at that exact level, there is no
--     matching row to UPDATE and nothing happens -- this migration does
--     not, and must not, insert a student_skills row on their behalf.
--     Folded into the same atomic transaction as scoring itself (not a
--     separate Python-side call) for the same reason 014/the ported 015
--     already do everything else in one PL/pgSQL function body: a crash
--     between "scored" and "verified" must not be possible.

-- ============================================================
-- 1. assessment_blueprint_rules -- "how many questions of which
--    difficulty should an attempt draw from the bank."
-- ============================================================
create table if not exists assessment_blueprint_rules (
  id uuid primary key default gen_random_uuid(),
  assessment_id uuid not null references assessments (id) on delete cascade,
  difficulty text not null check (difficulty in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),
  question_count int not null check (question_count > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint assessment_blueprint_rules_unique_difficulty unique (assessment_id, difficulty)
);

create index if not exists assessment_blueprint_rules_assessment_id_idx on assessment_blueprint_rules (assessment_id);

alter table assessment_blueprint_rules enable row level security;

-- Gated to STUDENT, matching 004_assessments.sql's own precedent for
-- assessments/assessment_questions/assessment_question_options (narrower
-- than 003_skills.sql's catalog tables) -- a question-count breakdown is
-- not itself sensitive, but there is no faculty/admin surface in this
-- phase that needs to read it, so this stays as narrow as the rest of
-- the assessment tables rather than defaulting to "any authenticated."
-- No insert/update/delete policy for `authenticated` -- only service_role
-- can configure blueprints, exactly like assessments/assessment_questions
-- content today.
drop policy if exists "Students can view blueprint rules for active assessments" on assessment_blueprint_rules;

create policy "Students can view blueprint rules for active assessments"
  on assessment_blueprint_rules for select
  to authenticated
  using (
    public.is_student(auth.uid())
    and exists (
      select 1 from assessments a
      where a.id = assessment_blueprint_rules.assessment_id
        and a.is_active = true
    )
  );

drop trigger if exists assessment_blueprint_rules_set_updated_at on assessment_blueprint_rules;

create trigger assessment_blueprint_rules_set_updated_at
  before update on assessment_blueprint_rules
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 2. assessment_attempt_questions -- the persisted, per-attempt
--    randomized selection. Append-only: written exactly once, inside
--    create_assessment_attempt() below, and never updated or deleted by
--    anything -- no UPDATE/DELETE policy exists for any role, and no
--    INSERT policy exists for `authenticated` either (only service_role,
--    via the RPC, ever writes here). No updated_at column, for the same
--    reason.
-- ============================================================
create table if not exists assessment_attempt_questions (
  attempt_id uuid not null references assessment_attempts (id) on delete cascade,
  question_id uuid not null references assessment_questions (id) on delete restrict,
  display_order int not null default 0,
  created_at timestamptz not null default now(),
  primary key (attempt_id, question_id),
  constraint assessment_attempt_questions_unique_order unique (attempt_id, display_order)
);

create index if not exists assessment_attempt_questions_attempt_id_idx on assessment_attempt_questions (attempt_id);

alter table assessment_attempt_questions enable row level security;

-- A student may only ever read the selection for their OWN attempt --
-- same ownership shape as "Students can view their own attempts" in
-- 004_assessments.sql.
drop policy if exists "Students can view their own attempt's selected questions" on assessment_attempt_questions;

create policy "Students can view their own attempt's selected questions"
  on assessment_attempt_questions for select
  to authenticated
  using (
    exists (
      select 1 from assessment_attempts aa
      where aa.id = assessment_attempt_questions.attempt_id
        and aa.student_id = auth.uid()
    )
  );

-- ============================================================
-- 3. Student visibility widening -- a question/option that was
--    legitimately selected into one of a student's own attempts must
--    stay visible to that student even if it is later deactivated.
--    Without this, create_assessment_attempt() could freeze a question
--    into an attempt today, and a routine content deactivation tomorrow
--    would silently break that same student's in-progress taking UI for
--    reasons entirely outside their control.
--
--    Additive only -- these are NEW, separate permissive policies
--    alongside the existing "approved active" ones from
--    004_assessments.sql (Postgres OR's multiple permissive SELECT
--    policies together); nothing existing is dropped or narrowed. Does
--    NOT touch assessment_question_answers here -- that table's answer-
--    key policy is handled separately, in section 3a below, because it
--    needs the opposite treatment (narrowed, not widened -- see that
--    section's comment and the CORRECTION note in the migration header).
-- ============================================================
drop policy if exists "Students can view questions in their own attempts" on assessment_questions;

create policy "Students can view questions in their own attempts"
  on assessment_questions for select
  to authenticated
  using (
    exists (
      select 1
      from assessment_attempt_questions aq
      join assessment_attempts aa on aa.id = aq.attempt_id
      where aq.question_id = assessment_questions.id
        and aa.student_id = auth.uid()
    )
  );

drop policy if exists "Students can view options for questions in their own attempts" on assessment_question_options;

create policy "Students can view options for questions in their own attempts"
  on assessment_question_options for select
  to authenticated
  using (
    exists (
      select 1
      from assessment_attempt_questions aq
      join assessment_attempts aa on aa.id = aq.attempt_id
      where aq.question_id = assessment_question_options.question_id
        and aa.student_id = auth.uid()
    )
  );

-- ============================================================
-- 3a. assessment_question_answers -- RE-SCOPE the "own completed
--     attempt" policy from 004_assessments.sql to the per-attempt
--     frozen selection.
--
--     The 004-era policy joined assessment_questions to
--     assessment_attempts directly on assessment_id, which was correct
--     when every approved question in an assessment WAS the exam. Now
--     that an attempt only ever contains a random subset
--     (assessment_attempt_questions), that join is a leak: it exposes
--     the answer key for every OTHER question in the same assessment's
--     bank too, the moment a student completes any one attempt on it.
--     See the CORRECTION note in this migration's header for how this
--     was found and verified.
--
--     Postgres has no CREATE OR REPLACE POLICY, so this is a DROP +
--     CREATE of the exact same policy name -- not a new, additional
--     policy. The only behavioral change is the join target:
--     assessment_attempt_questions (this student's own frozen
--     selections) instead of assessment_questions.assessment_id (the
--     assessment's entire bank).
-- ============================================================
drop policy if exists "Students can view answer keys for their own completed attempts"
  on assessment_question_answers;

create policy "Students can view answer keys for their own completed attempts"
  on assessment_question_answers for select
  to authenticated
  using (
    public.is_student(auth.uid())
    and exists (
      select 1
      from assessment_attempt_questions aq
      join assessment_attempts aa on aa.id = aq.attempt_id
      where aq.question_id = assessment_question_answers.question_id
        and aa.student_id = auth.uid()
        and aa.status = 'COMPLETED'
    )
  );

-- ============================================================
-- 4. create_assessment_attempt() -- the ONE trusted, atomic operation
--    that starts an attempt AND persists its randomized question
--    selection. Same rationale as score_assessment_attempt()
--    (014_score_assessment_attempt.sql): PostgREST gives no
--    cross-statement transaction to an external client, so "insert the
--    attempt, then separately insert N selection rows" as ordinary REST
--    calls would risk an orphaned attempt with no questions if the
--    process died in between. Any raised exception here (no blueprint,
--    insufficient pool) rolls back the attempt insert together with
--    everything else -- no partial/invalid attempt is ever left behind.
--
--    Callable ONLY via the backend's service-role client, after the
--    backend has already verified the caller's own identity through the
--    normal RLS-respecting path. p_student_id is a second, defense-in-
--    depth check inside the trusted function itself.
--
--    The existing partial unique index
--    assessment_attempts_one_in_progress_idx still does all the work of
--    preventing a double-click Start from creating two attempts: the
--    INSERT below raises the same 23505 unique-violation it always did.
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
        and scoring_method = 'OBJECTIVE'
        and difficulty = v_rule.difficulty
      order by random()
      limit v_rule.question_count
    ) eligible;

    v_available := coalesce(array_length(v_bucket, 1), 0);

    if v_available < v_rule.question_count then
      -- Rolls back the attempt insert above too -- see header comment.
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
-- 5. assessments.passing_percentage -- the threshold PASS/FAIL and skill
--    verification are now computed against. Every assessment needs one
--    to be meaningfully verifiable; existing rows get the documented
--    default below rather than being left with an undefined threshold.
--    Genuinely per-assessment, not a global constant -- service_role can
--    override it per row, the same way every other assessment field is
--    managed today (no write API exists; direct/seed SQL only).
-- ============================================================
alter table assessments
  add column if not exists passing_percentage numeric(5, 2) not null default 70
    check (passing_percentage >= 0 and passing_percentage <= 100);

-- ============================================================
-- 6. student_skills.verified_at -- timestamp companion to the existing
--    is_verified boolean (003_skills.sql). Set only alongside
--    is_verified = true, by service_role, from inside
--    score_assessment_attempt() below.
-- ============================================================
alter table student_skills
  add column if not exists verified_at timestamptz;

-- CREATE OR REPLACE of the exact same function/trigger from
-- 003_skills.sql -- not a new trigger, not a schema change to the
-- trigger's attachment. Extends the existing guard to also cover
-- verified_at (a column that did not exist when this function was first
-- written, and so was never protected by it): service_role steps aside
-- entirely (unchanged); every ordinary RLS-governed caller is now also
-- blocked from setting verified_at directly, exactly as they already are
-- for is_verified.
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

  if new.is_verified is distinct from old.is_verified then
    raise exception 'Cannot change skill verification status directly.' using errcode = '42501';
  end if;

  if new.verified_at is distinct from old.verified_at then
    raise exception 'Cannot change skill verification status directly.' using errcode = '42501';
  end if;

  return new;
end;
$$;

-- ============================================================
-- 7. score_assessment_attempt() -- CREATE OR REPLACE, not an edit to
--    014_score_assessment_attempt.sql. Two changes from that file's
--    original body:
--      a) the eligible-question loop now reads the attempt's own
--         persisted selection (assessment_attempt_questions) instead of
--         live-querying assessment_questions by assessment_id --
--         deliberately does NOT re-filter by review_status/is_active/
--         scoring_method here, so a question already selected into an
--         attempt stays part of that attempt's scored population even
--         if later deactivated (matching this function's existing
--         philosophy of never letting a later content change
--         retroactively alter an attempt that already happened).
--      b) a new final step: exact-match skill verification. Every other
--         line -- SELECT FOR UPDATE, the unanswered-placeholder
--         insert-or-reread, the content-based placeholder check, the
--         hard failures on a missing answer key or unsupported OBJECTIVE
--         type, the totals math, the concurrency handling -- is
--         unchanged from 014_score_assessment_attempt.sql.
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
  v_assessment public.assessments;
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

  -- Skill verification -- EXACT match only, and only ever sets
  -- is_verified TO true, never to false. A student's declared
  -- proficiency_level is never downgraded by a failing or a
  -- different-skill/different-level attempt: if v_percentage falls short,
  -- or no student_skills row exists for this exact (skill_id,
  -- proficiency_level) pair, this UPDATE simply matches zero rows and
  -- changes nothing. "is_verified = false" in the WHERE clause is an
  -- optimization (skip a no-op write for an already-verified skill), not
  -- a correctness requirement -- the SET clause alone is already
  -- idempotent.
  if v_percentage >= v_assessment.passing_percentage then
    update public.student_skills
    set is_verified = true,
        verified_at = now()
    where student_id = p_student_id
      and skill_id = v_assessment.skill_id
      and proficiency_level = v_assessment.difficulty
      and is_verified = false;
  end if;

  return v_attempt;
end;
$$;

revoke all on function public.score_assessment_attempt(uuid, uuid) from public;
revoke all on function public.score_assessment_attempt(uuid, uuid) from anon;
revoke all on function public.score_assessment_attempt(uuid, uuid) from authenticated;
grant execute on function public.score_assessment_attempt(uuid, uuid) to service_role;