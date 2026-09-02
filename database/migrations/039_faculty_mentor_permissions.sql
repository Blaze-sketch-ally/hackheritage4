-- Migration: 039_faculty_mentor_permissions
-- Purpose: Phase F4.2's capability layer for Faculty -> Student
-- mentorship. Mirrors 027_faculty_assessment_permissions.sql's own
-- pattern (capability state in a dedicated table, no user-facing table
-- policy, RPC-only reads/writes) but is DELIBERATELY a separate table,
-- not a new value added to `assessment_capability` -- assessment
-- authority and mentorship authority are two independent trust axes with
-- no shared semantics: a Faculty member can hold every assessment
-- capability and still have no mentorship capability, and vice versa.
-- Nothing in this migration reads or writes faculty_assessment_permissions.
--
-- Unlike assessment_capability (five distinct capabilities per Faculty
-- member), mentorship has exactly one conceptual capability --
-- "may this Faculty member participate in mentorship workflows at all"
-- -- so this is a single-row-per-Faculty status table, not a
-- (faculty_id, capability) pair. `faculty_mentor` is the name used in the
-- API/frontend for this capability; it has no enum column of its own to
-- represent because there is only one value.
--
-- IMPORTANT: this capability authorizes PARTICIPATION in the mentorship
-- workflow (creating/accepting requests, appearing as a candidate
-- mentor). It never grants access to any specific student -- that access
-- is granted exclusively through an ACTIVE row in
-- faculty_student_mentorships (040_faculty_student_mentorships.sql),
-- which additionally re-checks this capability at read time (see that
-- migration for the downstream visibility policies).

create type public.faculty_mentor_permission_status as enum (
  'GRANTED',
  'SUSPENDED',
  'REVOKED'
);

create table public.faculty_mentor_permissions (
  id uuid primary key default gen_random_uuid(),
  faculty_id uuid not null references public.profiles(id) on delete cascade,
  status public.faculty_mentor_permission_status not null default 'GRANTED',
  granted_by uuid references public.profiles(id) on delete set null,
  status_changed_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- Exactly one capability row per Faculty member -- re-granting after a
  -- REVOKED/SUSPENDED status is an update to this same row (see the admin
  -- RPC below), not a new row, matching 027's own per-capability
  -- uniqueness reasoning applied here to the single implicit capability.
  constraint faculty_mentor_permissions_unique_faculty unique (faculty_id)
);

create index faculty_mentor_permissions_effective_lookup_idx
  on public.faculty_mentor_permissions (faculty_id)
  where status = 'GRANTED';

alter table public.faculty_mentor_permissions enable row level security;

-- No user-facing table policies, deliberately -- same precedent as
-- faculty_assessment_permissions: ordinary users, including the Faculty
-- member the row is about, cannot read grant metadata or mutate this
-- table directly. get_my_mentor_capability() below is the only
-- authenticated read surface; admin_* RPCs further below are the only
-- write surface.

create table public.faculty_mentor_permission_audit (
  id uuid primary key default gen_random_uuid(),
  permission_id uuid references public.faculty_mentor_permissions(id) on delete set null,
  faculty_id uuid not null references public.profiles(id) on delete cascade,
  previous_status public.faculty_mentor_permission_status,
  new_status public.faculty_mentor_permission_status not null,
  actor_id uuid references public.profiles(id) on delete set null,
  occurred_at timestamptz not null default now()
);

create index faculty_mentor_permission_audit_faculty_id_idx
  on public.faculty_mentor_permission_audit (faculty_id, occurred_at desc);

alter table public.faculty_mentor_permission_audit enable row level security;

-- No authenticated policy at all -- internal governance data, written
-- solely by the trigger below, same precedent as
-- faculty_assessment_permission_audit.

create or replace function public.audit_faculty_mentor_permission_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    insert into public.faculty_mentor_permission_audit (
      permission_id, faculty_id, previous_status, new_status, actor_id
    ) values (
      new.id, new.faculty_id, null, new.status, new.granted_by
    );
  elsif old.status is distinct from new.status
    or old.status_changed_by is distinct from new.status_changed_by then
    insert into public.faculty_mentor_permission_audit (
      permission_id, faculty_id, previous_status, new_status, actor_id
    ) values (
      new.id, new.faculty_id, old.status, new.status, new.status_changed_by
    );
  end if;
  return new;
end;
$$;

revoke all on function public.audit_faculty_mentor_permission_change() from public;

create trigger faculty_mentor_permissions_audit
  after insert or update on public.faculty_mentor_permissions
  for each row execute procedure public.audit_faculty_mentor_permission_change();

create trigger faculty_mentor_permissions_set_updated_at
  before update on public.faculty_mentor_permissions
  for each row execute procedure public.set_updated_at();

-- Boolean primitive, used both by get_my_mentor_capability() below and by
-- every downstream student-visibility RLS policy added in
-- 040_faculty_student_mentorships.sql. The FACULTY prerequisite is
-- checked here as defence in depth, same reasoning as
-- has_assessment_capability().
create or replace function public.has_mentor_capability(profile_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.profiles p
    join public.faculty_mentor_permissions permission
      on permission.faculty_id = p.id
    where p.id = profile_id
      and p.role = 'FACULTY'
      and permission.status = 'GRANTED'
  );
$$;

