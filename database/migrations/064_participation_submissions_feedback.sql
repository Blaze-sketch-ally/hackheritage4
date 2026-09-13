-- Migration: 064_participation_submissions_feedback
-- Purpose: PHASE 3 of the shared Participation Workspace architecture --
-- submissions, industry review of a submission, general participant
-- feedback (deliberately separate from a submission review -- see
-- header note below), and skill recommendations. Mirrors
-- workspace_submissions / submission_reviews (051) for the shared
-- PROJECT/TRAINING/WORKSHOP domain (062/063).
--
-- ============================================================
-- Assignment Review vs. Participant Feedback (explicit product distinction)
-- ============================================================
-- participation_submission_reviews is scoped to ONE submitted assignment
-- attempt -- the same role internship's submission_reviews plays.
-- participation_feedback is broader: an Industry account's observations
-- about the student's overall performance in the workspace, not tied to
-- any single submission (a "how are they doing generally" note). Neither
-- table is a specialization of the other; they coexist.
--
-- ============================================================
-- Append-only submissions (mirrors workspace_submissions, 051)
-- ============================================================
-- attempt_number is SERVER-COMPUTED (set_participation_submission_attempt_number
-- below) -- a client-supplied value is ignored, and history is never
-- overwritten: a resubmission is a new row with attempt_number + 1, never
-- an UPDATE of the previous attempt.
--
-- ============================================================
-- Skill recommendations (advisory only -- see the task's own explicit
-- instruction, repeated here as the authoritative in-repo record of it)
-- ============================================================
-- participation_skill_recommendations.skill_id references the CANONICAL
-- skills(id) catalog (003_skills.sql) -- no free-text duplicate skill
-- taxonomy. This table is NEVER read by, written by, or joined into
-- student_skills or any proficiency-scoring path anywhere in this
-- repository, and no trigger here touches student_skills. A
-- recommendation is Industry evidence/advice only; it does not change the
-- student's actual recorded proficiency. Any future integration into the
-- Skill Mapping engine is out of scope for this migration.
--
-- ============================================================
-- Object creation order
-- ============================================================
--   1. participation_submissions       (table + attempt trigger + RLS)
--   2. participation_submission_reviews (table + RLS)
--   3. participation_feedback           (table + RLS)
--   4. participation_skill_recommendations (table + RLS)

create table if not exists participation_submissions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references participation_workspaces (id) on delete cascade,
  assignment_id uuid not null references participation_assignments (id) on delete restrict,

  attempt_number int not null check (attempt_number >= 1),

  submission_text text,
  submission_url text,

  submitted_at timestamptz not null default now(),
  status text not null default 'SUBMITTED' check (status in ('SUBMITTED', 'UNDER_REVIEW', 'REVIEWED')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint participation_submissions_has_content
    check (submission_text is not null or submission_url is not null),
  constraint participation_submissions_unique_attempt
    unique (workspace_id, assignment_id, attempt_number)
);

create index if not exists participation_submissions_workspace_id_idx on participation_submissions (workspace_id);
create index if not exists participation_submissions_assignment_id_idx on participation_submissions (assignment_id);

-- Server-computed attempt_number: one more than the highest existing
-- attempt for this (workspace, assignment) pair, or 1 for the first.
-- Mirrors set_workspace_submission_attempt_number (051).
create or replace function public.set_participation_submission_attempt_number()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_next int;
begin
  select coalesce(max(attempt_number), 0) + 1 into v_next
  from public.participation_submissions
  where workspace_id = new.workspace_id and assignment_id = new.assignment_id;

  new.attempt_number := v_next;
  return new;
end;
$$;

revoke all on function public.set_participation_submission_attempt_number() from public;

drop trigger if exists participation_submissions_set_attempt_number on participation_submissions;
create trigger participation_submissions_set_attempt_number
  before insert on participation_submissions
  for each row
  execute procedure public.set_participation_submission_attempt_number();

