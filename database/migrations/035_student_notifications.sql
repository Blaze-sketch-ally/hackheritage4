-- Migration: 035_student_notifications
-- Purpose: the DATABASE FOUNDATION for the Student Notifications MVP
-- (Phase S6) -- per-student, in-app notification records that represent
-- real portal events (an application status change, an interview being
-- scheduled, an assessment result, a learning milestone, ...).
--
-- The Notifications feature's numbered placeholder was 010_notifications.sql
-- (never given DDL, "Not implemented yet"). Following the same
-- "placeholder superseded by a later real migration" pattern used for
-- 005/006 -> 018/019, 007 -> 033, and 008 -> 034, that placeholder is
-- NOT edited here -- this is the real schema, numbered after this
-- branch's current tip (034).
--
-- ============================================================
-- Scope: STORAGE + STUDENT CONSUMPTION ONLY
-- ============================================================
-- S6 delivers the table, its RLS, and a secure Student read/mark-read
-- API. It deliberately ships NO producer integration: no existing
-- feature (applications, assessments, learning, events, mentorship,
-- interviews) is modified to emit notification rows in this phase.
-- Producer wiring is a system-context concern (writes happen with the
-- service role, from trusted backend code / triggers) and is explicitly
-- deferred to a later integration phase. Until then this table is
-- correctly empty and the UI shows an honest "No notifications yet."
--
-- ============================================================
-- Creation model: SYSTEM-ONLY inserts
-- ============================================================
-- There is intentionally NO insert policy. With RLS enabled and no
-- permissive INSERT policy, NO authenticated user -- student or otherwise
-- -- can create a row. Notifications are only ever written by trusted
-- backend code using the service role (which bypasses RLS). This is the
-- structural guarantee that a student cannot fabricate a notification,
-- address one to another student, or forge its type/title/body.
--
-- ============================================================
-- Mutation model: a student may only toggle their own read state
-- ============================================================
-- The single UPDATE policy lets the recipient update their own row, and
-- a BEFORE UPDATE trigger (student_notifications_freeze_content) rejects
-- any change to a column other than read_at -- so "mark read / mark
-- unread" is the only mutation a student can perform, and title / body /
-- type / student_id / related_* / created_at are immutable to them even
-- through a raw authenticated client. There is NO delete policy: a
-- student cannot delete notifications.
--
-- ============================================================
-- Conventions reused from existing migrations
-- ============================================================
-- * uuid PK: `id uuid primary key default gen_random_uuid()` (003/004/033/034)
-- * created_at timestamptz not null default now() (all)
-- * Student-owned table: `student_id uuid not null references profiles(id)
--   on delete cascade`, ownership predicate
--   `auth.uid() = student_id and public.is_student(auth.uid())`
--   (identical shape to student_projects / student_certifications in 034).
-- * public.is_student(uuid) -- the SECURITY DEFINER role check from
--   012/013, used, never redefined.
-- * Idempotent in shape: create table if not exists, create index if not
--   exists, drop policy/trigger/function if exists + create. Forward-only,
--   additive, non-destructive: no DROP TABLE, no destructive ALTER, no
--   change to any existing table, policy, trigger, or function.
--
-- There is NO updated_at column: a notification's content is immutable
-- once written; `read_at` is the only mutable field and it carries its
-- own timestamp. So public.set_updated_at() is deliberately NOT attached.
--
-- No seed data -- notifications are produced by the running system, never
-- pre-populated.

create table if not exists student_notifications (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,

  -- Finite, server-validated vocabulary. Mirrored in
  -- backend/app/schemas/student_notification.py. SYSTEM covers portal-wide
  -- announcements and anything without a more specific category.
  type text not null check (type in (
    'APPLICATION_STATUS',
    'INTERVIEW',
    'ASSESSMENT',
    'LEARNING',
    'MENTORSHIP',
    'EVENT',
    'SYSTEM'
  )),

  title text not null,
  body text not null,

  -- Optional pointer to the entity this notification is about, so the UI
  -- can offer a "view" link. Only a known type -> known Student route
  -- mapping is ever followed by the frontend; an unknown/missing value
  -- renders the notification as non-navigable.
  related_entity_type text check (related_entity_type in (
    'APPLICATION',
    'INTERVIEW',
    'ASSESSMENT',
    'LEARNING_RESOURCE',
    'MENTORSHIP',
    'EVENT'
  )),
  related_entity_id uuid,

  -- NULL = unread. Set once when the recipient marks it read; cleared
  -- again on "mark unread". Never set by an insert.
  read_at timestamptz,

  created_at timestamptz not null default now(),

  -- A pointer is all-or-nothing: either both parts are present or neither.
  constraint student_notifications_related_entity_paired
    check ((related_entity_type is null) = (related_entity_id is null))
);

-- The list query: a student's own notifications, newest first.
create index if not exists student_notifications_student_created_idx
  on student_notifications (student_id, created_at desc);

-- The unread-count / "Unread" filter query.
create index if not exists student_notifications_unread_idx
  on student_notifications (student_id)
  where read_at is null;

alter table student_notifications enable row level security;

-- Read: recipient only.
drop policy if exists "Students can view their own notifications" on student_notifications;
create policy "Students can view their own notifications"
  on student_notifications for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

-- Update: recipient only, and the freeze trigger below restricts it to
-- read_at. No INSERT policy (system-only writes) and no DELETE policy
-- (students cannot delete) -- both omissions are deliberate.
drop policy if exists "Students can mark their own notifications read" on student_notifications;
create policy "Students can mark their own notifications read"
  on student_notifications for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

-- Defence in depth: even though the Student API only ever writes read_at,
-- a raw authenticated client holding the student's token could otherwise
-- rewrite title/body/type/related_*/created_at on its own row. This
-- trigger makes read_at the ONLY column a student update may change.
-- Same "raise exception on a forbidden change" pattern, and the same
-- service_role step-aside, as 002/023/032's role guards -- so trusted
-- system-context writes (a future producer that needs to amend a row)
-- are unaffected.
create or replace function public.enforce_student_notification_immutability()
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
     or new.student_id is distinct from old.student_id
     or new.type is distinct from old.type
     or new.title is distinct from old.title
     or new.body is distinct from old.body
     or new.related_entity_type is distinct from old.related_entity_type
     or new.related_entity_id is distinct from old.related_entity_id
     or new.created_at is distinct from old.created_at then
    raise exception 'Only the read state of a notification can be changed.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_student_notification_immutability() from public;

drop trigger if exists student_notifications_enforce_immutability on student_notifications;
create trigger student_notifications_enforce_immutability
  before update on student_notifications
  for each row
  execute procedure public.enforce_student_notification_immutability();