revoke all on function public.has_mentor_capability(uuid) from public;
revoke all on function public.has_mentor_capability(uuid) from anon;
grant execute on function public.has_mentor_capability(uuid) to authenticated;

-- Self-only read surface for the frontend/API -- a single boolean, never
-- grant actors or history.
create or replace function public.get_my_mentor_capability()
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select public.has_mentor_capability(auth.uid());
$$;

revoke all on function public.get_my_mentor_capability() from public;
revoke all on function public.get_my_mentor_capability() from anon;
grant execute on function public.get_my_mentor_capability() to authenticated;

-- ============================================================
-- Admin management surface -- same shape as
-- 035_admin_faculty_permission_management.sql, deliberately a narrow RPC
-- surface rather than a table policy (an ADMIN-scoped `for all` policy
-- would let an ADMIN forge granted_by/status_changed_by or grant the
-- capability to a non-FACULTY profile with only a client-side promise to
-- behave -- exactly what that migration's own header argues against).
-- is_admin() already exists (035); not redefined here.
-- ============================================================

create or replace function public.admin_grant_mentor_capability(
  target_faculty_id uuid
)
returns table (
  permission_id uuid,
  faculty_id uuid,
  status public.faculty_mentor_permission_status,
  granted_by uuid,
  status_changed_by uuid,
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
  result_row public.faculty_mentor_permissions;
begin
  if caller_id is null then
    raise exception 'Authentication required.' using errcode = '28000';
  end if;

  if not public.is_admin(caller_id) then
    raise exception 'Only ADMIN accounts may grant the Faculty mentor capability.'
      using errcode = '42501';
  end if;

  select role into target_role from public.profiles where id = target_faculty_id;

  if target_role is null then
    raise exception 'Target user does not exist.' using errcode = 'P0002';
  end if;

  if target_role <> 'FACULTY' then
    raise exception 'The mentor capability may only be granted to FACULTY accounts.'
      using errcode = '42501';
  end if;

  insert into public.faculty_mentor_permissions (
    faculty_id, status, granted_by, status_changed_by
  ) values (
    target_faculty_id, 'GRANTED', caller_id, caller_id
  )
  on conflict (faculty_id) do update
    set status = 'GRANTED',
        granted_by = caller_id,
        status_changed_by = caller_id,
        updated_at = now()
  returning * into result_row;

  return query
  select
    result_row.id, result_row.faculty_id, result_row.status,
    result_row.granted_by, result_row.status_changed_by,
    result_row.created_at, result_row.updated_at;
end;
$$;

revoke all on function public.admin_grant_mentor_capability(uuid) from public;
revoke all on function public.admin_grant_mentor_capability(uuid) from anon;
grant execute on function public.admin_grant_mentor_capability(uuid) to authenticated;

create or replace function public.admin_set_mentor_permission_status(
  target_permission_id uuid,
  new_status public.faculty_mentor_permission_status
)
returns table (
  permission_id uuid,
  faculty_id uuid,
  status public.faculty_mentor_permission_status,
  granted_by uuid,
  status_changed_by uuid,
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
  result_row public.faculty_mentor_permissions;
begin
  if caller_id is null then
    raise exception 'Authentication required.' using errcode = '28000';
  end if;

  if not public.is_admin(caller_id) then
    raise exception 'Only ADMIN accounts may change the Faculty mentor permission status.'
      using errcode = '42501';
  end if;

  select faculty_id into target_faculty_id
  from public.faculty_mentor_permissions
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

  update public.faculty_mentor_permissions
  set status = new_status,
      status_changed_by = caller_id,
      updated_at = now()
  where id = target_permission_id
  returning * into result_row;

  return query
  select
    result_row.id, result_row.faculty_id, result_row.status,
    result_row.granted_by, result_row.status_changed_by,
    result_row.created_at, result_row.updated_at;
end;
$$;

revoke all on function public.admin_set_mentor_permission_status(
  uuid, public.faculty_mentor_permission_status
) from public;
revoke all on function public.admin_set_mentor_permission_status(
  uuid, public.faculty_mentor_permission_status
) from anon;
grant execute on function public.admin_set_mentor_permission_status(
  uuid, public.faculty_mentor_permission_status
) to authenticated;

-- Read side of the same admin surface -- one row per FACULTY profile,
-- LEFT JOINed so a Faculty member with no grant yet still appears (an
-- admin needs to see them in order to grant their first capability).
create or replace function public.admin_list_faculty_mentor_permissions()
returns table (
  faculty_id uuid,
  faculty_email text,
  faculty_username text,
  faculty_full_name text,
  permission_id uuid,
  status public.faculty_mentor_permission_status,
  granted_by uuid,
  status_changed_by uuid,
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
    raise exception 'Only ADMIN accounts may list Faculty mentor permissions.'
      using errcode = '42501';
  end if;

  return query
  select
    p.id,
    p.email,
    p.username,
    p.full_name,
    perm.id,
    perm.status,
    perm.granted_by,
    perm.status_changed_by,
    perm.created_at,
    perm.updated_at
  from public.profiles p
  left join public.faculty_mentor_permissions perm on perm.faculty_id = p.id
  where p.role = 'FACULTY'
  order by p.full_name nulls last, p.id;
end;
$$;

revoke all on function public.admin_list_faculty_mentor_permissions() from public;
revoke all on function public.admin_list_faculty_mentor_permissions() from anon;
grant execute on function public.admin_list_faculty_mentor_permissions() to authenticated;
