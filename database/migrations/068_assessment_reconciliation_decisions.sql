-- Migration: 068_assessment_reconciliation_decisions
-- Purpose: Faculty Assessment Reconciliation -- implements the approved
-- Option C governance design (see the Faculty Assessment Reconciliation
-- design-gate report). Adds a SEPARATE, append-only-by-supersession
-- `reconciliation_decisions` record and the two SECURITY DEFINER RPCs
-- that write it; extends `fold_in_attempt_evaluation()` (049) via
-- CREATE OR REPLACE (049 itself is NOT edited) to consume an authoritative
-- decision for a conflicting question instead of leaving the whole
-- attempt permanently stuck at NEEDS_RECONCILIATION.
--
-- ============================================================
-- THE CENTRAL INVARIANT THIS MIGRATION PRESERVES
-- ============================================================
-- FINALIZED evaluator evaluations remain exactly as immutable as 045
-- already made them. Nothing in this migration ever INSERTs, UPDATEs, or
-- DELETEs a row in `evaluations` or `evaluator_assignments`. The
-- reconciliation mechanism works entirely by adding a SECOND,
-- independently-auditable source of truth (`reconciliation_decisions`)
-- that the fold-in function additionally consults -- the original
-- disagreeing marks are never read differently, rewritten, or discarded;
-- they remain permanently queryable exactly as they were finalized.
--
-- ============================================================
-- Reconciliation unit: per (attempt_id, question_id), not per attempt
-- ============================================================
-- Re-verified directly from 049's own loop: `v_has_conflict` is an
-- attempt-scoped boolean set true by ANY conflicting question, so the
-- attempt cannot leave NEEDS_RECONCILIATION until EVERY conflicting
-- question either naturally resolves (never happens once FINALIZED,
-- since marks don't change) or has an ACTIVE reconciliation decision.
-- The decision itself must therefore be scoped to the specific
-- question, not the bare attempt -- an attempt with 3 conflicting
-- questions needs up to 3 independent decisions.
--
-- ============================================================
-- 1. reconciliation_decisions table
-- ============================================================
-- Composite FK to assessment_attempt_questions' own composite primary
-- key (attempt_id, question_id) -- the IDENTICAL, already-proven pattern
-- evaluator_assignments itself uses (045) for the exact same grain, not
-- an invented one.
create table if not exists reconciliation_decisions (
  id uuid primary key default gen_random_uuid(),

  attempt_id uuid not null,
  question_id uuid not null,
  foreign key (attempt_id, question_id)
    references assessment_attempt_questions (attempt_id, question_id)
    on delete cascade,

  -- Never client-supplied -- always auth.uid(), set exclusively inside
  -- the two RPCs below (see their own bodies).
  moderator_id uuid not null references profiles (id) on delete restrict,

  -- Same numeric(6,2) precision as evaluations.awarded_marks /
  -- assessment_questions.points throughout this project -- no new scale
  -- invented. Upper bound (<= question.points) cannot be expressed as a
  -- plain CHECK (it depends on a sibling table), so it is enforced
  -- inside the RPCs, mirroring exactly how prevent_unauthorized_
  -- evaluation_change() (045) already enforces the identical class of
  -- rule (awarded_marks <= rubric.max_marks) in PL/pgSQL rather than a
  -- static CHECK.
  final_awarded_marks numeric(6, 2) not null check (final_awarded_marks >= 0),

  -- Mandatory, non-empty after trim -- same convention already
  -- established for portfolio title/description/name/issuer
  -- (025_portfolio_projects_and_certifications.sql): "check (length(trim(x)) > 0)".
  -- No maximum-length CHECK is added: no existing text column in this
  -- schema has one, so none is invented here either.
  rationale text not null check (length(trim(rationale)) > 0),

  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'SUPERSEDED')),

  created_at timestamptz not null default now(),

  -- Immutability by supersession (not by edit): a corrected decision
  -- never UPDATEs final_awarded_marks/rationale/moderator_id on this
  -- row -- it INSERTs a new ACTIVE row and sets this column on the OLD
  -- row, alongside flipping its own status to SUPERSEDED. Nullable,
  -- self-referencing, SET NULL on delete (this table's own rows are
  -- never deleted by any code path in this migration, but SET NULL is
  -- the safe default for a historical cross-reference, matching
  -- assessment_questions' own deferred "replaced_by_question_id"
  -- precedent comment in 015).
  superseded_by uuid references reconciliation_decisions (id) on delete set null
);

