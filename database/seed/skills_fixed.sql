-- Seed data: initial master skill catalog (simplified structure).
-- Populates public.skill_categories and public.skills
-- (schema: database/migrations/003_skills.sql).
--
-- This file replaces the CROSS JOIN / subquery-in-FROM structure of
-- database/seed/skills.sql with the simplest possible form: one plain
-- INSERT ... VALUES for categories, then one plain INSERT ... SELECT ...
-- FROM (VALUES ...) per category, with the category looked up via a
-- scalar subquery directly in the SELECT list. No WITH, no CROSS JOIN,
-- no CTEs, no DO blocks, no functions, no temporary tables.
--
-- Scope: catalog only. Does NOT touch student_profiles, student_skills,
-- or profiles.
--
-- Idempotent / safe to run more than once:
--   - public.skill_categories has a unique index on lower(name).
--   - public.skills has a unique index on lower(name), globally unique
--     across the whole table (not per-category) — every skill below
--     appears in exactly one category.
--   - Every insert uses ON CONFLICT DO NOTHING (no column list), which
--     catches a violation of any unique index on the target table,
--     including the expression-based lower(name) indexes above.
--   - No UUIDs are hard-coded. category_id is resolved by name via a
--     scalar subquery, so this works whether the category was just
--     inserted above or already existed from a prior run.
--
-- All entries are inserted with is_active = true.

-- ============================================================
-- STEP 1 — Categories
-- ============================================================

INSERT INTO public.skill_categories (name)
VALUES
  ('Programming Languages'),
  ('Web Development'),
  ('Frontend Frameworks'),
  ('Backend Frameworks'),
  ('Databases'),
  ('Cloud Computing'),
  ('DevOps'),
  ('Tools & Version Control'),
  ('Data Science'),
  ('Artificial Intelligence'),
  ('Machine Learning'),
  ('Deep Learning'),
  ('Generative AI'),
  ('Cybersecurity'),
  ('Mobile Development'),
  ('UI/UX & Design'),
  ('Testing & QA'),
  ('Data Engineering'),
  ('Big Data'),
  ('Soft Skills'),
  ('Business & Management')
ON CONFLICT DO NOTHING;

-- ============================================================
-- STEP 2 — Skills
-- ============================================================