drop trigger if exists participation_submissions_set_updated_at on participation_submissions;
create trigger participation_submissions_set_updated_at
  before update on participation_submissions
  for each row
  execute procedure public.set_updated_at();

alter table participation_submissions enable row level security;

drop policy if exists "Students can view their own participation submissions" on participation_submissions;
create policy "Students can view their own participation submissions"
  on participation_submissions for select
  to authenticated
  using (public.student_owns_participation_workspace(participation_submissions.workspace_id));

-- A student may only submit to their OWN workspace, for a PUBLISHED
-- assignment on that workspace's program -- checked inline (the
-- assignment's own RLS SELECT policy, 063, already enforces the same
-- published+workspace-holder gate, so a student could not even see an
-- unpublished assignment id to submit against).
drop policy if exists "Students can submit to their own participation workspace" on participation_submissions;
create policy "Students can submit to their own participation workspace"
  on participation_submissions for insert
  to authenticated
  with check (
    public.student_owns_participation_workspace(participation_submissions.workspace_id)
    and exists (
      select 1 from participation_assignments a
      where a.id = participation_submissions.assignment_id and a.is_published
    )
  );

drop policy if exists "Industry can view submissions for their own participation workspaces" on participation_submissions;
create policy "Industry can view submissions for their own participation workspaces"
  on participation_submissions for select
  to authenticated
  using (public.industry_owns_participation_workspace(participation_submissions.workspace_id));

-- No UPDATE/DELETE policy for either role -- append-only history; status
-- (SUBMITTED -> UNDER_REVIEW -> REVIEWED) is set by service-role from the
-- review-creation path only, never by an ordinary authenticated caller.

create table if not exists participation_submission_reviews (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references participation_submissions (id) on delete cascade,
  reviewer_id uuid not null references profiles (id) on delete restrict,

  score numeric(6, 2) check (score is null or score >= 0),
  feedback text,
  status text not null check (status in ('REVIEWED', 'NEEDS_REVISION', 'ACCEPTED')),

  reviewed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists participation_submission_reviews_submission_id_idx
  on participation_submission_reviews (submission_id);

-- reviewer_id is derived from the caller, never client-supplied, and the
-- caller must own the workspace behind the submission -- so a student can
-- never review their own work, and one Industry account can never review
-- another's participant.
create or replace function public.set_participation_review_reviewer_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.reviewer_id := auth.uid();
  return new;
end;
$$;

revoke all on function public.set_participation_review_reviewer_id() from public;

drop trigger if exists participation_submission_reviews_set_reviewer on participation_submission_reviews;
create trigger participation_submission_reviews_set_reviewer
  before insert on participation_submission_reviews
  for each row
  execute procedure public.set_participation_review_reviewer_id();

alter table participation_submission_reviews enable row level security;

drop policy if exists "Students can view reviews of their own submissions" on participation_submission_reviews;
create policy "Students can view reviews of their own submissions"
  on participation_submission_reviews for select
  to authenticated
  using (
    exists (
      select 1 from participation_submissions s
      where s.id = participation_submission_reviews.submission_id
        and public.student_owns_participation_workspace(s.workspace_id)
    )
  );

drop policy if exists "Industry can view reviews for their own participation workspaces" on participation_submission_reviews;
create policy "Industry can view reviews for their own participation workspaces"
  on participation_submission_reviews for select
  to authenticated
  using (
    exists (
      select 1 from participation_submissions s
      where s.id = participation_submission_reviews.submission_id
        and public.industry_owns_participation_workspace(s.workspace_id)
    )
  );

drop policy if exists "Industry can review submissions for their own participation workspaces" on participation_submission_reviews;
create policy "Industry can review submissions for their own participation workspaces"
  on participation_submission_reviews for insert
  to authenticated
  with check (
    public.is_industry(auth.uid())
    and exists (
      select 1 from participation_submissions s
      where s.id = participation_submission_reviews.submission_id
        and public.industry_owns_participation_workspace(s.workspace_id)
    )
  );

-- No UPDATE/DELETE policy -- a review is a permanent record; a changed
-- mind is a new review row (mirrors submission_reviews, 051, which is
-- also insert-only).

create table if not exists participation_feedback (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references participation_workspaces (id) on delete cascade,
  industry_id uuid not null references profiles (id) on delete restrict,

  feedback_type text not null check (feedback_type in ('GENERAL', 'PROGRESS', 'STRENGTH', 'IMPROVEMENT', 'FINAL_NOTE')),
  title text,
  feedback text not null,

  created_at timestamptz not null default now()
);

create index if not exists participation_feedback_workspace_id_idx on participation_feedback (workspace_id);

create or replace function public.set_participation_feedback_industry_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.industry_id := auth.uid();
  return new;
end;
$$;

revoke all on function public.set_participation_feedback_industry_id() from public;

drop trigger if exists participation_feedback_set_industry_id on participation_feedback;
create trigger participation_feedback_set_industry_id
  before insert on participation_feedback
  for each row
  execute procedure public.set_participation_feedback_industry_id();

alter table participation_feedback enable row level security;

drop policy if exists "Students can view feedback on their own workspace" on participation_feedback;
create policy "Students can view feedback on their own workspace"
  on participation_feedback for select
  to authenticated
  using (public.student_owns_participation_workspace(participation_feedback.workspace_id));

-- No DELETE/UPDATE policy -- feedback is an append-only record, like
-- participation_submission_reviews. A changed assessment is new feedback.
drop policy if exists "Industry can view feedback for their own workspaces" on participation_feedback;
create policy "Industry can view feedback for their own workspaces"
  on participation_feedback for select
  to authenticated
  using (public.industry_owns_participation_workspace(participation_feedback.workspace_id));

drop policy if exists "Industry can create feedback for their own workspaces" on participation_feedback;
create policy "Industry can create feedback for their own workspaces"
  on participation_feedback for insert
  to authenticated
  with check (public.industry_owns_participation_workspace(participation_feedback.workspace_id));

create table if not exists participation_skill_recommendations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references participation_workspaces (id) on delete cascade,
  skill_id uuid not null references skills (id) on delete restrict,

  recommended_level text check (recommended_level in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),
  reason text not null,
  priority text not null default 'MEDIUM' check (priority in ('LOW', 'MEDIUM', 'HIGH')),

  created_by uuid not null references profiles (id) on delete restrict,
  created_at timestamptz not null default now()
);