-- Idempotency / concurrency backstop (Layer 2, matching this project's
-- own "app discipline + DB constraint" pattern, e.g.
-- faculty_notifications_dedupe_idx): at most one ACTIVE decision per
-- conflicting question, ever. This is what makes "two moderators
-- resolve the same case at the same time" safe: the second INSERT
-- attempt fails this constraint, not merely loses an application-level
-- race.
create unique index if not exists reconciliation_decisions_one_active_idx
  on reconciliation_decisions (attempt_id, question_id)
  where status = 'ACTIVE';

create index if not exists reconciliation_decisions_attempt_id_idx
  on reconciliation_decisions (attempt_id);
create index if not exists reconciliation_decisions_question_id_idx
  on reconciliation_decisions (question_id);
create index if not exists reconciliation_decisions_moderator_id_idx
  on reconciliation_decisions (moderator_id);

alter table reconciliation_decisions enable row level security;
-- No SELECT/INSERT/UPDATE/DELETE policy for `authenticated` at all --
-- identical posture to evaluation_history (045) and faculty_notifications
-- (066): this is internal governance data, written and read exclusively
-- through the SECURITY DEFINER RPCs below, never through a raw
-- authenticated client. A moderator cannot create a decision, alter one,
-- or bypass fold-in by talking to this table directly -- there is
-- structurally nothing to talk to.

