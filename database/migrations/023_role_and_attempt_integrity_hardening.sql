-- Migration: 023_role_and_attempt_integrity_hardening
-- Purpose: a full-project architecture/dependency/integration audit found
-- five real, verifiable database issues, none touching Phase 1K's frozen
-- scoring model or migration 014. All fixes here are additive
-- (CREATE OR REPLACE on existing trigger functions, or DROP+CREATE on a
-- policy) -- no historical migration file is edited, matching this
-- project's established governance (see the "Migration governance"
-- section of docs/architecture/assessment-lifecycle.md).

-- ============================================================
-- 1. PRIVILEGE ESCALATION FIX (the serious one)
--
-- 002_protect_admin_role.sql's prevent_self_admin_promotion() only ever
-- blocked a transition INTO 'ADMIN'. Every other role transition was left
-- completely unguarded by that trigger -- and 001_profiles.sql's own
-- UPDATE policy ("Users can update their own profile") only checks row
-- ownership, not which value `role` is being set to. Confirmed live-
-- exploitable: any authenticated user could PATCH their own profile's
-- role STUDENT -> FACULTY (gaining question-bank write access, peer-
-- review authority, and answer-key visibility per
-- 015_question_bank_random_assessment.sql / 018_faculty_view_all_
-- questions.sql), then flip back to STUDENT at will. This is the exact
-- same class of hole 002 already fixed for ADMIN specifically -- this
-- closes it for every role.
--
-- The intended, legitimate flow (role-selection.tsx / onboarding) only
-- ever sets `role` ONCE, from NULL -- see docs/PROJECT_CONTEXT.md's
-- description of the onboarding flow. That is the only self-service role
-- transition this project's product design has ever called for. This
-- migration codifies exactly that: a non-service_role caller may set
-- `role` only when it was previously NULL; once set, only service_role
-- (a future, deliberately-built admin-provisioning mechanism -- see
-- 002's own "Known, honestly-documented limitations") may change it
-- again, in either direction. The existing ADMIN-specific rule is kept
-- (redundant with the new general rule now, but left explicit for
-- clarity and defense in depth).
--
-- Renamed from prevent_self_admin_promotion to
-- prevent_unauthorized_role_change since its scope is no longer
-- ADMIN-specific -- the OLD function is dropped (CASCADE would drop the
-- trigger using it, so the trigger is explicitly re-pointed first).
-- ============================================================

create or replace function public.prevent_unauthorized_role_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.role = 'ADMIN' and old.role is distinct from 'ADMIN' then
    raise exception 'Cannot self-assign the ADMIN role.' using errcode = '42501';
  end if;

  -- Role may only be self-assigned ONCE, from NULL (the onboarding
  -- role-selection flow). A no-op (new.role = old.role, including two
  -- NULLs) is always allowed -- it isn't a transition at all.
  if old.role is not null and new.role is distinct from old.role then
    raise exception 'Cannot change your role once it has been set.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_unauthorized_role_change() from public;

drop trigger if exists prevent_self_admin_promotion_trigger on profiles;

create trigger prevent_unauthorized_role_change_trigger
  before update on profiles
  for each row
  execute procedure public.prevent_unauthorized_role_change();

-- The old function is no longer referenced by any trigger; dropped
-- rather than left as dead code with a misleading name.
drop function if exists public.prevent_self_admin_promotion();

-- ============================================================
-- 2. student_skills.is_verified INSERT bypass
--
-- 003_skills.sql's student_skills_prevent_self_verification trigger is
-- BEFORE UPDATE only -- it never fires on INSERT, and the INSERT policy
-- ("Students can add their own skills") never constrains is_verified
-- either. A student could therefore INSERT a new student_skills row with
-- is_verified: true set directly in the payload, bypassing verification
-- entirely -- contradicting that migration's own stated intent. Fixed by
-- narrowing the INSERT policy's WITH CHECK, not by touching the trigger
-- (which correctly continues to guard UPDATE).
-- ============================================================

drop policy if exists "Students can add their own skills" on student_skills;

create policy "Students can add their own skills"
  on student_skills for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()) and is_verified = false);

