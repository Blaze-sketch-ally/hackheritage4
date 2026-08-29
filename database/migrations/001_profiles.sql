-- Migration: 001_profiles
-- Purpose: authentication foundation. One profile row per Supabase Auth
-- user, carrying the platform role (STUDENT / FACULTY / INDUSTRY /
-- INSTITUTION / ADMIN) and basic identity fields shared across all roles.
--
-- This is the minimum schema needed for the Authentication feature:
--   - profiles: role/username/identity, auto-created for every new
--     auth.users row (role starts NULL — assigned during onboarding).
--   - get_email_for_identifier: lets the login form accept a username by
--     safely resolving it to the auth email, without exposing the
--     service role key to the frontend or granting broad read access to
--     other users' emails.
--
-- Full profile fields (bio, department, etc.) land with later features.

create table if not exists profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  username text,
  role text check (role in ('STUDENT', 'FACULTY', 'INDUSTRY', 'INSTITUTION', 'ADMIN')),
  full_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint username_format check (username ~ '^[a-zA-Z0-9_.-]{3,30}$')
);

-- Case-insensitive uniqueness (also the only uniqueness constraint on
-- username — a plain UNIQUE would be redundant with this).
create unique index if not exists profiles_username_lower_idx on profiles (lower(username));

alter table profiles enable row level security;

create policy "Users can view their own profile"
  on profiles for select
  to authenticated
  using (auth.uid() = id);

create policy "Users can update their own profile"
  on profiles for update
  to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Auto-create a (role-less) profile row whenever a new Supabase Auth user
-- is created, whether via email/password sign-up or an OAuth provider
-- (e.g. Google). Role stays NULL until the onboarding flow sets it —
-- nothing here assumes STUDENT or any other role.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, email, full_name, avatar_url)
  values (
    new.id,
    new.email,
    new.raw_user_meta_data ->> 'full_name',
    new.raw_user_meta_data ->> 'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Resolves a login identifier to the email Supabase Auth needs:
--   - already an email -> returned as-is (no lookup)
--   - a username -> looked up case-insensitively in profiles
-- SECURITY DEFINER so anonymous callers can resolve a username without
-- being granted direct SELECT access to the profiles table.
create or replace function public.get_email_for_identifier(identifier text)
returns text
language plpgsql
security definer set search_path = ''
as $$
declare
  resolved_email text;
begin
  if identifier ilike '%@%' then
    return identifier;
  end if;

  select email into resolved_email
  from public.profiles
  where lower(username) = lower(identifier)
  limit 1;

  return resolved_email;
end;
$$;

grant execute on function public.get_email_for_identifier(text) to anon, authenticated;
