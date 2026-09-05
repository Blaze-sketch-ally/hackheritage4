-- Migration: 045_evaluation_foundation
-- Purpose: Phase F8.1 -- the DATABASE-ONLY data-model foundation for human
-- Evaluation & Rubrics, per the approved F8 architecture audit. This
-- migration does NOT wire up any backend API, any frontend, and does NOT
-- touch objective scoring (create_assessment_attempt()/
-- score_assessment_attempt() are completely untouched) or the visibility of
-- assessment_answers/assessment_attempt_questions to Faculty in any way --
-- that RLS boundary is deliberately deferred to the dedicated F8.2 security
-- phase (see this migration's own RLS sections for exactly what is, and is
-- not, granted here).
--
-- Five new tables, in FK-dependency order:
--   1. evaluator_assignments  -- WHO (an evaluator) is authorized to
--      evaluate WHAT (one specific assessment_attempt_questions row --
--      i.e. one specific student's one specific answered question).
--   2. rubrics                -- a named grading rubric belonging to one
--      assessment_questions row.
--   3. rubric_criteria        -- ordered criteria within one rubric.
--   4. evaluations            -- the CURRENT evaluation record for one
--      assignment (1:1 with evaluator_assignments).
--   5. evaluation_history     -- APPEND-ONLY, one row per evaluations
--      transition, mirroring 027_faculty_assessment_permissions.sql's own
--      faculty_assessment_permission_audit precedent exactly.
--
-- Architectural decisions this migration encodes (approved by the user
-- ahead of this phase, per the F8 audit's own "Architectural Decisions
-- Requiring Approval" section):
--   1. Evaluation history is APPEND-ONLY (evaluation_history, #5 above) --
--      NOT F7's latest-review-state-only model. A finalized evaluation is
--      a real, high-stakes number a student's outcome depends on; F7's own
--      audit explicitly reserved the latest-state pattern for lower-stakes
--      review-gate metadata, not this.
--   2. Evaluation lifecycle: ASSIGNED -> IN_PROGRESS -> SUBMITTED ->
--      FINALIZED, strictly forward, one step at a time. FINALIZED is
--      immutable (enforced by trigger, not just convention).
--   3. Final-score integration (objective + finalized human evaluation)
--      is explicitly F8.4's concern -- nothing here changes
--      assessment_attempts.score/total_marks/percentage or how they're
--      computed.
--   4. Question-author visibility into evaluation data: DEFERRED. No RLS
--      policy here grants a question's author anything.
--   5. Admin oversight: DEFERRED. See section 6 below for the specific,
--      narrower decision this required for assignment-creation authority.
--   6. Rubrics (rubrics + rubric_criteria, #2/#3 above) are the
--      authoritative evaluation-criteria model -- there is no competing
--      `assessment_questions.evaluation_criteria`-style column anywhere,
--      and none is added here.
--   7. CODE/practical evaluation: DEFERRED. Nothing in this migration
--      makes CODE questions any more reachable than they already are (see
--      043_question_authoring_metadata.sql -- still schema-only, still
--      blocked from ever reaching APPROVED+OBJECTIVE, still never
--      selected into a live attempt). No file/execution/artifact
--      infrastructure of any kind is added.
--
-- ============================================================
-- WHY THIS GRAIN: (attempt_id, question_id), not a bare attempt_id
-- ============================================================
-- assessment_attempt_questions (015_question_bank_random_assessment.sql)
-- has NO surrogate id column -- its primary key is the composite
-- (attempt_id, question_id). An evaluator assignment references that exact
-- composite via a two-column foreign key, rather than either (a) adding a
-- surrogate id column to that table (an unrelated, append-only table this
-- migration has no reason to alter) or (b) scoping assignment at the whole-
-- attempt level (which would hand an evaluator every question in an
-- attempt, including ones nothing assigned them to -- the "unrestricted
-- access" shape the F8 audit's own security section explicitly rejected).
-- This is the narrowest safe grain: it scopes exactly
-- student + attempt + question, and it is exactly what a future F8.2 RLS
-- policy on assessment_answers needs to join through (assessment_answers
-- already carries both attempt_id and question_id directly).
--
-- ============================================================
-- WHY ASSIGNMENT CREATION IS service_role-ONLY IN F8.1 (not is_admin())
-- ============================================================
-- Note for the record: while researching this migration, is_admin()
-- (035_admin_faculty_permission_management.sql) and the FastAPI
-- require_admin() dependency were confirmed to already exist and already
-- gate an exactly analogous governance action
-- (admin_grant_assessment_capability()) -- correcting an earlier F8 audit
-- finding that no admin guard exists anywhere in this codebase. That
-- finding was about the *documentation* (docs/architecture/
-- assessment-lifecycle.md, written before 035), not the actual schema.
--
-- Even so, this migration does NOT gate evaluator-assignment creation on
-- is_admin(): the user's own approved F8 decision list explicitly defers
-- "Admin oversight" as an open architectural question, and reusing
-- is_admin() here -- however tempting given the precedent now confirmed to
-- exist -- would be deciding that question silently rather than
-- surfacing it. Per this phase's own explicit instructions ("If no
-- existing user-facing actor is authorized to create assignments yet, an
-- RPC-only write model is acceptable"), assignment creation is
-- service_role-only: create_evaluator_assignment()/
-- revoke_evaluator_assignment() below are revoked from authenticated/anon
-- entirely, exactly like create_assessment_attempt()/
-- score_assessment_attempt() already are. The real governance-actor
-- question (Admin? a new capability? something else?) is left open for
-- F8.2/F8.3 to decide explicitly, not resolved here as a side effect.
--
-- ============================================================
-- WHY evaluations IS A MUTABLE "CURRENT RECORD" *PLUS* AN APPEND-ONLY
-- evaluation_history TABLE, NOT ONE TABLE ALONE
-- ============================================================
-- A single fully-immutable, insert-only table (one new row per lifecycle
-- event) was considered and rejected: it would force every consumer to
-- always compute "the current state" via a MAX(created_at)/window-function
-- query, and would make the evaluator's own natural draft-and-revise UX
-- (matching assessment_answers' own proven "mutable while IN_PROGRESS,
-- trigger-locked once it matters" shape) awkward to express. A single
-- ordinary mutable table alone was also rejected: it would satisfy
-- decision #2 (immutable once FINALIZED) but not decision #1 (append-only
-- HISTORY) -- an intermediate IN_PROGRESS revision (evaluator changes
-- their mind about the marks before submitting) would simply vanish,
-- which is fine for a *draft*, but there is no way to durably reconstruct
-- "what did the evaluator actually enter, and when" for governance
-- purposes without a second table.
--
-- The chosen design -- evaluations (current, mutable-until-FINALIZED,
-- trigger-guarded) + evaluation_history (append-only, one row per
-- meaningful transition, written by an AFTER trigger) -- is not invented
-- for this migration: it is 027_faculty_assessment_permissions.sql's own
-- exact pattern (faculty_assessment_permissions + the AFTER trigger onto
-- faculty_assessment_permission_audit), reused verbatim for a new domain.
--
-- ============================================================
-- WHY RUBRICS BECOME IMMUTABLE ONCE USED BY A FINALIZED EVALUATION
-- (rather than a full rubric-versioning/copy-on-use system)
-- ============================================================
-- This project's central invariant ("Configuration determines what can
-- happen. An attempt records what actually happened. Historical records
-- are never reconstructed from today's configuration." --
-- docs/architecture/assessment-lifecycle.md) applies here exactly as it
-- does to assessment_questions: a rubric a finalized evaluation was
-- graded against must never be able to change meaning out from under that
-- historical record. Rather than build a version-chain/copy-on-use system
-- (explicitly discouraged unless required), this migration reuses this
-- project's own proven, minimal answer to the identical problem for
-- questions: usage-triggered content-immutability
-- (prevent_unauthorized_question_review()'s "APPROVED -> immutable"
-- branch, 015). Here: once ANY FINALIZED evaluation references a rubric,
-- that rubric's (and its criteria's) name/description/marks become
-- immutable -- see prevent_rubric_modification_after_use() /
-- prevent_rubric_criteria_modification_after_use() below.

-- ============================================================
-- 1. evaluator_assignments -- evaluator <-> exact (attempt, question) scope
-- ============================================================
create table if not exists evaluator_assignments (
  id uuid primary key default gen_random_uuid(),

  -- NOT NULL: an assignment always names a specific evaluator (the whole
  -- point of this table). CASCADE matches this project's own convention
  -- for a NOT NULL "this row fundamentally belongs to this identity" FK
  -- (assessment_attempts.student_id, faculty_assessment_permissions.
  -- faculty_id) rather than the "accountability metadata" SET NULL
  -- convention used for nullable actor columns like created_by below.
  evaluator_id uuid not null references profiles (id) on delete cascade,

  -- The exact (attempt, question) scope -- see the migration header
  -- comment ("WHY THIS GRAIN") for why this is a composite FK to
  -- assessment_attempt_questions' own composite primary key rather than a
  -- bare attempt_id or a new surrogate column on that table. CASCADE
  -- matches assessment_answers'/assessment_attempt_questions' own
  -- existing cascade-from-assessment_attempts convention -- an assignment
  -- is exactly as disposable as the attempt-question row it scopes.
  attempt_id uuid not null,
  question_id uuid not null,
  foreign key (attempt_id, question_id)
    references assessment_attempt_questions (attempt_id, question_id)
    on delete cascade,

  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'REVOKED')),

  -- Accountability metadata -- nullable + SET NULL, matching this
  -- project's own existing convention for exactly this kind of column
  -- (assessment_questions.created_by, faculty_assessment_permissions.
  -- granted_by/status_changed_by, assessment_questions.reviewed_by). The
  -- create_evaluator_assignment()/revoke_evaluator_assignment() RPCs
  -- below always require a real value for these at call time regardless
  -- of the column's own nullability -- see those functions' own comments.
  created_by uuid references profiles (id) on delete set null,
  revoked_by uuid references profiles (id) on delete set null,
  revoked_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint evaluator_assignments_revoked_fields_consistent check (
    (status = 'REVOKED') = (revoked_at is not null)
  )
);

create index if not exists evaluator_assignments_evaluator_id_idx on evaluator_assignments (evaluator_id);
create index if not exists evaluator_assignments_attempt_question_idx on evaluator_assignments (attempt_id, question_id);

-- Prevents two SIMULTANEOUS active assignments of the SAME evaluator to
-- the SAME scope (a genuine duplicate) while still allowing a REVOKED row
-- to remain as permanent history and a later, genuinely new assignment to
-- the same evaluator+scope to be created afterward as its own new row --
-- exactly the same partial-unique-index shape as
-- assessment_attempts_one_in_progress_idx (004_assessments.sql).
create unique index if not exists evaluator_assignments_unique_active_idx
  on evaluator_assignments (evaluator_id, attempt_id, question_id)
  where status = 'ACTIVE';

alter table evaluator_assignments enable row level security;

-- Read-only, self-scoped, and additionally gated on currently holding the
-- assessment_evaluator capability (not just having been assigned once) --
-- matching this project's existing double-gate pattern for exactly this
-- shape of question (mentor visibility: an ACTIVE faculty_student_
-- mentorships row AND has_mentor_capability(), 040_faculty_student_
-- mentorships.sql). No INSERT/UPDATE/DELETE policy for `authenticated` at
-- all -- see the migration header comment on why creation/revocation are
-- service_role-only in F8.1.
create policy "Evaluators can view their own assignments"
  on evaluator_assignments for select
  to authenticated
  using (
    evaluator_id = auth.uid()
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
  );

create trigger evaluator_assignments_set_updated_at
  before update on evaluator_assignments
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 2. rubrics -- belongs to exactly one question. RLS deliberately fully
--    closed to `authenticated` in F8.1 (see the migration header) --
--    who may read/author a rubric is an F8.3 decision, not decided here.
-- ============================================================
create table if not exists rubrics (
  id uuid primary key default gen_random_uuid(),
  question_id uuid not null references assessment_questions (id) on delete cascade,

  name text not null,
  description text,
  max_marks numeric(6, 2) not null check (max_marks > 0),

  -- Minimal lifecycle: a rubric can be retired from future use without
  -- being deleted (deleting it would violate the historical-integrity
  -- requirement below the moment ANY evaluation has ever referenced it --
  -- see the FK on evaluations.rubric_id, which is RESTRICT, not CASCADE).
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'ARCHIVED')),

  created_by uuid references profiles (id) on delete set null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists rubrics_question_id_idx on rubrics (question_id);

