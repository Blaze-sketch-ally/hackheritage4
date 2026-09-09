-- Migration: 054_student_interview_visibility
-- Purpose: Give a STUDENT a read path to their OWN scheduled interview.
--
-- Background: `interviews` (030_industry_interviews.sql) was built
-- INDUSTRY-side only. Its RLS deliberately ships no student SELECT policy
-- -- 030's own header says "add one in a later migration when that view
-- is built". 037_institution_tenancy.sql later added an Institution
-- SELECT policy for the "upcoming interviews for your students" action
-- item, but the student -- the actual interviewee -- still had no way to
-- see the date/time/mode/location of an interview scheduled for them. The
-- Student Portal showed only the amber "Interview Scheduled" status badge.
--
-- This migration adds that read path as a SECURITY DEFINER function,
-- NOT a table SELECT policy, for two reasons:
--
--   1. `interviews.notes` is Industry-private preparation notes. A plain
--      `FOR SELECT` policy exposes the WHOLE row (Postgres RLS has no
--      column-level filtering), so a direct PostgREST call with a student
--      token could read `notes`. A function returns only an explicit,
--      student-safe column list -- `notes` has no path out.
--   2. It mirrors the pattern already established for the exact same kind
--      of "a role needs to see a narrow slice of a row its table RLS does
--      not grant" problem: application_applicant_names (036),
--      collaboration_counterparty_names (029), institution_student_names
--      (039). Same hardening: SECURITY DEFINER, pinned empty search_path,
--      EXECUTE granted to `authenticated` only, revoked from public/anon.
--
-- This is a READ-ONLY helper. It creates NO table, changes NO column, and
-- touches NO existing RLS policy or trigger on `interviews`. The existing
-- Industry and Institution SELECT policies are untouched and unweakened.
-- It is additive and idempotent (CREATE OR REPLACE).
--
-- Authorization: re-derived inside the function from auth.uid(). A row is
-- returned ONLY when:
--   * the interview's student_id IS the caller (auth.uid() = student_id),
--   * the caller is a student (public.is_student(auth.uid())), and
--   * the interview is LIVE (status = 'SCHEDULED') -- a COMPLETED or
--     CANCELLED interview is never returned, so a cancelled-then-not-yet-
--     rescheduled application shows "being scheduled", never a stale row.
-- A student asking about another student's application id, or an
-- application with no live interview, simply gets no row back.
--
-- Exposure: id, application_id, scheduled_at, duration_minutes, mode,
-- location, status, created_at, updated_at -- exactly what the Student
-- "My Applications" interview card needs. NEVER `notes`, `industry_id`,
-- or `student_id`.
--
-- The `interviews_one_live_per_application_idx` partial unique index
-- (030) already guarantees at most one SCHEDULED interview per
-- application, so the caller can safely treat the result as a
-- one-interview-per-application map.

create or replace function public.student_interviews(application_ids uuid[])
returns table (
  id uuid,
  application_id uuid,
  scheduled_at timestamptz,
  duration_minutes int,
  mode text,
  location text,
  status text,
  created_at timestamptz,
  updated_at timestamptz
)
language sql
security definer
set search_path = ''
stable
as $$
  select
    i.id,
    i.application_id,
    i.scheduled_at,
    i.duration_minutes,
    i.mode,
    i.location,
    i.status,
    i.created_at,
    i.updated_at
  from public.interviews i
  where i.application_id = any(application_ids)
    and i.student_id = auth.uid()
    and i.status = 'SCHEDULED'
    and public.is_student(auth.uid());
$$;

revoke all on function public.student_interviews(uuid[]) from public;
revoke all on function public.student_interviews(uuid[]) from anon;
grant execute on function public.student_interviews(uuid[]) to authenticated;

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the interviewee STUDENT: returns their own live interviews
--   select * from public.student_interviews(
--     array(select id from public.applications where student_id = auth.uid())
--   );
--
--   -- as any caller, for an application id they are not the student of: 0 rows
--   select * from public.student_interviews(array['<other-students-application-id>'::uuid]);
--
--   -- as an INDUSTRY / INSTITUTION caller: 0 rows -- this function is
--   -- student-only (public.is_student(auth.uid()) fails); their own
--   -- interview visibility is unchanged and still comes from 030 / 037.
--
--   -- `notes` is not a column of the result type -- there is no argument
--   -- or option that makes this function return it.
-- ============================================================
