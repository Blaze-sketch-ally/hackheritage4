-- Migration: 036_application_applicant_names
-- Purpose: P1 UI/data finding -- the Industry Applicants list/detail views
-- (frontend/components/industry/applicants, .../recruitment,
-- .../candidate-card.tsx) showed every applicant only as a truncated
-- student_id ("Applicant db8b0e39"), never their real name. `applications`
-- carries `student_id` (a uuid) and nothing else identifying the student
-- (020_applications.sql), and Industry has no RLS read access to
-- `profiles` for a row it doesn't own (001_profiles.sql: "Users can view
-- their own profile", auth.uid() = id only) -- so there was no data path
-- to a display name at all, not just a missing UI wire-up.
--
-- The missing piece is a DISPLAY NAME for the applicant:
--   student_id -> the applicant's profiles.full_name.
--
-- Why this needs a function rather than a plain join: same wall
-- collaboration_counterparty_names (029) already climbs for the same
-- reason -- profiles' only SELECT policy is ownership-only, so a normal
-- user-scoped Industry client cannot read another user's
-- profiles.full_name via a join, RPC, or any other query built on the
-- user-scoped client. This function is that same pattern, keyed by
-- application id instead of collaboration id.
--
-- This is a READ-ONLY helper. It creates NO table, changes NO column, and
-- touches NO RLS policy or trigger on `profiles` or `applications` --
-- Industry's visibility into WHICH applications it may resolve names for
-- is still governed entirely by the existing RLS predicate below, just
-- re-derived inside the function instead of relying on RLS to filter a
-- join. It is additive and idempotent (CREATE OR REPLACE).
--
-- Authorization: re-derived inside the function from auth.uid(). A row is
-- returned only when the caller's own visibility of that application is
-- exactly what 020's own SELECT policy already grants:
--   "Industry can view applications to their own postings"
--     -- auth.uid() = industry_id AND is_industry(auth.uid())
-- A caller asking for an id they do not own (another Industry account's
-- applicant, or a student's own id) simply gets no row back. No
-- application this function can name a student for is one the caller
-- could not already GET through the applications API.
--
-- Exposure: only full_name -- no email, phone, avatar_url, or any other
-- profiles / student_profiles column. Exactly the minimal display
-- identity the Applicants list needs, matching
-- collaboration_counterparty_names' "company_name / full_name only"
-- precedent.
--
-- Hardened exactly like collaboration_counterparty_names (029):
-- SECURITY DEFINER, pinned empty search_path, EXECUTE granted to
-- `authenticated` only, revoked from public and anon up front.

create or replace function public.application_applicant_names(application_ids uuid[])
returns table (
  application_id uuid,
  student_name text
)
language sql
security definer
set search_path = ''
stable
as $$
  select
    a.id,
    p.full_name
  from public.applications a
  join public.profiles p on p.id = a.student_id
  where a.id = any(application_ids)
    and a.industry_id = auth.uid()
    and public.is_industry(auth.uid());
$$;

revoke all on function public.application_applicant_names(uuid[]) from public;
revoke all on function public.application_applicant_names(uuid[]) from anon;
grant execute on function public.application_applicant_names(uuid[]) to authenticated;

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INDUSTRY account: returns names for its own applicants
--   select * from public.application_applicant_names(
--     array(select id from public.applications where industry_id = auth.uid())
--   );
--
--   -- as any caller, for an application id they do NOT own: 0 rows
--   select * from public.application_applicant_names(array['<other-tenant-application-id>'::uuid]);
--
--   -- as a STUDENT (even the applicant themselves): 0 rows -- this
--   -- function is Industry-only, matching the applications SELECT policy
-- ============================================================