-- Programming Languages
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Programming Languages'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Python', 'General-purpose language widely used in web, data, and AI.'),
      ('Java', 'Object-oriented language widely used in enterprise and Android apps.'),
      ('JavaScript', 'Core scripting language for interactive web applications.'),
      ('TypeScript', 'Typed superset of JavaScript for safer, scalable code.'),
      ('C', 'Low-level systems programming language.'),
      ('C++', 'Performance-oriented language used in systems and game development.'),
      ('C#', 'Object-oriented language used with .NET and game development.'),
      ('Go', 'Compiled language known for concurrency and cloud-native services.'),
      ('Rust', 'Systems language focused on memory safety and performance.'),
      ('PHP', 'Server-side scripting language widely used for web backends.'),
      ('Ruby', 'Dynamic language known for developer productivity and Rails.'),
      ('Kotlin', 'Modern language for Android and JVM development.'),
      ('Swift', 'Apple''s language for iOS and macOS development.'),
      ('Dart', 'Language used to build cross-platform apps with Flutter.'),
      ('SQL', 'Standard language for querying and managing relational data.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Web Development
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Web Development'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('HTML', 'Markup language for structuring web content.'),
      ('CSS', 'Stylesheet language for designing and laying out web pages.'),
      ('Tailwind CSS', 'Utility-first CSS framework for rapid UI styling.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Frontend Frameworks
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Frontend Frameworks'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('React', 'Component-based JavaScript library for building user interfaces.'),
      ('Next.js', 'React framework for server-rendered and static web apps.'),
      ('Angular', 'TypeScript-based framework for building large-scale web apps.'),
      ('Vue.js', 'Progressive JavaScript framework for building user interfaces.'),
      ('Svelte', 'Compiler-based framework for building fast web interfaces.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Backend Frameworks
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Backend Frameworks'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Node.js', 'JavaScript runtime for building server-side applications.'),
      ('Express.js', 'Minimal web framework for Node.js backends.'),
      ('FastAPI', 'Modern Python framework for building fast APIs.'),
      ('Django', 'High-level Python framework for rapid web development.'),
      ('Flask', 'Lightweight Python framework for web applications and APIs.'),
      ('Spring Boot', 'Java framework for building production-ready applications.'),
      ('.NET', 'Microsoft framework for building cross-platform applications.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Databases
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Databases'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('PostgreSQL', 'Advanced open-source relational database.'),
      ('MySQL', 'Widely used open-source relational database.'),
      ('SQLite', 'Lightweight, file-based relational database.'),
      ('MongoDB', 'Document-oriented NoSQL database.'),
      ('Redis', 'In-memory data store used for caching and queues.'),
      ('Firebase', 'Backend-as-a-service platform with a real-time NoSQL database.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Cloud Computing
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Cloud Computing'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('AWS', 'Amazon''s cloud computing platform and services.'),
      ('Microsoft Azure', 'Microsoft''s cloud computing platform and services.'),
      ('Google Cloud Platform', 'Google''s cloud computing platform and services.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- DevOps
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'DevOps'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Docker', 'Platform for building and running containerized applications.'),
      ('Kubernetes', 'Container orchestration platform for deploying at scale.'),
      ('GitHub Actions', 'CI/CD automation built into GitHub.'),
      ('Jenkins', 'Open-source automation server for CI/CD pipelines.'),
      ('Terraform', 'Infrastructure-as-code tool for provisioning cloud resources.'),
      ('CI/CD', 'Practice of automating build, test, and deployment pipelines.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Tools & Version Control
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Tools & Version Control'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Git', 'Distributed version control system for tracking code changes.'),
      ('GitHub', 'Platform for hosting and collaborating on Git repositories.'),
      ('GitLab', 'Platform for Git repository hosting and DevOps pipelines.'),
      ('Postman', 'Tool for building, testing, and documenting APIs.'),
      ('Linux', 'Open-source operating system widely used in servers and DevOps.'),
      ('VS Code', 'Popular lightweight source code editor.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Data Science
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Data Science'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Data Analysis', 'Examining data to extract insights and inform decisions.'),
      ('Pandas', 'Python library for data manipulation and analysis.'),
      ('NumPy', 'Python library for numerical and array computing.'),
      ('Matplotlib', 'Python library for data visualization.'),
      ('Power BI', 'Microsoft''s business analytics and visualization tool.'),
      ('Tableau', 'Data visualization and business intelligence tool.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Artificial Intelligence
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Artificial Intelligence'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Artificial Intelligence', 'Building systems that perform tasks requiring human-like intelligence.'),
      ('Natural Language Processing', 'Enabling computers to understand and generate human language.'),
      ('Computer Vision', 'Enabling computers to interpret and process visual data.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Machine Learning
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Machine Learning'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Machine Learning', 'Building models that learn patterns from data.'),
      ('Scikit-learn', 'Python library for classical machine learning.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Deep Learning
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Deep Learning'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Deep Learning', 'Building and training neural networks on large datasets.'),
      ('PyTorch', 'Deep learning framework popular for research and production.'),
      ('TensorFlow', 'Deep learning framework for building and deploying models.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Generative AI
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Generative AI'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Generative AI', 'Building systems that generate text, images, or other content.'),
      ('Large Language Models', 'Working with and applying large-scale language models.'),
      ('Prompt Engineering', 'Designing effective prompts to guide AI model outputs.'),
      ('Hugging Face', 'Platform and libraries for sharing and using AI models.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Cybersecurity
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Cybersecurity'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Network Security', 'Protecting network infrastructure from threats and attacks.'),
      ('Web Security', 'Securing web applications against common vulnerabilities.'),
      ('Application Security', 'Building and testing software to resist attacks.'),
      ('Ethical Hacking', 'Legally testing systems to find security weaknesses.'),
      ('Penetration Testing', 'Simulating attacks to evaluate system security.'),
      ('OWASP', 'Following best practices for secure application development.'),
      ('Cryptography', 'Techniques for securing data through encryption.'),
      ('Security Operations', 'Monitoring and responding to security incidents.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Mobile Development
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Mobile Development'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Android Development', 'Building native applications for the Android platform.'),
      ('iOS Development', 'Building native applications for the iOS platform.'),
      ('React Native', 'Framework for building cross-platform mobile apps with React.'),
      ('Flutter', 'Google''s toolkit for building cross-platform apps with Dart.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- UI/UX & Design
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'UI/UX & Design'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('UI Design', 'Designing visual interfaces for digital products.'),
      ('UX Design', 'Designing user experiences based on usability and research.'),
      ('Figma', 'Collaborative interface design and prototyping tool.'),
      ('Wireframing', 'Creating low-fidelity layouts to plan interfaces.'),
      ('Prototyping', 'Building interactive mockups to test design concepts.'),
      ('User Research', 'Studying user needs and behavior to inform design.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Testing & QA
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Testing & QA'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Software Testing', 'Verifying that software behaves as expected.'),
      ('Unit Testing', 'Testing individual components of code in isolation.'),
      ('Integration Testing', 'Testing how combined components work together.'),
      ('API Testing', 'Verifying the functionality and reliability of APIs.'),
      ('Automation Testing', 'Using tools to automatically run test cases.'),
      ('Selenium', 'Tool for automating web browser testing.'),
      ('Playwright', 'Modern tool for automated end-to-end web testing.'),
      ('Cypress', 'JavaScript-based tool for end-to-end web testing.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Data Engineering
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Data Engineering'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('ETL', 'Extracting, transforming, and loading data between systems.'),
      ('Data Warehousing', 'Designing systems to store and analyze large datasets.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Big Data
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Big Data'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Apache Spark', 'Distributed engine for large-scale data processing.'),
      ('Hadoop', 'Framework for distributed storage and processing of big data.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Soft Skills
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Soft Skills'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Communication', 'Clearly conveying ideas and information to others.'),
      ('Leadership', 'Guiding and motivating individuals or teams toward goals.'),
      ('Teamwork', 'Collaborating effectively with others to achieve shared goals.'),
      ('Problem Solving', 'Identifying issues and developing effective solutions.'),
      ('Critical Thinking', 'Analyzing information objectively to make sound judgments.'),
      ('Time Management', 'Organizing and prioritizing tasks to use time effectively.'),
      ('Adaptability', 'Adjusting effectively to new conditions and challenges.'),
      ('Public Speaking', 'Communicating confidently and clearly to an audience.'),
      ('Collaboration', 'Working with others to achieve a common goal.')
) AS v(name, description)
ON CONFLICT DO NOTHING;

-- Business & Management
INSERT INTO public.skills
    (name, category_id, description, is_active)
SELECT
    v.name,
    (SELECT id
     FROM public.skill_categories
     WHERE name = 'Business & Management'
     LIMIT 1),
    v.description,
    true
FROM (
    VALUES
      ('Project Management', 'Planning and overseeing projects to meet goals.'),
      ('Product Management', 'Guiding product strategy and development.'),
      ('Business Analysis', 'Identifying business needs and recommending solutions.'),
      ('Entrepreneurship', 'Identifying opportunities and building new ventures.'),
      ('Agile', 'Iterative approach to managing and delivering projects.'),
      ('Scrum', 'Framework for managing work using an Agile approach.')
) AS v(name, description)
ON CONFLICT DO NOTHING;
