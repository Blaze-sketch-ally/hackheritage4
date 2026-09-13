-- Migration: 065_participation_evaluation_completion
-- Purpose: PHASE 4 (final) of the shared Participation Workspace
-- architecture -- configurable evaluation criteria, a structured final
-- evaluation scored against those criteria, and the completion record.
-- Mirrors internship_completions' shape (051) where it fits, extended
-- with a real rubric (criteria + weights) instead of a single
-- pass/fail outcome, per explicit product requirement.
--
-- ============================================================
-- Why a rubric instead of one free-text score
-- ============================================================
-- participation_evaluation_criteria is authored per PROGRAM (so every
-- participant in that Project/Training/Workshop is scored against the
-- same rubric). participation_evaluations is one row per WORKSPACE,
-- holding an overall_score/overall_feedback that the SERVICE LAYER
-- computes from the weighted participation_evaluation_scores rows -- a
-- client-supplied overall_score is never trusted (mirrors match_service's
-- "the backend is the sole source of the score" stance for Skill Match).
-- score <= criterion.max_score is enforced by a trigger (cross-table, so a
-- plain CHECK cannot express it) -- see
-- enforce_participation_evaluation_score_bound below.
--
-- ============================================================
-- Finalization is a one-way door (no reopen concept in this phase)
-- ============================================================
-- Once participation_evaluations.status = 'FINALIZED', the
-- enforce_participation_evaluation_immutability trigger blocks ANY
-- further change to that evaluation OR its scores from an ordinary
-- authenticated caller -- score/feedback edits after finalization would
-- silently invalidate a completion record. service_role can still amend
-- it (an operator-run correction script, if ever needed) -- same
-- "service_role is the trusted correction path" pattern used throughout
-- this schema (002/023/032/052).
--
-- ============================================================
-- Completion
-- ============================================================
-- participation_completions.final_evaluation_id, when set, MUST point at
-- a FINALIZED evaluation for the same workspace (enforced by
-- enforce_participation_completion_requires_finalized_evaluation) -- a
-- completion can also be recorded with no evaluation at all
-- (final_evaluation_id null) for a lightweight Workshop that skipped
-- formal evaluation, per the product brief ("Workshops... light final
-- evaluation" / evaluation is optional content, not mandatory
-- architecture). No certificate table is added here -- out of scope for
-- this phase, and completion is shaped so one can be added later exactly
-- as internship_certificates was added after internship_completions.
--
-- ============================================================
-- Object creation order
-- ============================================================
--   1. participation_evaluation_criteria  (table + RLS)
--   2. participation_evaluations           (table + immutability trigger + RLS)
--   3. participation_evaluation_scores     (table + score-bound trigger + RLS)
--   4. participation_completions           (table + cross-table check trigger + RLS)

create table if not exists participation_evaluation_criteria (
  id uuid primary key default gen_random_uuid(),
  program_id uuid not null references participation_programs (id) on delete cascade,

  name text not null,
  description text,
  max_score numeric(6, 2) not null check (max_score > 0),
  weight numeric(5, 2) not null check (weight > 0 and weight <= 100),
  sequence_order int not null default 0 check (sequence_order >= 0),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists participation_evaluation_criteria_program_id_idx
  on participation_evaluation_criteria (program_id);

alter table participation_evaluation_criteria enable row level security;

-- "for all" (including delete) is a deliberate exception here, same as
-- program_skills (049): criteria are a small, freely-editable rubric
-- configuration, not an append-only history. An unused criterion (never
-- scored) can be removed outright; ON DELETE RESTRICT on
-- participation_evaluation_scores.criterion_id already protects any
-- criterion a real evaluation has scored against.
drop policy if exists "Industry can manage their own evaluation criteria" on participation_evaluation_criteria;
create policy "Industry can manage their own evaluation criteria"
  on participation_evaluation_criteria for all
  to authenticated
  using (public.owns_participation_program(participation_evaluation_criteria.program_id))
  with check (public.owns_participation_program(participation_evaluation_criteria.program_id));

-- Students may read the rubric for their own workspace's program (so the
-- Student UI can show "what you'll be evaluated on" before/alongside the
-- final result) -- read-only, never write.
drop policy if exists "Students can view evaluation criteria for their workspace" on participation_evaluation_criteria;
create policy "Students can view evaluation criteria for their workspace"
  on participation_evaluation_criteria for select
  to authenticated
  using (public.student_has_workspace_for_program(participation_evaluation_criteria.program_id));

drop trigger if exists participation_evaluation_criteria_set_updated_at on participation_evaluation_criteria;
create trigger participation_evaluation_criteria_set_updated_at
  before update on participation_evaluation_criteria
  for each row
  execute procedure public.set_updated_at();

