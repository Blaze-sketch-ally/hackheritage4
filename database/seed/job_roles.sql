-- Seed data: initial job-role catalog, their skill requirements, and a
-- skill-relationship graph for deterministic recommendations.
-- Populates public.job_roles / job_role_skills / skill_relationships
-- (schema: database/migrations/016_skill_gap.sql).
--
-- Follows the exact same convention as database/seed/skills_fixed.sql:
-- plain INSERT ... VALUES / INSERT ... SELECT ... FROM (VALUES ...), no
-- CTEs, no DO blocks, no temporary tables. Skill references are resolved
-- by NAME via a scalar subquery against the EXISTING skills catalog --
-- no UUIDs are hardcoded, and no new skills are created here. Every
-- skill name below was verified against the live 114-row catalog before
-- writing this file; none are invented.
--
-- Idempotent / safe to run more than once:
--   - job_roles has a unique index on lower(name).
--   - job_role_skills has unique(job_role_id, skill_id).
--   - skill_relationships has unique(skill_id, related_skill_id, relationship_type).
--   - Every insert uses ON CONFLICT DO NOTHING.
--
-- Scope: 9 roles (per the approved starting list), not hundreds -- more
-- can be added later with the same pattern.

-- ============================================================
-- STEP 1 -- Job roles
-- ============================================================

insert into job_roles (name, description, category) values
  ('Backend Developer', 'Builds and maintains server-side application logic, APIs, and databases.', 'Engineering'),
  ('Frontend Developer', 'Builds user-facing web interfaces and client-side application logic.', 'Engineering'),
  ('Full Stack Developer', 'Works across both client-side and server-side layers of a web application.', 'Engineering'),
  ('Data Analyst', 'Analyzes structured data to produce reports and actionable business insights.', 'Data'),
  ('Data Scientist', 'Builds statistical and machine learning models to extract insight and predictions from data.', 'Data'),
  ('ML Engineer', 'Designs, trains, and deploys machine learning models into production systems.', 'Data'),
  ('DevOps Engineer', 'Builds and operates CI/CD pipelines, deployment automation, and infrastructure reliability.', 'Infrastructure'),
  ('Cloud Engineer', 'Designs and manages cloud infrastructure, provisioning, and cost/reliability at scale.', 'Infrastructure'),
  ('Software Engineer', 'General-purpose software design, implementation, and testing across the stack.', 'Engineering')
on conflict do nothing;

-- ============================================================
-- STEP 2 -- Job role skill requirements
-- (job_role name, skill name, required_level, importance)
-- ============================================================

insert into job_role_skills (job_role_id, skill_id, required_level, importance)
select
  (select id from job_roles where lower(name) = lower(v.role_name)),
  (select id from skills where lower(name) = lower(v.skill_name)),
  v.required_level,
  v.importance
