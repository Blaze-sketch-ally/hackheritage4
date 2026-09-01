-- Migration: 029_collaboration_counterparty_names
-- Purpose: P1 release-hardening finding -- the Industry collaboration
-- list/detail views, and the Faculty/Institution incoming view, showed
-- only the recipient *type* ("Faculty" / "Institution"), never which
-- account. A reader could not tell who a proposal was from or to without
-- parsing the free-text description.
--
-- The missing piece is a DISPLAY NAME for the counterparty:
--   * Industry side  -> the FACULTY / INSTITUTION recipient's
--     profiles.full_name.
--   * Recipient side -> the INDUSTRY initiator's
--     industry_profiles.company_name (its profiles.full_name is the
--     fallback for an INDUSTRY account that has not filled in a company
--     profile yet -- 026 keys industry_id to profiles(id), not
--     industry_profiles(id), exactly so posting can happen first).
--
-- Why this needs a function rather than a plain join:
--   * industry_profiles is already readable by any authenticated user
--     (017: "Authenticated users can view industry profiles" USING
--     (true)) -- so the recipient side alone could be a join.
--   * profiles is NOT: its only SELECT policy is "Users can view their
--     own profile" (auth.uid() = id). A normal user-scoped client cannot
--     read the OTHER party's profiles.full_name at all. This is the same
--     wall resolve_collaboration_recipient() (026) climbs for the
--     create-form username lookup; this function is its read-side
--     counterpart, keyed by collaboration id.
--
-- This is a READ-ONLY helper. It creates NO table, changes NO column, and
-- touches NO RLS policy or trigger. It is additive and idempotent
-- (CREATE OR REPLACE).
--
-- Authorization: re-derived inside the function from auth.uid(). A row is
-- returned only when the caller's own visibility of that collaboration is
-- exactly what 026's two SELECT policies already grant:
--   * industry_id = auth.uid() AND is_industry(auth.uid())            -- owner
--   * OR recipient_id = auth.uid() AND status <> 'DRAFT'              -- recipient
--        AND ((recipient_type='FACULTY'      AND is_faculty(auth.uid()))
--          OR (recipient_type='INSTITUTION'  AND is_institution(auth.uid())))
-- -> the predicate is byte-identical to
--    "Industry can view their own collaborations" (027) UNION
--    "Recipients can view collaborations addressed to them" (026).
-- A caller asking for an id they are not party to (e.g. another tenant's
-- collaboration) simply gets no row back. No collaboration this function
-- can name is one the caller could not already GET through the API.
--
-- Exposure: only company_name / full_name -- the same minimal display
-- identity resolve_collaboration_recipient already returns, and (for
-- company_name) data every authenticated user can already read. No
-- email, phone, avatar, or any other profile column.
--
-- Hardened exactly like is_industry (017) / resolve_collaboration_recipient
-- (026): SECURITY DEFINER, pinned empty search_path, EXECUTE granted to
-- `authenticated` only, revoked from public and anon up front.
--
-- Idempotent: CREATE OR REPLACE + drop/re-grant, matching the convention
-- used throughout migrations 001-028.

create or replace function public.collaboration_counterparty_names(collaboration_ids uuid[])
returns table (
  collaboration_id uuid,
  industry_name text,
  recipient_name text
)
language sql
security definer
set search_path = ''
stable
as $$
  select
    c.id,
    coalesce(ip.company_name, ind.full_name) as industry_name,
    rec.full_name                            as recipient_name
  from public.industry_collaborations c
  left join public.industry_profiles ip  on ip.id  = c.industry_id
  left join public.profiles          ind on ind.id = c.industry_id
  left join public.profiles          rec on rec.id = c.recipient_id
  where c.id = any(collaboration_ids)
    and (
      (c.industry_id = auth.uid() and public.is_industry(auth.uid()))
      or (
        c.recipient_id = auth.uid()
        and c.status <> 'DRAFT'
        and (
          (c.recipient_type = 'FACULTY' and public.is_faculty(auth.uid()))
          or (c.recipient_type = 'INSTITUTION' and public.is_institution(auth.uid()))
        )
      )
    );
$$;

revoke all on function public.collaboration_counterparty_names(uuid[]) from public;
revoke all on function public.collaboration_counterparty_names(uuid[]) from anon;
grant execute on function public.collaboration_counterparty_names(uuid[]) to authenticated;

-- ============================================================
-- Post-conditions (for reviewers / a live check after `supabase db push`):
--
--   -- as an INDUSTRY owner: returns its own collaborations' names
--   select * from public.collaboration_counterparty_names(
--     array(select id from public.industry_collaborations where industry_id = auth.uid())
--   );
--
--   -- as any caller, for a collaboration they are NOT party to: 0 rows
--   select * from public.collaboration_counterparty_names(array['<other-tenant-collab-id>'::uuid]);
--
--   -- as a recipient: only non-DRAFT rows addressed to them resolve
-- ============================================================