-- ============================================================
-- 2. create_reconciliation_decision(...)
-- ============================================================
-- Creates the FIRST decision for a genuinely conflicting question.
-- Returns the new decision plus the freshly-refolded attempt's own
-- evaluation_status/final_percentage, plus parallel arrays of the
-- evaluator_ids and their own evaluation_ids whose FINALIZED mark
-- applied to this question (so the calling backend can notify each one
-- with a deep link to THEIR OWN evaluation -- see
-- app.services.faculty_notification_producer;
-- this RPC itself never writes to faculty_notifications, keeping this
-- migration's only write surface scoped to reconciliation_decisions +
-- the pre-existing assessment_attempts write inside fold-in).
create or replace function public.create_reconciliation_decision(
  p_attempt_id uuid,
  p_question_id uuid,
  p_final_awarded_marks numeric,
  p_rationale text
)
returns table (
  decision_id uuid,
  attempt_id uuid,
  question_id uuid,
  moderator_id uuid,
  final_awarded_marks numeric(6, 2),
  rationale text,
  status text,
  created_at timestamptz,
  affected_evaluator_ids uuid[],
  affected_evaluation_ids uuid[],
  evaluation_status text,
  final_percentage numeric(5, 2)
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_attempt public.assessment_attempts;
  v_question public.assessment_questions;
  v_distinct_count int;
  v_eligible_marks numeric(6, 2)[];
  v_evaluator_ids uuid[];
  v_evaluation_ids uuid[];
  v_existing_active uuid;
  v_new_id uuid;
  v_folded public.assessment_attempts;
begin
  if not public.has_assessment_capability(auth.uid(), 'assessment_moderator') then
    raise exception 'Only an assessment_moderator may create a reconciliation decision.'
      using errcode = '42501';
  end if;

  -- Same lock-ordering discipline as fold_in_attempt_evaluation() itself
  -- (lock the attempt FIRST) -- this is also what makes the later
  -- fold-in call inside this same transaction never re-acquire a lock it
  -- doesn't already hold, exactly mirroring 050's own "cannot self-
  -- deadlock" reasoning.
  select * into v_attempt from public.assessment_attempts where id = p_attempt_id for update;
  if not found then
    raise exception 'Attempt not found.' using errcode = 'P0002';
  end if;

  if v_attempt.evaluation_status <> 'NEEDS_RECONCILIATION' then
    raise exception 'This attempt is not currently awaiting reconciliation.' using errcode = '55000';
  end if;

  select q.* into v_question
  from public.assessment_questions q
  join public.assessment_attempt_questions aq on aq.question_id = q.id
  where aq.attempt_id = p_attempt_id and q.id = p_question_id;

  if not found then
    raise exception 'This question does not belong to this attempt.' using errcode = 'P0002';
  end if;

  -- Re-derive the conflict from source, exactly the eligibility rule
  -- fold-in itself uses -- never trust a client-displayed pair of marks.
  select array_agg(distinct e.awarded_marks)
  into v_eligible_marks
  from public.evaluations e
  join public.evaluator_assignments ea on ea.id = e.assignment_id
  join public.rubrics r on r.id = e.rubric_id
  where ea.attempt_id = p_attempt_id
    and ea.question_id = p_question_id
    and e.status = 'FINALIZED'
    and r.max_marks = v_question.points;

  v_distinct_count := coalesce(array_length(v_eligible_marks, 1), 0);
  if v_distinct_count <= 1 then
    raise exception 'This question is not currently in conflict.' using errcode = '55000';
  end if;

  -- Row-level (not distinct-marks) pairing of evaluator <-> their own
  -- evaluation id, ordered consistently, so the calling backend can zip
  -- these two arrays together to notify each affected evaluator with
  -- the correct deep link (their OWN evaluation, never another's).
  select array_agg(e.evaluator_id order by e.id), array_agg(e.id order by e.id)
  into v_evaluator_ids, v_evaluation_ids
  from public.evaluations e
  join public.evaluator_assignments ea on ea.id = e.assignment_id
  join public.rubrics r on r.id = e.rubric_id
  where ea.attempt_id = p_attempt_id
    and ea.question_id = p_question_id
    and e.status = 'FINALIZED'
    and r.max_marks = v_question.points;

  select id into v_existing_active
  from public.reconciliation_decisions
  where attempt_id = p_attempt_id and question_id = p_question_id and status = 'ACTIVE';
  if v_existing_active is not null then
    raise exception 'An active reconciliation decision already exists for this question.'
      using errcode = '23505';
  end if;

  if p_final_awarded_marks < 0 or p_final_awarded_marks > v_question.points then
    raise exception 'Final awarded marks (%) must be between 0 and the question''s points (%).',
      p_final_awarded_marks, v_question.points using errcode = '23514';
  end if;

  insert into public.reconciliation_decisions (
    attempt_id, question_id, moderator_id, final_awarded_marks, rationale, status
  ) values (
    p_attempt_id, p_question_id, auth.uid(), p_final_awarded_marks, p_rationale, 'ACTIVE'
  )
  returning id into v_new_id;

  -- Re-fold in the SAME transaction -- the existing, unmodified-in-
  -- signature fold_in_attempt_evaluation() (049, extended below) remains
  -- the ONE place evaluation_status/final_* are ever computed. This RPC
  -- never writes those columns directly.
  v_folded := public.fold_in_attempt_evaluation(p_attempt_id);

  return query
  select
    v_new_id, p_attempt_id, p_question_id, auth.uid(), p_final_awarded_marks, p_rationale,
    'ACTIVE'::text, now(), v_evaluator_ids, v_evaluation_ids, v_folded.evaluation_status, v_folded.final_percentage;
end;
$$;

revoke all on function public.create_reconciliation_decision(uuid, uuid, numeric, text) from public;
revoke all on function public.create_reconciliation_decision(uuid, uuid, numeric, text) from anon;
grant execute on function public.create_reconciliation_decision(uuid, uuid, numeric, text) to authenticated;

-- ============================================================
-- 3. supersede_reconciliation_decision(...)
-- ============================================================
-- Corrects an existing ACTIVE decision. Deliberately NOT gated on the
-- attempt's CURRENT evaluation_status -- see this migration's own
-- "Stage 7 edge case" note further down. The old decision's own
-- final_awarded_marks/rationale/moderator_id are never touched; only its
-- status and superseded_by change, and only via this one write path.
create or replace function public.supersede_reconciliation_decision(
  p_decision_id uuid,
  p_final_awarded_marks numeric,
  p_rationale text
)
returns table (
  decision_id uuid,
  attempt_id uuid,
  question_id uuid,
  moderator_id uuid,
  final_awarded_marks numeric(6, 2),
  rationale text,
  status text,
  created_at timestamptz,
  affected_evaluator_ids uuid[],
  affected_evaluation_ids uuid[],
  evaluation_status text,
  final_percentage numeric(5, 2)
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_old public.reconciliation_decisions;
  v_question public.assessment_questions;
  v_evaluator_ids uuid[];
  v_evaluation_ids uuid[];
  v_new_id uuid;
  v_folded public.assessment_attempts;
begin
  if not public.has_assessment_capability(auth.uid(), 'assessment_moderator') then
    raise exception 'Only an assessment_moderator may supersede a reconciliation decision.'
      using errcode = '42501';
  end if;

  select * into v_old from public.reconciliation_decisions where id = p_decision_id;
  if not found then
    raise exception 'Decision not found.' using errcode = 'P0002';
  end if;

  if v_old.status <> 'ACTIVE' then
    raise exception 'This decision has already been superseded.' using errcode = '55000';
  end if;

  -- Lock the attempt (same ordering as create_reconciliation_decision /
  -- fold_in_attempt_evaluation) -- MUST be locked even though this RPC
  -- does not require the attempt to still be NEEDS_RECONCILIATION (see
  -- the Stage 7 note below): the lock still serializes this correction
  -- against any concurrent fold-in-triggering write on the same attempt.
  perform 1 from public.assessment_attempts where id = v_old.attempt_id for update;

  select q.* into v_question from public.assessment_questions q where q.id = v_old.question_id;

  if p_final_awarded_marks < 0 or p_final_awarded_marks > v_question.points then
    raise exception 'Final awarded marks (%) must be between 0 and the question''s points (%).',
      p_final_awarded_marks, v_question.points using errcode = '23514';
  end if;

  select array_agg(e.evaluator_id order by e.id), array_agg(e.id order by e.id)
  into v_evaluator_ids, v_evaluation_ids
  from public.evaluations e
  join public.evaluator_assignments ea on ea.id = e.assignment_id
  join public.rubrics r on r.id = e.rubric_id
  where ea.attempt_id = v_old.attempt_id
    and ea.question_id = v_old.question_id
    and e.status = 'FINALIZED'
    and r.max_marks = v_question.points;

  insert into public.reconciliation_decisions (
    attempt_id, question_id, moderator_id, final_awarded_marks, rationale, status
  ) values (
    v_old.attempt_id, v_old.question_id, auth.uid(), p_final_awarded_marks, p_rationale, 'ACTIVE'
  )
  returning id into v_new_id;

  update public.reconciliation_decisions
  set status = 'SUPERSEDED', superseded_by = v_new_id
  where id = v_old.id;

  v_folded := public.fold_in_attempt_evaluation(v_old.attempt_id);

  return query
  select
    v_new_id, v_old.attempt_id, v_old.question_id, auth.uid(), p_final_awarded_marks, p_rationale,
    'ACTIVE'::text, now(), v_evaluator_ids, v_evaluation_ids, v_folded.evaluation_status, v_folded.final_percentage;
end;
$$;

revoke all on function public.supersede_reconciliation_decision(uuid, numeric, text) from public;
revoke all on function public.supersede_reconciliation_decision(uuid, numeric, text) from anon;
grant execute on function public.supersede_reconciliation_decision(uuid, numeric, text) to authenticated;

-- ============================================================
-- STAGE 7 EDGE CASE -- supersession after an attempt has already
-- reached COMPLETE
-- ============================================================
-- Deliberately ALLOWED, not forbidden and not gated behind a new
-- "reopen" state -- reasoned explicitly, not assumed:
--
-- 1. fold_in_attempt_evaluation() (049, unmodified in this regard) only
--    requires assessment_attempts.status = 'COMPLETED' (the OBJECTIVE
--    completion flag, set once, forever, by score_assessment_attempt())
--    -- it does not require evaluation_status to be any particular
--    value to re-run. Re-invoking it after a correction is exactly as
--    safe, and computes exactly as correctly, as any other re-fold.
-- 2. Every downstream consumer of evaluation_status/final_percentage in
--    this codebase (Phase 3A's get_student_skill_scores(), Phase 3D's
--    recommend_assessments()/get_completed_assessment_ids()) is a PURE,
--    ALWAYS-FRESH derivation with no caching layer of any kind -- there
--    is nothing to invalidate. The next read after a correction simply
--    sees the corrected value, exactly as Phase 3A already handles a
--    COMPLETE result appearing at an arbitrary later time relative to
--    when the attempt was originally COMPLETED.
-- 3. The partial unique index (reconciliation_decisions_one_active_idx)
--    guarantees exactly one ACTIVE decision per (attempt, question) at
--    every instant, including mid-supersession (the old row's UPDATE to
--    SUPERSEDED and the new row's INSERT happen inside one transaction,
--    so no window exists with zero or two ACTIVE rows for the same
--    question).
--
-- KNOWN LIMITATION, explicitly flagged rather than silently assumed
-- safe forever: if a FUTURE feature ever snapshots/caches
-- final_percentage somewhere Phase 3A does not already re-derive from
-- (e.g. a certificate, an already-submitted application decision), that
-- future feature would need its own invalidation/re-notification
-- strategy -- this migration does not and cannot solve that pre-emptively,
-- and no such consumer exists in this codebase today (verified by
-- inspection of every existing final_percentage/evaluation_status
-- reader before writing this migration).

-- ============================================================
-- 4. list_reconciliation_decisions(p_attempt_id, p_question_id)
-- ============================================================
-- Full decision history (ACTIVE + every SUPERSEDED ancestor) for one
-- question -- moderator-only, read-only. Extends the Stage 8 visibility
-- requirement WITHOUT modifying 067's own two RPCs (their existing
-- return shape stays exactly as originally shipped/tested) -- this is a
-- separate, additive RPC, not a change to an already-established
-- contract.
create or replace function public.list_reconciliation_decisions(
  p_attempt_id uuid,
  p_question_id uuid
)
returns table (
  decision_id uuid,
  moderator_id uuid,
  final_awarded_marks numeric(6, 2),
  rationale text,
  status text,
  created_at timestamptz,
  superseded_by uuid
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.has_assessment_capability(auth.uid(), 'assessment_moderator') then
    raise exception 'Only an assessment_moderator may view reconciliation decision history.'
      using errcode = '42501';
  end if;

  return query
  select d.id, d.moderator_id, d.final_awarded_marks, d.rationale, d.status, d.created_at, d.superseded_by
  from public.reconciliation_decisions d
  where d.attempt_id = p_attempt_id and d.question_id = p_question_id
  order by d.created_at;
end;
$$;

revoke all on function public.list_reconciliation_decisions(uuid, uuid) from public;
revoke all on function public.list_reconciliation_decisions(uuid, uuid) from anon;
grant execute on function public.list_reconciliation_decisions(uuid, uuid) to authenticated;

-- ============================================================
-- 5. fold_in_attempt_evaluation() -- CREATE OR REPLACE, same signature,
--    same everything except the conflicting-question branch. 049 itself
--    is NOT edited; this is a superseding definition, exactly the same
--    "forward-only, create-or-replace, never touch the original
--    migration file" convention already used throughout this project
--    (e.g. has_assessment_capability itself is create-or-replace'd
--    across 027/etc.).
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
  v_decision_marks numeric(6, 2);
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
      -- 068: a raw conflict no longer automatically means the ATTEMPT
      -- stays NEEDS_RECONCILIATION -- if an ACTIVE, authoritative
      -- reconciliation_decisions row exists for this exact
      -- (attempt, question), its moderated final_awarded_marks is used
      -- instead, exactly as if it were the single agreeing evaluator
      -- mark. The disagreeing evaluations themselves are never read
      -- differently, altered, or removed by this branch -- only this
      -- one SELECT against the new table is added.
      select d.final_awarded_marks
      into v_decision_marks
      from public.reconciliation_decisions d
      where d.attempt_id = p_attempt_id
        and d.question_id = v_question.question_id
        and d.status = 'ACTIVE';

      if v_decision_marks is not null then
        v_resolved_count := v_resolved_count + 1;
        v_human_score := v_human_score + v_decision_marks;
        v_human_total := v_human_total + v_question.points;
      else
        v_has_conflict := true;
      end if;
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
-- create_reconciliation_decision/supersede_reconciliation_decision above
-- also need to call this function; as SECURITY DEFINER functions they
-- execute with their own elevated privilege regardless of the calling
-- authenticated user's own grants on fold_in_attempt_evaluation, exactly
-- how 050's fold_in_after_attempt_completed() trigger function already
-- calls it today without ever being granted execute itself.

-- ============================================================
-- 6. faculty_notifications CHECK widening -- additive only
-- ============================================================
-- Same "062 widens 059's CHECK" precedent, applied to 066 instead of
-- 059. Adds exactly one new type: RECONCILIATION_RESOLVED, emitted to
-- an evaluator whose FINALIZED mark applied to a question a moderator
-- has now resolved. Per the approved decision, an evaluator learns ONLY
-- that a decision was recorded -- never the other evaluator's mark,
-- the rationale, or the moderator's identity; this widening only makes
-- the TYPE representable, it does not itself expose anything (the
-- producer, app.services.faculty_notification_producer, controls the
-- actual body text -- see the accompanying backend change). No other
-- column, policy, or trigger on faculty_notifications is touched; 066
-- itself is not edited.
do $$
declare
  v_name text;
begin
  select con.conname into v_name
  from pg_constraint con
  join pg_attribute att
    on att.attrelid = con.conrelid and att.attnum = con.conkey[1]
  where con.conrelid = 'public.faculty_notifications'::regclass
    and con.contype = 'c'
    and array_length(con.conkey, 1) = 1
    and att.attname = 'type';

  if v_name is not null then
    execute format('alter table public.faculty_notifications drop constraint %I', v_name);
  end if;
end $$;

alter table public.faculty_notifications
  add constraint faculty_notifications_type_check
  check (type in (
    'EVALUATION_ASSIGNED',
    'EVALUATION_REVOKED',
    'REVIEW_DECISION',
    'MENTORSHIP',
    'RECONCILIATION_RESOLVED'
  ));

-- related_entity_type already includes 'EVALUATION' (066) -- the deep
-- link for RECONCILIATION_RESOLVED points at the evaluator's own
-- evaluation (/faculty/evaluation-workspace/{evaluation_id}), so no
-- widening is needed there.
