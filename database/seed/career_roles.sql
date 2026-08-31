-- Seed data: initial career-role catalog + required skills (Phase 1L).
-- Populates public.career_roles and public.career_role_skill_requirements
-- (schema: database/migrations/022_career_roles_skill_gap.sql).
--
-- Follows the exact idiom database/seed/skills_fixed.sql already
-- established: plain INSERT ... SELECT ... FROM (VALUES ...), every
-- foreign key resolved by NAME via a scalar subquery (never a
-- hard-coded UUID), and ON CONFLICT DO NOTHING relying on this table's
-- own unique constraints for idempotency -- safe to re-run.
--
-- Every skill named below is a REAL row from database/seed/skills_fixed.sql
-- (21 categories / 114 skills) -- no new skill is invented here. If a
-- name below doesn't exactly match an existing skill, the scalar
-- subquery returns NULL and the insert fails loudly against
-- career_role_skill_requirements.skill_id's NOT NULL constraint --
-- deliberately, so a typo here is caught immediately rather than silently
-- seeding a broken requirement.
--
-- required_level/weight are deterministic, hand-chosen values (not
-- random) -- required_level uses the same 0-100 scale as
-- assessment_attempts.percentage (see "Skill Evidence Boundary" in
-- docs/architecture/assessment-lifecycle.md); weight is relative
-- importance within one role, primary skills weighted higher than
-- supporting ones.

-- ============================================================
-- STEP 1 -- Career roles
-- ============================================================

INSERT INTO public.career_roles (title, description, category)
VALUES
  ('Software Engineer', 'Builds and maintains general-purpose backend and full-stack applications.', 'Engineering'),
  ('Frontend Developer', 'Builds user-facing web interfaces and client-side applications.', 'Engineering'),
  ('Backend Developer', 'Builds server-side APIs, services, and data-backed systems.', 'Engineering'),
  ('Data Analyst', 'Analyzes data to produce reports and inform business decisions.', 'Data'),
  ('Data Scientist', 'Builds statistical and machine-learning models from data.', 'Data'),
  ('Cloud Engineer', 'Designs, deploys, and operates cloud infrastructure.', 'Infrastructure')
ON CONFLICT DO NOTHING;

-- ============================================================
-- STEP 2 -- Required skills per role
-- ============================================================

-- Software Engineer
INSERT INTO public.career_role_skill_requirements
    (career_role_id, skill_id, required_level, weight)
SELECT
    (SELECT id FROM public.career_roles WHERE lower(title) = lower('Software Engineer') LIMIT 1),
    (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1),
    v.required_level,
    v.weight
FROM (
    VALUES
      ('Python', 75.0, 1.5),
      ('SQL', 65.0, 1.0),
      ('Git', 60.0, 1.0),
      ('JavaScript', 60.0, 1.0),
      ('Docker', 55.0, 0.75),
      ('Problem Solving', 65.0, 0.75)
) AS v(skill_name, required_level, weight)
ON CONFLICT DO NOTHING;

-- Frontend Developer
INSERT INTO public.career_role_skill_requirements
    (career_role_id, skill_id, required_level, weight)
SELECT
    (SELECT id FROM public.career_roles WHERE lower(title) = lower('Frontend Developer') LIMIT 1),
    (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1),
    v.required_level,
    v.weight
FROM (
    VALUES
      ('JavaScript', 75.0, 1.5),
      ('TypeScript', 65.0, 1.0),
      ('React', 75.0, 1.5),
      ('HTML', 60.0, 0.75),
      ('CSS', 60.0, 0.75),
      ('Next.js', 60.0, 1.0),
      ('Git', 55.0, 0.5)
) AS v(skill_name, required_level, weight)
ON CONFLICT DO NOTHING;

-- Backend Developer
INSERT INTO public.career_role_skill_requirements
    (career_role_id, skill_id, required_level, weight)
SELECT
    (SELECT id FROM public.career_roles WHERE lower(title) = lower('Backend Developer') LIMIT 1),
    (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1),
    v.required_level,
    v.weight
FROM (
    VALUES
      ('Python', 70.0, 1.5),
      ('SQL', 70.0, 1.5),
      ('FastAPI', 65.0, 1.0),
      ('PostgreSQL', 60.0, 1.0),
      ('Docker', 55.0, 0.75),
      ('Git', 55.0, 0.5)
) AS v(skill_name, required_level, weight)
ON CONFLICT DO NOTHING;

-- Data Analyst
INSERT INTO public.career_role_skill_requirements
    (career_role_id, skill_id, required_level, weight)
SELECT
    (SELECT id FROM public.career_roles WHERE lower(title) = lower('Data Analyst') LIMIT 1),
    (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1),
    v.required_level,
    v.weight
FROM (
    VALUES
      ('SQL', 75.0, 1.5),
      ('Python', 65.0, 1.0),
      ('Data Analysis', 75.0, 1.5),
      ('Pandas', 60.0, 1.0),
      ('Power BI', 55.0, 0.75),
      ('Communication', 55.0, 0.5)
) AS v(skill_name, required_level, weight)
ON CONFLICT DO NOTHING;

-- Data Scientist
INSERT INTO public.career_role_skill_requirements
    (career_role_id, skill_id, required_level, weight)
SELECT
    (SELECT id FROM public.career_roles WHERE lower(title) = lower('Data Scientist') LIMIT 1),
    (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1),
    v.required_level,
    v.weight
FROM (
    VALUES
      ('Python', 75.0, 1.5),
      ('Machine Learning', 70.0, 1.5),
      ('Pandas', 65.0, 1.0),
      ('NumPy', 60.0, 1.0),
      ('SQL', 60.0, 1.0),
      ('Scikit-learn', 55.0, 0.75)
) AS v(skill_name, required_level, weight)
ON CONFLICT DO NOTHING;

-- Cloud Engineer
INSERT INTO public.career_role_skill_requirements
    (career_role_id, skill_id, required_level, weight)
SELECT
    (SELECT id FROM public.career_roles WHERE lower(title) = lower('Cloud Engineer') LIMIT 1),
    (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1),
    v.required_level,
    v.weight
FROM (
    VALUES
      ('AWS', 75.0, 1.5),
      ('Docker', 70.0, 1.5),
      ('Kubernetes', 65.0, 1.5),
      ('Linux', 60.0, 1.0),
      ('CI/CD', 55.0, 0.75),
      ('Git', 50.0, 0.5)
) AS v(skill_name, required_level, weight)
ON CONFLICT DO NOTHING;
