-- Migration: 055_industry_notifications
-- Purpose: the INDUSTRY-side mirror of `student_notifications`
-- (035_student_notifications.sql) -- per-industry-account, in-app
-- notification records for events an Industry user needs to react to
-- (a new application to one of their postings, a candidate withdrawing).
--
-- Until this migration there was NO Industry notification storage at all
-- -- not a bug fix, a net-new feature built on the exact same shape as
-- the Student table so both sides share one mental model:
--   * SYSTEM-ONLY inserts: no INSERT policy: only trusted backend code
--     (service_role, via notification_producer.py) can create a row.
--   * The only mutation an Industry account can make is toggling its own
--     `read_at` -- enforced by a BEFORE UPDATE freeze trigger identical in
--     spirit to `enforce_student_notification_immutability`.
--   * No DELETE policy.
--
-- related_entity_id deliberately points at the POSTING (internship_id /
-- job_id / industry_projects.id / industry_workshops.id) rather than the
-- application row -- Industry's action from a notification is "go look at
-- who applied to X", i.e. the applicants view for that posting, not one
-- specific applicant. This mirrors the product requirement: clicking a
-- new-Project-application notification opens that Project's applicants
-- view, and clicking a new-Workshop-application notification opens that
-- Workshop's applicants view.
--
-- No seed data -- notifications are produced by the running system.

create table if not exists industry_notifications (
  id uuid primary key default gen_random_uuid(),

  industry_id uuid not null references profiles (id) on delete cascade,

  -- Finite, server-validated vocabulary, mirrored in
  -- backend/app/schemas/industry_notification.py.
  type text not null check (type in (
    'NEW_APPLICATION',
    'WITHDRAWAL',
    'SYSTEM'
  )),

  title text not null,
  body text not null,

  -- Points at the POSTING the application belongs to (see module note
  -- above) -- not the application row.
  related_entity_type text check (related_entity_type in (
    'INTERNSHIP_APPLICATION',
    'JOB_APPLICATION',
    'PROJECT_APPLICATION',
    'WORKSHOP_APPLICATION'
  )),
  related_entity_id uuid,

  -- NULL = unread. Set once when the recipient marks it read; cleared
  -- again on "mark unread". Never set by an insert.
  read_at timestamptz,

  created_at timestamptz not null default now(),

  constraint industry_notifications_related_entity_paired
    check ((related_entity_type is null) = (related_entity_id is null))
);

-- The list query: an industry account's own notifications, newest first.
create index if not exists industry_notifications_industry_created_idx
  on industry_notifications (industry_id, created_at desc);

-- The unread-count / "Unread" filter query.
create index if not exists industry_notifications_unread_idx
  on industry_notifications (industry_id)
  where read_at is null;

alter table industry_notifications enable row level security;

-- Read: recipient only.
drop policy if exists "Industry can view their own notifications" on industry_notifications;
create policy "Industry can view their own notifications"
  on industry_notifications for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- Update: recipient only, and the freeze trigger below restricts it to
-- read_at. No INSERT policy (system-only writes) and no DELETE policy.
drop policy if exists "Industry can mark their own notifications read" on industry_notifications;
create policy "Industry can mark their own notifications read"
  on industry_notifications for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- Same immutability guard as student_notifications_enforce_immutability:
-- makes read_at the ONLY column an Industry update may change, even
-- through a raw authenticated client. service_role steps aside so a
-- future producer amendment is unaffected.
create or replace function public.enforce_industry_notification_immutability()
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
     or new.industry_id is distinct from old.industry_id
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

revoke all on function public.enforce_industry_notification_immutability() from public;

drop trigger if exists industry_notifications_enforce_immutability on industry_notifications;
create trigger industry_notifications_enforce_immutability
  before update on industry_notifications
  for each row
  execute procedure public.enforce_industry_notification_immutability();
