-- Migration: 035_admin_faculty_permission_management
-- Purpose: Phase F2's admin control surface over
-- 027_faculty_assessment_permissions.sql. That migration deliberately
-- shipped with NO user-facing table policies at all -- not even for the
-- owning Faculty member -- because no admin authorization primitive
-- existed yet. This migration adds exactly that primitive, plus the two
-- SECURITY DEFINER RPCs an ADMIN needs to manage capabilities, following
-- 027's own pattern (narrow RPC surface, not a table policy) rather than
-- widening RLS on faculty_assessment_permissions.
--
-- Deliberately NOT a table policy: an ADMIN-scoped `for all` policy on
-- faculty_assessment_permissions would let an ADMIN write ANY column
-- (including forging granted_by/status_changed_by as someone else, or
-- setting a capability on a non-FACULTY profile) with only a client-side
-- promise to behave -- exactly the kind of "broad policy for admin
-- convenience" 027's own header and this project's is_faculty/is_student
-- SECURITY DEFINER precedent both argue against. The two RPCs below are
-- the complete, narrow write surface instead: each independently
-- re-verifies the caller is ADMIN (defense in depth -- these are granted
-- to `authenticated`, so a non-admin authenticated user calling the RPC
-- directly via PostgREST, bypassing the FastAPI require_admin() layer
-- entirely, must still be rejected here), and each derives
-- granted_by/status_changed_by from auth.uid() only, never from a
-- request parameter.

-- 1. is_admin(): role-check helper, identical shape to is_student()
-- (012_student_profiles.sql), is_faculty() (015), is_industry() (024),
-- and is_institution() (032).
create or replace function public.is_admin(profile_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1 from public.profiles where id = profile_id and role = 'ADMIN'
  );
$$;

revoke all on function public.is_admin(uuid) from public;
revoke all on function public.is_admin(uuid) from anon;
grant execute on function public.is_admin(uuid) to authenticated;

