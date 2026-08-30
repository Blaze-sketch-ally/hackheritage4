-- Migration: 015_question_bank_random_assessment
-- Purpose: Phase 1K -- a shared multi-setter question bank with peer review,
-- assessment blueprints, and per-student server-side randomized question
-- selection persisted per attempt.
--
-- Product decisions made before this migration was written (see the Phase
-- 1K architecture audit) -- not derived from the schema, recorded here so
-- the "why" travels with the schema:
--   1. Reviewer identity: PEER FACULTY REVIEW. Any FACULTY account other
--      than a question's own setter may approve/reject it. No ADMIN
--      dependency -- the project currently has no way to provision a
--      trusted admin account at all, so gating review on ADMIN would have
--      blocked this phase entirely.
--   2. Lifecycle states: REUSED AS-IS. assessment_questions.review_status
--      already has exactly the three states this phase needs
--      (PENDING/APPROVED/REJECTED, added in 004_assessments.sql) -- no new
--      DRAFT state, no CHECK-constraint change. A question is PENDING the
--      moment its setter creates it; "submit for review" is a UI concept,
--      not a database state transition. A REJECTED question's own setter
--      may keep editing it and it silently becomes reviewable again the
--      moment they set review_status back to PENDING (see the trigger
--      below) -- this is Phase 1K's entire "REJECTED -> revision" path,
--      with no extra state required.
--   3. Question mutability: APPROVED QUESTIONS ARE CONTENT-IMMUTABLE. Once
--      review_status = 'APPROVED', no content field may change again
--      (matches this project's existing philosophy that assessment_answers
--      and get_attempt_result_rows() must never retroactively diverge from
--      what a student actually saw -- see 014_score_assessment_attempt.sql
--      and app/services/assessment_service.py's own docstrings). is_active
--      remains togglable even after approval, so a flawed approved
--      question can still be retired from future selection without
--      rewriting history for attempts that already used it.
--
-- What this migration does NOT do: it does not touch
-- 014_score_assessment_attempt.sql as a file (historical migrations are
-- never edited) -- instead it CREATE OR REPLACEs
-- public.score_assessment_attempt() at the bottom of this file, changing
-- only its question-selection FROM/WHERE clause (live query by
-- assessment_id -> persisted query by attempt_id via the new
-- assessment_attempt_questions table). Every other line of that function's
-- body -- SELECT FOR UPDATE, unanswered-placeholder handling, the
-- content-based placeholder check, the hard failures on a missing answer
-- key or an unsupported OBJECTIVE type, the totals math -- is copied
-- verbatim, unchanged.

-- ============================================================
-- 1. assessment_questions: add setter identity
-- ============================================================
-- Nullable: existing questions (created before this phase existed) have no
-- known individual author and stay that way -- they remain visible to
-- students via the existing "approved active" policy either way, and
-- simply never appear in any faculty member's "my questions" view.
alter table assessment_questions
  add column if not exists created_by uuid references profiles (id) on delete set null;

create index if not exists assessment_questions_created_by_idx on assessment_questions (created_by);

-- ============================================================
-- 2. is_faculty(): role-check helper, same shape as is_student()
--    (012_student_profiles.sql / 013_harden_is_student.sql)
-- ============================================================
create or replace function public.is_faculty(profile_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.profiles where id = profile_id and role = 'FACULTY'
  );
$$;

revoke all on function public.is_faculty(uuid) from public;
revoke all on function public.is_faculty(uuid) from anon;
grant execute on function public.is_faculty(uuid) to authenticated;

-- ============================================================
-- 3. assessment_blueprint_rules -- "how should questions be selected"
--    per assessment, per difficulty bucket. Normalized (not JSONB) to
--    match every other table in this schema and so counts can be
--    CHECK-constrained individually.
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

-- Readable by any authenticated user for the same reason assessments
-- themselves are readable -- a difficulty/count breakdown carries no
-- sensitive information (no answer keys, no setter identities).
create policy "Authenticated users can view blueprint rules for active assessments"
  on assessment_blueprint_rules for select
  to authenticated
  using (
    exists (
      select 1 from assessments a
      where a.id = assessment_blueprint_rules.assessment_id
        and a.is_active = true
    )
  );

-- Assessments have no owner/creator column in this schema (unlike
-- questions) -- blueprint configuration is a shared FACULTY capability,
-- not scoped to an individual setter, matching how assessments themselves
-- have always been managed.
create policy "Faculty can create blueprint rules"
  on assessment_blueprint_rules for insert
  to authenticated
  with check (public.is_faculty(auth.uid()));

create policy "Faculty can update blueprint rules"
  on assessment_blueprint_rules for update
  to authenticated
  using (public.is_faculty(auth.uid()))
  with check (public.is_faculty(auth.uid()));

create policy "Faculty can delete blueprint rules"
  on assessment_blueprint_rules for delete
  to authenticated
  using (public.is_faculty(auth.uid()));

drop trigger if exists assessment_blueprint_rules_set_updated_at on assessment_blueprint_rules;

create trigger assessment_blueprint_rules_set_updated_at
  before update on assessment_blueprint_rules
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 4. assessment_attempt_questions -- the persisted, per-attempt
--    randomized selection. Once a row exists here it is never updated,
--    only ever read (by the taking UI and by scoring) -- append-only, no
--    updated_at, no UPDATE policy for anyone.
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

-- Students may only ever read the selection for their own attempt. Written
-- exclusively by create_assessment_attempt() below, via service_role --
-- there is deliberately no INSERT/UPDATE/DELETE policy for `authenticated`
-- at all, the same posture this project already uses for
-- assessment_question_answers (the answer key).
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
-- 5. Question review workflow -- RLS (broad "in the door" check) +
--    trigger (fine-grained enforcement), the same two-layer pattern
--    already used for assessment_attempts' UPDATE policy +
--    prevent_self_attempt_scoring.
-- ============================================================

create policy "Faculty can create their own questions"
  on assessment_questions for insert
  to authenticated
  with check (
    created_by = auth.uid()
    and public.is_faculty(auth.uid())
    and review_status = 'PENDING'
  );

create policy "Faculty can view their own or pending questions"
  on assessment_questions for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and (created_by = auth.uid() or review_status = 'PENDING')
  );

