-- Migration: 027_faculty_assessment_permissions
-- Purpose: Phase F2's capability layer beneath the existing FACULTY role.
-- This does not change existing question, answer-key, blueprint, or attempt
-- policies; those continue to use the established FACULTY compatibility model
-- until their later, capability-specific phases.

create type public.assessment_capability as enum (
  'assessment_author',
  'assessment_reviewer',
  'assessment_evaluator',
  'assessment_moderator',
  'assessment_lead'
);

create type public.faculty_assessment_permission_status as enum (
  'GRANTED',
  'SUSPENDED',
  'EXPIRED',
  'REVOKED'
);

create table public.faculty_assessment_permissions (
  id uuid primary key default gen_random_uuid(),
  faculty_id uuid not null references public.profiles(id) on delete cascade,
  capability public.assessment_capability not null,
  status public.faculty_assessment_permission_status not null default 'GRANTED',
  granted_by uuid references public.profiles(id) on delete set null,
  status_changed_by uuid references public.profiles(id) on delete set null,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint faculty_assessment_permissions_unique_capability unique (faculty_id, capability)
);

create index faculty_assessment_permissions_effective_lookup_idx
  on public.faculty_assessment_permissions (faculty_id, capability)
  where status = 'GRANTED';

alter table public.faculty_assessment_permissions enable row level security;

-- No user-facing table policies are deliberate. Ordinary users, including
-- Faculty, cannot read internal grant metadata or mutate permissions. The
-- narrowly-scoped get_my_assessment_capabilities() RPC below is the only
-- authenticated read surface; future AIC/Admin management is service-role
-- backed and must supply the acting user in granted_by/status_changed_by.

create table public.faculty_assessment_permission_audit (
  id uuid primary key default gen_random_uuid(),
  permission_id uuid references public.faculty_assessment_permissions(id) on delete set null,
  faculty_id uuid not null references public.profiles(id) on delete cascade,
  capability public.assessment_capability not null,
  previous_status public.faculty_assessment_permission_status,
  new_status public.faculty_assessment_permission_status not null,
  actor_id uuid references public.profiles(id) on delete set null,
  occurred_at timestamptz not null default now()
);

create index faculty_assessment_permission_audit_faculty_id_idx
  on public.faculty_assessment_permission_audit (faculty_id, occurred_at desc);

alter table public.faculty_assessment_permission_audit enable row level security;

-- No authenticated SELECT/INSERT/UPDATE/DELETE policy: audit records are
-- internal governance data and are written solely by the trigger below.

create or replace function public.audit_faculty_assessment_permission_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    insert into public.faculty_assessment_permission_audit (
      permission_id, faculty_id, capability, previous_status, new_status, actor_id
    ) values (
      new.id, new.faculty_id, new.capability, null, new.status, new.granted_by
    );
  elsif old.status is distinct from new.status
    or old.expires_at is distinct from new.expires_at
    or old.status_changed_by is distinct from new.status_changed_by then
    insert into public.faculty_assessment_permission_audit (
      permission_id, faculty_id, capability, previous_status, new_status, actor_id
    ) values (
      new.id, new.faculty_id, new.capability, old.status, new.status, new.status_changed_by
    );
  end if;
  return new;
end;
$$;

revoke all on function public.audit_faculty_assessment_permission_change() from public;

create trigger faculty_assessment_permissions_audit
  after insert or update on public.faculty_assessment_permissions
  for each row execute procedure public.audit_faculty_assessment_permission_change();

create trigger faculty_assessment_permissions_set_updated_at
  before update on public.faculty_assessment_permissions
  for each row execute procedure public.set_updated_at();

-- Boolean primitive for future RLS policies and server-side authorization.
-- The FACULTY prerequisite is intentionally checked here as defence in depth:
-- even an invalid permission row on a non-Faculty profile can never grant an
-- effective capability.
create or replace function public.has_assessment_capability(
  profile_id uuid,
  requested_capability public.assessment_capability
)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.profiles p
    join public.faculty_assessment_permissions permission
      on permission.faculty_id = p.id
    where p.id = profile_id
      and p.role = 'FACULTY'
      and permission.capability = requested_capability
      and permission.status = 'GRANTED'
      and (permission.expires_at is null or permission.expires_at > now())
  );
$$;

revoke all on function public.has_assessment_capability(uuid, public.assessment_capability) from public;
revoke all on function public.has_assessment_capability(uuid, public.assessment_capability) from anon;
grant execute on function public.has_assessment_capability(uuid, public.assessment_capability) to authenticated;

-- Self-only, data-minimised read surface for the frontend/API. It returns
-- effective capability identifiers only, never grant actors, history, status,
-- or expiration metadata.
create or replace function public.get_my_assessment_capabilities()
returns table (capability public.assessment_capability)
language sql
security definer
set search_path = ''
stable
as $$
  select permission.capability
  from public.profiles p
  join public.faculty_assessment_permissions permission
    on permission.faculty_id = p.id
  where p.id = auth.uid()
    and p.role = 'FACULTY'
    and permission.status = 'GRANTED'
    and (permission.expires_at is null or permission.expires_at > now())
  order by permission.capability;
$$;

revoke all on function public.get_my_assessment_capabilities() from public;
revoke all on function public.get_my_assessment_capabilities() from anon;
grant execute on function public.get_my_assessment_capabilities() to authenticated;
