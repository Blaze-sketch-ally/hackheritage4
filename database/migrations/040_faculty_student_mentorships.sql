-- Migration: 040_faculty_student_mentorships
-- Purpose: Phase F4.2 -- the approved Faculty -> Student mentorship
-- relationship. This is the FIRST relationship in this project between a
-- FACULTY account and a STUDENT account; every prior audit (F1 through
-- F4.1) confirmed Faculty->Student visibility was exactly zero. This
-- migration introduces it, but strictly scoped: a Faculty mentor gains
-- read access to a specific student's data ONLY through an ACTIVE row in
-- the table below, and only for the narrow set of tables explicitly
-- listed in the approved audit (student_profiles, student_skills,
-- portfolio_projects, portfolio_certifications, assessment_attempts).
--
-- Explicitly untouched by this migration: industry_mentorship (031,
-- stays a Student-facing Industry posting table with no pairing
-- concept), industry_collaborations (032), faculty_engagements (038),
-- applications/opportunities (024), and assessment_answers/
-- assessment_question_answers (004) -- see the "mentor != evaluator"
-- section below for why the latter two are deliberately never granted a
-- Faculty-mentor policy.
--
-- ============================================================
-- DATA MODEL: ONE DEDICATED TABLE, REAL FKS, NO POLYMORPHISM
-- ============================================================
-- faculty_student_mentorships mirrors the shape of faculty_engagements
-- (038) -- a single relationship table with real, typed foreign keys to
-- profiles(id) for both participants. Rejected: a generic relationship
-- registry (no second use case exists anywhere in this schema, and one
-- would be the single largest accidental-cross-relationship-exposure
-- risk in this project -- see the F4.2 audit's Option comparison);
-- reusing industry_mentorship or industry_collaborations (neither has
-- any Faculty<->Student semantics -- see their own migrations).
--
-- UNIQUENESS: a plain UNIQUE(faculty_id, student_id) -- NOT a partial
-- index scoped to ACTIVE, unlike faculty_engagements'
-- unique(industry_eoi_id). This is a deliberate, approved simplification
-- for this initial implementation: once a mentorship relationship has
-- ever existed between a given Faculty/Student pair (REQUESTED,
-- DECLINED, WITHDRAWN, or any other status), no second row for that same
-- pair can ever be created -- there is no "request again after a
-- decline" path in this phase. A future phase may revisit this if the
-- product needs re-requesting; not built here because it was not asked
-- for.

create table public.faculty_student_mentorships (
  id uuid primary key default gen_random_uuid(),

  faculty_id uuid not null references public.profiles(id) on delete cascade,
  student_id uuid not null references public.profiles(id) on delete cascade,

  -- Which of the two participants created this row. Always equal to
  -- faculty_id or student_id (enforced by the guard trigger below), kept
  -- as its own column rather than inferred, so the trigger's
  -- self-approval/self-withdrawal checks never need to guess.
  requested_by uuid not null references public.profiles(id) on delete cascade,

  -- LIFECYCLE (exact meaning of each state is documented on the guard
  -- trigger below, not just in this comment, so it stays next to the
  -- code that enforces it):
  --   REQUESTED  a request exists; not yet consented to by the other side.
  --   ACCEPTED   both parties have consented; the relationship is
  --              confirmed, but has NOT yet started -- this state grants
  --              NO student-data visibility. It exists as an explicit
  --              "confirmed but not yet live" checkpoint between consent
  --              and access, mirroring how faculty_industry_opportunity_
  --              expressions' ACCEPTED status is a terminal EOI outcome
  --              that then requires a SEPARATE step (activation) before
  --              anything downstream unlocks.
  --   ACTIVE     the mentorship is currently in effect. This is the ONLY
  --              status that satisfies the downstream visibility
  --              policies added later in this migration.
  --   DECLINED   terminal. The non-requesting party rejected the request.
  --   WITHDRAWN  terminal. The requesting party withdrew their own
  --              request before the other side responded.
  --   COMPLETED  terminal. The mentorship ran its course.
  --   ENDED      terminal. The mentorship was ended before completion.
  status text not null default 'REQUESTED' check (
    status in ('REQUESTED', 'ACCEPTED', 'ACTIVE', 'DECLINED', 'WITHDRAWN', 'COMPLETED', 'ENDED')
  ),

  -- Shared, both-parties-visible context -- unlike mentor notes (see
  -- faculty_mentorship_notes further below), focus_area is naturally
  -- known to both sides of the relationship (it is typically set at
  -- request time and describes what the mentorship is about), so it
  -- lives directly on this shared row rather than in a private table.
  focus_area text,

  start_date date,
  end_date date,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint faculty_student_mentorships_dates_check check (
    start_date is null or end_date is null or end_date >= start_date
  ),

  -- requested_by must be one of the two real participants -- never a
  -- third party, never null-able to "unknown".
  constraint faculty_student_mentorships_requested_by_is_participant check (
    requested_by = faculty_id or requested_by = student_id
  ),

  -- THE duplicate-prevention guarantee, enforced by Postgres, not by an
  -- application-layer "check then insert" race-prone read. See the
  -- header comment above for why this is a full (not partial) unique
  -- constraint in this initial implementation.
  constraint faculty_student_mentorships_unique_pair unique (faculty_id, student_id)
);

create index faculty_student_mentorships_faculty_id_idx on public.faculty_student_mentorships (faculty_id);
create index faculty_student_mentorships_student_id_idx on public.faculty_student_mentorships (student_id);
create index faculty_student_mentorships_status_idx on public.faculty_student_mentorships (status);

alter table public.faculty_student_mentorships enable row level security;

-- ============================================================
-- RLS: role+identity check the row's OWN table; role+capability+
-- participant validation for who may create one; guard trigger (further
-- down) decides which status transitions are legal.
-- ============================================================

-- SELECT: either participant may view their own mentorship rows, at any
-- status (including terminal ones -- mentorship history, category M of
-- the approved visibility matrix, stays visible forever; only the
-- DOWNSTREAM student-data policies further down are status-gated).
create policy "Faculty can view their own mentorships"
  on public.faculty_student_mentorships for select
  to authenticated
  using (auth.uid() = faculty_id and public.is_faculty(auth.uid()));

create policy "Students can view their own mentorships"
  on public.faculty_student_mentorships for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

-- INSERT: a Faculty member may request a mentorship of a specific
-- student, but only while holding the faculty_mentor capability --
-- "faculty_mentor authorizes participation in mentorship workflows" is
-- enforced right here, at the one point where a Faculty account first
-- enters the workflow. The target must genuinely be a STUDENT account
-- (re-checked again, independently, by the guard trigger below as
-- defence in depth against a hypothetical future service-role insert
-- path). faculty_id/requested_by must equal the caller -- never
-- client-forgeable to someone else's id.
create policy "Faculty can request mentorship of a student"
  on public.faculty_student_mentorships for insert
  to authenticated
  with check (
    auth.uid() = faculty_id
    and auth.uid() = requested_by
    and status = 'REQUESTED'
    and public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
    and public.is_student(student_id)
  );

-- A Student may request a specific Faculty member as their mentor, but
-- only if that Faculty member already holds the faculty_mentor
-- capability -- a student cannot create a request that could never be
-- legitimately accepted, and this keeps the capability gate meaningful
-- from both directions of initiation.
create policy "Students can request mentorship from a faculty member"
  on public.faculty_student_mentorships for insert
  to authenticated
  with check (
    auth.uid() = student_id
    and auth.uid() = requested_by
    and status = 'REQUESTED'
    and public.is_student(auth.uid())
    and public.is_faculty(faculty_id)
    and public.has_mentor_capability(faculty_id)
  );

-- UPDATE: both participants may attempt to update their own mentorship
-- row (the guard trigger below decides which specific transition is
-- legal and by whom). A Faculty participant additionally must STILL hold
-- the mentor capability to perform ANY lifecycle action -- if an admin
-- suspends/revokes a Faculty member's capability mid-relationship, that
-- Faculty member immediately loses the ability to accept/activate/
-- complete/end it (they may still be responded to by the student side,
-- e.g. a student can still decline/end on their own).
create policy "Faculty can update their own mentorships"
  on public.faculty_student_mentorships for update
  to authenticated
  using (auth.uid() = faculty_id and public.is_faculty(auth.uid()) and public.has_mentor_capability(auth.uid()))
  with check (auth.uid() = faculty_id and public.is_faculty(auth.uid()) and public.has_mentor_capability(auth.uid()));

create policy "Students can update their own mentorships"
  on public.faculty_student_mentorships for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

-- No DELETE policy for anyone -- a mentorship, once created, is a
-- permanent historical record (category M, "mentorship history," of the
-- approved visibility matrix), only ever transitioned to a terminal
-- status, never removed.

-- ============================================================
-- Guard trigger: RLS (above) decides WHO may attempt to touch a row;
-- this decides WHICH mutation is legal. Same division of labor as
-- guard_faculty_engagement_update() (038) and the EOI guard triggers
-- (037).
-- ============================================================
create or replace function public.guard_faculty_student_mentorship()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if tg_op = 'INSERT' then
    if not public.is_faculty(new.faculty_id) then
      raise exception 'faculty_id must reference a FACULTY account.' using errcode = '23514';
    end if;
    if not public.is_student(new.student_id) then
      raise exception 'student_id must reference a STUDENT account.' using errcode = '23514';
    end if;
    if new.status <> 'REQUESTED' then
      raise exception 'A new mentorship must start in REQUESTED status.' using errcode = '23514';
    end if;
    return new;
  end if;

  -- UPDATE: identity fields are permanently immutable.
  if new.faculty_id is distinct from old.faculty_id
    or new.student_id is distinct from old.student_id
    or new.requested_by is distinct from old.requested_by
  then
    raise exception 'Cannot change a mentorship''s participants or requester.' using errcode = '42501';
  end if;

  if new.status is distinct from old.status then
    if old.status = 'REQUESTED' and new.status = 'ACCEPTED' then
      if caller_id = old.requested_by then
        raise exception 'The requesting party cannot accept their own request.' using errcode = '42501';
      end if;
    elsif old.status = 'REQUESTED' and new.status = 'DECLINED' then
      if caller_id = old.requested_by then
        raise exception 'The requesting party cannot decline their own request.' using errcode = '42501';
      end if;
    elsif old.status = 'REQUESTED' and new.status = 'WITHDRAWN' then
      if caller_id is distinct from old.requested_by then
        raise exception 'Only the requesting party may withdraw a request.' using errcode = '42501';
      end if;
    elsif old.status = 'ACCEPTED' and new.status = 'ACTIVE' then
      null; -- either participant may activate a confirmed mentorship
    elsif old.status = 'ACTIVE' and new.status = 'COMPLETED' then
      null; -- either participant may mark it complete
    elsif old.status = 'ACTIVE' and new.status = 'ENDED' then
      null; -- either participant may end it early
    else
      raise exception 'Invalid mentorship status transition: % -> %', old.status, new.status
        using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.guard_faculty_student_mentorship() from public;

create trigger faculty_student_mentorships_guard
  before insert or update on public.faculty_student_mentorships
  for each row execute procedure public.guard_faculty_student_mentorship();

create trigger faculty_student_mentorships_set_updated_at
  before update on public.faculty_student_mentorships
  for each row execute procedure public.set_updated_at();

-- ============================================================
-- DOWNSTREAM STUDENT VISIBILITY -- purely additive SELECT policies,
-- following the exact proven pattern already in this schema:
-- "Industry can view projects of their own applicants"
-- (025_portfolio_projects_and_certifications.sql), which grants a
-- specific, relationship-scoped read via a plain EXISTS join -- no
-- broad is_faculty() policy, no new helper beyond the ones already
-- introduced above. Every policy below requires ALL of:
--   1. caller is FACULTY
--   2. caller currently holds the faculty_mentor capability (so a
--      suspended/revoked capability immediately cuts off visibility,
--      even into an otherwise-still-ACTIVE mentorship)
--   3. an ACTIVE faculty_student_mentorships row exists with
--      faculty_id = caller and student_id = the row being read
--
-- NOT added anywhere below, deliberately: assessment_answers,
-- assessment_question_answers, assessment_questions,
-- assessment_question_options, applications, opportunities, or any
-- industry_* table. A mentor sees results/scores (assessment_attempts
-- carries score/percentage directly, with no per-answer detail on that
-- table), never individual answers or the answer key -- "mentor !=
-- evaluator" is enforced structurally, by table separation, not by a
-- runtime branch that could be gotten wrong.
-- ============================================================

-- Identity (category A of the approved visibility matrix). Exact same
-- precedent and shape as "Industry can view profiles of their own
-- applicants" (024_opportunities_and_applications.sql) -- the first time
-- this project let one role read another named individual's profiles
-- row through a real relationship. Deliberately ACTIVE-gated like every
-- other mentor-visibility policy below: per the approved scope, "An
-- ACTIVE mentorship relationship is the gate for mentor visibility" --
-- even basic identity is withheld from the Faculty side until then, so a
-- Faculty member reviewing a still-REQUESTED/ACCEPTED mentorship sees
-- only a bare id until they activate it. This is a deliberate, strict
-- reading of the approved requirement, not an oversight -- see the F4.2
-- report's Risks section for the resulting UX trade-off.
create policy "Faculty mentors can view profiles of their active mentees"
  on public.profiles for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
    and exists (
      select 1 from public.faculty_student_mentorships m
      where m.student_id = profiles.id
        and m.faculty_id = auth.uid()
        and m.status = 'ACTIVE'
    )
  );