-- ============================================================
-- 3. profiles.updated_at was never maintained
--
-- Every other table with an updated_at column has a matching
-- *_set_updated_at trigger (see 003_skills.sql, 004_assessments.sql,
-- 012_student_profiles.sql onward) -- profiles was the one exception,
-- silently never updating updated_at on any UPDATE (username change,
-- avatar change, role assignment) since the row's initial INSERT.
-- ============================================================

drop trigger if exists profiles_set_updated_at on profiles;

create trigger profiles_set_updated_at
  before update on profiles
  for each row
  execute procedure public.set_updated_at();

-- ============================================================
-- 4. assessment_attempts: assessment_id / started_at / submitted_at
--    were not protected once an attempt is historical
--
-- prevent_self_attempt_scoring() (004_assessments.sql) already blocks
-- score/total_marks/percentage changes and transitioning INTO COMPLETED.
-- It did not block: (a) reassigning assessment_id at all -- never a
-- legitimate operation, an attempt belongs to exactly one assessment for
-- its whole life; (b) rewriting started_at/submitted_at once the attempt
-- is COMPLETED -- these become historical fact at that point, same
-- "never reconstruct history" principle this whole project is built on
-- (see docs/architecture/assessment-lifecycle.md). Legitimate writes are
-- unaffected: mark_attempt_submitted() (Phase 1G, assessment_service.py)
-- sets submitted_at exactly once while status is still IN_PROGRESS --
-- that write happens BEFORE the COMPLETED transition, so this new check
-- (gated on old.status = 'COMPLETED') never blocks it.
-- ============================================================

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

  if new.assessment_id is distinct from old.assessment_id then
    raise exception 'Cannot reassign an attempt to a different assessment.' using errcode = '42501';
  end if;

  if old.status = 'COMPLETED' and (
    new.started_at is distinct from old.started_at
    or new.submitted_at is distinct from old.submitted_at
  ) then
    raise exception 'Cannot modify a completed attempt''s historical timestamps.' using errcode = '42501';
  end if;

  return new;
end;
$$;

-- ============================================================
-- 5. assessment_answers: attempt_id / question_id were reassignable
--    on UPDATE
--
-- prevent_self_answer_scoring() (004_assessments.sql) already blocks
-- awarded_marks/is_correct changes. It did not block reassigning which
-- attempt or question an existing answer row belongs to -- never a
-- legitimate operation (a revision changes answer_text/
-- selected_option_ids on the SAME (attempt_id, question_id) pair, per
-- that migration's own "Students can revise their own in-progress
-- answers" policy).
-- ============================================================

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

  if new.attempt_id is distinct from old.attempt_id
    or new.question_id is distinct from old.question_id
  then
    raise exception 'Cannot reassign an answer to a different attempt or question.' using errcode = '42501';
  end if;

  return new;
end;
$$;

-- ============================================================
-- Explicitly NOT fixed here (documented, deliberate, matches existing
-- governance -- see docs/architecture/assessment-lifecycle.md's
-- "Migration governance" section):
--
-- 003_skills.sql and 004_assessments.sql both reference
-- public.set_updated_at() AND public.is_student(uuid) before either is
-- actually defined (in 012_student_profiles.sql) -- a fresh from-scratch
-- replay of 001->023 in strict order would fail at 003. This is
-- pre-existing technical debt (the set_updated_at() half was already
-- documented; the is_student() half is a second, independent instance of
-- the same class of gap, found by this audit). NOT fixed in this
-- migration: fixing it means reordering or renumbering historical files,
-- which this project's governance rule exists specifically to prevent
-- without a separate, deliberate decision to do so -- not a side effect
-- of a security-hardening pass. Does not affect the already-bootstrapped
-- live database this migration applies to.
-- ============================================================
