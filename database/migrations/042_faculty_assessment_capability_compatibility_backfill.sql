-- Migration: 042_faculty_assessment_capability_compatibility_backfill
-- Purpose: Phase F5A -- a ONE-TIME compatibility backfill, run immediately
-- after 041_assessment_capability_authorization.sql narrows question-bank/
-- review/blueprint authorization from "any FACULTY account" to
-- "FACULTY account that also holds assessment_author/assessment_reviewer".
--
-- RATIONALE (why this migration exists at all):
-- Before 041, every FACULTY account could author, edit, and peer-review
-- questions, and manage blueprints -- there was no capability gate at
-- all (only the bare FACULTY role, since 015/017/018/019). Existing
-- Faculty users who were already relying on this -- real accounts with
-- real question-bank history -- must not be silently locked out of
-- functionality they already had the moment 041 is applied. This
-- migration grants assessment_author and assessment_reviewer to every
-- FACULTY profile that exists AT THE MOMENT THIS MIGRATION RUNS, so
-- their existing capability is preserved across the transition to
-- explicit capability governance.
--
-- THIS IS A TRANSITION MECHANISM, NOT A PERMANENT POLICY:
--   - This is a plain one-time INSERT ... SELECT over the CURRENT
--     contents of `profiles`. It is not a trigger, not a function, and
--     creates no ongoing behavior. A FACULTY account created AFTER this
--     migration runs receives NEITHER capability automatically -- their
--     first assessment_author/assessment_reviewer grant must come from
--     an ADMIN via admin_grant_assessment_capability()
--     (035_admin_faculty_permission_management.sql), exactly like any
--     other capability grant from this point forward.
--   - `granted_by` and `status_changed_by` are left NULL for every
--     backfilled row -- there is no acting ADMIN for a system migration,
--     and NULL here is truthfully "no human admin granted this," not a
--     forged identity. Both columns already allow NULL
--     (`references profiles(id) on delete set null`, 027) specifically
--     to represent this case.
--   - `on conflict (faculty_id, capability) do nothing`: this backfill
--     NEVER overwrites an existing permission row. If an ADMIN had
--     already explicitly granted, suspended, or revoked either
--     capability for some Faculty member before this migration runs
--     (e.g. during a staged rollout), that explicit decision is left
--     completely untouched -- this migration only fills in accounts that
--     have no row for a given capability at all.
--   - Suspending or revoking a backfilled grant afterward works
--     identically to any other grant -- admin_set_assessment_permission_
--     status() (035) governs it the same way, and the newly-activated
--     RLS/RPC checks (041) immediately respect that status change, same
--     as for any explicitly-granted capability.
--
-- Deliberately NOT backfilled: assessment_evaluator, assessment_moderator,
-- assessment_lead. Those three were dormant before 041 and remain
-- dormant after it -- no existing Faculty behavior depended on them, so
-- there is nothing to preserve compatibility for. They remain fully
-- reserved for F8 (evaluation) and F10 (governance).

insert into public.faculty_assessment_permissions (faculty_id, capability, status)
select p.id, cap.capability, 'GRANTED'
from public.profiles p
cross join (
  values ('assessment_author'::public.assessment_capability),
         ('assessment_reviewer'::public.assessment_capability)
) as cap(capability)
where p.role = 'FACULTY'
on conflict (faculty_id, capability) do nothing;