-- The reverse direction is NOT security-sensitive the same way: a
-- Faculty member's basic profile (name/email/department-adjacent
-- identity) is not private student data, and a Student who is already a
-- legitimate party to a mentorship (at ANY status, including a still-
-- pending request they sent) has an obvious legitimate need to see who
-- they requested or were requested by. No capability check either --
-- this is about the Student's own read, not about gating Faculty's
-- access to anything.
create policy "Students can view profiles of their mentorship faculty"
  on public.profiles for select
  to authenticated
  using (
    public.is_student(auth.uid())
    and exists (
      select 1 from public.faculty_student_mentorships m
      where m.faculty_id = profiles.id
        and m.student_id = auth.uid()
    )
  );

create policy "Faculty mentors can view their active mentees' academic profile"
  on public.student_profiles for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
    and exists (
      select 1 from public.faculty_student_mentorships m
      where m.student_id = student_profiles.id
        and m.faculty_id = auth.uid()
        and m.status = 'ACTIVE'
    )
  );

create policy "Faculty mentors can view their active mentees' skills"
  on public.student_skills for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
    and exists (
      select 1 from public.faculty_student_mentorships m
      where m.student_id = student_skills.student_id
        and m.faculty_id = auth.uid()
        and m.status = 'ACTIVE'
    )
  );

