-- Migration: 058_student_notifications_workshop_project
-- Purpose: widen `student_notifications.related_entity_type` so a Student
-- can be notified when the owning Industry account accepts/rejects a
-- Workshop application or shortlists/selects/rejects a Project
-- application (056_workshop_applications.sql /
-- 057_project_applications.sql), reusing the existing
-- 'APPLICATION_STATUS' `type` value -- these are exactly that: a status
-- change on the student's own application.
--
-- Same additive, forward-only, non-destructive CHECK-widening shape as
-- 039_institution_student_directory.sql / 052_job_training.sql used for
-- this exact table: read the real (Postgres-auto-named) constraint name
-- from the catalog, drop it, re-add it with two more allowed values.
-- Every existing row still satisfies the widened constraint.
--
-- related_entity_id for these two new values is the WORKSHOP / PROJECT
-- posting id (industry_workshops.id / industry_projects.id) -- not the
-- application row -- so the frontend can link straight to
-- /student/workshops/{id} or /student/industry-projects/{id}. This
-- mirrors the same choice made for industry_notifications
-- (055_industry_notifications.sql).

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
    'WORKSHOP', 'PROJECT'
  ));