from (values
  -- Backend Developer
  ('Backend Developer', 'Python', 'Advanced', 'CORE'),
  ('Backend Developer', 'FastAPI', 'Intermediate', 'CORE'),
  ('Backend Developer', 'SQL', 'Intermediate', 'CORE'),
  ('Backend Developer', 'PostgreSQL', 'Intermediate', 'CORE'),
  ('Backend Developer', 'Git', 'Intermediate', 'IMPORTANT'),
  ('Backend Developer', 'Docker', 'Beginner', 'IMPORTANT'),
  ('Backend Developer', 'Redis', 'Beginner', 'OPTIONAL'),
  ('Backend Developer', 'Software Testing', 'Intermediate', 'IMPORTANT'),
  ('Backend Developer', 'Linux', 'Beginner', 'OPTIONAL'),

  -- Frontend Developer
  ('Frontend Developer', 'JavaScript', 'Advanced', 'CORE'),
  ('Frontend Developer', 'TypeScript', 'Intermediate', 'CORE'),
  ('Frontend Developer', 'React', 'Advanced', 'CORE'),
  ('Frontend Developer', 'HTML', 'Intermediate', 'CORE'),
  ('Frontend Developer', 'CSS', 'Intermediate', 'CORE'),
  ('Frontend Developer', 'Git', 'Intermediate', 'IMPORTANT'),
  ('Frontend Developer', 'Tailwind CSS', 'Beginner', 'OPTIONAL'),
  ('Frontend Developer', 'UI Design', 'Beginner', 'OPTIONAL'),

  -- Full Stack Developer
  ('Full Stack Developer', 'JavaScript', 'Advanced', 'CORE'),
  ('Full Stack Developer', 'TypeScript', 'Intermediate', 'IMPORTANT'),
  ('Full Stack Developer', 'React', 'Intermediate', 'CORE'),
  ('Full Stack Developer', 'Node.js', 'Intermediate', 'CORE'),
  ('Full Stack Developer', 'SQL', 'Intermediate', 'IMPORTANT'),
  ('Full Stack Developer', 'PostgreSQL', 'Beginner', 'IMPORTANT'),
  ('Full Stack Developer', 'Git', 'Intermediate', 'IMPORTANT'),
  ('Full Stack Developer', 'Docker', 'Beginner', 'OPTIONAL'),

  -- Data Analyst
  ('Data Analyst', 'SQL', 'Advanced', 'CORE'),
  ('Data Analyst', 'Python', 'Intermediate', 'CORE'),
  ('Data Analyst', 'Pandas', 'Intermediate', 'CORE'),
  ('Data Analyst', 'Data Analysis', 'Advanced', 'CORE'),
  ('Data Analyst', 'Tableau', 'Intermediate', 'IMPORTANT'),
  ('Data Analyst', 'Power BI', 'Beginner', 'OPTIONAL'),

  -- Data Scientist
  ('Data Scientist', 'Python', 'Advanced', 'CORE'),
  ('Data Scientist', 'Pandas', 'Advanced', 'CORE'),
  ('Data Scientist', 'NumPy', 'Intermediate', 'CORE'),
  ('Data Scientist', 'Machine Learning', 'Advanced', 'CORE'),
  ('Data Scientist', 'Scikit-learn', 'Intermediate', 'IMPORTANT'),
  ('Data Scientist', 'SQL', 'Intermediate', 'IMPORTANT'),
  ('Data Scientist', 'Data Analysis', 'Advanced', 'IMPORTANT'),
  ('Data Scientist', 'Matplotlib', 'Beginner', 'OPTIONAL'),

  -- ML Engineer
  ('ML Engineer', 'Python', 'Advanced', 'CORE'),
  ('ML Engineer', 'Machine Learning', 'Advanced', 'CORE'),
  ('ML Engineer', 'TensorFlow', 'Intermediate', 'CORE'),
  ('ML Engineer', 'PyTorch', 'Intermediate', 'IMPORTANT'),
  ('ML Engineer', 'Deep Learning', 'Advanced', 'CORE'),
  ('ML Engineer', 'Scikit-learn', 'Intermediate', 'IMPORTANT'),
  ('ML Engineer', 'SQL', 'Beginner', 'OPTIONAL'),
  ('ML Engineer', 'Docker', 'Intermediate', 'IMPORTANT'),

  -- DevOps Engineer
  ('DevOps Engineer', 'Docker', 'Advanced', 'CORE'),
  ('DevOps Engineer', 'Kubernetes', 'Advanced', 'CORE'),
  ('DevOps Engineer', 'CI/CD', 'Advanced', 'CORE'),
  ('DevOps Engineer', 'Linux', 'Advanced', 'CORE'),
  ('DevOps Engineer', 'Terraform', 'Intermediate', 'IMPORTANT'),
  ('DevOps Engineer', 'Jenkins', 'Intermediate', 'IMPORTANT'),
  ('DevOps Engineer', 'Git', 'Intermediate', 'IMPORTANT'),
  ('DevOps Engineer', 'Python', 'Beginner', 'OPTIONAL'),

  -- Cloud Engineer
  ('Cloud Engineer', 'AWS', 'Advanced', 'CORE'),
  ('Cloud Engineer', 'Google Cloud Platform', 'Intermediate', 'IMPORTANT'),
  ('Cloud Engineer', 'Microsoft Azure', 'Intermediate', 'IMPORTANT'),
  ('Cloud Engineer', 'Terraform', 'Advanced', 'CORE'),
  ('Cloud Engineer', 'Docker', 'Intermediate', 'IMPORTANT'),
  ('Cloud Engineer', 'Kubernetes', 'Intermediate', 'IMPORTANT'),
  ('Cloud Engineer', 'Linux', 'Intermediate', 'CORE'),
  ('Cloud Engineer', 'CI/CD', 'Beginner', 'OPTIONAL'),

  -- Software Engineer
  ('Software Engineer', 'Git', 'Advanced', 'CORE'),
  ('Software Engineer', 'Python', 'Intermediate', 'CORE'),
  ('Software Engineer', 'Java', 'Intermediate', 'CORE'),
  ('Software Engineer', 'SQL', 'Intermediate', 'IMPORTANT'),
  ('Software Engineer', 'Software Testing', 'Intermediate', 'IMPORTANT'),
  ('Software Engineer', 'Docker', 'Beginner', 'OPTIONAL'),
  ('Software Engineer', 'Problem Solving', 'Intermediate', 'IMPORTANT')
) as v(role_name, skill_name, required_level, importance)
where exists (select 1 from job_roles where lower(name) = lower(v.role_name))
  and exists (select 1 from skills where lower(name) = lower(v.skill_name))