-- Broad at the RLS layer by design (mirrors assessment_attempts' own
-- UPDATE policy) -- lets a setter touch their own row and lets any other
-- faculty member touch a PENDING row for review purposes. The trigger
-- below is what actually restricts WHAT each of those two cases may
-- change.
create policy "Faculty can update their own or review pending questions"
  on assessment_questions for update
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and (created_by = auth.uid() or review_status = 'PENDING')
  )
  with check (public.is_faculty(auth.uid()));

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
    -- it (see assessment_attempt_questions and the updated
    -- score_assessment_attempt() below, neither of which re-checks
    -- is_active once a question has been persisted to an attempt).
    if new.question_text is distinct from old.question_text
      or new.question_type is distinct from old.question_type
      or new.scoring_method is distinct from old.scoring_method
      or new.difficulty is distinct from old.difficulty
      or new.points is distinct from old.points
      or new.display_order is distinct from old.display_order
      or new.review_status is distinct from old.review_status
      or new.created_by is distinct from old.created_by
    then
      raise exception 'Cannot modify an approved question, other than deactivating it.'
        using errcode = '42501';
    end if;
    return new;
  end if;

  if new.created_by = auth.uid() then
    -- The question's own setter may edit its content freely while it is
    -- not yet approved (including moving a REJECTED question back to
    -- PENDING after revising it -- Phase 1K's entire "resubmit" path) but
    -- may never approve or reject their own question.
    if new.review_status is distinct from old.review_status
      and new.review_status in ('APPROVED', 'REJECTED')
    then
      raise exception 'Cannot review your own question.' using errcode = '42501';
    end if;
  else
    -- A reviewer (any other faculty member, RLS above already confirmed
    -- the row was PENDING) may only ever change review_status -- never
    -- the question's actual content.
    if new.question_text is distinct from old.question_text
      or new.question_type is distinct from old.question_type
      or new.scoring_method is distinct from old.scoring_method
      or new.difficulty is distinct from old.difficulty
      or new.points is distinct from old.points
      or new.display_order is distinct from old.display_order
      or new.is_active is distinct from old.is_active
      or new.created_by is distinct from old.created_by
    then
      raise exception 'Reviewers may only change review_status.' using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_unauthorized_question_review() from public;

drop trigger if exists assessment_questions_protect_review on assessment_questions;

create trigger assessment_questions_protect_review
  before update on assessment_questions
  for each row
  execute procedure public.prevent_unauthorized_question_review();

-- ============================================================
-- 6. assessment_question_options -- faculty write access, scoped to
--    their own non-approved questions (immutability applies transitively:
--    once the parent question is APPROVED, its options can no longer be
--    written at all, by anyone but service_role).
-- ============================================================

create policy "Faculty can view options for their own or pending questions"
  on assessment_question_options for select
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and public.is_faculty(auth.uid())
        and (q.created_by = auth.uid() or q.review_status = 'PENDING')
    )
  );

