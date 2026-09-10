-- Migration: 052_student_achievements
-- Purpose: Phase 1N (portfolio) follow-up -- adds `student_achievements`,
-- a third portfolio-evidence resource (award / recognition / milestone)
-- alongside the existing portfolio_projects/portfolio_certifications
-- (025_portfolio_projects_and_certifications.sql). Not merged into
-- either existing table: an achievement has its own distinct shape
-- (achievement_date/issuing_organization, no technologies/github_url/
-- issuer/credential_url) and no shared query pattern with either.
--
-- Same historical-integrity boundary as 025's own header: an achievement
-- row is student-presented context, authored by the student, never
-- scored, never converted into skill evidence, never read by
-- compute_alignment()/application matching.
--
-- Same RLS ownership design as 025: no SECURITY DEFINER helper needed,
-- RLS's own symmetric USING/WITH CHECK on UPDATE already prevents
-- student_id reassignment for free (is_student() already exists, from
-- 003_skills.sql/013_harden_is_student.sql).
--
-- `create table if not exists` -- this table already exists in some
-- environments (created directly, ahead of this migration file
-- existing); this migration is what makes a fresh environment match,
-- exactly like every other `if not exists` migration in this project.

create table if not exists student_achievements (
  id uuid primary key default gen_random_uuid(),

  student_id uuid not null references profiles (id) on delete cascade,

  title text not null,
  description text,

  achievement_date date,
  issuing_organization text,
  url text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists student_achievements_student_id_idx
  on student_achievements (student_id);

alter table student_achievements enable row level security;

drop policy if exists "Students can view their own achievements" on student_achievements;
create policy "Students can view their own achievements"
  on student_achievements for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can add their own achievements" on student_achievements;
create policy "Students can add their own achievements"
  on student_achievements for insert
  to authenticated
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can update their own achievements" on student_achievements;
create policy "Students can update their own achievements"
  on student_achievements for update
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()))
  with check (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Students can delete their own achievements" on student_achievements;
create policy "Students can delete their own achievements"
  on student_achievements for delete
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop trigger if exists student_achievements_set_updated_at on student_achievements;
create trigger student_achievements_set_updated_at
  before update on student_achievements
  for each row
  execute procedure public.set_updated_at();

