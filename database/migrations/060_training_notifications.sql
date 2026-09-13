-- Migration: 060_training_notifications
-- Purpose: widen `industry_notifications.related_entity_type` (055) to add
-- 'TRAINING_APPLICATION' and `student_notifications.related_entity_type`
-- (035, already widened by 039/052/058) to add 'TRAINING', so the Training
-- application pipeline (059_training_applications.sql) can notify both
-- sides exactly like Workshop/Project already do (058). Same additive,
-- forward-only, non-destructive CHECK-widening shape as 058.

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
    'WORKSHOP_APPLICATION', 'TRAINING_APPLICATION'
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
    'WORKSHOP', 'PROJECT', 'TRAINING'
  ));