alter table rubrics enable row level security;
-- No policies for `authenticated` in F8.1 -- see migration header. Fully
-- closed except service_role, exactly like faculty_assessment_permission_
-- audit's own posture (027).

create trigger rubrics_set_updated_at
  before update on rubrics
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 3. rubric_criteria -- ordered criteria within one rubric.
-- ============================================================
create table if not exists rubric_criteria (
  id uuid primary key default gen_random_uuid(),
  rubric_id uuid not null references rubrics (id) on delete cascade,

  criterion text not null,
  description text,
  max_marks numeric(6, 2) not null check (max_marks > 0),
  display_order int not null default 0,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Same "batch-created, rarely reordered independently" uniqueness
  -- shape as assessment_question_options_unique_order (004_assessments.
  -- sql) -- deterministic ordering, duplicate-order bugs caught at
  -- insert time.
  constraint rubric_criteria_unique_order unique (rubric_id, display_order)
);

create index if not exists rubric_criteria_rubric_id_idx on rubric_criteria (rubric_id);

alter table rubric_criteria enable row level security;
-- No policies for `authenticated` in F8.1 -- same posture as rubrics
-- above, deferred to F8.3 as one decision alongside rubric visibility
-- itself (criteria are never meaningfully readable independently of
-- their parent rubric).

