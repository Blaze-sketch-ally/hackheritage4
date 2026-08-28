-- Migration: 001_profiles
-- Purpose: user profile records, one per Supabase Auth user, carrying the
-- platform role (STUDENT / FACULTY / INDUSTRY / INSTITUTION / ADMIN) and
-- basic identity fields shared across all roles.
--
-- This is intentionally minimal for now — just enough to verify Supabase
-- connectivity. Full profile fields land with the Authentication feature.

create table if not exists profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  role text not null default 'STUDENT',
  full_name text,
  created_at timestamptz not null default now()
);