create table if not exists participation_evaluations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references participation_workspaces (id) on delete cascade,
  evaluator_id uuid not null references profiles (id) on delete restrict,

  status text not null default 'DRAFT' check (status in ('DRAFT', 'FINALIZED')),
  -- Computed server-side from participation_evaluation_scores x criteria
  -- weights -- see app.services.participation_evaluation_service. Never
  -- accepted verbatim from a client request.
  overall_score numeric(5, 2) check (overall_score is null or (overall_score >= 0 and overall_score <= 100)),
  overall_feedback text,

  evaluated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint participation_evaluations_one_per_workspace unique (workspace_id),
  constraint participation_evaluations_finalized_requires_fields check (
    status = 'DRAFT' or (evaluated_at is not null and overall_score is not null)
  )
);

create or replace function public.set_participation_evaluator_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    new.evaluator_id := auth.uid();
  end if;
  return new;
end;
$$;

revoke all on function public.set_participation_evaluator_id() from public;

drop trigger if exists participation_evaluations_set_evaluator on participation_evaluations;
create trigger participation_evaluations_set_evaluator
  before insert on participation_evaluations
  for each row
  execute procedure public.set_participation_evaluator_id();

-- One-way door: once FINALIZED, no ordinary caller may change anything on
-- this row again (including re-finalizing). service_role steps aside.
create or replace function public.enforce_participation_evaluation_immutability()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if old.status = 'FINALIZED' then
    raise exception 'This evaluation has been finalized and can no longer be changed.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_participation_evaluation_immutability() from public;

drop trigger if exists participation_evaluations_enforce_immutability on participation_evaluations;
create trigger participation_evaluations_enforce_immutability
  before update on participation_evaluations
  for each row
  execute procedure public.enforce_participation_evaluation_immutability();

drop trigger if exists participation_evaluations_set_updated_at on participation_evaluations;
create trigger participation_evaluations_set_updated_at
  before update on participation_evaluations
  for each row
  execute procedure public.set_updated_at();

alter table participation_evaluations enable row level security;

drop policy if exists "Students can view their own final evaluation" on participation_evaluations;
create policy "Students can view their own final evaluation"
  on participation_evaluations for select
  to authenticated
  using (public.student_owns_participation_workspace(participation_evaluations.workspace_id));

-- No DELETE policy -- an evaluation (DRAFT or FINALIZED) is a permanent
-- record; UPDATE is further restricted to DRAFT by
-- enforce_participation_evaluation_immutability above.
drop policy if exists "Industry can view evaluations for their own workspaces" on participation_evaluations;
create policy "Industry can view evaluations for their own workspaces"
  on participation_evaluations for select
  to authenticated
  using (public.industry_owns_participation_workspace(participation_evaluations.workspace_id));

drop policy if exists "Industry can create evaluations for their own workspaces" on participation_evaluations;
create policy "Industry can create evaluations for their own workspaces"
  on participation_evaluations for insert
  to authenticated
  with check (public.industry_owns_participation_workspace(participation_evaluations.workspace_id));

drop policy if exists "Industry can update evaluations for their own workspaces" on participation_evaluations;
create policy "Industry can update evaluations for their own workspaces"
  on participation_evaluations for update
  to authenticated
  using (public.industry_owns_participation_workspace(participation_evaluations.workspace_id))
  with check (public.industry_owns_participation_workspace(participation_evaluations.workspace_id));

create table if not exists participation_evaluation_scores (
  id uuid primary key default gen_random_uuid(),
  evaluation_id uuid not null references participation_evaluations (id) on delete cascade,
  criterion_id uuid not null references participation_evaluation_criteria (id) on delete restrict,

  score numeric(6, 2) not null check (score >= 0),
  feedback text,

  constraint participation_evaluation_scores_unique_per_criterion unique (evaluation_id, criterion_id)
);

create index if not exists participation_evaluation_scores_evaluation_id_idx
  on participation_evaluation_scores (evaluation_id);

-- score <= the criterion's own max_score -- cross-table, so a plain CHECK
-- cannot express it; enforced here instead.
create or replace function public.enforce_participation_evaluation_score_bound()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_max numeric(6, 2);
begin
  select max_score into v_max from public.participation_evaluation_criteria where id = new.criterion_id;
  if v_max is null then
    raise exception 'Referenced evaluation criterion does not exist.' using errcode = '23503';
  end if;
  if new.score > v_max then
    raise exception 'Score cannot exceed this criterion''s max score (%).', v_max using errcode = '23514';
  end if;
  return new;
end;
$$;

revoke all on function public.enforce_participation_evaluation_score_bound() from public;

drop trigger if exists participation_evaluation_scores_enforce_bound on participation_evaluation_scores;
create trigger participation_evaluation_scores_enforce_bound
  before insert or update on participation_evaluation_scores
  for each row
  execute procedure public.enforce_participation_evaluation_score_bound();

-- Blocks changing a score once its parent evaluation is FINALIZED --
-- same one-way-door rule as the evaluation row itself, applied to its
-- children (service_role steps aside, matching every guard above).
create or replace function public.enforce_participation_evaluation_score_immutability()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_status text;
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  select status into v_status from public.participation_evaluations
  where id = coalesce(new.evaluation_id, old.evaluation_id);

  if v_status = 'FINALIZED' then
    raise exception 'This evaluation has been finalized and its scores can no longer be changed.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_participation_evaluation_score_immutability() from public;