create trigger rubric_criteria_set_updated_at
  before update on rubric_criteria
  for each row
  execute procedure public.set_updated_at();

-- Deliberately NOT enforced here: sum(rubric_criteria.max_marks) must
-- equal rubrics.max_marks. The F8.1 brief's own constraints section asks
-- for this only "eventually" -- a hard trigger would fight incremental,
-- one-criterion-at-a-time rubric construction (the only way this schema
-- lets criteria be added). Deferred to F8.3's actual rubric-authoring
-- workflow, once that workflow's real shape (all-at-once vs incremental)
-- is decided.

-- ============================================================
-- 4. evaluations -- the CURRENT evaluation record, 1:1 with
--    evaluator_assignments. Mutable while not FINALIZED (by the assigned
--    evaluator only), trigger-immutable once FINALIZED.
-- ============================================================
create table if not exists evaluations (
  id uuid primary key default gen_random_uuid(),

  -- 1:1 with its assignment (unique below) -- CASCADE matches this
  -- migration's own attempt-question cascade convention (an evaluation is
  -- exactly as disposable as the assignment that authorized it).
  assignment_id uuid not null references evaluator_assignments (id) on delete cascade,

  -- Duplicated from evaluator_assignments.evaluator_id (NOT a violation of
  -- "don't duplicate student_id/question_id if derivable" -- this
  -- migration deliberately does NOT duplicate the scope's student_id or
  -- question_id anywhere on this table; they remain reachable only via
  -- assignment_id -> evaluator_assignments -> assessment_attempt_
  -- questions). evaluator_id is kept as its own column because it is the
  -- one identity every trigger check below needs to compare directly
  -- against auth.uid() without an extra join, exactly mirroring why
  -- 044_question_review_governance.sql keeps reviewed_by directly on
  -- assessment_questions even though it is, in principle, re-derivable.
  -- The identity-lock at the top of prevent_unauthorized_evaluation_
  -- change() below is the defense-in-depth guard that keeps this column
  -- from ever disagreeing with its assignment's own evaluator_id.
  evaluator_id uuid not null references profiles (id) on delete cascade,

  -- Nullable: whether every evaluation must reference a rubric before it
  -- can be FINALIZED is explicitly NOT decided here -- see the migration
  -- header. RESTRICT (not CASCADE, not SET NULL): once referenced, a
  -- rubric must not silently detach from the evaluation that used it --
  -- deleting a rubric that any evaluation (finalized or not) points to is
  -- refused outright, forcing an explicit ARCHIVED status change instead.
  rubric_id uuid references rubrics (id) on delete restrict,

  status text not null default 'ASSIGNED'
    check (status in ('ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'FINALIZED')),

  awarded_marks numeric(6, 2) check (awarded_marks >= 0),
  feedback text,

  submitted_at timestamptz,
  finalized_at timestamptz,
  -- Distinct from evaluator_id on purpose, even though F8.1 only ever
  -- supports self-finalization (enforced by
  -- evaluations_finalized_by_matches_evaluator below) -- this is the one
  -- column a future F10-governance moderation step could legitimately set
  -- to someone other than the original evaluator, without an F8.1-era
  -- schema change.
  finalized_by uuid references profiles (id) on delete set null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint evaluations_unique_assignment unique (assignment_id),
  constraint evaluations_submitted_at_consistent check (
    status not in ('SUBMITTED', 'FINALIZED') or submitted_at is not null
  ),
  constraint evaluations_finalized_at_consistent check (
    (status = 'FINALIZED') = (finalized_at is not null)
  ),
  constraint evaluations_finalized_requires_marks check (
    status <> 'FINALIZED' or awarded_marks is not null
  ),
  -- F8.1 supports self-finalization only -- see the migration header and
  -- the trigger below (this CHECK is the belt to the trigger's
  -- suspenders: even a hypothetical future direct write cannot desync
  -- this pair).
  constraint evaluations_finalized_by_matches_evaluator check (
    finalized_by is null or finalized_by = evaluator_id
  )
);

create index if not exists evaluations_evaluator_id_idx on evaluations (evaluator_id);
create index if not exists evaluations_rubric_id_idx on evaluations (rubric_id);

alter table evaluations enable row level security;

-- Self-scoped, and additionally gated on the assignment still being
-- ACTIVE (so a revoked assignment immediately stops its evaluator from
-- continuing to edit -- a FINALIZED row is separately immutable
-- regardless, via the trigger below, so this ACTIVE gate matters only for
-- an evaluation still in progress at the moment of revocation) and on
-- currently holding the assessment_evaluator capability -- the exact same
-- double/triple-gate shape as evaluator_assignments' own SELECT policy
-- above.
create policy "Evaluators can view their own evaluations"
  on evaluations for select
  to authenticated
  using (
    evaluator_id = auth.uid()
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
  );

create policy "Evaluators can update their own evaluations while assigned is active"
  on evaluations for update
  to authenticated
  using (
    evaluator_id = auth.uid()
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
    and exists (
      select 1 from evaluator_assignments ea
      where ea.id = evaluations.assignment_id
        and ea.status = 'ACTIVE'
    )
  )
  with check (
    evaluator_id = auth.uid()
    and public.has_assessment_capability(auth.uid(), 'assessment_evaluator')
  );
-- No INSERT/DELETE policy for `authenticated` -- an evaluations row is
-- created only as a side effect of create_evaluator_assignment() below
-- (service_role), never self-service, and is never deleted (append-only
-- philosophy -- see evaluation_history for how a "mistake" is corrected:
-- a new assignment/evaluation, not a delete).

-- Enforces, for every non-service_role UPDATE:
--   - assignment_id/evaluator_id never change after creation (identity is
--     fixed at creation time, matching evaluator_assignments' own shape)
--   - once FINALIZED, the row is completely immutable (no exception, not
--     even updated_at) -- see the migration header on why this is
--     stricter than F7's own reviewed_by/review_note precedent (a
--     validate-only check, not a force-set): a real score deserves the
--     stronger guarantee.
--   - pre-FINALIZED, only the assigned evaluator (never anyone else) may
--     write, matching this table's own RLS UPDATE policy at the trigger
--     layer too (defense in depth, the same two-layer pattern this
--     project uses everywhere)
--   - status transitions are strictly forward, one step at a time
--   - submitted_at/finalized_at/finalized_by are ALWAYS server-forced when
--     entering SUBMITTED/FINALIZED, never trusted from the client -- this
--     is the stronger pattern this project's OWN 037_faculty_
--     opportunities_and_expressions.sql precedent uses (unconditionally
--     forcing reviewed_by = caller_id in the trigger), which F7.4's own
--     audit flagged 044_question_review_governance.sql for NOT doing
--     (044 only validates reviewed_by if the client changes it, rather
--     than forcing it) -- applied here as the corrected, stronger version
--     of that exact lesson.
--   - a rubric, if referenced, must belong to the SAME question this
--     assignment scopes, and awarded_marks may never exceed that rubric's
--     max_marks
create or replace function public.prevent_unauthorized_evaluation_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_rubric_question_id uuid;
  v_rubric_max_marks numeric(6, 2);
  v_assignment_question_id uuid;
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.assignment_id is distinct from old.assignment_id
    or new.evaluator_id is distinct from old.evaluator_id
  then
    raise exception 'Evaluation identity/assignment cannot be changed.' using errcode = '42501';
  end if;

  if old.status = 'FINALIZED' then
    if new.status is distinct from old.status
      or new.rubric_id is distinct from old.rubric_id
      or new.awarded_marks is distinct from old.awarded_marks
      or new.feedback is distinct from old.feedback
      or new.submitted_at is distinct from old.submitted_at
      or new.finalized_at is distinct from old.finalized_at
      or new.finalized_by is distinct from old.finalized_by
    then
      raise exception 'Cannot modify a finalized evaluation.' using errcode = '42501';
    end if;
    return new;
  end if;

  if new.evaluator_id is distinct from auth.uid() then
    raise exception 'Only the assigned evaluator may update this evaluation.' using errcode = '42501';
  end if;

  if new.status is distinct from old.status then
    if not (
      (old.status = 'ASSIGNED' and new.status = 'IN_PROGRESS')
      or (old.status = 'IN_PROGRESS' and new.status = 'SUBMITTED')
      or (old.status = 'SUBMITTED' and new.status = 'FINALIZED')
    ) then
      raise exception 'Invalid evaluation status transition: % -> %.', old.status, new.status
        using errcode = '22023';
    end if;
  end if;

  -- Server-forced, never client-trusted -- see the function's own header
  -- comment.
  if new.status = 'SUBMITTED' and old.status is distinct from 'SUBMITTED' then
    new.submitted_at := now();
  end if;

  if new.status = 'FINALIZED' and old.status is distinct from 'FINALIZED' then
    new.finalized_at := now();
    new.finalized_by := auth.uid();
  end if;

  if new.rubric_id is not null and new.rubric_id is distinct from old.rubric_id then
    select question_id, max_marks into v_rubric_question_id, v_rubric_max_marks
    from public.rubrics where id = new.rubric_id;

    select question_id into v_assignment_question_id
    from public.evaluator_assignments where id = new.assignment_id;

    if v_rubric_question_id is distinct from v_assignment_question_id then
      raise exception 'Rubric does not belong to this assignment''s question.' using errcode = '23514';
    end if;
  end if;

  if new.rubric_id is not null and new.awarded_marks is not null then
    select max_marks into v_rubric_max_marks from public.rubrics where id = new.rubric_id;
    if new.awarded_marks > v_rubric_max_marks then
      raise exception 'Awarded marks (%) exceed the rubric''s maximum (%).',
        new.awarded_marks, v_rubric_max_marks using errcode = '23514';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_unauthorized_evaluation_change() from public;

create trigger evaluations_protect_lifecycle
  before update on evaluations
  for each row
  execute procedure public.prevent_unauthorized_evaluation_change();

create trigger evaluations_set_updated_at
  before update on evaluations
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 5. evaluation_history -- APPEND-ONLY. One row per evaluations
--    INSERT/meaningful UPDATE, written exclusively by the trigger below --
--    exact same shape as audit_faculty_assessment_permission_change()
--    (027_faculty_assessment_permissions.sql). No authenticated
--    SELECT/INSERT/UPDATE/DELETE policy at all -- same posture as
--    faculty_assessment_permission_audit.
-- ============================================================
create table if not exists evaluation_history (
  id uuid primary key default gen_random_uuid(),
  evaluation_id uuid not null references evaluations (id) on delete cascade,
  assignment_id uuid not null references evaluator_assignments (id) on delete cascade,
  evaluator_id uuid not null references profiles (id) on delete cascade,

  previous_status text,
  new_status text not null,
  rubric_id uuid,
  awarded_marks numeric(6, 2),
  feedback text,

  actor_id uuid references profiles (id) on delete set null,
  occurred_at timestamptz not null default now()
);

create index if not exists evaluation_history_evaluation_id_idx on evaluation_history (evaluation_id, occurred_at desc);

alter table evaluation_history enable row level security;
-- No policies for `authenticated` -- internal governance data, same as
-- faculty_assessment_permission_audit (027).

create or replace function public.record_evaluation_history()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    insert into public.evaluation_history (
      evaluation_id, assignment_id, evaluator_id, previous_status, new_status,
      rubric_id, awarded_marks, feedback, actor_id
    ) values (
      new.id, new.assignment_id, new.evaluator_id, null, new.status,
      new.rubric_id, new.awarded_marks, new.feedback, auth.uid()
    );
  elsif old.status is distinct from new.status
    or old.rubric_id is distinct from new.rubric_id
    or old.awarded_marks is distinct from new.awarded_marks
    or old.feedback is distinct from new.feedback
  then
    insert into public.evaluation_history (
      evaluation_id, assignment_id, evaluator_id, previous_status, new_status,
      rubric_id, awarded_marks, feedback, actor_id
    ) values (
      new.id, new.assignment_id, new.evaluator_id, old.status, new.status,
      new.rubric_id, new.awarded_marks, new.feedback, auth.uid()
    );
  end if;
  return new;
end;
$$;

revoke all on function public.record_evaluation_history() from public;

create trigger evaluations_record_history
  after insert or update on evaluations
  for each row
  execute procedure public.record_evaluation_history();

-- ============================================================
-- 6. Rubric content-immutability once used by a FINALIZED evaluation --
--    see the migration header comment for the full reasoning.
-- ============================================================
create or replace function public.prevent_rubric_modification_after_use()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if (
    new.name is distinct from old.name
    or new.description is distinct from old.description
    or new.max_marks is distinct from old.max_marks
    or new.question_id is distinct from old.question_id
  ) and exists (
    select 1 from public.evaluations e where e.rubric_id = old.id and e.status = 'FINALIZED'
  ) then
    raise exception 'Cannot modify a rubric already used by a finalized evaluation.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_rubric_modification_after_use() from public;

create trigger rubrics_protect_after_use
  before update on rubrics
  for each row
  execute procedure public.prevent_rubric_modification_after_use();

-- Fires on INSERT too, not just UPDATE/DELETE: adding a new criterion to
-- an already-finalized-and-used rubric would change what that rubric
-- means just as much as editing an existing one would -- checked against
-- the rubric the row is (or, for DELETE/UPDATE, currently is) attached
-- to, never the post-UPDATE target if that ever differs.
create or replace function public.prevent_rubric_criteria_modification_after_use()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_check_rubric_id uuid;
begin
  if current_setting('role', true) = 'service_role' then
    return coalesce(new, old);
  end if;

  if tg_op = 'INSERT' then
    v_check_rubric_id := new.rubric_id;
  else
    v_check_rubric_id := old.rubric_id;
  end if;

  if exists (
    select 1 from public.evaluations e where e.rubric_id = v_check_rubric_id and e.status = 'FINALIZED'
  ) then
    if tg_op = 'INSERT' then
      raise exception 'Cannot add a criterion to a rubric already used by a finalized evaluation.'
        using errcode = '42501';
    elsif tg_op = 'DELETE' then
      raise exception 'Cannot delete a criterion of a rubric already used by a finalized evaluation.'
        using errcode = '42501';
    else
      raise exception 'Cannot modify a criterion of a rubric already used by a finalized evaluation.'
        using errcode = '42501';
    end if;
  end if;

  return coalesce(new, old);
end;
$$;

revoke all on function public.prevent_rubric_criteria_modification_after_use() from public;

create trigger rubric_criteria_protect_after_use
  before insert or update or delete on rubric_criteria
  for each row
  execute procedure public.prevent_rubric_criteria_modification_after_use();

-- ============================================================
-- 7. create_evaluator_assignment() -- the ONE trusted, atomic operation
--    that creates an assignment AND its corresponding evaluations row
--    (status = 'ASSIGNED'), together. service_role-only -- see the
--    migration header ("WHY ASSIGNMENT CREATION IS service_role-ONLY").
--    p_created_by is a required parameter, not derived from auth.uid()
--    (service_role has none) -- exactly mirroring
--    create_assessment_attempt()'s own p_student_id: a value the trusted
--    backend caller supplies after already verifying it through whatever
--    the real (not-yet-built) caller-authorization path turns out to be.
-- ============================================================
create or replace function public.create_evaluator_assignment(
  p_evaluator_id uuid,
  p_attempt_id uuid,
  p_question_id uuid,
  p_created_by uuid
)
returns public.evaluator_assignments
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_assignment public.evaluator_assignments;
  v_evaluator_role text;
begin
  select role into v_evaluator_role from public.profiles where id = p_evaluator_id;

  if v_evaluator_role is null then
    raise exception 'Evaluator does not exist.' using errcode = 'P0002';
  end if;

  if v_evaluator_role <> 'FACULTY' then
    raise exception 'Only FACULTY accounts may be assigned as an evaluator.' using errcode = '42501';
  end if;

  if not exists (
    select 1 from public.assessment_attempt_questions
    where attempt_id = p_attempt_id and question_id = p_question_id
  ) then
    raise exception 'No such attempt-question to assign.' using errcode = 'P0002';
  end if;

  insert into public.evaluator_assignments (evaluator_id, attempt_id, question_id, created_by)
  values (p_evaluator_id, p_attempt_id, p_question_id, p_created_by)
  returning * into v_assignment;

  insert into public.evaluations (assignment_id, evaluator_id, status)
  values (v_assignment.id, p_evaluator_id, 'ASSIGNED');

  return v_assignment;
end;
$$;

revoke all on function public.create_evaluator_assignment(uuid, uuid, uuid, uuid) from public;
revoke all on function public.create_evaluator_assignment(uuid, uuid, uuid, uuid) from anon;
revoke all on function public.create_evaluator_assignment(uuid, uuid, uuid, uuid) from authenticated;
grant execute on function public.create_evaluator_assignment(uuid, uuid, uuid, uuid) to service_role;

-- ============================================================
-- 8. revoke_evaluator_assignment() -- service_role-only, symmetric to
--    creation. Does NOT touch the assignment's evaluations row directly --
--    an evaluator already mid-evaluation loses further write access the
--    moment the assignment is no longer ACTIVE (evaluations' own UPDATE
--    policy re-checks this), and a FINALIZED evaluation is immutable
--    regardless of assignment status.
-- ============================================================
create or replace function public.revoke_evaluator_assignment(
  p_assignment_id uuid,
  p_revoked_by uuid
)
returns public.evaluator_assignments
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_assignment public.evaluator_assignments;
begin
  select * into v_assignment from public.evaluator_assignments where id = p_assignment_id for update;

  if not found then
    raise exception 'Assignment not found.' using errcode = 'P0002';
  end if;

  if v_assignment.status = 'REVOKED' then
    raise exception 'Assignment is already revoked.' using errcode = '55000';
  end if;

  update public.evaluator_assignments
  set status = 'REVOKED', revoked_at = now(), revoked_by = p_revoked_by
  where id = p_assignment_id
  returning * into v_assignment;

  return v_assignment;
end;
$$;

revoke all on function public.revoke_evaluator_assignment(uuid, uuid) from public;
revoke all on function public.revoke_evaluator_assignment(uuid, uuid) from anon;
revoke all on function public.revoke_evaluator_assignment(uuid, uuid) from authenticated;
grant execute on function public.revoke_evaluator_assignment(uuid, uuid) to service_role;

-- ============================================================
-- NOT DONE HERE (explicitly, per F8.1's own scope boundary)
-- ============================================================
-- - No RLS change of any kind to assessment_answers or
--   assessment_attempt_questions -- F8.2's dedicated security phase.
-- - No change to create_assessment_attempt() or
--   score_assessment_attempt() -- F8.4's concern.
-- - No FastAPI route, no service, no frontend component anywhere.
-- - No rubric-authoring RPC (rubrics/rubric_criteria are populated by
--   service_role only in F8.1 -- the actual authoring workflow, and who
--   may use it, is an F8.3 decision).
-- - No file/execution/artifact support of any kind for CODE/practical
--   evaluation.
-- - No moderator/lead activation, no AI evaluation of any kind.

