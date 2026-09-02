-- Migration: 026_industry_profiles
-- Purpose: adds a lazily-created, INDUSTRY-owned company profile without
-- changing the unified opportunities/application model introduced in 024.
--
-- Ownership: one row per INDUSTRY profile (id = profiles.id). An industry
-- account owns its row; any authenticated user may read company display data
-- so published opportunities can identify their poster. The existing
-- public.is_industry(uuid) helper from 024 is reused rather than redefined.

create table if not exists industry_profiles (
  id uuid primary key references profiles (id) on delete cascade,

  company_name text,
  industry_sector text,
  company_size text check (company_size in ('1-10', '11-50', '51-200', '201-500', '501-1000', '1000+')),
  website_url text,
  company_description text,
  headquarters_location text,
  founded_year int check (founded_year between 1800 and 2100),
  contact_phone text,
  constraint industry_profiles_phone_format check (contact_phone ~ '^[0-9+\-\s()]{7,20}$'),
  linkedin_url text,
  logo_url text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table industry_profiles enable row level security;

-- Industry accounts create and maintain only their own company record.
create policy "Industry can view their own industry profile"
  on industry_profiles for select
  to authenticated
  using (auth.uid() = id and public.is_industry(auth.uid()));

create policy "Industry can insert their own industry profile"
  on industry_profiles for insert
  to authenticated
  with check (auth.uid() = id and public.is_industry(auth.uid()));

create policy "Industry can update their own industry profile"
  on industry_profiles for update
  to authenticated
  using (auth.uid() = id and public.is_industry(auth.uid()))
  with check (auth.uid() = id and public.is_industry(auth.uid()));

-- Company identity is non-sensitive display data for opportunity browsing.
create policy "Authenticated users can view industry profiles"
  on industry_profiles for select
  to authenticated
  using (true);

create trigger industry_profiles_set_updated_at
  before update on industry_profiles
  for each row
  execute procedure public.set_updated_at();
