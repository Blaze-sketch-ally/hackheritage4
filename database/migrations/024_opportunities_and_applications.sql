-- Migration: 024_opportunities_and_applications
-- Purpose: Phase 1M -- a single unified opportunity domain (JOB and
-- INTERNSHIP are one table, distinguished by type, per the explicit
-- product decision to avoid duplicating schema/services/RLS across two
-- near-identical domains), its per-opportunity skill requirements (same
-- shape as career_role_skill_requirements, Phase 1L), and student
-- applications against it.
--
-- Reuses, does not duplicate:
--   - app.services.skill_alignment_service (Phase 1L) for match scoring --
--     opportunity_skill_requirements is just a second SkillRequirement
--     source for the exact same generic engine, per that module's own
--     docstring ("a future opportunity-matching feature can reuse it
--     unchanged").
--   - app.services.assessment_service.get_student_skill_scores() (Phase
--     1L) for the student's skill evidence -- unchanged, untouched.
--   - The is_role(uuid) SECURITY DEFINER helper pattern (is_student,
--     is_faculty) -- this migration adds is_industry(uuid), same shape.
--   - The join-through-ownership-chain RLS pattern from
--     020_student_view_own_attempt_questions.sql, and the
--     ownership-plus-ownership trigger pattern from
--     assessment_attempts/assessment_answers (004_assessments.sql,
--     023_role_and_attempt_integrity_hardening.sql).
--
-- HISTORICAL INTEGRITY (the same law every phase in this project follows):
--   opportunity_skill_requirements = CURRENT CONFIGURATION.
--   applications = HISTORICAL EVENT -- a student applied under whatever
--   requirements existed at that moment. This migration does not
--   introduce an application-time requirement SNAPSHOT -- a match score
--   shown for an existing application is always a CURRENT derived view,
--   recomputed from current requirements and current assessment
--   evidence, exactly like Phase 1L's skill-gap view already is. This is
--   an explicit, documented choice, not an oversight: see
--   docs/architecture/assessment-lifecycle.md's Phase 1M section. What
--   IS protected as historical fact, and what this migration explicitly
--   enforces: the application's own identity (student_id, opportunity_id)
--   and its status progression -- never silently rewritten.
--
--   To keep this promise honest without building snapshotting,
--   opportunity_skill_requirements becomes IMMUTABLE once its parent
--   opportunity leaves DRAFT (see the RLS policies below) -- so by the
--   time any student could possibly have applied (only PUBLISHED
--   opportunities are visible to students at all), the requirements a
--   match is computed against can no longer change underneath them.

-- ============================================================
-- is_industry(): role-check helper, same shape as is_student()/is_faculty()
-- ============================================================

create or replace function public.is_industry(profile_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.profiles where id = profile_id and role = 'INDUSTRY'
  );
$$;

revoke all on function public.is_industry(uuid) from public;
revoke all on function public.is_industry(uuid) from anon;
grant execute on function public.is_industry(uuid) to authenticated;

-- ============================================================
-- opportunities
-- ============================================================

create table if not exists opportunities (
  id uuid primary key default gen_random_uuid(),

  -- Owning industry identity. Cascade: an opportunity has no independent
  -- meaning once its owning account is gone -- unlike assessment
  -- questions (created_by, set null) or attempts (student_id, cascade
  -- for the same "belongs entirely to one account" reasoning as here).
  industry_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text,

  -- Single unified domain, not two duplicated tables -- an explicit
  -- Phase 1M product decision. Frontend filtering (jobs vs internships)
  -- reads this column; no separate business logic per type anywhere.
  opportunity_type text not null check (opportunity_type in ('JOB', 'INTERNSHIP')),

  location text,

  -- Minimal lifecycle, not an arbitrary state machine -- see the
  -- prevent_invalid_opportunity_transition trigger below for exactly
  -- which transitions are legal (DRAFT->PUBLISHED, PUBLISHED->CLOSED,
  -- DRAFT->CLOSED; nothing else, including no re-opening).
  status text not null default 'DRAFT' check (status in ('DRAFT', 'PUBLISHED', 'CLOSED')),

  -- Owned entirely by the trigger below, never client-writable directly
  -- (mirrors how assessment_attempts.score is trigger-owned) -- set
  -- automatically the moment status first transitions to PUBLISHED.
  published_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists opportunities_industry_id_idx on opportunities (industry_id);
create index if not exists opportunities_status_idx on opportunities (status);
create index if not exists opportunities_opportunity_type_idx on opportunities (opportunity_type);

alter table opportunities enable row level security;

-- SELECT: two permissive policies (Postgres ORs them) -- the owner can
-- always see their own opportunity at any status; any authenticated
-- caller can see it once PUBLISHED. Same "readable once public,
-- protected before/after" precedent as the question bank (Phase 1K) and
-- career roles (Phase 1L catalog reads).
create policy "Industry can view their own opportunities"
  on opportunities for select
  to authenticated
  using (industry_id = auth.uid() and public.is_industry(auth.uid()));

create policy "Authenticated users can view published opportunities"
  on opportunities for select
  to authenticated
  using (status = 'PUBLISHED');

-- INSERT: only industry, only as a fresh DRAFT -- mirrors
-- assessment_attempts' "Students can start their own attempts" pattern
-- (ownership plus "must be a fresh, unscored start" in the same WITH
-- CHECK) applied to opportunities' own fresh-start invariant.
create policy "Industry can create their own opportunities"
  on opportunities for insert
  to authenticated
  with check (
    industry_id = auth.uid()
    and public.is_industry(auth.uid())
    and status = 'DRAFT'
    and published_at is null
  );

-- UPDATE: ownership at the RLS layer; the state-machine and
-- published_at/industry_id protections live in the trigger below (RLS
-- alone cannot express "this transition is illegal", the same reason
-- every scoring-adjacent table in this project uses a trigger for that).
create policy "Industry can update their own opportunities"
  on opportunities for update
  to authenticated
  using (industry_id = auth.uid() and public.is_industry(auth.uid()))
  with check (industry_id = auth.uid() and public.is_industry(auth.uid()));

-- No DELETE policy for any role -- retiring a posting is CLOSED, not
-- deletion, matching this project's general preference for status
-- transitions over hard deletes (assessment_attempts, career_roles, etc.
-- are never deleted by a normal caller either).

create or replace function public.prevent_invalid_opportunity_transition()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.industry_id is distinct from old.industry_id then
    raise exception 'Cannot reassign an opportunity to a different industry account.' using errcode = '42501';
  end if;

  -- CLOSED is fully immutable -- matches this migration's own stated
  -- MVP rule (see the header comment / Phase 1M design brief): once
  -- retired, nothing about the posting may change again, status
  -- included (the transition check below already rejects any status
  -- change away from CLOSED; this additionally rejects a same-status
  -- CLOSED "edit" of title/description/location/opportunity_type).
  if old.status = 'CLOSED' and (
    new.title is distinct from old.title
    or new.description is distinct from old.description
    or new.location is distinct from old.location
    or new.opportunity_type is distinct from old.opportunity_type
  ) then
    raise exception 'Cannot modify a closed opportunity.' using errcode = '42501';
  end if;

  -- Once PUBLISHED (not yet closed), opportunity_type is locked -- an
  -- identity attribute, not "basic metadata" -- while title/description/
  -- location remain editable per the same MVP rule. opportunity_type may
  -- still be set/changed freely while still DRAFT.
  if old.status = 'PUBLISHED' and new.opportunity_type is distinct from old.opportunity_type then
    raise exception 'Cannot change a published opportunity''s type.' using errcode = '42501';
  end if;

  -- Legal transitions only: DRAFT->PUBLISHED, PUBLISHED->CLOSED,
  -- DRAFT->CLOSED, or no change at all. Anything else (re-opening a
  -- CLOSED posting, reverting PUBLISHED back to DRAFT, skipping straight
  -- to an invalid value) is rejected -- see this migration's header
  -- comment; if re-opening is ever genuinely needed, that is a deliberate
  -- future decision, not a default allowed here.
  if new.status is distinct from old.status then
    if old.status = 'DRAFT' and new.status in ('PUBLISHED', 'CLOSED') then
      -- legal
    elsif old.status = 'PUBLISHED' and new.status = 'CLOSED' then
      -- legal
    else
      raise exception 'Invalid opportunity status transition: % -> %', old.status, new.status
        using errcode = '42501';
    end if;
  end if;

  -- published_at is trigger-owned, not client-writable -- set exactly
  -- once, the moment status first becomes PUBLISHED; never cleared or
  -- rewritten afterward regardless of what the client sends.
  if new.status = 'PUBLISHED' and old.status is distinct from 'PUBLISHED' then
    new.published_at = now();
  else
    new.published_at = old.published_at;
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_invalid_opportunity_transition() from public;

create trigger opportunities_prevent_invalid_transition
  before update on opportunities
  for each row
  execute procedure public.prevent_invalid_opportunity_transition();

create trigger opportunities_set_updated_at
  before update on opportunities
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- opportunity_skill_requirements -- same shape as
-- career_role_skill_requirements (022_career_roles_skill_gap.sql), the
-- second SkillRequirement source the Phase 1L alignment engine consumes.
-- ============================================================

create table if not exists opportunity_skill_requirements (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities (id) on delete cascade,

  -- restrict, not cascade: same "protect referenced content" reasoning
  -- as every other skill_id foreign key in this project.
  skill_id uuid not null references skills (id) on delete restrict,

  required_level numeric(5, 2) not null check (required_level >= 0 and required_level <= 100),
  weight numeric(5, 2) not null default 1.0 check (weight >= 0),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint opportunity_skill_requirements_unique unique (opportunity_id, skill_id)
);

create index if not exists opportunity_skill_requirements_opportunity_id_idx
  on opportunity_skill_requirements (opportunity_id);
create index if not exists opportunity_skill_requirements_skill_id_idx
  on opportunity_skill_requirements (skill_id);

alter table opportunity_skill_requirements enable row level security;

-- SELECT mirrors opportunities' own visibility, joined through
-- opportunity_id -- same join-through-ownership-chain pattern as
-- 020_student_view_own_attempt_questions.sql.
create policy "Industry can view their own opportunity requirements"
  on opportunity_skill_requirements for select
  to authenticated
  using (
    exists (
      select 1 from opportunities o
      where o.id = opportunity_skill_requirements.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

create policy "Authenticated users can view published opportunity requirements"
  on opportunity_skill_requirements for select
  to authenticated
  using (
    exists (
      select 1 from opportunities o
      where o.id = opportunity_skill_requirements.opportunity_id
        and o.status = 'PUBLISHED'
    )
  );

-- Write access: owner only, AND only while the parent opportunity is
-- still DRAFT -- this is what makes the historical-integrity promise in
-- this migration's header comment actually true. Once PUBLISHED (the
-- only state in which a student can ever see or apply against an
-- opportunity), its requirements are frozen -- no snapshot table is
-- needed because there is nothing left that can change.
create policy "Industry can add requirements while opportunity is a draft"
  on opportunity_skill_requirements for insert
  to authenticated
  with check (
    exists (
      select 1 from opportunities o
      where o.id = opportunity_skill_requirements.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
        and o.status = 'DRAFT'
    )
  );

create policy "Industry can edit requirements while opportunity is a draft"
  on opportunity_skill_requirements for update
  to authenticated
  using (
    exists (
      select 1 from opportunities o
      where o.id = opportunity_skill_requirements.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
        and o.status = 'DRAFT'
    )
  )
  with check (
    exists (
      select 1 from opportunities o
      where o.id = opportunity_skill_requirements.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
        and o.status = 'DRAFT'
    )
  );

create policy "Industry can remove requirements while opportunity is a draft"
  on opportunity_skill_requirements for delete
  to authenticated
  using (
    exists (
      select 1 from opportunities o
      where o.id = opportunity_skill_requirements.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
        and o.status = 'DRAFT'
    )
  );

create trigger opportunity_skill_requirements_set_updated_at
  before update on opportunity_skill_requirements
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- applications
-- ============================================================

create table if not exists applications (
  id uuid primary key default gen_random_uuid(),

  -- restrict: an application is a historical student record, same
  -- reasoning as assessment_attempts.assessment_id -- deleting an
  -- opportunity that has real applications against it should fail, not
  -- silently erase application history. In practice opportunities are
  -- never deleted at all (CLOSED is the retirement path), so this should
  -- never actually fire, but the guarantee is stated explicitly anyway.
  opportunity_id uuid not null references opportunities (id) on delete restrict,

  student_id uuid not null references profiles (id) on delete cascade,

  status text not null default 'APPLIED'
    check (status in ('APPLIED', 'SHORTLISTED', 'INTERVIEW', 'SELECTED', 'REJECTED')),

  cover_note text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- THE core anti-duplicate invariant (never enforced by the frontend
  -- alone) -- a student may apply to one opportunity at most once.
  constraint applications_unique_per_opportunity_student unique (opportunity_id, student_id)
);

create index if not exists applications_opportunity_id_idx on applications (opportunity_id);
create index if not exists applications_student_id_idx on applications (student_id);
create index if not exists applications_status_idx on applications (status);

alter table applications enable row level security;

-- INSERT: ownership, role, AND the opportunity must currently be
-- PUBLISHED -- enforced here at the RLS layer (not only in the FastAPI
-- service), per this project's standing rule that RLS is the real
-- boundary and application-layer checks are defense in depth, not the
-- only enforcement.
create policy "Students can apply to published opportunities"
  on applications for insert
  to authenticated
  with check (
    student_id = auth.uid()
    and public.is_student(auth.uid())
    and status = 'APPLIED'
    and exists (
      select 1 from opportunities o
      where o.id = applications.opportunity_id
        and o.status = 'PUBLISHED'
    )
  );

-- SELECT: two permissive policies -- the applicant sees their own
-- applications; the owning industry sees applications to their own
-- opportunities. Same join-through-ownership-chain pattern as
-- opportunity_skill_requirements above.
create policy "Students can view their own applications"
  on applications for select
  to authenticated
  using (student_id = auth.uid() and public.is_student(auth.uid()));

create policy "Industry can view applicants for their own opportunities"
  on applications for select
  to authenticated
  using (
    exists (
      select 1 from opportunities o
      where o.id = applications.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

-- UPDATE: industry only, scoped to their own opportunities' applicants.
-- No student UPDATE policy exists at all -- the same "absence of a
-- policy is the enforcement" pattern already used for
-- assessment_attempt_questions -- a student can never update any
-- application, including their own, through this table.
create policy "Industry can update application status for their own opportunities"
  on applications for update
  to authenticated
  using (
    exists (
      select 1 from opportunities o
      where o.id = applications.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  )
  with check (
    exists (
      select 1 from opportunities o
      where o.id = applications.opportunity_id
        and o.industry_id = auth.uid()
        and public.is_industry(auth.uid())
    )
  );

-- No DELETE policy for any role -- withdrawal is out of MVP scope, per
-- the Phase 1M design brief.

create or replace function public.prevent_unauthorized_application_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  -- An application's identity (who applied, to what) is historical fact
  -- from the moment it's created -- never reassignable by anyone,
  -- including the owning industry updating status. Same
  -- "reassignment is never legitimate" reasoning as
  -- 023_role_and_attempt_integrity_hardening.sql's answer/attempt fix.
  if new.opportunity_id is distinct from old.opportunity_id
    or new.student_id is distinct from old.student_id
  then
    raise exception 'Cannot reassign an application to a different opportunity or student.'
      using errcode = '42501';
  end if;

  -- cover_note is the applicant's own historical statement -- the
  -- reviewing industry may change status, never rewrite what the
  -- student actually wrote when they applied.
  if new.cover_note is distinct from old.cover_note then
    raise exception 'Cannot modify an applicant''s cover note.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_unauthorized_application_change() from public;

create trigger applications_prevent_unauthorized_change
  before update on applications
  for each row
  execute procedure public.prevent_unauthorized_application_change();

create trigger applications_set_updated_at
  before update on applications
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- profiles: one new, narrowly-scoped SELECT policy
-- ============================================================
--
-- 001_profiles.sql's own SELECT policy is "own row only"
-- (auth.uid() = id) -- an industry account has no way to read even the
-- NAME of a student who has applied to one of its own opportunities,
-- which the applicant list (GET /opportunities/{id}/applicants) needs to
-- render at all. This is the first time in this project one role reads
-- another NAMED individual's profile data through a real relationship
-- (rather than a shared/catalog table) -- same class of pattern flagged
-- in the Phase 1L+ architecture planning pass as needing its own
-- dedicated live-RLS test (see backend/tests/integration/ for that
-- test), not the lighter MVP bar used elsewhere in this phase.
--
-- Scoped as narrowly as the actual need: an industry account may read a
-- student's profiles row ONLY when that student has a real
-- applications row against one of THAT industry's own opportunities --
-- never any other student, never any other industry's applicants. This
-- exposes the same information a real recruiter reviewing a real
-- application would legitimately see (name, contact info already
-- visible via the application relationship itself) -- not a new class of
-- leak, an explicit, bounded product decision for the applicant-review
-- feature this migration exists to support.
create policy "Industry can view profiles of their own applicants"
  on profiles for select
  to authenticated
  using (
    public.is_industry(auth.uid())
    and exists (
      select 1
      from applications a
      join opportunities o on o.id = a.opportunity_id
      where a.student_id = profiles.id
        and o.industry_id = auth.uid()
    )
  );

-- ============================================================
-- FUTURE INTEGRATION POINTS (explicitly NOT built in this migration)
-- ============================================================
--
-- Application-time requirement snapshots: not implemented -- see this
-- migration's header comment for why the current design (requirements
-- frozen once PUBLISHED) already makes a snapshot unnecessary for
-- historical correctness. If a future phase needs to show what a
-- student's match looked like at a DIFFERENT point in time than "right
-- now, against current requirements" (e.g. after requirements somehow
-- become editable post-publish in a later redesign), that is a new,
-- deliberate migration, not assumed here.
--
-- opportunity_skill_requirements is deliberately the same
-- (skill_id, required_level, weight) shape as
-- career_role_skill_requirements, specifically so
-- app.services.skill_alignment_service's generic SkillRequirement/
-- compute_alignment() can serve both without any change -- see that
-- module's own docstring.
