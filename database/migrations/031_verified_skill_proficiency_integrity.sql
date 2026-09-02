-- Migration: 031_verified_skill_proficiency_integrity
-- Purpose: close the verified-skill integrity gap found by the Phase 4
-- assessment audit (P1-B). Forward migration in this branch's own
-- numbering -- no historical migration file is edited.
--
-- ============================================================
-- Background
-- ============================================================
-- student_skills.is_verified / verified_at are written ONLY by the
-- trusted scoring path: public.score_assessment_attempt()
-- (015_assessment_verification.sql), which runs as service_role and, on a
-- passing attempt, sets is_verified = true / verified_at = now() on the
-- student_skills row whose (skill_id, proficiency_level) EXACTLY matches
-- the assessment's (skill_id, difficulty).
--
-- public.prevent_self_skill_verification() (defined in 003_skills.sql,
-- CREATE OR REPLACEd in 015_assessment_verification.sql to also cover
-- verified_at) already blocks every non-service_role caller from changing
-- is_verified / verified_at directly.
--
-- ============================================================
-- The gap
-- ============================================================
-- That trigger never inspected proficiency_level / proficiency_score. A
-- student revises their own self-reported proficiency through the
-- "Students can update their own skills" UPDATE policy (003_skills.sql)
-- via frontend/lib/student/skills.ts::updateStudentSkillProficiency, whose
-- payload contains ONLY proficiency_level. is_verified is therefore
-- unchanged in the payload, the trigger's is_verified check sees no
-- change, and the row is written with the NEW proficiency_level still
-- flagged is_verified = true.
--
-- Result: a skill verified at "Intermediate" can be self-edited to
-- "Expert" while keeping its verified badge -- inflating Skill Gap
-- readiness (skill_gap_service.py) and every match score derived from
-- student_skills (student_opportunity_service.compute_opportunity_match,
-- application_skill_match / 021_application_skill_match.sql).
--
-- ============================================================
-- Fix (auto-clear, not reject)
-- ============================================================
-- Extend the SAME trigger function (CREATE OR REPLACE): when a
-- non-service_role caller changes proficiency_level or proficiency_score
-- on a row that is currently is_verified = true, the trigger AUTO-CLEARS
-- the verification (is_verified := false, verified_at := null) before the
-- row is written. The verification was earned against the OLD level and
-- does not carry over -- re-taking the matching assessment at the new
-- level is the only way to re-earn it.
--
-- "Auto-clear" is chosen over "reject" because revising one's own
-- self-reported proficiency is a legitimate, expected student action (the
-- edit dialog exists for exactly this) and must not be blocked outright.
--
-- Because the student is structurally barred from setting is_verified /
-- verified_at themselves, the neutralisation has to happen inside the
-- trigger (SECURITY DEFINER, BEFORE UPDATE -- it may mutate NEW).
--
-- ============================================================
-- What is deliberately relaxed, and why it is safe
-- ============================================================
-- The pre-031 function raised on ANY is_verified change (both
-- directions). This version raises only on the DANGEROUS direction --
-- false -> true (fabricating a verification) -- and on any attempt to set
-- verified_at to a non-null value. It now ALLOWS a non-service_role
-- caller to move is_verified true -> false (and verified_at -> null):
--   * that is required for the auto-clear above to write through the
--     same trigger;
--   * a student voluntarily un-verifying their own skill only lowers
--     their own standing -- it cannot inflate readiness or any match
--     score, so it is not a security property anyone relies on.
--
-- ============================================================
-- What is NOT changed
-- ============================================================
-- * No column added or dropped. No table touched. No RLS policy changed.
-- * score_assessment_attempt() is untouched -- assessment scoring and
--   verification still happen exclusively on the trusted service_role
--   path and never trust a client value.
-- * The is_verified INSERT guard (student_skills INSERT policy WITH CHECK
--   is_verified = false, added by the teammate's 023 hardening and
--   already live) is unaffected.
-- * One CREATE OR REPLACE FUNCTION + a re-attached trigger, both
--   idempotent -- safe to run more than once.

create or replace function public.prevent_self_skill_verification()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- service_role (score_assessment_attempt(), 015_assessment_verification.sql)
  -- is the only trusted writer of verification state -- it writes the row
  -- exactly as intended and is never second-guessed here.
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  -- Auto-invalidate an assessment verification when the student revises
  -- the self-reported proficiency it was earned against.
  if old.is_verified
    and (
      new.proficiency_level is distinct from old.proficiency_level
      or new.proficiency_score is distinct from old.proficiency_score
    )
  then
    new.is_verified := false;
    new.verified_at := null;
  end if;

  -- Keep verified_at consistent with is_verified whenever verification is
  -- lost by any non-trusted path (the auto-clear above, or a deliberate
  -- self-reset of is_verified to false).
  if old.is_verified and not new.is_verified then
    new.verified_at := null;
  end if;

  -- A non-trusted caller may LOSE verification but never GAIN it.
  if new.is_verified and not old.is_verified then
    raise exception 'Cannot change skill verification status directly.' using errcode = '42501';
  end if;

  -- verified_at may never be set to (or changed to) a non-null value by a
  -- non-trusted caller -- only ever moved to null alongside is_verified.
  if new.verified_at is distinct from old.verified_at and new.verified_at is not null then
    raise exception 'Cannot change skill verification status directly.' using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_self_skill_verification() from public;

drop trigger if exists student_skills_prevent_self_verification on student_skills;

create trigger student_skills_prevent_self_verification
  before update on student_skills
  for each row
  execute procedure public.prevent_self_skill_verification();
