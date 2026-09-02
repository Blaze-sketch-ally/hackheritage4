-- Migration: 032_profile_role_immutability
-- Purpose: repository reproducibility. Make a fresh database replayed from
-- THIS repo's migration lineage (001..032) reproduce the role-immutability
-- security state that the live Supabase project already has.
--
-- ============================================================
-- Background
-- ============================================================
-- 001_profiles.sql's "Users can update their own profile" UPDATE policy
-- checks only row ownership (auth.uid() = id) -- it says nothing about
-- which value `role` may take. 002_protect_admin_role.sql added
-- prevent_self_admin_promotion(), a BEFORE UPDATE trigger, but it only
-- ever blocked a transition INTO 'ADMIN'; every OTHER self-initiated role
-- transition (STUDENT -> INDUSTRY, STUDENT -> FACULTY, ...) was left
-- unguarded by this repo's migrations.
--
-- The live database is not affected by that gap: the contributor's
-- 023_role_and_attempt_integrity_hardening.sql (applied to the shared
-- Supabase project, NOT part of this repo's lineage) closed it with a
-- general "role settable once, from NULL" rule -- confirmed during Phase 5
-- by a read-only probe: PATCH /rest/v1/profiles {role:"INDUSTRY"} as a
-- STUDENT returns 403 "Cannot change your role once it has been set."
--
-- This migration reproduces ONLY that role-immutability rule, so the repo
-- and the live database agree on this one security property. It does NOT
-- reproduce anything else from 023 (the student_skills INSERT WITH CHECK,
-- the profiles.updated_at trigger, the assessment_attempts /
-- assessment_answers field guards, is_faculty(), faculty permissions,
-- ...) -- those are out of scope here.
--
-- ============================================================
-- Invariant
-- ============================================================
--   Once profiles.role has been assigned (is not null), the profile owner
--   -- any ordinary RLS-governed caller, i.e. Postgres role
--   `authenticated` reaching this table via the anon key + a user JWT,
--   which is how the frontend always talks to Supabase -- must NOT be
--   able to change their own role, to ANY value, in either direction
--   (including back to null).
--
-- Still allowed, unchanged:
--   * The one-time onboarding assignment: old.role IS NULL -> a real role.
--     (frontend/lib/auth.ts::updateProfileRole, only reachable from
--     /onboarding, which redirects away once a role exists.)
--   * A no-op UPDATE that does not touch role (new.role = old.role),
--     including two NULLs -- it isn't a transition.
--   * Every legitimate profile field update (full_name / username /
--     avatar_url / bio / ...): this trigger only inspects `role`.
--   * service_role: the RLS-bypassing backend-only path. It steps aside
--     entirely, exactly as it does in 002/003/004/015. A future,
--     deliberately-built admin role-provisioning mechanism using that
--     path is unaffected -- same posture 002 already documented.
--
-- ============================================================
-- Mechanism
-- ============================================================
-- A BEFORE UPDATE trigger, comparing OLD.role vs NEW.role -- the same
-- pattern 002_protect_admin_role.sql chose, and for the same reason it
-- documents: a `WITH CHECK (role <> ...)` addition to the UPDATE policy
-- would re-evaluate against the resulting row on EVERY update and cannot
-- see OLD, so it would permanently freeze an already-set profile out of
-- unrelated edits. A trigger comparing OLD vs NEW does not have that
-- problem.
--
-- This is ADDITIVE. It does not touch 002's prevent_self_admin_promotion
-- (still valid -- it also blocks NULL -> ADMIN during onboarding, which
-- this migration deliberately leaves to 002) and does not touch any RLS
-- policy. On a fresh replay the two BEFORE UPDATE triggers on `profiles`
-- coexist; on the live database this trigger is redundant with 023's
-- prevent_unauthorized_role_change_trigger and simply doubles the guard.
--
-- Distinct names from 002 (prevent_self_admin_promotion*) and from 023
-- (prevent_unauthorized_role_change*) so nothing collides on any lineage.
--
-- Idempotent: CREATE OR REPLACE FUNCTION + DROP TRIGGER IF EXISTS +
-- CREATE TRIGGER + a defensive REVOKE. Non-destructive: no column, table,
-- policy, or historical migration is altered; profiles is neither dropped
-- nor recreated.

create or replace function public.enforce_profile_role_immutability()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- service_role (backend-only, RLS-bypassing) is the trusted path for
  -- any administrative role management. Every other caller reaches this
  -- table as `authenticated` (a signed-in user via the anon key + JWT) or
  -- `anon` -- both fully RLS-governed, which is everything the frontend
  -- ever uses.
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  -- The only self-service role transition the product allows is the
  -- one-time onboarding assignment from NULL. Once role is set, a
  -- non-trusted caller may not change it -- to any value, in any
  -- direction. A no-op (new.role is not distinct from old.role) is never
  -- a transition and is always fine.
  if old.role is not null and new.role is distinct from old.role then
    raise exception 'Your role cannot be changed once it has been set.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

-- Defensive revoke, matching prevent_self_skill_verification() /
-- set_updated_at(): trigger-typed functions aren't callable as PostgREST
-- RPCs regardless of grants, but this closes off direct invocation
-- without affecting the trigger.
revoke all on function public.enforce_profile_role_immutability() from public;

drop trigger if exists profiles_enforce_role_immutability on profiles;

create trigger profiles_enforce_role_immutability
  before update on profiles
  for each row
  execute procedure public.enforce_profile_role_immutability();
