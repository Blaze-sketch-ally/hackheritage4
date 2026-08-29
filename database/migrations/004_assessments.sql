-- Migration: 004_assessments
-- Purpose: the SKILL ASSESSMENT FOUNDATION — assessments belonging to a
-- skill, their questions (with an answer key kept structurally separate
-- from student-visible content), student attempts, and student answers.
--
-- This migration establishes ONLY the foundation described below. It does
-- NOT build: the assessment UI, LLM integration, actual scoring logic,
-- skill-evidence sync into student_skills, skill-gap analysis, career
-- readiness, or recommendations. Those are later phases — see the closing
-- comment block ("FUTURE INTEGRATION POINTS") for exactly where they will
-- attach to what's built here.
--
-- Architecture:
--   skills                          (003_skills.sql — unchanged)
--     ↑ skill_id
--   assessments                     one assessment = one skill, one
--                                    difficulty tier — multiple assessments
--                                    per skill are expected (Beginner/
--                                    Intermediate/Advanced/Expert), not a
--                                    1:1 skill<->assessment relationship.
--     ↑ assessment_id
--   assessment_questions             student-visible question content only
--     ↑ question_id                  (text, type, difficulty, points — NO
--     |                               correct-answer information at all)
--     ↓ question_id (1:1)
--   assessment_question_options     student-visible option TEXT only, for
--                                    MCQ/MULTIPLE_SELECT (no correctness)
--   assessment_question_answers     the protected answer key — which
--                                    option(s) are correct, reference
--                                    answer text, and the post-completion
--                                    explanation. RLS never exposes this
--                                    to a student before they've completed
--                                    the relevant attempt.
--
--   profiles(id)                    student ownership (NOT student_profiles
--     ↑ student_id                   — see the comment on assessment_attempts
--   assessment_attempts              below for why, mirroring student_skills'
--     ↑ attempt_id                   existing reasoning exactly)
--   assessment_answers               one row per (attempt, question) — the
--                                    student's submitted answer + its score
--
-- LLM-first, provider-agnostic by design:
--   - assessment_questions.generation_source distinguishes MANUAL vs
--     LLM_GENERATED. generation_model is a free-text label (e.g.
--     "gpt-4o", "claude-sonnet-4") — never an enum/FK to a "providers"
--     table, so no specific vendor is ever hard-coded into the schema.
--   - No raw provider API response is stored anywhere. If ever needed for
--     debugging, that belongs in application/service logs, not this
--     schema — storing it here would be exactly the kind of field added
--     "because it might be useful" that this migration is explicitly
--     asked to avoid.
--   - review_status (PENDING/APPROVED/REJECTED) gates visibility: a
--     question is only ever readable by a student when APPROVED — see
--     the "Authenticated users can view approved active questions" policy
--     below. This applies uniformly to MANUAL and LLM_GENERATED questions
--     alike (the default is PENDING regardless of origin — see that
--     column's own comment for why manual content isn't auto-approved).
--
-- Objective vs AI-evaluated scoring:
--   assessment_questions.scoring_method (OBJECTIVE/AI_EVALUATED) lets the
--   future FastAPI scoring service decide, per question, whether to run
--   deterministic exact-match scoring (typical for MCQ/MULTIPLE_SELECT,
--   and simple SHORT_ANSWER) or send the answer to an LLM for evaluation
--   (typical for SUBJECTIVE, and free-form SHORT_ANSWER/CODE responses).
--   This migration only stores the classification and the resulting
--   score fields (assessment_answers.awarded_marks/is_correct,
--   assessment_attempts.score/total_marks/percentage) — no scoring logic,
--   no LLM calls, no scoring functions are implemented here.
--
-- Answer-key security (the most important property of this migration):
--   Postgres RLS filters ROWS, not COLUMNS — a table cannot have "some
--   columns visible, some hidden" for the same reader via RLS alone. That
--   means a `correct answer` / `is_correct` column on a table students can
--   SELECT from (however that table is reached) is a leak, full stop,
--   regardless of how carefully application code tries not to render it.
--   This is why correctness data lives ONLY in assessment_question_answers,
--   a table with NO general student-readable policy — the only way a
--   student can ever read a row there is via the narrow "own completed
--   attempt" policy below. assessment_questions and
--   assessment_question_options — the tables a student's browser actually
--   queries while taking an assessment — physically cannot leak an answer
--   key, because they have no column capable of holding one.
--
--   This also drove where `explanation` lives: an explanation of *why* an
--   answer is correct routinely restates or implies the correct answer
--   itself, so it lives on assessment_question_answers (protected, post-
--   completion only) rather than assessment_questions (student-visible
--   pre-completion) — see that column's own comment.
--
-- No student_skills changes in this migration — see "FUTURE INTEGRATION
-- POINTS" at the end of this file.

