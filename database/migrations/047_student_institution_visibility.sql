-- Migration: 047_student_institution_visibility
-- Purpose: PHASE 12 -- STUDENT INSTITUTION PORTAL. Lets a STUDENT read
-- the institution-relevant rows their own linked institution has already
-- created/curated: their own department's name, their own institution's
-- placement drives, their own institution's curated internships, and
-- their own institution's organized events. This migration adds ZERO new
-- tables -- only four new, additive SELECT policies on existing tables.
-- No INSERT/UPDATE/DELETE policy is added anywhere here -- a student
-- gains no new write path to anything.
--
-- Audit finding this migration acts on: every one of these four tables
-- already has full INSTITUTION-side RLS (040/041/045/046) but NO
-- student-facing SELECT policy at all -- a linked, verified student
-- (student_profiles.institution_id set by the existing
-- institution_link_requests approval workflow, 038) currently cannot
-- read any of them, even their own institution's. That gap is exactly
-- what this migration closes -- nothing else changes:
--
--   - departments (040): needed so a student can resolve their own
--     department_id to a human-readable name ("CSE") on their My
--     Institution page -- today they can read their own
--     student_profiles.department_id (a bare uuid) but not the
--     department row it points to.
--   - placement_drives (041): needed so a student can see placement
--     drives their OWN institution is running. Scoped to
--     status <> 'DRAFT' -- a drive not yet announced must stay
--     invisible; every other status (OPEN/IN_PROGRESS/COMPLETED/
--     CANCELLED) was, at some point, real and announced, and stays
--     visible for the student's own historical record -- same "once
--     real, stays visible" principle already used for internships
--     remaining in an institution's curated list after their posting
--     closes (046).
--   - institution_internships (046): needed so a student can see which
--     internships their OWN institution has curated. Scoped to
--     status = 'ACTIVE' only -- a REMOVED (INACTIVE) curation is not
--     re-exposed to students, matching the Institution-Curated
--     Internships module's own "removed disappears from the curated
--     list" behavior. The canonical `internships` row itself remains
--     readable to the student only while PUBLISHED (018's existing
--     public policy, unchanged here) -- this migration does not widen
--     internship content visibility at all, only which internship IDs a
--     student is told are "curated by my institution".
--   - institution_events (045): needed so a student can see events their
--     OWN institution has organized. Scoped to status = 'PUBLISHED' --
--     the EXACT SAME visibility rule already used for
--     industry_workshops ("Authenticated users can view published
--     workshops", 024) that student_event_service.py reads today; this
--     migration extends the same rule to institution_events rather than
--     inventing a different one.
--
-- Every new policy below uses the identical shape: `public.is_student
-- (auth.uid()) and exists (select 1 from public.student_profiles sp
-- where sp.id = auth.uid() and sp.institution_id = <table>.
-- institution_id)` -- the student's own `institution_id` (set ONLY by
-- the institution_link_requests approval trigger, 038 -- never
-- student-writable) is the sole scoping key, so a student with no linked
-- institution (institution_id is null) matches nothing anywhere here,
-- and a student can never see a DIFFERENT institution's rows. This does
-- NOT auto-join a student to an institution -- it only grants a READ once
-- the existing, explicit, institution-approved link already exists.

-- ============================================================
-- departments (040_institution_departments.sql)
-- ============================================================

drop policy if exists "Students can view departments in their own institution" on departments;
create policy "Students can view departments in their own institution"
  on departments for select
  to authenticated
  using (
    public.is_student(auth.uid())
    and exists (
      select 1 from public.student_profiles sp
      where sp.id = auth.uid() and sp.institution_id = departments.institution_id
    )
  );

-- ============================================================
-- placement_drives (041_institution_placement_drives.sql)
-- ============================================================

drop policy if exists "Students can view their own institution's announced placement drives" on placement_drives;
create policy "Students can view their own institution's announced placement drives"
  on placement_drives for select
  to authenticated
  using (
    status <> 'DRAFT'
    and public.is_student(auth.uid())
    and exists (
      select 1 from public.student_profiles sp
      where sp.id = auth.uid() and sp.institution_id = placement_drives.institution_id
    )
  );

-- ============================================================
-- institution_internships (046_institution_internships.sql)
-- ============================================================

drop policy if exists "Students can view their own institution's curated internships" on institution_internships;
create policy "Students can view their own institution's curated internships"
  on institution_internships for select
  to authenticated
  using (
    status = 'ACTIVE'
    and public.is_student(auth.uid())
    and exists (
      select 1 from public.student_profiles sp
      where sp.id = auth.uid() and sp.institution_id = institution_internships.institution_id
    )
  );

-- ============================================================
-- institution_events (045_institution_events.sql)
-- ============================================================

drop policy if exists "Students can view their own institution's published events" on institution_events;
create policy "Students can view their own institution's published events"
  on institution_events for select
  to authenticated
  using (
    status = 'PUBLISHED'
    and public.is_student(auth.uid())
    and exists (
      select 1 from public.student_profiles sp
      where sp.id = auth.uid() and sp.institution_id = institution_events.institution_id
    )
  );

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as a STUDENT linked (institution_id set) to Institution X:
--   select * from public.departments where institution_id = '<X>'::uuid;          -- own dept only, readable
--   select * from public.placement_drives where institution_id = '<X>'::uuid;     -- non-DRAFT only
--   select * from public.institution_internships where institution_id = '<X>'::uuid; -- ACTIVE only
--   select * from public.institution_events where institution_id = '<X>'::uuid;   -- PUBLISHED only
--
--   -- as the SAME student, rows for a DIFFERENT institution Y: 0 rows in all four
--
--   -- as a student with institution_id IS NULL (never linked, or a
--   -- pending/rejected/cancelled request only): 0 rows in all four --
--   -- these policies grant nothing until the institution's own approval
--   -- workflow (038) has actually set institution_id
--
--   -- as an INDUSTRY or FACULTY caller: 0 rows (is_student(auth.uid()) is false)
--
--   -- as the owning INSTITUTION itself: unaffected -- its own pre-existing
--   -- policies (040/041/045/046) are untouched by this migration
-- ============================================================