drop trigger if exists participation_evaluation_scores_enforce_immutability on participation_evaluation_scores;
create trigger participation_evaluation_scores_enforce_immutability
  before insert or update or delete on participation_evaluation_scores
  for each row
  execute procedure public.enforce_participation_evaluation_score_immutability();

alter table participation_evaluation_scores enable row level security;

drop policy if exists "Students can view scores on their own final evaluation" on participation_evaluation_scores;
create policy "Students can view scores on their own final evaluation"
  on participation_evaluation_scores for select
  to authenticated
  using (
    exists (
      select 1 from participation_evaluations e
      where e.id = participation_evaluation_scores.evaluation_id
        and public.student_owns_participation_workspace(e.workspace_id)
    )
  );

-- "for all" (including delete) while the parent evaluation is DRAFT --
-- Industry may freely add/edit/remove a per-criterion score before
-- finalizing. enforce_participation_evaluation_score_immutability (above)
-- blocks every one of these (insert/update/delete) once the parent
-- evaluation is FINALIZED, regardless of this policy.
drop policy if exists "Industry can manage scores for their own evaluations" on participation_evaluation_scores;
create policy "Industry can manage scores for their own evaluations"
  on participation_evaluation_scores for all
  to authenticated
  using (
    exists (
      select 1 from participation_evaluations e
      where e.id = participation_evaluation_scores.evaluation_id
        and public.industry_owns_participation_workspace(e.workspace_id)
    )
  )
  with check (
    exists (
      select 1 from participation_evaluations e
      where e.id = participation_evaluation_scores.evaluation_id
        and public.industry_owns_participation_workspace(e.workspace_id)
    )
  );

create table if not exists participation_completions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references participation_workspaces (id) on delete cascade,
  final_evaluation_id uuid references participation_evaluations (id) on delete restrict,

  completed_at timestamptz not null default now(),
  completion_status text not null default 'COMPLETED' check (completion_status in ('COMPLETED')),
  final_score numeric(5, 2) check (final_score is null or (final_score >= 0 and final_score <= 100)),

  created_at timestamptz not null default now(),

  constraint participation_completions_one_per_workspace unique (workspace_id)
);

create index if not exists participation_completions_workspace_id_idx on participation_completions (workspace_id);

-- A completion referencing an evaluation may only reference a FINALIZED
-- one for the SAME workspace -- cross-table, so enforced by trigger.
create or replace function public.enforce_participation_completion_requires_finalized_evaluation()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_status text;
  v_workspace_id uuid;
begin
  if new.final_evaluation_id is null then
    return new;
  end if;

  select status, workspace_id into v_status, v_workspace_id
  from public.participation_evaluations where id = new.final_evaluation_id;

  if v_workspace_id is null then
    raise exception 'Referenced evaluation does not exist.' using errcode = '23503';
  end if;
  if v_workspace_id <> new.workspace_id then
    raise exception 'The referenced evaluation belongs to a different workspace.' using errcode = '23514';
  end if;
  if v_status <> 'FINALIZED' then
    raise exception 'Completion can only reference a FINALIZED evaluation.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_participation_completion_requires_finalized_evaluation() from public;

drop trigger if exists participation_completions_enforce_finalized_evaluation on participation_completions;
create trigger participation_completions_enforce_finalized_evaluation
  before insert or update on participation_completions
  for each row
  execute procedure public.enforce_participation_completion_requires_finalized_evaluation();

alter table participation_completions enable row level security;

drop policy if exists "Students can view their own completion" on participation_completions;
create policy "Students can view their own completion"
  on participation_completions for select
  to authenticated
  using (public.student_owns_participation_workspace(participation_completions.workspace_id));

-- SELECT + INSERT only -- a completion is terminal and permanent, never
-- updated or deleted by an ordinary caller once recorded.
drop policy if exists "Industry can view completions for their own workspaces" on participation_completions;
create policy "Industry can view completions for their own workspaces"
  on participation_completions for select
  to authenticated
  using (public.industry_owns_participation_workspace(participation_completions.workspace_id));

drop policy if exists "Industry can create completions for their own workspaces" on participation_completions;
create policy "Industry can create completions for their own workspaces"
  on participation_completions for insert
  to authenticated
  with check (public.industry_owns_participation_workspace(participation_completions.workspace_id));

-- No UPDATE/DELETE policy for either role on participation_completions,
-- participation_evaluations, participation_modules, _resources,
-- _assignments, participation_feedback, or
-- participation_skill_recommendations -- every one of these is a
-- permanent record once created (evaluations only permit UPDATE while
-- still DRAFT, per the immutability trigger above). Only
-- participation_evaluation_criteria and participation_evaluation_scores
-- allow delete, both deliberately, both documented at their own policy.