on conflict do nothing;

-- ============================================================
-- STEP 3 -- Skill relationships (see 016_skill_gap.sql for the exact
-- directional semantics of each relationship_type).
-- ============================================================

insert into skill_relationships (skill_id, related_skill_id, relationship_type, priority)
select
  (select id from skills where lower(name) = lower(v.skill_name)),
  (select id from skills where lower(name) = lower(v.related_skill_name)),
  v.relationship_type,
  v.priority
from (values
  -- PREREQUISITE
  ('Python', 'FastAPI', 'PREREQUISITE', 1),
  ('Python', 'Django', 'PREREQUISITE', 2),
  ('Python', 'Flask', 'PREREQUISITE', 3),
  ('Python', 'Pandas', 'PREREQUISITE', 1),
  ('Python', 'NumPy', 'PREREQUISITE', 1),
  ('Python', 'Scikit-learn', 'PREREQUISITE', 2),
  ('Python', 'Machine Learning', 'PREREQUISITE', 1),
  ('JavaScript', 'React', 'PREREQUISITE', 1),
  ('JavaScript', 'Node.js', 'PREREQUISITE', 1),
  ('JavaScript', 'Vue.js', 'PREREQUISITE', 2),
  ('React', 'Next.js', 'PREREQUISITE', 1),
  ('Linux', 'Docker', 'PREREQUISITE', 1),
  ('Docker', 'Kubernetes', 'PREREQUISITE', 1),
  ('NumPy', 'Pandas', 'PREREQUISITE', 2),

  -- NEXT_STEP
  ('SQL', 'PostgreSQL', 'NEXT_STEP', 1),
  ('SQL', 'MySQL', 'NEXT_STEP', 2),
  ('JavaScript', 'TypeScript', 'NEXT_STEP', 1),
  ('HTML', 'JavaScript', 'NEXT_STEP', 1),
  ('CSS', 'Tailwind CSS', 'NEXT_STEP', 1),
  ('Node.js', 'Express.js', 'NEXT_STEP', 1),
  ('Git', 'GitHub Actions', 'NEXT_STEP', 2),
  ('Pandas', 'Data Analysis', 'NEXT_STEP', 1),
  ('Data Analysis', 'Tableau', 'NEXT_STEP', 1),
  ('Data Analysis', 'Power BI', 'NEXT_STEP', 2),
  ('Machine Learning', 'Deep Learning', 'NEXT_STEP', 1),
  ('Machine Learning', 'TensorFlow', 'NEXT_STEP', 2),
  ('Machine Learning', 'PyTorch', 'NEXT_STEP', 3),
  ('Software Testing', 'Automation Testing', 'NEXT_STEP', 1),
  ('Software Testing', 'Selenium', 'NEXT_STEP', 2),
  ('Software Testing', 'Playwright', 'NEXT_STEP', 3),
  ('AWS', 'Terraform', 'NEXT_STEP', 1),
  ('CI/CD', 'Jenkins', 'NEXT_STEP', 1),

  -- COMPLEMENTARY
  ('FastAPI', 'Docker', 'COMPLEMENTARY', 1),
  ('FastAPI', 'Redis', 'COMPLEMENTARY', 2),
  ('FastAPI', 'PostgreSQL', 'COMPLEMENTARY', 1),
  ('FastAPI', 'Software Testing', 'COMPLEMENTARY', 3),
  ('PostgreSQL', 'Redis', 'COMPLEMENTARY', 1),
  ('Docker', 'CI/CD', 'COMPLEMENTARY', 1),
  ('Git', 'GitHub', 'COMPLEMENTARY', 1),
  ('Terraform', 'AWS', 'COMPLEMENTARY', 1),
  ('AWS', 'Kubernetes', 'COMPLEMENTARY', 2),
  ('React', 'TypeScript', 'COMPLEMENTARY', 1),
  ('TensorFlow', 'Deep Learning', 'COMPLEMENTARY', 1),
  ('PyTorch', 'Deep Learning', 'COMPLEMENTARY', 1),
  ('Pandas', 'Matplotlib', 'COMPLEMENTARY', 1),
  ('Software Testing', 'Unit Testing', 'COMPLEMENTARY', 1),
  ('Software Testing', 'API Testing', 'COMPLEMENTARY', 2),

  -- RELATED
  ('HTML', 'CSS', 'RELATED', 1),
  ('CI/CD', 'GitHub Actions', 'RELATED', 1),
  ('Git', 'CI/CD', 'RELATED', 2)
) as v(skill_name, related_skill_name, relationship_type, priority)
where exists (select 1 from skills where lower(name) = lower(v.skill_name))
  and exists (select 1 from skills where lower(name) = lower(v.related_skill_name))
on conflict do nothing;
