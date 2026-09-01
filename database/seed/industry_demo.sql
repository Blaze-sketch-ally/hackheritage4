-- Industry Portal demonstration dataset (additive, idempotent).
-- Generated from industry_demo_seed.py — do not edit by hand.
-- Safe to run repeatedly: every INSERT is guarded by NOT EXISTS.
-- Apply with the Supabase SQL editor or `supabase db` against the
-- project that already has migrations 001-028.

begin;

-- internships
insert into internships (industry_id, title, description, location, work_mode, duration_months, stipend_amount, openings, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'technova_demo'), 'Machine Learning Engineering Intern', 'Overview: Join TechNova''s Applied ML team and ship models that power our recommendation, search-ranking, and document-intelligence products.

Responsibilities: build and evaluate training pipelines; run offline experiments and error analysis; help package models for the serving platform; write clear experiment reports.

You''ll learn: production ML workflow end to end — feature stores, experiment tracking, model packaging, and A/B evaluation.

Eligibility: comfortable with Python and NumPy/pandas; exposure to PyTorch or scikit-learn; coursework in ML or statistics.', 'Remote (India)', 'REMOTE', 6, 35000, 3, 'Pre-final / final-year students in CS, Data Science, or related; prior ML coursework or projects.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from internships where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Machine Learning Engineering Intern');
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Machine Learning Engineering Intern' and s.name = 'Python'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Machine Learning Engineering Intern' and s.name = 'Machine Learning'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Machine Learning Engineering Intern' and s.name = 'PyTorch'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Machine Learning Engineering Intern' and s.name = 'Pandas'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);

insert into internships (industry_id, title, description, location, work_mode, duration_months, stipend_amount, openings, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'technova_demo'), 'Cloud & DevOps Engineering Intern', 'Overview: Work with the Platform Engineering team that keeps TechNova''s services reliable, observable, and cheap to run.

Responsibilities: extend CI/CD pipelines; write Terraform for cloud infrastructure; build Grafana dashboards and alerts; participate in blameless incident reviews.

You''ll learn: infrastructure-as-code, container orchestration, and how a real on-call rotation works.

Eligibility: solid Linux fundamentals; some Docker; curiosity about distributed systems.', 'Bengaluru, Karnataka, India', 'HYBRID', 6, 30000, 2, 'Final-year students in CS/IT with hands-on Linux and scripting experience.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from internships where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Cloud & DevOps Engineering Intern');
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Cloud & DevOps Engineering Intern' and s.name = 'Docker'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Cloud & DevOps Engineering Intern' and s.name = 'Linux'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Cloud & DevOps Engineering Intern' and s.name = 'CI/CD'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Beginner', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Cloud & DevOps Engineering Intern' and s.name = 'Terraform'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);

insert into internships (industry_id, title, description, location, work_mode, duration_months, stipend_amount, openings, eligibility_criteria, status)
select (select id from profiles where username = 'technova_demo'), 'Computer Vision Research Intern', 'Overview (DRAFT — not yet published): Prototype visual-inspection and document-parsing models for TechNova''s enterprise customers.

Responsibilities: curate and label datasets; fine-tune detection and segmentation models; benchmark accuracy vs. latency trade-offs.

You''ll learn: the full research-to-prototype loop on real customer data.

