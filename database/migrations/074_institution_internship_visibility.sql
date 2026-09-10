-- Migration: 074_institution_internship_visibility
-- Purpose: PHASE 7 -- lets an INSTITUTION see the full display details of
-- an internship one of its OWN linked students has applied to, even
-- after that internship is no longer PUBLISHED. This migration adds
-- exactly ONE function. It does NOT create institution_internships,
-- institution_internship_applications, a stipend ledger, or a
-- participation/completion table -- none of those are needed:
--
--   - "Applied to" / "Selected" still means exactly what it has meant
--     since 020_applications.sql: an `applications` row with
--     opportunity_type = 'INTERNSHIP' and status = 'SELECTED' for
--     SELECTED.
--   - Stipend info is (and remains) the existing flat
--     `internships.stipend_amount` / `stipend_currency` columns
--     (018_internships.sql) -- there is no separate disbursement ledger
--     anywhere in this schema, so none is invented here.
--   - "Active" / "Completed" participation is not a tracked status
--     anywhere in this schema (no attendance/completion table exists).
--     The application layer (institution_internship_service.py) derives
--     a best-effort ESTIMATE from the internship's own start_date +
--     duration_months, documented as an estimate, never as a tracked
--     fact -- no schema change is needed or made for that.
--
-- Same wall, same fix, as institution_visible_job_details
-- (073_institution_placement_drives.sql) and
-- institution_visible_opportunity_titles (071_institution_student_
-- directory.sql, which already resolves an internship's TITLE the same
-- way -- this function resolves the FULL row instead, since the
-- Institution Internship Directory (Phase 7) needs location/work_mode/
-- duration/stipend/deadline/status, not just a title): `internships` is
-- only readable to a non-owner while status = 'PUBLISHED' (018). Once a
-- company closes/archives an internship that an institution's student
-- already applied to, the Internship Directory would otherwise go blind
-- to that internship's own details. Returns full display fields, but
-- ONLY for an internship one of the caller's OWN linked students has an
-- application against -- never a general posting lookup, and never
-- anything beyond what a published internship already shows any
-- authenticated user.
-- ============================================================

create or replace function public.institution_visible_internship_details(internship_ids uuid[])
returns table (
  id uuid,
  title text,
  description text,
  location text,
  work_mode text,
  duration_months int,
  stipend_amount numeric,
  stipend_currency text,
  eligibility_criteria text,
  application_deadline date,
  start_date date,
  status text,
  industry_id uuid
)
language sql
security definer
set search_path = ''
stable
as $$
  select i.id, i.title, i.description, i.location, i.work_mode, i.duration_months,
         i.stipend_amount, i.stipend_currency, i.eligibility_criteria,
         i.application_deadline, i.start_date, i.status, i.industry_id
  from public.internships i
  where i.id = any(internship_ids)
    and public.is_institution(auth.uid())
    and exists (
      select 1
      from public.applications a
      join public.student_profiles sp on sp.id = a.student_id
      where a.internship_id = i.id
        and sp.institution_id = auth.uid()
    );
$$;

revoke all on function public.institution_visible_internship_details(uuid[]) from public;
revoke all on function public.institution_visible_internship_details(uuid[]) from anon;
grant execute on function public.institution_visible_internship_details(uuid[]) to authenticated;

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as the owning INSTITUTION: full details for a CLOSED internship one
--   -- of its own linked students applied to
--   select * from public.institution_visible_internship_details(
--     array(
--       select internship_id from public.applications a
--       join public.student_profiles sp on sp.id = a.student_id
--       where sp.institution_id = auth.uid() and a.internship_id is not null
--     )
--   );
--
--   -- for an internship NONE of the caller's students applied to: 0 rows,
--   -- even if PUBLISHED (use the ordinary internships table read for that
--   -- case instead -- this function is only for the historical-visibility
--   -- gap on non-PUBLISHED internships)
--
--   -- as a STUDENT or INDUSTRY caller: 0 rows -- requires
--   -- is_institution(auth.uid()), which is false for either
-- ============================================================
