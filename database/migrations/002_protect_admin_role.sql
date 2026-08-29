-- Migration: 002_protect_admin_role
-- Purpose: close a privilege-escalation gap in the self-update policy from
-- 001_profiles.sql. That policy ("Users can update their own profile")
-- only checks auth.uid() = id — it says nothing about which VALUES the
-- role column may take, so any authenticated user could currently PATCH
-- their own row straight to role = 'ADMIN' via the Supabase REST API,
-- bypassing the onboarding UI entirely (the UI only hides ADMIN as an
-- option; it never enforced anything server-side).
--
-- Fix: a BEFORE UPDATE trigger that rejects any row-level transition INTO
-- 'ADMIN' (from NULL or any other role) when performed by an ordinary
-- RLS-governed request (Postgres role `authenticated`, i.e. the anon key
-- + a user's JWT — exactly how the frontend always talks to Supabase).
--
-- This is intentionally NOT a `WITH CHECK (role <> 'ADMIN')` addition to
-- the existing UPDATE policy: that would also permanently block a row
-- that is *already* ADMIN from ever being updated again (WITH CHECK runs
-- against the resulting row on every update, not just the changed
-- columns), locking out a legitimate admin's own future profile edits.
-- Comparing OLD.role vs NEW.role in a trigger avoids that — a no-op
-- transition (ADMIN -> ADMIN) is allowed; only NON-ADMIN -> ADMIN is not.
--
-- The trigger explicitly steps aside for Postgres role `service_role`
-- (RLS-bypassing, never used from the frontend — see frontend/lib/auth.ts
-- and frontend/lib/supabase/client.ts, neither of which ever references
-- the service role key). That is deliberately left as the only path able
-- to grant ADMIN — a concrete trusted/admin provisioning mechanism using
-- that path is a later feature, not built here.

create or replace function public.prevent_self_admin_promotion()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  -- service_role (backend-only, RLS-bypassing) is the trusted path for
  -- assigning ADMIN. Every other caller reaches this table as either
  -- `authenticated` (a signed-in user, via the anon key + their JWT) or
  -- `anon` — both fully RLS-governed, which is everything the frontend
  -- ever uses.
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.role = 'ADMIN' and old.role is distinct from 'ADMIN' then
    raise exception 'Cannot self-assign the ADMIN role.' using errcode = '42501';
  end if;

  return new;
end;
$$;

drop trigger if exists prevent_self_admin_promotion_trigger on profiles;

create trigger prevent_self_admin_promotion_trigger
  before update on profiles
  for each row
  execute procedure public.prevent_self_admin_promotion();
