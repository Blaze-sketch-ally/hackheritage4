-- Migration: 066_faculty_notifications
-- Purpose: the DATABASE FOUNDATION for the Faculty Notification system --
-- per-faculty, in-app notification records that represent real portal
-- events (an evaluator assignment, an evaluator revocation, a question
-- review decision, a mentorship request/status change).
--
-- ============================================================
-- Reuse, not duplication
-- ============================================================
-- database/migrations/059_student_notifications.sql already solved this
-- exact problem for Students -- storage, RLS, read/unread semantics,
-- immutability -- but that table is Student-scoped by design
-- (`student_id` column, `public.is_student()` predicate) and cannot be
-- widened to a generic recipient without either a schema change to an
-- already-live table (risking that verified system) or a role column
-- that would let RLS accidentally leak one role's notifications to
-- another if a policy predicate were ever written wrong. Consistent with
-- this project's own established precedent of a SEPARATE, parallel table
-- per distinct owning role rather than one shared table with a
-- discriminator (e.g. faculty_student_mentorships vs.
-- student_mentorship_opportunities, or this project's per-role dashboard/
-- recommendation services), this migration creates a second table with
-- the identical shape/semantics, scoped to `faculty_id` and
-- `public.is_faculty()` instead. Every structural decision below
-- (columns, constraint pairing, indexes, RLS shape, immutability
-- trigger) mirrors 059 line-for-line on purpose -- see that migration's
-- own header for the full reasoning, not repeated here.
--
-- ============================================================
-- Scope: STORAGE + FACULTY CONSUMPTION + PRODUCER INTEGRATION
-- ============================================================
-- Unlike 059 (which explicitly deferred producer wiring to "a later
-- integration phase"), this phase DOES wire real producers
-- (app.services.faculty_notification_producer) into the four event
-- sources the Faculty Notification System audit found genuine, single-
-- recipient event data for: evaluator assignment, evaluator revocation,
-- a review decision (approve/reject), and a mentorship request/status
-- change initiated by the student side. See that module's own docstring
-- for the exact call sites and the reasoning for why each one is safe to
-- call at most once per real event.
--
-- ============================================================
-- Idempotency: two layers, matching this project's "defense in depth"
-- convention (an app-layer guarantee backed by a DB-level constraint)
-- ============================================================
-- Layer 1 (primary): every producer is invoked from the exact backend
-- code path that performs a one-time state transition already guarded by
-- an existing uniqueness constraint or state-machine check (evaluator
-- assignment creation raises 23505 on a genuine duplicate; assignment
-- revocation raises 55000 if already revoked; a review decision raises
-- 55000/409 if the question is no longer PENDING; a mentorship request
-- raises 23505 on a duplicate pair; a mentorship status transition is
-- rejected if the row is no longer in the required FROM state). A
-- retried/duplicated client request therefore fails the underlying
-- action itself before the producer call is ever reached a second time --
-- exactly the same reasoning app.services.notification_producer's own
-- functions already document (e.g. emit_internship_completed: "the
-- caller invokes this exactly once... never on a repeated/idempotent
-- verify").
--
-- Layer 2 (belt-and-suspenders, new in this migration): `dedupe_key`, a
-- nullable text column carrying a deterministic identifier for the
-- specific event instance (e.g. 'eval_assigned:<assignment_id>',
-- 'mentorship_status:<mentorship_id>:<new_status>'), enforced unique per
-- faculty_id via a partial unique index below. This is what makes the
-- guarantee a real constraint the database enforces under concurrent
-- writes, not merely an "if not exists then insert" race in application
-- code -- if Layer 1 is ever somehow bypassed (a future code path calls
-- a producer function without going through a guarded transition), the
-- second insert attempt fails on this constraint instead of creating a
-- duplicate row. Producers catch and swallow that failure (best-effort,
-- matching notification_producer.py's own contract) rather than
-- propagating it.
--
-- ============================================================
-- Creation model: SYSTEM-ONLY inserts (identical to 059)
-- ============================================================
-- No INSERT policy exists. With RLS enabled and no permissive INSERT
-- policy, no authenticated user -- Faculty or otherwise -- can create a
-- row. Notifications are only ever written by trusted backend code using
-- the service role (which bypasses RLS), exactly like 059's own
-- reasoning: this is what makes "a Faculty user cannot fabricate a
-- notification, address one to another Faculty member, or forge its
-- type/title/body" a structural guarantee, not an application convention.
--
-- ============================================================
-- Mutation model: a Faculty member may only toggle their own read state
-- ============================================================
-- Identical to 059: the single UPDATE policy lets the recipient update
-- their own row, and a BEFORE UPDATE trigger
-- (faculty_notifications_enforce_immutability) rejects any change to a
-- column other than read_at. There is no DELETE policy.
--
-- ============================================================
-- Conventions reused from existing migrations
-- ============================================================
-- * uuid PK, created_at timestamptz default now(), Faculty-owned FK with
--   on delete cascade + ownership predicate `auth.uid() = faculty_id and
--   public.is_faculty(auth.uid())` -- same shape as every other
--   Faculty-owned table in this project (faculty_profiles,
--   faculty_student_mentorships).
-- * public.is_faculty(uuid) -- the existing SECURITY DEFINER role check
--   (015/032), used, never redefined.
-- * Idempotent DDL: create table if not exists, create index if not
--   exists, drop policy/trigger/function if exists + create. Forward-
--   only, additive, non-destructive -- no DROP TABLE, no destructive
--   ALTER, no change to any existing table, policy, trigger, or function
--   (059/065 and everything before them are untouched by this file).
--
-- No seed data -- notifications are produced by the running system.

create table if not exists faculty_notifications (
  id uuid primary key default gen_random_uuid(),

  faculty_id uuid not null references profiles (id) on delete cascade,

  -- Finite, server-validated vocabulary. Mirrored in
  -- backend/app/schemas/faculty_notification.py. Only types with a real,
  -- single-recipient event source (see this migration's own header and
  -- the Faculty Notification System audit report) are included --
  -- deliberately no generic SYSTEM bucket, since nothing emits one yet;
  -- widening this CHECK later (the same "062 widens 059's CHECK" pattern)
  -- is a small additive migration whenever a real new event source is
  -- built, not something to speculatively include now.
  type text not null check (type in (
    'EVALUATION_ASSIGNED',
    'EVALUATION_REVOKED',
    'REVIEW_DECISION',
    'MENTORSHIP'
  )),

  title text not null,
  body text not null,

  -- Optional pointer to the entity this notification is about, so the UI
  -- can offer a "view" link -- same all-or-nothing pairing as 059.
  related_entity_type text check (related_entity_type in (
    'QUESTION',
    'EVALUATION',
    'MENTORSHIP'
  )),
  related_entity_id uuid,

  -- Belt-and-suspenders idempotency (see this migration's own header,
  -- "Idempotency" section, Layer 2). Null for any future producer that
  -- doesn't need it; the partial unique index below only constrains rows
  -- that set it.
  dedupe_key text,

  -- NULL = unread. Set once when the recipient marks it read; cleared
  -- again on "mark unread". Never set by an insert.
  read_at timestamptz,

  created_at timestamptz not null default now(),

  constraint faculty_notifications_related_entity_paired
    check ((related_entity_type is null) = (related_entity_id is null))
);

-- The list query: a faculty member's own notifications, newest first.
create index if not exists faculty_notifications_faculty_created_idx
  on faculty_notifications (faculty_id, created_at desc);

-- The unread-count / "Unread" filter query.
create index if not exists faculty_notifications_unread_idx
  on faculty_notifications (faculty_id)
  where read_at is null;

-- Idempotency Layer 2 (see header): at most one notification per
-- (faculty_id, dedupe_key) when a producer chooses to set one.
create unique index if not exists faculty_notifications_dedupe_idx
  on faculty_notifications (faculty_id, dedupe_key)
  where dedupe_key is not null;

alter table faculty_notifications enable row level security;

-- Read: recipient only.
drop policy if exists "Faculty can view their own notifications" on faculty_notifications;
create policy "Faculty can view their own notifications"
  on faculty_notifications for select
  to authenticated
  using (auth.uid() = faculty_id and public.is_faculty(auth.uid()));

-- Update: recipient only, and the freeze trigger below restricts it to
-- read_at. No INSERT policy (system-only writes) and no DELETE policy
-- (Faculty cannot delete) -- both omissions are deliberate, mirroring 059.
drop policy if exists "Faculty can mark their own notifications read" on faculty_notifications;
create policy "Faculty can mark their own notifications read"
  on faculty_notifications for update
  to authenticated
  using (auth.uid() = faculty_id and public.is_faculty(auth.uid()))
  with check (auth.uid() = faculty_id and public.is_faculty(auth.uid()));

-- Defence in depth: even though the Faculty API only ever writes
-- read_at, a raw authenticated client holding the Faculty member's token
-- could otherwise rewrite title/body/type/related_*/created_at on its
-- own row. This trigger makes read_at the ONLY column a Faculty update
-- may change -- identical pattern to
-- public.enforce_student_notification_immutability() (059).
create or replace function public.enforce_faculty_notification_immutability()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.id is distinct from old.id
     or new.faculty_id is distinct from old.faculty_id
     or new.type is distinct from old.type
     or new.title is distinct from old.title
     or new.body is distinct from old.body
     or new.related_entity_type is distinct from old.related_entity_type
     or new.related_entity_id is distinct from old.related_entity_id
     or new.dedupe_key is distinct from old.dedupe_key
     or new.created_at is distinct from old.created_at then
    raise exception 'Only the read state of a notification can be changed.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_faculty_notification_immutability() from public;

drop trigger if exists faculty_notifications_enforce_immutability on faculty_notifications;
create trigger faculty_notifications_enforce_immutability
  before update on faculty_notifications
  for each row
  execute procedure public.enforce_faculty_notification_immutability();