create index if not exists participation_skill_recommendations_workspace_id_idx
  on participation_skill_recommendations (workspace_id);

create or replace function public.set_participation_recommendation_created_by()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.created_by := auth.uid();
  return new;
end;
$$;

revoke all on function public.set_participation_recommendation_created_by() from public;

drop trigger if exists participation_skill_recommendations_set_created_by on participation_skill_recommendations;
create trigger participation_skill_recommendations_set_created_by
  before insert on participation_skill_recommendations
  for each row
  execute procedure public.set_participation_recommendation_created_by();

alter table participation_skill_recommendations enable row level security;

drop policy if exists "Students can view recommendations on their own workspace" on participation_skill_recommendations;
create policy "Students can view recommendations on their own workspace"
  on participation_skill_recommendations for select
  to authenticated
  using (public.student_owns_participation_workspace(participation_skill_recommendations.workspace_id));

-- No DELETE/UPDATE policy -- a recommendation is a permanent record, like
-- participation_feedback. A revised recommendation is a new row.
drop policy if exists "Industry can view recommendations for their own workspaces" on participation_skill_recommendations;
create policy "Industry can view recommendations for their own workspaces"
  on participation_skill_recommendations for select
  to authenticated
  using (public.industry_owns_participation_workspace(participation_skill_recommendations.workspace_id));

drop policy if exists "Industry can create recommendations for their own workspaces" on participation_skill_recommendations;
create policy "Industry can create recommendations for their own workspaces"
  on participation_skill_recommendations for insert
  to authenticated
  with check (public.industry_owns_participation_workspace(participation_skill_recommendations.workspace_id));