create policy "Faculty can create options for their own non-approved questions"
  on assessment_question_options for insert
  to authenticated
  with check (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
    )
  );

create policy "Faculty can update options for their own non-approved questions"
  on assessment_question_options for update
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
    )
  )
  with check (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
    )
  );

create policy "Faculty can delete options for their own non-approved questions"
  on assessment_question_options for delete
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_options.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
    )
  );

-- ============================================================
-- 7. assessment_question_answers -- same shape as options above. A
--    reviewer needs SELECT on a PENDING question's answer key to actually
--    review it (verify correctness), but never write access.
-- ============================================================

create policy "Faculty can view answer keys for their own or pending questions"
  on assessment_question_answers for select
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_answers.question_id
        and public.is_faculty(auth.uid())
        and (q.created_by = auth.uid() or q.review_status = 'PENDING')
    )
  );

create policy "Faculty can create answer keys for their own non-approved questions"
  on assessment_question_answers for insert
  to authenticated
  with check (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_answers.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
    )
  );

create policy "Faculty can update answer keys for their own non-approved questions"
  on assessment_question_answers for update
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_answers.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
    )
  )
  with check (
    exists (
      select 1 from assessment_questions q
      where q.id = assessment_question_answers.question_id
        and q.created_by = auth.uid()
        and q.review_status <> 'APPROVED'
        and public.is_faculty(auth.uid())
    )
  );

-- ============================================================
-- 8. create_assessment_attempt() -- the ONE trusted, atomic operation
--    that starts an attempt AND persists its randomized question
--    selection. Same rationale as score_assessment_attempt()
--    (014_score_assessment_attempt.sql): PostgREST gives no
--    cross-statement transaction to an external client, and "insert the
--    attempt, then separately insert N selection rows" as ordinary REST
--    calls would risk an orphaned attempt with no questions if the
--    process died in between. A single PL/pgSQL function body is one
--    transaction -- any raised exception (insufficient pool, no
--    blueprint, inactive assessment) rolls back the attempt insert
--    together with everything else, automatically.
--
--    Callable ONLY via the backend's service-role client, after the
--    backend has already verified the caller's own identity through the
--    normal RLS-respecting path -- exactly mirroring
--    score_assessment_attempt()'s existing call pattern. p_student_id is
--    a second, defense-in-depth check inside the trusted function itself.
--
--    The existing partial unique index
--    assessment_attempts_one_in_progress_idx still does all the work of
--    preventing a double-click Start from creating two attempts: the
--    INSERT below raises the same 23505 unique-violation it always did,
--    and the backend's existing DuplicateInProgressAttemptError handling
--    (looking for code == "23505") needs no changes to catch it here too.
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

  -- Existing partial unique index (student_id, assessment_id) WHERE
  -- status = 'IN_PROGRESS' still guards this exactly as it always has --
  -- a concurrent double-click raises 23505 here, unchanged behavior.
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

    v_available := array_length(v_bucket, 1);
    v_available := coalesce(v_available, 0);

    if v_available < v_rule.question_count then
      -- Rolls back the attempt insert above too -- see header comment.
      -- No partial/invalid attempt is ever left behind.
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
-- 9. score_assessment_attempt() -- CREATE OR REPLACE, not a new
--    function and not an edit to 014_score_assessment_attempt.sql. The
--    ONLY change from the original body: the eligible-question loop now
--    reads the attempt's own persisted selection
--    (assessment_attempt_questions) instead of live-querying
--    assessment_questions by assessment_id. Deliberately does NOT
--    re-filter by review_status/is_active/scoring_method here -- a
--    question already selected into an attempt stays part of that
--    attempt's scored population even if it is later deactivated,
--    matching this same function's existing, pre-Phase-1K philosophy of
--    never letting a later content/state change retroactively alter an
--    attempt that already happened (see the original file's comment on
--    assessments.is_active not being re-checked at scoring time either).
--    Every other line below -- SELECT FOR UPDATE, the unanswered-
--    placeholder insert-or-reread, the content-based placeholder check,
--    the hard failures on a missing answer key or unsupported OBJECTIVE
--    type, the totals math, the concurrency handling -- is unchanged from
--    014_score_assessment_attempt.sql.
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

  return v_attempt;
end;
$$;

revoke all on function public.score_assessment_attempt(uuid, uuid) from public;
revoke all on function public.score_assessment_attempt(uuid, uuid) from anon;
revoke all on function public.score_assessment_attempt(uuid, uuid) from authenticated;
grant execute on function public.score_assessment_attempt(uuid, uuid) to service_role;
