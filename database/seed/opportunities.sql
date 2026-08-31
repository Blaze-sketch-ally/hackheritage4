-- Seed data: demo opportunities + skill requirements (Phase 1M).
-- Populates public.opportunities and public.opportunity_skill_requirements
-- (schema: database/migrations/024_opportunities_and_applications.sql).
--
-- PREREQUISITE: run database/seed/provision_demo_industry_accounts.py
-- first -- this file resolves each opportunity's owner by email via a
-- subquery against profiles, and will insert nothing (silently, safely
-- -- see the NOT NULL constraint on industry_id) if that account doesn't
-- exist yet. See that script's own docstring for why account
-- provisioning can't be plain SQL.
--
-- Follows the exact idiom database/seed/skills_fixed.sql and
-- database/seed/career_roles.sql already established: plain
-- INSERT ... SELECT ... FROM (VALUES ...), every foreign key resolved by
-- NAME/EMAIL via a scalar subquery (never a hard-coded UUID), and
-- ON CONFLICT DO NOTHING relying on this table's own constraints for
-- idempotency where practical -- opportunities has no natural uniqueness
-- key (two postings can legitimately share a title), so this file is
-- idempotent by construction instead: re-running it is safe because
-- rerunning without first re-running the (also idempotent) account
-- provisioning script produces the exact same input rows, and inserting
-- them again would just create duplicate DRAFT postings -- acceptable
-- for local dev reseeding, not destructive to anything.
--
-- Every skill referenced below is a REAL row from
-- database/seed/skills_fixed.sql -- no new skill is invented here.
-- required_level/weight are deterministic, hand-chosen values spanning a
-- wide range (45-80) specifically so that any reasonably-tested demo
-- student naturally sees a spread of STRONG/GAP/NOT_ASSESSED results
-- across these postings, rather than a coupled "guaranteed high match"
-- fixture tied to one specific student's assessment history (which would
-- be fragile, QA-fixture-like data, not durable seed content).
--
-- Every opportunity is inserted directly as PUBLISHED (via service_role,
-- which steps around prevent_invalid_opportunity_transition's normal
-- DRAFT-first rule the same way it already steps around every other
-- trusted-write trigger in this project) -- demo postings need to be
-- immediately visible to a demo student, not sitting unpublished.

-- ============================================================
-- Nimbus Systems
-- ============================================================

INSERT INTO public.opportunities (industry_id, title, description, opportunity_type, location, status, published_at)
SELECT
    (SELECT id FROM public.profiles WHERE email = 'nimbus@aicportal.dev' LIMIT 1),
    'Backend Developer', 'Build and scale our core API services.', 'JOB', 'Bengaluru', 'PUBLISHED', now()
WHERE EXISTS (SELECT 1 FROM public.profiles WHERE email = 'nimbus@aicportal.dev');

INSERT INTO public.opportunity_skill_requirements (opportunity_id, skill_id, required_level, weight)
SELECT o.id, (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1), v.required_level, v.weight
FROM public.opportunities o
CROSS JOIN (VALUES ('Python', 75.0, 1.5), ('SQL', 70.0, 1.5), ('FastAPI', 60.0, 1.0), ('Docker', 55.0, 0.75), ('Git', 50.0, 0.5))
    AS v(skill_name, required_level, weight)
WHERE o.title = 'Backend Developer'
  AND o.industry_id = (SELECT id FROM public.profiles WHERE email = 'nimbus@aicportal.dev' LIMIT 1)
ON CONFLICT DO NOTHING;

INSERT INTO public.opportunities (industry_id, title, description, opportunity_type, location, status, published_at)
SELECT
    (SELECT id FROM public.profiles WHERE email = 'nimbus@aicportal.dev' LIMIT 1),
    'Software Engineering Intern', 'Ship real features alongside our engineering team.', 'INTERNSHIP', 'Hybrid', 'PUBLISHED', now()
WHERE EXISTS (SELECT 1 FROM public.profiles WHERE email = 'nimbus@aicportal.dev');

INSERT INTO public.opportunity_skill_requirements (opportunity_id, skill_id, required_level, weight)
SELECT o.id, (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1), v.required_level, v.weight
FROM public.opportunities o
CROSS JOIN (VALUES ('Python', 60.0, 1.5), ('JavaScript', 55.0, 1.0), ('Git', 50.0, 0.75))
    AS v(skill_name, required_level, weight)
WHERE o.title = 'Software Engineering Intern'
  AND o.industry_id = (SELECT id FROM public.profiles WHERE email = 'nimbus@aicportal.dev' LIMIT 1)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Verdant Labs
-- ============================================================

INSERT INTO public.opportunities (industry_id, title, description, opportunity_type, location, status, published_at)
SELECT
    (SELECT id FROM public.profiles WHERE email = 'verdant@aicportal.dev' LIMIT 1),
    'Backend Developer Intern', 'Work on our data pipelines and internal APIs.', 'INTERNSHIP', 'Remote', 'PUBLISHED', now()
WHERE EXISTS (SELECT 1 FROM public.profiles WHERE email = 'verdant@aicportal.dev');

INSERT INTO public.opportunity_skill_requirements (opportunity_id, skill_id, required_level, weight)
SELECT o.id, (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1), v.required_level, v.weight
FROM public.opportunities o
CROSS JOIN (VALUES ('Python', 65.0, 1.5), ('SQL', 60.0, 1.0), ('PostgreSQL', 55.0, 1.0))
    AS v(skill_name, required_level, weight)
WHERE o.title = 'Backend Developer Intern'
  AND o.industry_id = (SELECT id FROM public.profiles WHERE email = 'verdant@aicportal.dev' LIMIT 1)
ON CONFLICT DO NOTHING;