create policy "Faculty mentors can view their active mentees' projects"
  on public.portfolio_projects for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
    and exists (
      select 1 from public.faculty_student_mentorships m
      where m.student_id = portfolio_projects.student_id
        and m.faculty_id = auth.uid()
        and m.status = 'ACTIVE'
    )
  );

create policy "Faculty mentors can view their active mentees' certifications"
  on public.portfolio_certifications for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
    and exists (
      select 1 from public.faculty_student_mentorships m
      where m.student_id = portfolio_certifications.student_id
        and m.faculty_id = auth.uid()
        and m.status = 'ACTIVE'
    )
  );

-- assessment_attempts carries status/score/total_marks/percentage
-- directly -- exactly the "RESULTS/SCORES" the approved visibility
-- matrix grants, and nothing more (no answer text lives on this table).
create policy "Faculty mentors can view their active mentees' assessment attempts"
  on public.assessment_attempts for select
  to authenticated
  using (
    public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
    and exists (
      select 1 from public.faculty_student_mentorships m
      where m.student_id = assessment_attempts.student_id
        and m.faculty_id = auth.uid()
        and m.status = 'ACTIVE'
    )
  );

-- ============================================================
-- PRIVATE MENTOR NOTES -- a separate, dedicated table, NOT a column on
-- faculty_student_mentorships and NOT a generic notes system.
-- ============================================================
-- This has to be its own table, not a `notes` column on the shared
-- mentorship row: Postgres RLS is ROW-level, not column-level (the same
-- limitation 022_career_roles_skill_gap.sql's own header documents for
-- why skill-gap evidence isn't materialized into a table Faculty could
-- accidentally over-select from). A `notes` column on
-- faculty_student_mentorships would be visible to BOTH participants
-- (the Student SELECT policy above returns the whole row) -- but the
-- approved scope is explicit: "do not expose private mentor notes by
-- default." A separate table is the only way to give the note a
-- genuinely different, narrower read policy than the mentorship row it
-- describes.
--
-- This is NOT the rejected "generic notes system" -- it has exactly one
-- purpose (a Faculty mentor's private note about one specific
-- mentorship), one author column, and no polymorphic target; the same
-- reasoning that already rejected a generic relationship registry for
-- the relationship itself applies here to notes about it.
--
-- Deliberately single-row-per-mentorship (not an append-only log): the
-- approved scope calls for "minimal" notes support, and nothing in this
-- project's existing architecture establishes a note-versioning
-- precedent to extend. A future phase can add history if the product
-- actually needs it.
create table public.faculty_mentorship_notes (
  id uuid primary key default gen_random_uuid(),
  mentorship_id uuid not null unique references public.faculty_student_mentorships(id) on delete cascade,
  -- Denormalized from the mentorship row rather than joined at policy
  -- time purely for policy simplicity -- immutable after creation
  -- (enforced by the guard trigger below), always equal to
  -- faculty_student_mentorships.faculty_id for the same mentorship_id
  -- (enforced by the INSERT policy's EXISTS check below).
  faculty_id uuid not null references public.profiles(id) on delete cascade,
  note text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.faculty_mentorship_notes enable row level security;

-- Faculty-only, own-mentorship-only, capability-gated -- no Student
-- policy and no Admin policy at all. Per the approved scope: "Admin must
-- NOT automatically inherit mentor-only student visibility through this
-- feature... Do not grant Admin automatic access to... private
-- mentorship notes... unless an existing independent Admin authorization
-- already provides it" -- no such independent authorization exists, so
-- none is added here.
create policy "Faculty can view their own mentorship notes"
  on public.faculty_mentorship_notes for select
  to authenticated
  using (
    auth.uid() = faculty_id
    and public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
  );

create policy "Faculty can create their own mentorship notes"
  on public.faculty_mentorship_notes for insert
  to authenticated
  with check (
    auth.uid() = faculty_id
    and public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
    and exists (
      select 1 from public.faculty_student_mentorships m
      where m.id = mentorship_id and m.faculty_id = auth.uid()
    )
  );

create policy "Faculty can update their own mentorship notes"
  on public.faculty_mentorship_notes for update
  to authenticated
  using (
    auth.uid() = faculty_id
    and public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
  )
  with check (
    auth.uid() = faculty_id
    and public.is_faculty(auth.uid())
    and public.has_mentor_capability(auth.uid())
  );

-- No DELETE policy -- a note, once written, stays with the mentorship's
-- historical record for as long as the mentorship row itself exists.

create or replace function public.guard_faculty_mentorship_note_update()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;
  if new.mentorship_id is distinct from old.mentorship_id
    or new.faculty_id is distinct from old.faculty_id
  then
    raise exception 'Cannot change which mentorship or Faculty member a note belongs to.'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

revoke all on function public.guard_faculty_mentorship_note_update() from public;

create trigger faculty_mentorship_notes_guard
  before update on public.faculty_mentorship_notes
  for each row execute procedure public.guard_faculty_mentorship_note_update();

create trigger faculty_mentorship_notes_set_updated_at
  before update on public.faculty_mentorship_notes
  for each row execute procedure public.set_updated_at();

-- ============================================================
-- ADMIN OVERSIGHT -- read-only, narrow RPC (not a table policy),
-- mirroring 035's own "RPC surface, not a broad ADMIN policy" precedent.
-- Returns exactly the fields the approved scope names: mentorship id,
-- Faculty, Student, status, lifecycle dates, request/approval metadata
-- (requested_by), and basic audit info (created_at/updated_at) --
-- deliberately EXCLUDES focus_area and never touches
-- faculty_mentorship_notes at all. Admin gets oversight of the
-- RELATIONSHIP, never the mentor-only student visibility that
-- relationship would otherwise grant to Faculty: Admin has no
-- is_admin()-based policy on student_profiles/student_skills/
-- portfolio_projects/portfolio_certifications/assessment_attempts
-- anywhere in this project, and none is added here -- reading this RPC
-- does not and cannot unlock a single row of the downstream student
-- tables above.
-- ============================================================
create or replace function public.admin_list_faculty_student_mentorships()
returns table (
  id uuid,
  faculty_id uuid,
  student_id uuid,
  status text,
  requested_by uuid,
  start_date date,
  end_date date,
  created_at timestamptz,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
stable
as $$
begin
  if not public.is_admin(auth.uid()) then
    raise exception 'Only ADMIN accounts may list Faculty-Student mentorships.'
      using errcode = '42501';
  end if;

  return query
  select m.id, m.faculty_id, m.student_id, m.status, m.requested_by,
         m.start_date, m.end_date, m.created_at, m.updated_at
  from public.faculty_student_mentorships m
  order by m.created_at desc;
end;
$$;

revoke all on function public.admin_list_faculty_student_mentorships() from public;
revoke all on function public.admin_list_faculty_student_mentorships() from anon;
grant execute on function public.admin_list_faculty_student_mentorships() to authenticated;