-- 2. admin_grant_assessment_capability(): grants (or re-grants) one
-- capability to one Faculty member. Upserts on the existing
-- (faculty_id, capability) unique constraint from 027 -- re-granting a
-- previously SUSPENDED/EXPIRED/REVOKED capability is the natural "grant"
-- action, not a separate "reactivate" operation, and this keeps a
-- Faculty member's history for one capability in a single row rather
-- than accumulating duplicates. On conflict, granted_by AND
-- status_changed_by are both refreshed to the acting admin -- 027's own
-- audit trigger uses status_changed_by (UPDATE path) / granted_by
-- (INSERT path) as the audit row's actor_id, so both paths must
-- correctly attribute this admin as the actor for the resulting audit
-- entry.
create or replace function public.admin_grant_assessment_capability(
  target_faculty_id uuid,
  requested_capability public.assessment_capability,
  capability_expires_at timestamptz default null
)
returns table (
  permission_id uuid,
  faculty_id uuid,
  capability public.assessment_capability,
  status public.faculty_assessment_permission_status,
  granted_by uuid,
  status_changed_by uuid,
  expires_at timestamptz,
  created_at timestamptz,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  target_role text;
  result_row public.faculty_assessment_permissions;
begin
  if caller_id is null then
    raise exception 'Authentication required.' using errcode = '28000';
  end if;

  if not public.is_admin(caller_id) then
    raise exception 'Only ADMIN accounts may grant Faculty assessment capabilities.'
      using errcode = '42501';
  end if;

  select role into target_role from public.profiles where id = target_faculty_id;

  if target_role is null then
    raise exception 'Target user does not exist.' using errcode = 'P0002';
  end if;

  if target_role <> 'FACULTY' then
    raise exception 'Assessment capabilities may only be granted to FACULTY accounts.'
      using errcode = '42501';
  end if;

  insert into public.faculty_assessment_permissions (
    faculty_id, capability, status, granted_by, status_changed_by, expires_at
  ) values (
    target_faculty_id, requested_capability, 'GRANTED', caller_id, caller_id, capability_expires_at
  )
  on conflict (faculty_id, capability) do update
    set status = 'GRANTED',
        granted_by = caller_id,
        status_changed_by = caller_id,
        expires_at = capability_expires_at,
        updated_at = now()
  returning * into result_row;

  return query
  select
    result_row.id, result_row.faculty_id, result_row.capability, result_row.status,
    result_row.granted_by, result_row.status_changed_by, result_row.expires_at,
    result_row.created_at, result_row.updated_at;
end;
$$;

revoke all on function public.admin_grant_assessment_capability(
  uuid, public.assessment_capability, timestamptz
) from public;
revoke all on function public.admin_grant_assessment_capability(
  uuid, public.assessment_capability, timestamptz
) from anon;
grant execute on function public.admin_grant_assessment_capability(
  uuid, public.assessment_capability, timestamptz
) to authenticated;

-- 3. admin_set_assessment_permission_status(): explicit admin-driven
-- status transition (GRANTED/SUSPENDED/EXPIRED/REVOKED) for an existing
-- permission row. Separate from the grant RPC above because changing
-- status is a distinct admin action from (re-)granting a capability with
-- a possibly new expiry -- this RPC never touches expires_at.
--
-- Reactivating to GRANTED re-checks the target is still a FACULTY
-- account (a profile's role is not otherwise guaranteed immutable) --
-- has_assessment_capability() already re-checks this at evaluation time,
-- but this RPC checks it too so an admin gets an explicit rejection
-- instead of silently creating a GRANTED row that can never actually be
-- effective.
create or replace function public.admin_set_assessment_permission_status(
  target_permission_id uuid,
  new_status public.faculty_assessment_permission_status
)
returns table (
  permission_id uuid,
  faculty_id uuid,
  capability public.assessment_capability,
  status public.faculty_assessment_permission_status,
  granted_by uuid,
  status_changed_by uuid,
  expires_at timestamptz,
  created_at timestamptz,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  target_faculty_id uuid;
  target_role text;
  result_row public.faculty_assessment_permissions;
begin
  if caller_id is null then
    raise exception 'Authentication required.' using errcode = '28000';
  end if;

  if not public.is_admin(caller_id) then
    raise exception 'Only ADMIN accounts may change Faculty assessment permission status.'
      using errcode = '42501';
  end if;

  select faculty_id into target_faculty_id
  from public.faculty_assessment_permissions
  where id = target_permission_id;

  if target_faculty_id is null then
    raise exception 'Permission not found.' using errcode = 'P0002';
  end if;

  if new_status = 'GRANTED' then
    select role into target_role from public.profiles where id = target_faculty_id;
    if target_role is distinct from 'FACULTY' then
      raise exception 'Cannot reactivate: target user is no longer a FACULTY account.'
        using errcode = '42501';
    end if;
  end if;

  update public.faculty_assessment_permissions
  set status = new_status,
      status_changed_by = caller_id,
      updated_at = now()
  where id = target_permission_id
  returning * into result_row;

  return query
  select
    result_row.id, result_row.faculty_id, result_row.capability, result_row.status,
    result_row.granted_by, result_row.status_changed_by, result_row.expires_at,
    result_row.created_at, result_row.updated_at;
end;
$$;

revoke all on function public.admin_set_assessment_permission_status(
  uuid, public.faculty_assessment_permission_status
) from public;
revoke all on function public.admin_set_assessment_permission_status(
  uuid, public.faculty_assessment_permission_status
) from anon;
grant execute on function public.admin_set_assessment_permission_status(
  uuid, public.faculty_assessment_permission_status
) to authenticated;

-- 4. admin_list_faculty_assessment_permissions(): the read side of the
-- same admin surface. One row per (Faculty, granted capability); a
-- Faculty member with zero permissions granted still needs to appear so
-- an admin can grant their first capability, so this is a LEFT JOIN, not
-- an inner join. Deliberately a single RPC covering both "list every
-- Faculty member" and "read one Faculty member's capabilities" (the
-- backend filters the result by faculty_id for the latter) rather than
-- two near-duplicate read paths.
create or replace function public.admin_list_faculty_assessment_permissions()
returns table (
  faculty_id uuid,
  faculty_email text,
  faculty_username text,
  faculty_full_name text,
  permission_id uuid,
  capability public.assessment_capability,
  status public.faculty_assessment_permission_status,
  granted_by uuid,
  status_changed_by uuid,
  expires_at timestamptz,
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
    raise exception 'Only ADMIN accounts may list Faculty assessment permissions.'
      using errcode = '42501';
  end if;

  return query
  select
    p.id,
    p.email,
    p.username,
    p.full_name,
    perm.id,
    perm.capability,
    perm.status,
    perm.granted_by,
    perm.status_changed_by,
    perm.expires_at,
    perm.created_at,
    perm.updated_at
  from public.profiles p
  left join public.faculty_assessment_permissions perm on perm.faculty_id = p.id
  where p.role = 'FACULTY'
  order by p.full_name nulls last, p.id, perm.capability;
end;
$$;

revoke all on function public.admin_list_faculty_assessment_permissions() from public;
revoke all on function public.admin_list_faculty_assessment_permissions() from anon;
grant execute on function public.admin_list_faculty_assessment_permissions() to authenticated;
