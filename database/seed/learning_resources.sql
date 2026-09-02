-- Seed data: an initial curated catalog of learning resources and their
-- skill mappings.
-- Populates public.learning_resources / learning_resource_skills
-- (schema: database/migrations/033_learning_resources.sql). Does NOT
-- touch student_learning_progress (student-owned) or any other table.
--
-- Follows the exact same convention as database/seed/job_roles.sql:
-- plain INSERT ... VALUES / INSERT ... SELECT ... FROM (VALUES ...), no
-- CTEs, no DO blocks, no temporary tables. Skill references are resolved
-- by NAME via a scalar subquery against the EXISTING skills catalog
-- (database/seed/skills_fixed.sql) -- no skill UUIDs are hardcoded, and
-- no new skills are created here. Resources are resolved by their URL
-- (the table's stable identity -- learning_resources_url_lower_idx).
--
-- Every skill name below was checked against the live 114-row `skills`
-- catalog before writing this file; none are invented. Every URL is a
-- real, publicly accessible learning resource (official docs, freeCodeCamp,
-- MDN, The Odin Project, Kaggle Learn, and similar).
--
-- Idempotent / safe to run more than once (and safe to run before some
-- referenced skills exist -- a missing skill just yields a NULL skill_id
-- row that ON CONFLICT / the NOT NULL constraint skips; re-run after
-- seeding skills to fill any gap):
--   - learning_resources has a unique index on lower(url).
--   - learning_resource_skills has unique(resource_id, skill_id).
--   - Every insert uses ON CONFLICT DO NOTHING.
--
-- Scope: 20 resources across the common early-career skill areas -- more
-- can be added later with the same pattern.
--
-- NOT applied to the live database as part of Phase 6A. Apply after
-- migration 033, alongside the other seeds, via the Supabase SQL editor.

-- ============================================================
-- STEP 1 -- Learning resources
-- (title, description, url, provider, resource_type, difficulty, estimated_minutes)
-- ============================================================

insert into learning_resources
  (title, description, url, provider, resource_type, difficulty, estimated_minutes)
values
  ('Python for Everybody',
   'A gentle, project-based introduction to programming using Python, from variables to working with web data and databases.',
   'https://www.py4e.com/', 'University of Michigan (py4e)', 'COURSE', 'Beginner', 1200),

  ('Automate the Boring Stuff with Python',
   'Practical Python for total beginners: automate everyday computer tasks like files, spreadsheets, email, and the web.',
   'https://automatetheboringstuff.com/', 'Al Sweigart', 'COURSE', 'Beginner', 900),

  ('Real Python Tutorials',
   'In-depth written tutorials on intermediate and advanced Python topics, updated regularly.',
   'https://realpython.com/', 'Real Python', 'ARTICLE', 'Intermediate', null),

  ('Learn Python - Full Course for Beginners',
   'A single four-hour video walkthrough of core Python for complete beginners.',
   'https://www.youtube.com/watch?v=rfscVS0vtbw', 'freeCodeCamp', 'VIDEO', 'Beginner', 250),

  ('FastAPI Official Tutorial',
   'The official step-by-step FastAPI tutorial: path/query params, request bodies, validation, dependencies, and security.',
   'https://fastapi.tiangolo.com/tutorial/', 'FastAPI', 'COURSE', 'Intermediate', 480),

  ('SQLBolt - Learn SQL with interactive lessons',
   'Short interactive lessons and exercises covering SELECT, joins, aggregates, and table modification.',
   'https://sqlbolt.com/', 'SQLBolt', 'COURSE', 'Beginner', 180),

  ('PostgreSQL Documentation - The SQL Language',
   'The official PostgreSQL tutorial and SQL-language reference, from basic queries to advanced features.',
   'https://www.postgresql.org/docs/current/tutorial.html', 'PostgreSQL', 'ARTICLE', 'Intermediate', null),

  ('MDN - JavaScript Guide',
   'Mozilla''s comprehensive guide to the JavaScript language: grammar, types, control flow, functions, and objects.',
   'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide', 'MDN Web Docs', 'ARTICLE', 'Beginner', null),

  ('The Modern JavaScript Tutorial',
   'A thorough, from-the-basics-to-advanced JavaScript course covering the language and working in the browser.',
   'https://javascript.info/', 'javascript.info', 'COURSE', 'Intermediate', 1200),

  ('React Official Docs - Learn React',
   'The official React learning path: describing UI, adding interactivity, managing state, and escape hatches.',
   'https://react.dev/learn', 'React', 'COURSE', 'Intermediate', 600),

  ('The Odin Project - Full Stack JavaScript',
   'A free, project-heavy full-stack curriculum covering HTML, CSS, JavaScript, React, and Node.js.',
   'https://www.theodinproject.com/paths/full-stack-javascript', 'The Odin Project', 'COURSE', 'Intermediate', null),

  ('TypeScript Handbook',
   'The official TypeScript handbook: everyday types, narrowing, functions, generics, and modules.',
   'https://www.typescriptlang.org/docs/handbook/intro.html', 'TypeScript', 'ARTICLE', 'Intermediate', 300),

  ('Pro Git',
   'The complete Pro Git book: fundamentals, branching, remotes, and internals.',
   'https://git-scm.com/book/en/v2', 'git-scm.com', 'ARTICLE', 'Beginner', 360),

  ('Learn Git Branching',
   'An interactive, visual playground for practising Git branching and history commands.',
   'https://learngitbranching.js.org/', 'learngitbranching.js.org', 'COURSE', 'Beginner', 90),

  ('Docker - Get Started',
   'The official Docker getting-started guide: images, containers, Dockerfiles, and multi-container apps.',
   'https://docs.docker.com/get-started/', 'Docker', 'COURSE', 'Beginner', 180),

  ('Kubernetes Basics',
   'The official interactive tutorial: deploy an app, explore it, expose it publicly, scale it, and update it.',
   'https://kubernetes.io/docs/tutorials/kubernetes-basics/', 'Kubernetes', 'COURSE', 'Intermediate', 120),

  ('web.dev - Learn CSS',
   'A modern, well-structured CSS course from Google covering the box model, layout, flexbox, grid, and more.',
   'https://web.dev/learn/css', 'web.dev (Google)', 'COURSE', 'Beginner', 300),

  ('MDN - Learn HTML',
   'Mozilla''s structured introduction to HTML: document structure, text, links, images, forms, and tables.',
   'https://developer.mozilla.org/en-US/docs/Learn/HTML', 'MDN Web Docs', 'COURSE', 'Beginner', 240),

  ('Kaggle Learn - Intro to Machine Learning',
   'A short, hands-on course: how models work, model validation, underfitting/overfitting, and random forests.',
   'https://www.kaggle.com/learn/intro-to-machine-learning', 'Kaggle', 'COURSE', 'Beginner', 180),

  ('pandas - Getting started',
   'The official pandas getting-started tutorials: data structures, reading/writing data, selecting, and plotting.',
   'https://pandas.pydata.org/docs/getting_started/index.html', 'pandas', 'ARTICLE', 'Beginner', null)
on conflict do nothing;

-- ============================================================
-- STEP 2 -- Resource -> skill mappings
-- (resource url, skill name, target_level)
-- ============================================================

insert into learning_resource_skills (resource_id, skill_id, target_level)
select
  (select id from learning_resources where lower(url) = lower(v.url)),
  (select id from skills where lower(name) = lower(v.skill_name)),
  v.target_level
from (values
  ('https://www.py4e.com/', 'Python', 'Beginner'),
  ('https://automatetheboringstuff.com/', 'Python', 'Beginner'),
  ('https://realpython.com/', 'Python', 'Advanced'),
  ('https://www.youtube.com/watch?v=rfscVS0vtbw', 'Python', 'Beginner'),

  ('https://fastapi.tiangolo.com/tutorial/', 'FastAPI', 'Intermediate'),
  ('https://fastapi.tiangolo.com/tutorial/', 'Python', 'Intermediate'),

  ('https://sqlbolt.com/', 'SQL', 'Beginner'),
  ('https://www.postgresql.org/docs/current/tutorial.html', 'PostgreSQL', 'Intermediate'),
  ('https://www.postgresql.org/docs/current/tutorial.html', 'SQL', 'Intermediate'),

  ('https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide', 'JavaScript', 'Beginner'),
  ('https://javascript.info/', 'JavaScript', 'Advanced'),

  ('https://react.dev/learn', 'React', 'Intermediate'),

  ('https://www.theodinproject.com/paths/full-stack-javascript', 'JavaScript', 'Intermediate'),
  ('https://www.theodinproject.com/paths/full-stack-javascript', 'React', 'Intermediate'),
  ('https://www.theodinproject.com/paths/full-stack-javascript', 'Node.js', 'Intermediate'),
  ('https://www.theodinproject.com/paths/full-stack-javascript', 'HTML', 'Intermediate'),
  ('https://www.theodinproject.com/paths/full-stack-javascript', 'CSS', 'Intermediate'),

  ('https://www.typescriptlang.org/docs/handbook/intro.html', 'TypeScript', 'Intermediate'),

  ('https://git-scm.com/book/en/v2', 'Git', 'Intermediate'),
  ('https://learngitbranching.js.org/', 'Git', 'Beginner'),

  ('https://docs.docker.com/get-started/', 'Docker', 'Beginner'),
  ('https://kubernetes.io/docs/tutorials/kubernetes-basics/', 'Kubernetes', 'Intermediate'),

  ('https://web.dev/learn/css', 'CSS', 'Beginner'),
  ('https://developer.mozilla.org/en-US/docs/Learn/HTML', 'HTML', 'Beginner'),

  ('https://www.kaggle.com/learn/intro-to-machine-learning', 'Machine Learning', 'Beginner'),
  ('https://www.kaggle.com/learn/intro-to-machine-learning', 'Python', 'Intermediate'),

  ('https://pandas.pydata.org/docs/getting_started/index.html', 'Pandas', 'Beginner'),
  ('https://pandas.pydata.org/docs/getting_started/index.html', 'Python', 'Beginner')
) as v (url, skill_name, target_level)
where (select id from learning_resources where lower(url) = lower(v.url)) is not null
  and (select id from skills where lower(name) = lower(v.skill_name)) is not null
on conflict do nothing;