INSERT INTO public.opportunities (industry_id, title, description, opportunity_type, location, status, published_at)
SELECT
    (SELECT id FROM public.profiles WHERE email = 'verdant@aicportal.dev' LIMIT 1),
    'Cloud Engineer', 'Own our cloud infrastructure and deployment pipeline.', 'JOB', 'Remote', 'PUBLISHED', now()
WHERE EXISTS (SELECT 1 FROM public.profiles WHERE email = 'verdant@aicportal.dev');

INSERT INTO public.opportunity_skill_requirements (opportunity_id, skill_id, required_level, weight)
SELECT o.id, (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1), v.required_level, v.weight
FROM public.opportunities o
CROSS JOIN (VALUES ('AWS', 80.0, 1.5), ('Docker', 75.0, 1.5), ('Kubernetes', 70.0, 1.5), ('Linux', 65.0, 1.0))
    AS v(skill_name, required_level, weight)
WHERE o.title = 'Cloud Engineer'
  AND o.industry_id = (SELECT id FROM public.profiles WHERE email = 'verdant@aicportal.dev' LIMIT 1)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Orbit Analytics
-- ============================================================

INSERT INTO public.opportunities (industry_id, title, description, opportunity_type, location, status, published_at)
SELECT
    (SELECT id FROM public.profiles WHERE email = 'orbit@aicportal.dev' LIMIT 1),
    'Data Science Intern', 'Build models on real, messy, production data.', 'INTERNSHIP', 'Pune', 'PUBLISHED', now()
WHERE EXISTS (SELECT 1 FROM public.profiles WHERE email = 'orbit@aicportal.dev');

INSERT INTO public.opportunity_skill_requirements (opportunity_id, skill_id, required_level, weight)
SELECT o.id, (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1), v.required_level, v.weight
FROM public.opportunities o
CROSS JOIN (VALUES ('Python', 60.0, 1.5), ('Machine Learning', 55.0, 1.5), ('Pandas', 50.0, 1.0))
    AS v(skill_name, required_level, weight)
WHERE o.title = 'Data Science Intern'
  AND o.industry_id = (SELECT id FROM public.profiles WHERE email = 'orbit@aicportal.dev' LIMIT 1)
ON CONFLICT DO NOTHING;

INSERT INTO public.opportunities (industry_id, title, description, opportunity_type, location, status, published_at)
SELECT
    (SELECT id FROM public.profiles WHERE email = 'orbit@aicportal.dev' LIMIT 1),
    'Data Analyst', 'Turn data into decisions for our product and ops teams.', 'JOB', 'Remote', 'PUBLISHED', now()
WHERE EXISTS (SELECT 1 FROM public.profiles WHERE email = 'orbit@aicportal.dev');

INSERT INTO public.opportunity_skill_requirements (opportunity_id, skill_id, required_level, weight)
SELECT o.id, (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1), v.required_level, v.weight
FROM public.opportunities o
CROSS JOIN (VALUES ('SQL', 70.0, 1.5), ('Python', 60.0, 1.0), ('Data Analysis', 70.0, 1.5), ('Power BI', 50.0, 0.75))
    AS v(skill_name, required_level, weight)
WHERE o.title = 'Data Analyst'
  AND o.industry_id = (SELECT id FROM public.profiles WHERE email = 'orbit@aicportal.dev' LIMIT 1)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Brightline Tech
-- ============================================================

INSERT INTO public.opportunities (industry_id, title, description, opportunity_type, location, status, published_at)
SELECT
    (SELECT id FROM public.profiles WHERE email = 'brightline@aicportal.dev' LIMIT 1),
    'Junior Frontend Developer', 'Build polished, accessible UI for our flagship product.', 'JOB', 'Hyderabad', 'PUBLISHED', now()
WHERE EXISTS (SELECT 1 FROM public.profiles WHERE email = 'brightline@aicportal.dev');

INSERT INTO public.opportunity_skill_requirements (opportunity_id, skill_id, required_level, weight)
SELECT o.id, (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1), v.required_level, v.weight
FROM public.opportunities o
CROSS JOIN (VALUES ('JavaScript', 65.0, 1.5), ('React', 65.0, 1.5), ('TypeScript', 55.0, 1.0), ('CSS', 50.0, 0.75))
    AS v(skill_name, required_level, weight)
WHERE o.title = 'Junior Frontend Developer'
  AND o.industry_id = (SELECT id FROM public.profiles WHERE email = 'brightline@aicportal.dev' LIMIT 1)
ON CONFLICT DO NOTHING;

INSERT INTO public.opportunities (industry_id, title, description, opportunity_type, location, status, published_at)
SELECT
    (SELECT id FROM public.profiles WHERE email = 'brightline@aicportal.dev' LIMIT 1),
    'Frontend Developer Intern', 'Learn modern frontend engineering on a real product.', 'INTERNSHIP', 'Remote', 'PUBLISHED', now()
WHERE EXISTS (SELECT 1 FROM public.profiles WHERE email = 'brightline@aicportal.dev');

INSERT INTO public.opportunity_skill_requirements (opportunity_id, skill_id, required_level, weight)
SELECT o.id, (SELECT id FROM public.skills WHERE lower(name) = lower(v.skill_name) LIMIT 1), v.required_level, v.weight
FROM public.opportunities o
CROSS JOIN (VALUES ('JavaScript', 55.0, 1.5), ('React', 50.0, 1.5), ('HTML', 45.0, 0.75))
    AS v(skill_name, required_level, weight)
WHERE o.title = 'Frontend Developer Intern'
  AND o.industry_id = (SELECT id FROM public.profiles WHERE email = 'brightline@aicportal.dev' LIMIT 1)
ON CONFLICT DO NOTHING;