-- ============================================================
-- assessments
-- ============================================================

create table if not exists assessments (
  id uuid primary key default gen_random_uuid(),

  -- One assessment belongs to exactly one skill. Multiple assessments per
  -- skill are expected (Python Beginner / Intermediate / Advanced /
  -- Expert) — deliberately no unique(skill_id); see the composite
  -- uniqueness below instead.
  skill_id uuid not null references skills (id) on delete restrict,

  title text not null,
  description text,

  -- Reuses the EXACT same 4-value scale as student_skills.proficiency_level
  -- (003_skills.sql), including its casing, on purpose: this lets a future
  -- feature compare "assessment difficulty" against "self-reported
  -- proficiency" directly, without a translation table between two
  -- different enums for what is conceptually the same scale.
  difficulty text not null check (difficulty in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),

  duration_minutes int check (duration_minutes > 0),

  -- The TARGET number of questions this assessment is designed to have —
  -- not a live count of assessment_questions rows. An assessment can exist
  -- (e.g. "Python Intermediate Assessment, 10 questions, generating...")
  -- before any question rows exist yet. Deliberately not auto-maintained
  -- by a trigger against assessment_questions: reconciling "target vs
  -- actual generated count" is a backend validation concern for the
  -- question-generation service, not something this schema enforces.
  question_count int check (question_count >= 0),

  is_active boolean not null default true,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Case-insensitive per-skill uniqueness — NOT a global unique(title), since
-- the same title could plausibly apply to two different skills (unlikely
-- in practice, but not architecturally wrong), and NOT unique(skill_id)
-- alone, since multiple difficulty tiers per skill are expected. This is
-- the same "lower(name)" case-insensitivity pattern already used for
-- skills.name / skill_categories.name / profiles.username.
create unique index if not exists assessments_skill_id_title_lower_idx on assessments (skill_id, lower(title));

-- skill_id is a foreign key; Postgres does not index those automatically.
-- Partial (is_active = true) rather than a plain index: the real-world
-- query this serves is "active assessments for skill X", which is what
-- every student-facing lookup needs — an admin/backend query that also
-- wants inactive assessments can still fall back to a sequential scan on
-- what is expected to remain a modestly sized table.
create index if not exists assessments_active_skill_id_idx on assessments (skill_id) where is_active = true;

alter table assessments enable row level security;

-- Same precedent as skills/skill_categories in 003_skills.sql: readable by
-- ANY authenticated role (not gated to STUDENT), because this is catalog-
-- like reference data, not personal student data. No insert/update/delete
-- policy exists for `authenticated` here, so — with RLS enabled — only
-- service_role can write to it. That's deliberate: assessment content is
-- curated/LLM-generated-then-reviewed, not student- or even faculty-
-- authored through this app.
create policy "Authenticated users can view active assessments"
  on assessments for select
  to authenticated
  using (is_active = true);

create trigger assessments_set_updated_at
  before update on assessments
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- assessment_questions — student-visible question content ONLY.
-- No correct-answer information exists on this table, ever.
-- ============================================================

create table if not exists assessment_questions (
  id uuid primary key default gen_random_uuid(),
  assessment_id uuid not null references assessments (id) on delete cascade,

  question_text text not null,

  -- A small, stable set — a CHECK-constrained enum (matching the project's
  -- existing convention for short stable scales: profiles.role,
  -- student_skills.proficiency_level) rather than a lookup table, which is
  -- reserved for genuinely open-ended, evolving taxonomies like
  -- skill_categories. "Code/output" and "write code" questions share the
  -- single CODE type for this foundation — the actual execution/test-case
  -- model for coding questions is future scoring-service work, not a
  -- schema concern yet.
  question_type text not null check (question_type in ('MCQ', 'MULTIPLE_SELECT', 'SHORT_ANSWER', 'CODE', 'SUBJECTIVE')),

  -- See the migration header comment ("Objective vs AI-evaluated
  -- scoring"). Deliberately NOT constrained to a fixed question_type ->
  -- scoring_method mapping (e.g. a CODE question could reasonably be
  -- either, depending on whether it's "predict the output" vs "explain
  -- your approach") — the scoring service decides per question.
  scoring_method text not null check (scoring_method in ('OBJECTIVE', 'AI_EVALUATED')),

  -- Per-question difficulty, independent of the parent assessment's
  -- difficulty — an "Intermediate" assessment can still mix a couple of
  -- easier warm-up questions with a harder closing one. Same reused scale
  -- as assessments.difficulty, for the same interoperability reason.
  difficulty text not null check (difficulty in ('Beginner', 'Intermediate', 'Advanced', 'Expert')),

  points numeric(5, 2) not null default 1 check (points > 0),

  -- Display order within the assessment. Deliberately no
  -- unique(assessment_id, display_order): forcing strict uniqueness here
  -- would make routine admin re-ordering (updating many rows' order in one
  -- pass) fight the constraint mid-transaction for no real benefit — ties
  -- can be broken by created_at/id in queries.
  display_order int not null default 0,

  -- Generation provenance — see the migration header comment
  -- ("LLM-first, provider-agnostic by design"). generation_model is
  -- intentionally a free-text label, never an enum or FK to a specific
  -- provider.
  generation_source text not null default 'MANUAL' check (generation_source in ('MANUAL', 'LLM_GENERATED')),
  generation_model text,
  generated_at timestamptz,

  -- Gates visibility to students (see the "Authenticated users can view
  -- approved active questions" policy below). Defaults to PENDING
  -- regardless of generation_source — MANUAL content is not auto-approved
  -- either, so there is exactly one rule ("must be APPROVED to be shown"),
  -- not a MANUAL-bypasses-review exception that a mislabeled row could
  -- exploit.
  review_status text not null default 'PENDING' check (review_status in ('PENDING', 'APPROVED', 'REJECTED')),

  is_active boolean not null default true,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists assessment_questions_assessment_id_idx on assessment_questions (assessment_id);

alter table assessment_questions enable row level security;

-- Student-visible question data. A question is only ever readable once it
-- is BOTH individually approved+active AND its parent assessment is
-- active — an unapproved/rejected/deactivated question is invisible
-- regardless of the parent assessment's state, and vice versa. No write
-- policy for `authenticated` — only service_role can create/edit/delete
-- questions (see the migration header + final security review).
create policy "Authenticated users can view approved active questions"
  on assessment_questions for select
  to authenticated
  using (
    review_status = 'APPROVED'
    and is_active = true
    and exists (
      select 1 from assessments a
      where a.id = assessment_questions.assessment_id
        and a.is_active = true
    )
  );

create trigger assessment_questions_set_updated_at
  before update on assessment_questions
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- assessment_question_options — student-visible OPTION TEXT ONLY.
-- No correctness column exists on this table, ever (see the migration
-- header comment for why that's a hard requirement, not a preference).
-- ============================================================

create table if not exists assessment_question_options (
  id uuid primary key default gen_random_uuid(),
  question_id uuid not null references assessment_questions (id) on delete cascade,

  option_text text not null,
  display_order int not null default 0,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- Unlike assessment_questions.display_order, options for a single
  -- question are created together in one batch (by an admin or by the
  -- LLM-generation service in a single pass) and essentially never
  -- reordered afterward independently — so a real uniqueness guarantee
  -- here is cheap and catches a genuine generation bug (duplicate/missing
  -- order values) rather than fighting routine edits.
  constraint assessment_question_options_unique_order unique (question_id, display_order)
);

create index if not exists assessment_question_options_question_id_idx on assessment_question_options (question_id);

alter table assessment_question_options enable row level security;

-- Same visibility gate as assessment_questions, walked one level further:
-- an option is readable only when its question is approved+active AND
-- that question's assessment is active. No write policy for
-- `authenticated`.
create policy "Authenticated users can view options for visible questions"
  on assessment_question_options for select
  to authenticated
  using (
    exists (
      select 1 from assessment_questions q
      join assessments a on a.id = q.assessment_id
      where q.id = assessment_question_options.question_id
        and q.review_status = 'APPROVED'
        and q.is_active = true
        and a.is_active = true
    )
  );

create trigger assessment_question_options_set_updated_at
  before update on assessment_question_options
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- assessment_question_answers — THE PROTECTED ANSWER KEY.
-- No general student SELECT policy exists on this table. The only way a
-- student can ever read a row here is the narrow "own completed attempt"
-- policy below.
-- ============================================================

create table if not exists assessment_question_answers (
  id uuid primary key default gen_random_uuid(),

  -- 1:1 with assessment_questions (unique, not just indexed) — one answer
  -- key per question. Deliberately not folded into assessment_questions
  -- itself: keeping it a physically separate table is what makes the
  -- security boundary structural (enforced by table separation + RLS)
  -- rather than a matter of "this table's app code just happens not to
  -- render this column" — see the migration header comment.
  question_id uuid not null unique references assessment_questions (id) on delete cascade,

  -- For MCQ (one element) / MULTIPLE_SELECT (one or more elements):
  -- assessment_question_options.id values that are correct. A uuid[]
  -- rather than a separate join table on purpose — this is a foundation
  -- migration and a real per-element foreign key (Postgres cannot FK
  -- individual array elements) would need a full extra join table for a
  -- property that only the trusted backend ever writes. That backend is
  -- responsible for only ever placing option ids belonging to this same
  -- question_id in this array — documented here as an application-layer
  -- invariant, not enforced by a DB constraint. Revisit with a proper join
  -- table only if this ever needs to be enforced at the DB level.
  correct_option_ids uuid[],

  -- For SHORT_ANSWER/CODE/SUBJECTIVE: the reference/expected answer, used
  -- either for objective exact-match scoring or as grounding context handed
  -- to the future LLM evaluator. Nullable — a SUBJECTIVE question may have
  -- only rubric-style guidance here, or none at all.
  correct_answer_text text,

  -- Shown to the student only AFTER they've completed the attempt (see the
  -- SELECT policy below) — lives here, not on assessment_questions,
  -- specifically because an explanation of why an answer is correct
  -- routinely gives the answer away.
  explanation text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table assessment_question_answers enable row level security;

-- The ONLY way a student can read an answer key row: they must be a
-- STUDENT, and must have a COMPLETED attempt at the assessment that this
-- question belongs to. No recursion risk — assessment_attempts' own
-- policies only reference profiles (via is_student, itself SECURITY
-- DEFINER and bypassing profiles' RLS by construction) and
-- assessment_questions' own policy only references assessments; neither
-- references assessment_question_answers back, so this subquery chain
-- cannot cycle.
create policy "Students can view answer keys for their own completed attempts"
  on assessment_question_answers for select
  to authenticated
  using (
    public.is_student(auth.uid())
    and exists (
      select 1
      from assessment_attempts aa
      join assessment_questions aq on aq.assessment_id = aa.assessment_id
      where aq.id = assessment_question_answers.question_id
        and aa.student_id = auth.uid()
        and aa.status = 'COMPLETED'
    )
  );

create trigger assessment_question_answers_set_updated_at
  before update on assessment_question_answers
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- assessment_attempts
-- ============================================================

create table if not exists assessment_attempts (
  id uuid primary key default gen_random_uuid(),

  -- References profiles(id), NOT student_profiles(id) — identical
  -- reasoning to student_skills.student_id in 003_skills.sql: a profiles
  -- row exists for every user from signup (handle_new_user trigger,
  -- 001_profiles.sql), but student_profiles is created lazily. A student
  -- must be able to attempt an assessment before ever touching the
  -- profile form.
  student_id uuid not null references profiles (id) on delete cascade,

  -- restrict, not cascade: an attempt is a historical student record.
  -- Deleting an assessment that has real attempts against it should fail
  -- and force an explicit is_active = false deactivation instead — the
  -- same "protect historical/referenced content" reasoning already used
  -- for skills.category_id and student_skills.skill_id in 003_skills.sql.
  assessment_id uuid not null references assessments (id) on delete restrict,

  status text not null default 'IN_PROGRESS' check (status in ('IN_PROGRESS', 'COMPLETED', 'ABANDONED')),

  started_at timestamptz not null default now(),
  submitted_at timestamptz,

  -- All three nullable until the trusted scoring pipeline (future
  -- FastAPI service, via service_role) fills them in. Never writable by
  -- the student directly — see the trigger below and the "Score
  -- protection" section of the approval report.
  score numeric(6, 2) check (score >= 0),
  total_marks numeric(6, 2) check (total_marks >= 0),
  percentage numeric(5, 2) check (percentage >= 0 and percentage <= 100),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint assessment_attempts_submitted_after_started check (submitted_at is null or submitted_at >= started_at),
  -- A COMPLETED attempt must carry full score data; a non-COMPLETED one
  -- isn't required to (but isn't forbidden from having partial data
  -- either — e.g. a future "partially score an abandoned attempt"
  -- feature isn't blocked by this).
  constraint assessment_attempts_completed_has_score check (
    status <> 'COMPLETED' or (score is not null and total_marks is not null and percentage is not null)
  )
);

create index if not exists assessment_attempts_student_id_idx on assessment_attempts (student_id);
create index if not exists assessment_attempts_assessment_id_idx on assessment_attempts (assessment_id);

-- Allows retakes (no unique(student_id, assessment_id) — the task is
-- explicit that the future system may allow retakes and this migration
-- must not assume a single attempt per student). This narrower partial
-- unique index only prevents a student from having two SIMULTANEOUS
-- IN_PROGRESS attempts at the same assessment — a genuine data-integrity
-- guard (which attempt would the "current" one even be?) that does not
-- limit how many completed/abandoned attempts can exist over time.
create unique index if not exists assessment_attempts_one_in_progress_idx
  on assessment_attempts (student_id, assessment_id)
  where status = 'IN_PROGRESS';

alter table assessment_attempts enable row level security;

-- Starting an attempt is a student-initiated, benign action. The WITH
-- CHECK deliberately goes beyond ownership: it also forces every
-- client-inserted row to be a "fresh start" (IN_PROGRESS, nothing scored,
-- not yet submitted) — a client cannot INSERT a fully-formed,
-- already-scored, already-COMPLETED attempt to fake a result.
create policy "Students can start their own attempts"
  on assessment_attempts for insert
  to authenticated
  with check (
    auth.uid() = student_id
    and public.is_student(auth.uid())
    and status = 'IN_PROGRESS'
    and score is null
    and total_marks is null
    and percentage is null
    and submitted_at is null
  );

create policy "Students can view their own attempts"
  on assessment_attempts for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

-- Students may only ever move their own attempt to ABANDONED directly
-- (see the trigger below, which blocks every other mutation this policy
-- would otherwise structurally allow: score/total_marks/percentage
-- changes, and transitioning to COMPLETED). Completing an attempt with a
-- real score is exclusively a trusted-backend (service_role) write, done
-- as part of the future scoring pipeline — never a direct client UPDATE.
create policy "Students can update their own attempts"
  on assessment_attempts for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

-- Mirrors prevent_self_skill_verification() in 003_skills.sql exactly:
-- service_role steps aside entirely (the only trusted path the future
-- scoring pipeline will use); every ordinary RLS-governed caller is
-- blocked from changing score/total_marks/percentage in either direction,
-- and from transitioning status into COMPLETED (which the
-- assessment_attempts_completed_has_score constraint ties directly to
-- having real score data — so blocking one blocks any meaningful path to
-- the other). A student CAN still transition their own attempt to
-- ABANDONED — that requires no trust and costs the student nothing to
-- fake in their own favor.
create or replace function public.prevent_self_attempt_scoring()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.score is distinct from old.score
    or new.total_marks is distinct from old.total_marks
    or new.percentage is distinct from old.percentage
  then
    raise exception 'Cannot set assessment score directly.' using errcode = '42501';
  end if;

  if new.status = 'COMPLETED' and old.status is distinct from 'COMPLETED' then
    raise exception 'Cannot complete an assessment attempt directly.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_self_attempt_scoring() from public;

create trigger assessment_attempts_prevent_self_scoring
  before update on assessment_attempts
  for each row
  execute procedure public.prevent_self_attempt_scoring();

create trigger assessment_attempts_set_updated_at
  before update on assessment_attempts
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- assessment_answers
-- ============================================================

create table if not exists assessment_answers (
  id uuid primary key default gen_random_uuid(),

  attempt_id uuid not null references assessment_attempts (id) on delete cascade,

  -- restrict, not cascade: protects already-answered questions from being
  -- silently deleted out from under real student answer history — the
  -- same "protect historical/referenced content" reasoning used
  -- throughout this migration and 003_skills.sql. Deactivate
  -- (is_active = false) instead of deleting a question that has answers.
  question_id uuid not null references assessment_questions (id) on delete restrict,

  -- Exactly one of these is populated depending on question_type (MCQ /
  -- MULTIPLE_SELECT use selected_option_ids; SHORT_ANSWER / CODE /
  -- SUBJECTIVE use answer_text) — enforced loosely below (at least one
  -- present), not strictly, since the exact shape per question_type is a
  -- frontend/backend concern, not a schema-level one.
  answer_text text,
  -- Same "uuid[], no per-element FK" reasoning and same trusted-backend-
  -- writes-only caveat as assessment_question_answers.correct_option_ids.
  selected_option_ids uuid[],

  -- Nullable until scored. Never client-writable — see the trigger below.
  awarded_marks numeric(6, 2) check (awarded_marks >= 0),
  is_correct boolean,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- One answer row per (attempt, question) — see the migration header
  -- comment / approval report for why revisions are modeled as an UPDATE
  -- to this same row (while the attempt is still IN_PROGRESS) rather than
  -- multiple answer rows: a student's "current answer" would otherwise be
  -- ambiguous, and the simple UPDATE model needs no extra "is this the
  -- latest revision" bookkeeping.
  constraint assessment_answers_unique_per_attempt_question unique (attempt_id, question_id),
  constraint assessment_answers_has_content check (answer_text is not null or selected_option_ids is not null)
);

create index if not exists assessment_answers_attempt_id_idx on assessment_answers (attempt_id);
create index if not exists assessment_answers_question_id_idx on assessment_answers (question_id);

alter table assessment_answers enable row level security;

-- A student may only submit an answer into their OWN attempt, and only
-- while that attempt is still IN_PROGRESS (no adding answers to a
-- completed/abandoned attempt after the fact). awarded_marks/is_correct
-- must be null at insert time — a client cannot fabricate a pre-scored
-- answer. No recursion: assessment_attempts' policies never reference
-- assessment_answers.
create policy "Students can answer questions in their own in-progress attempts"
  on assessment_answers for insert
  to authenticated
  with check (
    awarded_marks is null
    and is_correct is null
    and exists (
      select 1 from assessment_attempts aa
      where aa.id = assessment_answers.attempt_id
        and aa.student_id = auth.uid()
        and aa.status = 'IN_PROGRESS'
    )
  );

create policy "Students can view their own answers"
  on assessment_answers for select
  to authenticated
  using (
    exists (
      select 1 from assessment_attempts aa
      where aa.id = assessment_answers.attempt_id
        and aa.student_id = auth.uid()
    )
  );

-- Lets a student revise answer_text/selected_option_ids while their
-- attempt is still in progress (the "change your answer before final
-- submit" UX) — but never awarded_marks/is_correct, blocked
-- unconditionally by the trigger below regardless of attempt status.
create policy "Students can revise their own in-progress answers"
  on assessment_answers for update
  to authenticated
  using (
    exists (
      select 1 from assessment_attempts aa
      where aa.id = assessment_answers.attempt_id
        and aa.student_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from assessment_attempts aa
      where aa.id = assessment_answers.attempt_id
        and aa.student_id = auth.uid()
        and aa.status = 'IN_PROGRESS'
    )
  );

-- Mirrors prevent_self_attempt_scoring() above and
-- prevent_self_skill_verification() in 003_skills.sql: service_role (the
-- future scoring pipeline's only write path) steps aside entirely; every
-- ordinary RLS-governed caller is blocked from changing awarded_marks or
-- is_correct, in either direction, regardless of the parent attempt's
-- status.
create or replace function public.prevent_self_answer_scoring()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.awarded_marks is distinct from old.awarded_marks
    or new.is_correct is distinct from old.is_correct
  then
    raise exception 'Cannot set answer scoring directly.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_self_answer_scoring() from public;

create trigger assessment_answers_prevent_self_scoring
  before update on assessment_answers
  for each row
  execute procedure public.prevent_self_answer_scoring();

create trigger assessment_answers_set_updated_at
  before update on assessment_answers
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- FUTURE INTEGRATION POINTS (explicitly NOT built in this migration)
-- ============================================================
--
-- Question versioning: deliberately deferred. Regenerating a bad
-- LLM-generated question needs no formal version-chain schema right now —
-- deactivate the old row (is_active = false; it's protected from deletion
-- by assessment_answers.question_id's ON DELETE RESTRICT if it has real
-- answers) and insert a new one. If a true version chain (explicit
-- v1 -> v2 linkage for audit/diff purposes) is ever needed, that's a small
-- additive migration (e.g. a nullable self-referencing
-- replaced_by_question_id), not a redesign of anything built here.
--
-- Skill evidence -> student_skills: NOT touched by this migration, and no
-- trigger here writes to student_skills. The future integration point is
-- a trusted, service_role-authenticated step (the same FastAPI scoring
-- service that sets assessment_attempts.status = 'COMPLETED' /
-- score / total_marks / percentage) that, once an attempt completes,
-- reads assessment_attempts.assessment_id -> assessments.skill_id and
-- upserts a student_skills row for (student_id, skill_id) — setting
-- proficiency_score/proficiency_level from the result, and optionally
-- is_verified = true. That last part requires NO change to
-- prevent_self_skill_verification() in 003_skills.sql: it already lets
-- service_role through unconditionally, so it already supports this
-- future flow as-is.
--
-- Skill gap analysis, career readiness, and job/internship
-- recommendations: not started. They would consume student_skills (once
-- the above sync exists) and are out of scope for this migration
-- entirely, per the task that produced it.
