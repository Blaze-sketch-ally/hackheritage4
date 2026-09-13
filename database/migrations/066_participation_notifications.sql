-- Migration: 066_participation_notifications
-- Purpose: widen `student_notifications.type` / `.related_entity_type`
-- (035, already widened by 039/052/058/060) and
-- `industry_notifications.related_entity_type` (055, widened by 060) so
-- the Participation Workspace domain (062-065) can notify both sides
-- through the existing notification architecture -- same additive,
-- forward-only CHECK-widening shape as 058/060.
--
-- New values:
--   student_notifications.type: + 'PARTICIPATION'
--   student_notifications.related_entity_type: + 'PARTICIPATION_WORKSPACE'
--     (id = participation_workspaces.id -- links to
--     /student/.../workspace)
--   industry_notifications.related_entity_type: + 'PARTICIPATION_WORKSPACE'
--     (id = participation_workspaces.id -- links to the Industry
--     participant view for that workspace)
--
-- No new `type` value is added to industry_notifications: 'NEW_APPLICATION'
-- already fits "a student submitted/resubmitted an assignment" well enough
-- (it is, structurally, new work arriving for Industry to look at), so
-- reusing it avoids growing that vocabulary for no real behavioural gain.

do $$
declare
  v_name text;
begin
  select con.conname into v_name
  from pg_constraint con
  join pg_attribute att
    on att.attrelid = con.conrelid and att.attnum = con.conkey[1]
  where con.conrelid = 'public.student_notifications'::regclass
    and con.contype = 'c'
    and array_length(con.conkey, 1) = 1
    and att.attname = 'type';

  if v_name is not null then
    execute format('alter table public.student_notifications drop constraint %I', v_name);
  end if;
end $$;

alter table public.student_notifications
  add constraint student_notifications_type_check
  check (type in (
    'APPLICATION_STATUS', 'INTERVIEW', 'ASSESSMENT', 'LEARNING',
    'MENTORSHIP', 'EVENT', 'SYSTEM', 'INTERNSHIP', 'JOB_TRAINING',
    'PARTICIPATION'
  ));

do $$
declare
  v_name text;
begin
  select con.conname into v_name
  from pg_constraint con
  join pg_attribute att
    on att.attrelid = con.conrelid and att.attnum = con.conkey[1]
  where con.conrelid = 'public.student_notifications'::regclass
    and con.contype = 'c'
    and array_length(con.conkey, 1) = 1
    and att.attname = 'related_entity_type';

  if v_name is not null then
    execute format('alter table public.student_notifications drop constraint %I', v_name);
  end if;
end $$;

alter table public.student_notifications
  add constraint student_notifications_related_entity_type_check
  check (related_entity_type in (
    'APPLICATION', 'INTERVIEW', 'ASSESSMENT', 'LEARNING_RESOURCE',
    'MENTORSHIP', 'EVENT', 'INTERNSHIP_WORKSPACE', 'JOB_TRAINING_ENROLLMENT',
    'WORKSHOP', 'PROJECT', 'TRAINING', 'PARTICIPATION_WORKSPACE'
  ));

do $$
declare
  v_name text;
begin
  select con.conname into v_name
  from pg_constraint con
  join pg_attribute att
    on att.attrelid = con.conrelid and att.attnum = con.conkey[1]
  where con.conrelid = 'public.industry_notifications'::regclass
    and con.contype = 'c'
    and array_length(con.conkey, 1) = 1
    and att.attname = 'related_entity_type';

  if v_name is not null then
    execute format('alter table public.industry_notifications drop constraint %I', v_name);
  end if;
end $$;

alter table public.industry_notifications
  add constraint industry_notifications_related_entity_type_check
  check (related_entity_type in (
    'INTERNSHIP_APPLICATION', 'JOB_APPLICATION', 'PROJECT_APPLICATION',
    'WORKSHOP_APPLICATION', 'TRAINING_APPLICATION', 'PARTICIPATION_WORKSPACE'
  ));