Eligibility: PyTorch, OpenCV, and a portfolio CV project.', 'Bengaluru, Karnataka, India', 'ONSITE', 4, 32000, 1, 'Students with a computer-vision project or publication; strong linear algebra.', 'DRAFT'
where not exists (select 1 from internships where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Computer Vision Research Intern');
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Computer Vision Research Intern' and s.name = 'Computer Vision'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Computer Vision Research Intern' and s.name = 'PyTorch'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Computer Vision Research Intern' and s.name = 'Python'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);

insert into internships (industry_id, title, description, location, work_mode, duration_months, stipend_amount, openings, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Analytics Engineering Intern', 'Overview: Help DataForge Labs build the transformation layer that turns raw warehouse data into trustworthy analytics models.

Responsibilities: write and test dbt models; document metrics; add data quality checks; support analysts with clean datasets.

You''ll learn: analytics engineering practice — modelling, testing, lineage, and semantic layers.

Eligibility: fluent SQL; some Python; tidy, documented work.', 'Remote (India)', 'REMOTE', 6, 28000, 2, 'Students with strong SQL and an interest in the modern data stack.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from internships where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Analytics Engineering Intern');
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Analytics Engineering Intern' and s.name = 'SQL'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Analytics Engineering Intern' and s.name = 'Python'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Analytics Engineering Intern' and s.name = 'Data Analysis'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);

insert into internships (industry_id, title, description, location, work_mode, duration_months, stipend_amount, openings, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge BI & Visualization Intern', 'Overview: Build dashboards that DataForge''s client stakeholders actually use to make decisions.

Responsibilities: gather reporting requirements; model data for BI; build Power BI / Tableau dashboards; run short enablement sessions.

You''ll learn: dashboard design, data storytelling, and stakeholder management.

Eligibility: SQL basics; an eye for clear visual design.', 'Hyderabad, Telangana, India', 'HYBRID', 4, 25000, 2, 'Students comfortable with spreadsheets, SQL, and at least one BI tool.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from internships where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge BI & Visualization Intern');
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge BI & Visualization Intern' and s.name = 'Power BI'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge BI & Visualization Intern' and s.name = 'SQL'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge BI & Visualization Intern' and s.name = 'Data Analysis'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);

insert into internships (industry_id, title, description, location, work_mode, duration_months, stipend_amount, openings, eligibility_criteria, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Data Platform Intern', 'Overview (DRAFT — not yet published): Support the team that runs DataForge''s ingestion and orchestration platform.

Responsibilities: build Airflow DAGs; add pipeline monitoring; help migrate batch jobs to incremental models.

You''ll learn: orchestration, warehouse cost management, and pipeline SLAs.

Eligibility: Python; basic SQL; Linux comfort.', 'Hyderabad, Telangana, India', 'HYBRID', 6, 27000, 1, 'Students with Python and an interest in data infrastructure.', 'DRAFT'
where not exists (select 1 from internships where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Data Platform Intern');
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'CORE'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Data Platform Intern' and s.name = 'Python'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Beginner', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Data Platform Intern' and s.name = 'Apache Spark'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);
insert into internship_skills (internship_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from internships p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Data Platform Intern' and s.name = 'SQL'
and not exists (select 1 from internship_skills x where x.internship_id = p.id and x.skill_id = s.id);

-- jobs
insert into jobs (industry_id, title, description, location, work_mode, employment_type, salary_min, salary_max, experience_min_years, openings, eligibility_criteria, application_deadline, status)
select (select id from profiles where username = 'technova_demo'), 'Machine Learning Engineer', 'Overview: Own ML features end to end for TechNova''s AI products — from problem framing to a monitored production model.

Responsibilities: design training and evaluation pipelines; ship models to the serving platform; set up drift and quality monitoring; mentor interns.

Qualifications: strong Python; PyTorch or TensorFlow; experience with feature engineering and offline/online evaluation; comfort with cloud infrastructure.', 'Bengaluru, Karnataka, India', 'HYBRID', 'FULL_TIME', 1800000, 3200000, 2, 2, '2+ years building ML systems in production.', '2026-12-15', 'PUBLISHED'
where not exists (select 1 from jobs where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Machine Learning Engineer');
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Machine Learning Engineer' and s.name = 'Python'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Machine Learning Engineer' and s.name = 'Machine Learning'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Machine Learning Engineer' and s.name = 'PyTorch'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Machine Learning Engineer' and s.name = 'AWS'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);

insert into jobs (industry_id, title, description, location, work_mode, employment_type, salary_min, salary_max, experience_min_years, openings, eligibility_criteria, application_deadline, status)
select (select id from profiles where username = 'technova_demo'), 'Site Reliability Engineer', 'Overview: Keep TechNova''s platform fast, reliable, and cost-efficient as it scales.

Responsibilities: own SLOs and error budgets; improve CI/CD and rollout safety; drive incident response and postmortems; reduce cloud spend.

Qualifications: deep Linux and networking; Kubernetes; Terraform; strong scripting; calm under incident pressure.', 'Remote (India)', 'REMOTE', 'FULL_TIME', 2000000, 3600000, 3, 1, '3+ years operating production distributed systems.', '2026-12-15', 'PUBLISHED'
where not exists (select 1 from jobs where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Site Reliability Engineer');
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Site Reliability Engineer' and s.name = 'Kubernetes'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Site Reliability Engineer' and s.name = 'Linux'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Site Reliability Engineer' and s.name = 'Terraform'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'Site Reliability Engineer' and s.name = 'CI/CD'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);

insert into jobs (industry_id, title, description, location, work_mode, employment_type, salary_min, salary_max, experience_min_years, openings, eligibility_criteria, status)
select (select id from profiles where username = 'technova_demo'), 'AI Product Engineer', 'Overview (DRAFT — not yet published): Build user-facing features on top of large language models — retrieval, agents, and evaluation harnesses.

Responsibilities: design RAG and tool-use flows; build evaluation datasets; ship React front-ends and FastAPI services; measure quality in production.

Qualifications: TypeScript + React; Python + FastAPI; prompt engineering; product sense.', 'Bengaluru, Karnataka, India', 'HYBRID', 'FULL_TIME', 1600000, 2800000, 2, 2, 'Full-stack engineers who want to build LLM-powered product features.', 'DRAFT'
where not exists (select 1 from jobs where industry_id = (select id from profiles where username = 'technova_demo') and title = 'AI Product Engineer');
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'AI Product Engineer' and s.name = 'TypeScript'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'AI Product Engineer' and s.name = 'React'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'AI Product Engineer' and s.name = 'FastAPI'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Intermediate', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'technova_demo') and p.title = 'AI Product Engineer' and s.name = 'Large Language Models'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);

insert into jobs (industry_id, title, description, location, work_mode, employment_type, salary_min, salary_max, experience_min_years, openings, eligibility_criteria, application_deadline, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Senior Data Engineer', 'Overview: Lead the design of DataForge''s ingestion and transformation platform for enterprise analytics clients.

Responsibilities: architect batch + streaming pipelines; own data contracts and SLAs; optimise warehouse cost and performance; mentor analytics engineers.

Qualifications: expert SQL; Python; Spark; strong data-modelling fundamentals; cloud warehouse experience.', 'Hyderabad, Telangana, India', 'HYBRID', 'FULL_TIME', 2200000, 3800000, 4, 1, '4+ years building batch and streaming data platforms.', '2026-12-15', 'PUBLISHED'
where not exists (select 1 from jobs where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Senior Data Engineer');
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Senior Data Engineer' and s.name = 'Apache Spark'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Senior Data Engineer' and s.name = 'SQL'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Senior Data Engineer' and s.name = 'Python'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Senior Data Engineer' and s.name = 'ETL'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);

insert into jobs (industry_id, title, description, location, work_mode, employment_type, salary_min, salary_max, experience_min_years, openings, eligibility_criteria, application_deadline, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Machine Learning Engineer', 'Overview: Build forecasting and anomaly-detection models on top of DataForge''s warehouse for client analytics products.

Responsibilities: feature engineering on large tabular datasets; model training and evaluation; deployment as batch scoring jobs; monitoring.

Qualifications: Python; scikit-learn; strong SQL; MLOps basics.', 'Remote (India)', 'REMOTE', 'FULL_TIME', 1900000, 3300000, 3, 1, '3+ years shipping ML models on tabular / time-series data.', '2026-12-15', 'PUBLISHED'
where not exists (select 1 from jobs where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Machine Learning Engineer');
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Machine Learning Engineer' and s.name = 'Python'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Machine Learning Engineer' and s.name = 'Scikit-learn'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Machine Learning Engineer' and s.name = 'SQL'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Machine Learning Engineer' and s.name = 'Machine Learning'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);

insert into jobs (industry_id, title, description, location, work_mode, employment_type, salary_min, salary_max, experience_min_years, openings, eligibility_criteria, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Cloud Data Architect', 'Overview (DRAFT — not yet published): Define the reference architecture for DataForge''s next-generation client data platform.

Responsibilities: design multi-tenant warehouse and lakehouse patterns; set governance and security standards; lead build-vs-buy decisions.

Qualifications: deep cloud warehouse expertise; data governance; stakeholder leadership.', 'Hyderabad, Telangana, India', 'HYBRID', 'FULL_TIME', 2600000, 4200000, 6, 1, '6+ years designing cloud data platforms for regulated industries.', 'DRAFT'
where not exists (select 1 from jobs where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Cloud Data Architect');
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Cloud Data Architect' and s.name = 'Google Cloud Platform'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'CORE'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Cloud Data Architect' and s.name = 'Data Warehousing'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);
insert into job_skills (job_id, skill_id, required_level, importance)
select p.id, s.id, 'Advanced', 'IMPORTANT'
from jobs p, skills s
where p.industry_id = (select id from profiles where username = 'dataforge_demo') and p.title = 'DataForge Cloud Data Architect' and s.name = 'SQL'
and not exists (select 1 from job_skills x where x.job_id = p.id and x.skill_id = s.id);

-- industry_projects
insert into industry_projects (industry_id, title, description, location, work_mode, duration_months, team_size, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'technova_demo'), 'AI-Powered Student Recommendation Engine', 'Problem: campus placement cells struggle to match students to the right opportunities.

Scope: build a recommendation service that ranks internships and jobs for a student from their skills, interests, and history. TechNova provides an anonymised dataset, a mentor, and weekly reviews.

Deliverables: a working API, an offline evaluation report, and a short demo. Strong teams may be invited to internship interviews.', 'Remote (India)', 'REMOTE', 4, 5, 'Student teams with at least one ML-comfortable member.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_projects where industry_id = (select id from profiles where username = 'technova_demo') and title = 'AI-Powered Student Recommendation Engine');

insert into industry_projects (industry_id, title, description, location, work_mode, duration_months, team_size, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'technova_demo'), 'Real-Time Fraud Detection Prototype', 'Problem: detect suspicious transactions within seconds, not hours.

Scope: design a streaming pipeline that scores events in real time and flags anomalies for review. TechNova supplies a synthetic event stream and a mentor from the Platform team.

Deliverables: a running prototype, a latency/accuracy write-up, and a demo dashboard.', 'Bengaluru, Karnataka, India', 'HYBRID', 5, 4, 'Teams comfortable with streaming data and basic ML.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_projects where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Real-Time Fraud Detection Prototype');

insert into industry_projects (industry_id, title, description, location, work_mode, duration_months, team_size, eligibility_criteria, status)
select (select id from profiles where username = 'technova_demo'), 'Developer Productivity Analytics Platform', 'Problem (DRAFT — not yet published): engineering leaders lack a clear, humane view of team health.

Scope: build a dashboard from CI, review, and deployment signals that surfaces bottlenecks without turning into surveillance.

Deliverables: a dashboard, a metrics rationale document, and a demo.', 'Bengaluru, Karnataka, India', 'HYBRID', 4, 4, 'Teams interested in developer tooling and data visualisation.', 'DRAFT'
where not exists (select 1 from industry_projects where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Developer Productivity Analytics Platform');

insert into industry_projects (industry_id, title, description, location, work_mode, duration_months, team_size, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Streaming Ingestion Framework', 'Problem: onboarding a new client data source takes DataForge too long.

Scope: build a config-driven framework that ingests a new streaming source with schema validation and dead-letter handling. A DataForge engineer mentors the team.

Deliverables: the framework, tests, and documentation for adding a source.', 'Remote (India)', 'REMOTE', 5, 4, 'Teams with Python and some distributed-systems exposure.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_projects where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Streaming Ingestion Framework');

insert into industry_projects (industry_id, title, description, location, work_mode, duration_months, team_size, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Self-Serve BI Portal', 'Problem: business users file a ticket for every new report.

Scope: build a portal where users explore governed datasets and build their own charts, with a semantic layer underneath.

Deliverables: a working portal, a semantic-layer design, and a demo.', 'Hyderabad, Telangana, India', 'HYBRID', 4, 5, 'Teams that enjoy front-end work and data modelling.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_projects where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Self-Serve BI Portal');

insert into industry_projects (industry_id, title, description, location, work_mode, duration_months, team_size, eligibility_criteria, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Data Quality Monitoring', 'Problem (DRAFT — not yet published): bad data reaches dashboards before anyone notices.

Scope: build freshness, volume, and distribution checks with alerting and a simple incident view.

Deliverables: the checks, an alerting integration, and a demo.', 'Hyderabad, Telangana, India', 'HYBRID', 3, 3, 'Teams interested in data reliability engineering.', 'DRAFT'
where not exists (select 1 from industry_projects where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Data Quality Monitoring');

-- industry_training
insert into industry_training (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'technova_demo'), 'Machine Learning Foundations', 'A 6-week, project-based introduction to practical machine learning run by TechNova engineers.

Curriculum: the ML workflow; supervised learning; evaluation and leakage; feature engineering; a capstone on a real dataset.

Format: weekly live sessions + guided exercises. Certificate of completion for those who finish the capstone.', 'Remote (India)', 'REMOTE', 2, 40, 'Students and early-career engineers with Python basics.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_training where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Machine Learning Foundations');

insert into industry_training (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'technova_demo'), 'Generative AI Engineering', 'Build real applications on large language models.

Curriculum: prompting and evaluation; retrieval-augmented generation; tool use and agents; guardrails and cost control; a capstone RAG app.

Format: hybrid — onsite labs in Bengaluru plus remote study groups.', 'Bengaluru, Karnataka, India', 'HYBRID', 2, 30, 'Engineers comfortable with Python and REST APIs.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_training where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Generative AI Engineering');

insert into industry_training (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, status)
select (select id from profiles where username = 'technova_demo'), 'Secure Software Development', '(DRAFT — not yet published) A 4-week programme on building software that resists real attacks.

Curriculum: the OWASP Top 10 in practice; authentication and session design; secrets management; dependency and supply-chain risk; secure code review.', 'Remote (India)', 'REMOTE', 1, 35, 'Working developers who ship web services.', 'DRAFT'
where not exists (select 1 from industry_training where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Secure Software Development');

insert into industry_training (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Modern Data Stack Bootcamp', 'A 12-week bootcamp covering the tools DataForge uses every day: cloud warehouse, dbt, orchestration, and BI.

Curriculum: dimensional modelling; dbt project structure and testing; orchestration with Airflow; dashboard design; a portfolio capstone.', 'Remote (India)', 'REMOTE', 3, 35, 'Students and analysts with working SQL.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_training where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Modern Data Stack Bootcamp');

insert into industry_training (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge SQL for Analytics', 'A 4-week intensive that takes you from SELECT to window functions and query tuning.

Curriculum: joins and aggregation; subqueries and CTEs; window functions; query plans and indexing; analytics patterns.', 'Remote (India)', 'REMOTE', 1, 50, 'Beginners welcome; no prior SQL required.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_training where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge SQL for Analytics');

insert into industry_training (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge dbt and Analytics Engineering', 'A completed cohort on analytics engineering with dbt: modelling, testing, documentation, and CI. Kept visible as a reference; a new cohort will open later.', 'Hyderabad, Telangana, India', 'HYBRID', 2, 25, 'Analysts who know SQL and want to adopt engineering practice.', '2026-08-01', '2026-08-15', 'CLOSED'
where not exists (select 1 from industry_training where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge dbt and Analytics Engineering');

insert into industry_training (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Data Governance Essentials', '(DRAFT — not yet published) A 3-week overview of practical data governance: cataloguing, ownership, access control, quality SLAs, and privacy basics.', 'Remote (India)', 'REMOTE', 1, 30, 'Data practitioners and team leads.', 'DRAFT'
where not exists (select 1 from industry_training where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Data Governance Essentials');

-- industry_workshops
insert into industry_workshops (industry_id, title, description, location, work_mode, duration_days, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'technova_demo'), 'Building Your First RAG Application', 'A hands-on day: by the end you will have a working retrieval-augmented generation app.

Agenda: embeddings and vector search; chunking strategies; grounding and citations; a simple evaluation harness; deployment notes.', 'Remote (India)', 'REMOTE', 1, 80, 'Anyone who can write basic Python.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_workshops where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Building Your First RAG Application');

insert into industry_workshops (industry_id, title, description, location, work_mode, duration_days, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'technova_demo'), 'Production API Design', 'A practical workshop on designing HTTP APIs that are pleasant to consume and safe to evolve.

Agenda: resource modelling; pagination and filtering; errors and idempotency; versioning; auth patterns; documentation.', 'Bengaluru, Karnataka, India', 'ONSITE', 1, 40, 'Backend developers with some REST experience.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_workshops where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Production API Design');

insert into industry_workshops (industry_id, title, description, location, work_mode, duration_days, capacity, eligibility_criteria, status)
select (select id from profiles where username = 'technova_demo'), 'Prompt Engineering Workshop', '(DRAFT — not yet published) A half-day on getting reliable results from language models: structured prompts, few-shot design, evaluation, and common failure modes.', 'Remote (India)', 'REMOTE', 1, 100, 'No prerequisites.', 'DRAFT'
where not exists (select 1 from industry_workshops where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Prompt Engineering Workshop');

insert into industry_workshops (industry_id, title, description, location, work_mode, duration_days, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Building Data Pipelines with Airflow', 'Two hands-on days building real orchestration.

Agenda: DAG design and idempotency; backfills; retries and alerting; testing pipelines; incremental models.', 'Remote (India)', 'REMOTE', 2, 60, 'Python basics and some SQL.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_workshops where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Building Data Pipelines with Airflow');

insert into industry_workshops (industry_id, title, description, location, work_mode, duration_days, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Dashboards that Drive Decisions', 'A day on turning data into decisions.

Agenda: choosing the right chart; layout and hierarchy; metric definitions; avoiding misleading visuals; a redesign clinic on your own dashboard.', 'Hyderabad, Telangana, India', 'ONSITE', 1, 35, 'Analysts and anyone who builds reports.', '2026-12-15', '2027-01-20', 'PUBLISHED'
where not exists (select 1 from industry_workshops where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Dashboards that Drive Decisions');

insert into industry_workshops (industry_id, title, description, location, work_mode, duration_days, capacity, eligibility_criteria, application_deadline, start_date, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Cost-Efficient Cloud Warehousing', 'A completed session on cutting cloud warehouse spend without hurting performance: partitioning, clustering, materialisation, and workload isolation. Kept visible as a reference.', 'Remote (India)', 'REMOTE', 1, 45, 'Data engineers and platform owners.', '2026-07-20', '2026-08-05', 'CLOSED'
where not exists (select 1 from industry_workshops where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Cost-Efficient Cloud Warehousing');

insert into industry_workshops (industry_id, title, description, location, work_mode, duration_days, capacity, eligibility_criteria, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Data Contracts Workshop', '(DRAFT — not yet published) A half-day on defining and enforcing data contracts between producers and consumers: schemas, SLAs, versioning, and breaking-change process.', 'Remote (India)', 'REMOTE', 1, 50, 'Teams that produce or consume shared datasets.', 'DRAFT'
where not exists (select 1 from industry_workshops where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Data Contracts Workshop');

-- industry_mentorship
insert into industry_mentorship (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, status)
select (select id from profiles where username = 'technova_demo'), 'Data Science Career Mentorship', 'Six months of 1:1 mentorship with a senior TechNova data scientist.

Focus: building a portfolio, interview preparation (stats, ML, case studies), and choosing between analytics, ML, and research tracks. Monthly goals and fortnightly check-ins.', 'Remote (India)', 'REMOTE', 6, 8, 'Final-year students and recent graduates targeting data-science roles.', '2026-12-15T17:00:00+00:00', 'PUBLISHED'
where not exists (select 1 from industry_mentorship where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Data Science Career Mentorship');

insert into industry_mentorship (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, status)
select (select id from profiles where username = 'technova_demo'), 'Cloud Engineering Mentorship', 'Pair with a TechNova platform engineer for six months.

Focus: Linux and networking depth, infrastructure-as-code, on-call readiness, and building a home-lab portfolio project. Fortnightly sessions plus async review.', 'Remote (India)', 'REMOTE', 6, 6, 'Students and juniors who want to move into platform / infrastructure roles.', '2026-12-15T17:00:00+00:00', 'PUBLISHED'
where not exists (select 1 from industry_mentorship where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Cloud Engineering Mentorship');

insert into industry_mentorship (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, status)
select (select id from profiles where username = 'technova_demo'), 'Women in Technology Mentorship', '(DRAFT — not yet published) A nine-month cohort mentorship programme pairing participants with senior women engineers and leaders at TechNova, with group sessions on negotiation, visibility, and technical leadership alongside 1:1 mentoring.', 'Remote (India)', 'REMOTE', 9, 12, 'Women students and early-career engineers in any technical track.', 'DRAFT'
where not exists (select 1 from industry_mentorship where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Women in Technology Mentorship');

insert into industry_mentorship (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Analytics Engineering Mentorship', 'Six months with a DataForge analytics engineer.

Focus: SQL and modelling depth, dbt project craft, testing and documentation habits, and a portfolio project on a public dataset.', 'Remote (India)', 'REMOTE', 6, 6, 'Analysts and students moving toward analytics engineering.', '2026-12-15T17:00:00+00:00', 'PUBLISHED'
where not exists (select 1 from industry_mentorship where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Analytics Engineering Mentorship');

insert into industry_mentorship (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Data Science Mentorship', 'Pair with a DataForge data scientist for six months.

Focus: framing business problems, tabular and time-series modelling, evaluation discipline, and communicating results to stakeholders.', 'Remote (India)', 'REMOTE', 6, 6, 'Students targeting applied data-science roles.', '2026-12-15T17:00:00+00:00', 'PUBLISHED'
where not exists (select 1 from industry_mentorship where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Data Science Mentorship');

insert into industry_mentorship (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, application_deadline, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Platform Engineering Mentorship', 'A completed mentorship cohort on data-platform engineering: orchestration, reliability, and cost. Kept visible as a reference; a new cohort will open later.', 'Remote (India)', 'REMOTE', 6, 4, 'Juniors moving into data-platform roles.', '2026-07-01', 'CLOSED'
where not exists (select 1 from industry_mentorship where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Platform Engineering Mentorship');

insert into industry_mentorship (industry_id, title, description, location, work_mode, duration_months, capacity, eligibility_criteria, status)
select (select id from profiles where username = 'dataforge_demo'), 'DataForge Research-to-Industry Data Mentorship', '(DRAFT — not yet published) An eight-month programme helping researchers translate academic data skills into industry practice: productionising analysis, working with product teams, and industry interview prep.', 'Remote (India)', 'REMOTE', 8, 5, 'Postgraduate students and researchers moving into industry data roles.', 'DRAFT'
where not exists (select 1 from industry_mentorship where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Research-to-Industry Data Mentorship');

-- industry_collaborations (recipient_type set by trigger)
insert into industry_collaborations (industry_id, recipient_id, recipient_type, title, description, status)
select (select id from profiles where username = 'technova_demo'), (select id from profiles where username = 'faculty_demo'), 'FACULTY', 'Undergraduate AI Research Fellowship (DEMO)', 'TechNova proposes funding two undergraduate research fellows per year to work with the faculty''s lab on applied AI problems, with co-supervision and a stipend. Draft — still being scoped internally, not yet sent.', 'DRAFT'
where not exists (select 1 from industry_collaborations where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Undergraduate AI Research Fellowship (DEMO)');

insert into industry_collaborations (industry_id, recipient_id, recipient_type, title, description, status)
select (select id from profiles where username = 'technova_demo'), (select id from profiles where username = 'institution_demo'), 'INSTITUTION', 'Industry Capstone Project Partnership (DEMO)', 'A semester-long partnership where TechNova supplies real problem statements, datasets, and mentors for final-year capstone teams, and joins the evaluation panel. Sent to the institution for review.', 'SENT'
where not exists (select 1 from industry_collaborations where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Industry Capstone Project Partnership (DEMO)');

insert into industry_collaborations (industry_id, recipient_id, recipient_type, title, description, status)
select (select id from profiles where username = 'technova_demo'), (select id from profiles where username = 'faculty_demo'), 'FACULTY', 'Applied NLP Joint Study Group (DEMO)', 'A fortnightly joint study group between TechNova''s applied-NLP engineers and the faculty''s students, alternating paper discussions and hands-on sessions. Accepted by the faculty; kickoff scheduling in progress.', 'ACCEPTED'
where not exists (select 1 from industry_collaborations where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Applied NLP Joint Study Group (DEMO)');

insert into industry_collaborations (industry_id, recipient_id, recipient_type, title, description, status)
select (select id from profiles where username = 'technova_demo'), (select id from profiles where username = 'institution_demo'), 'INSTITUTION', 'Campus Placement Pipeline Agreement (DEMO)', 'A structured recruiting pipeline: TechNova runs pre-placement talks, a skills workshop series, and priority interview slots for the institution''s students. Accepted; rollout plan being finalised.', 'ACCEPTED'
where not exists (select 1 from industry_collaborations where industry_id = (select id from profiles where username = 'technova_demo') and title = 'Campus Placement Pipeline Agreement (DEMO)');

insert into industry_collaborations (industry_id, recipient_id, recipient_type, title, description, status)
select (select id from profiles where username = 'dataforge_demo'), (select id from profiles where username = 'faculty_demo'), 'FACULTY', 'DataForge Data Engineering Guest Lectures (DEMO)', 'DataForge Labs offers a four-session guest lecture series on the modern data stack for the faculty''s data courses. Sent for review.', 'SENT'
where not exists (select 1 from industry_collaborations where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Data Engineering Guest Lectures (DEMO)');

insert into industry_collaborations (industry_id, recipient_id, recipient_type, title, description, status)
select (select id from profiles where username = 'dataforge_demo'), (select id from profiles where username = 'institution_demo'), 'INSTITUTION', 'DataForge Analytics Curriculum Pilot (DEMO)', 'An active pilot co-developing an analytics-engineering elective with the institution, including shared lab materials and a DataForge teaching assistant. Currently running.', 'ACTIVE'
where not exists (select 1 from industry_collaborations where industry_id = (select id from profiles where username = 'dataforge_demo') and title = 'DataForge Analytics Curriculum Pilot (DEMO)');

-- applications (industry_id set by trigger)
insert into applications (student_id, opportunity_type, internship_id, status, cover_note)
select (select id from profiles where username = 'student_demo_1'), 'INTERNSHIP', o.id, 'APPLIED', 'Final-year CS student with two ML course projects and a Kaggle silver; keen to work on recommendation systems.'
from internships o
where o.industry_id = (select id from profiles where username = 'technova_demo') and o.title = 'Machine Learning Engineering Intern'
and not exists (select 1 from applications x where x.student_id = (select id from profiles where username = 'student_demo_1') and x.internship_id = o.id);

insert into applications (student_id, opportunity_type, job_id, status, cover_note)
select (select id from profiles where username = 'student_demo_2'), 'JOB', o.id, 'APPLIED', 'Backend background moving into ML; strong Python and SQL, comfortable with scikit-learn and evaluation.'
from jobs o
where o.industry_id = (select id from profiles where username = 'technova_demo') and o.title = 'Machine Learning Engineer'
and not exists (select 1 from applications x where x.student_id = (select id from profiles where username = 'student_demo_2') and x.job_id = o.id);

insert into applications (student_id, opportunity_type, job_id, status, cover_note)
select (select id from profiles where username = 'student_demo_1'), 'JOB', o.id, 'UNDER_REVIEW', 'Interested in the full model lifecycle; have shipped a small FastAPI model service for a class project.'
from jobs o
where o.industry_id = (select id from profiles where username = 'technova_demo') and o.title = 'Machine Learning Engineer'
and not exists (select 1 from applications x where x.student_id = (select id from profiles where username = 'student_demo_1') and x.job_id = o.id);

insert into applications (student_id, opportunity_type, job_id, status, cover_note)
select (select id from profiles where username = 'student_demo_2'), 'JOB', o.id, 'INTERVIEW_SCHEDULED', 'Run a home Kubernetes lab; comfortable with Linux internals, Terraform, and on-call style debugging.'
from jobs o
where o.industry_id = (select id from profiles where username = 'technova_demo') and o.title = 'Site Reliability Engineer'
and not exists (select 1 from applications x where x.student_id = (select id from profiles where username = 'student_demo_2') and x.job_id = o.id);

-- student_skills (additive)
insert into student_skills (student_id, skill_id, proficiency_level)
select (select id from profiles where username = 'student_demo_1'), sk.id, 'Intermediate'
from skills sk where sk.name = 'Machine Learning'
and not exists (select 1 from student_skills x where x.student_id = (select id from profiles where username = 'student_demo_1') and x.skill_id = sk.id);

insert into student_skills (student_id, skill_id, proficiency_level)
select (select id from profiles where username = 'student_demo_1'), sk.id, 'Intermediate'
from skills sk where sk.name = 'FastAPI'
and not exists (select 1 from student_skills x where x.student_id = (select id from profiles where username = 'student_demo_1') and x.skill_id = sk.id);

insert into student_skills (student_id, skill_id, proficiency_level)
select (select id from profiles where username = 'student_demo_2'), sk.id, 'Intermediate'
from skills sk where sk.name = 'AWS'
and not exists (select 1 from student_skills x where x.student_id = (select id from profiles where username = 'student_demo_2') and x.skill_id = sk.id);

insert into student_skills (student_id, skill_id, proficiency_level)
select (select id from profiles where username = 'student_demo_2'), sk.id, 'Intermediate'
from skills sk where sk.name = 'Apache Spark'
and not exists (select 1 from student_skills x where x.student_id = (select id from profiles where username = 'student_demo_2') and x.skill_id = sk.id);

commit;
