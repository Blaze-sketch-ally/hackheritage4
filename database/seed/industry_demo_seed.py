"""
Industry Portal demonstration dataset — additive, idempotent seed.

WHY THIS FILE EXISTS
--------------------
The Industry Portal (migrations 017–028) is fully built, but the live
database only carried a thin "just enough to pass E2E" slice of demo data
(5 records per module for TechNova, 1–3 for DataForge, 8 collaborations,
6 applications, and none of the DRAFT / SENT / ACCEPTED lifecycle states).
This seed turns it into a complete, presentation-ready demo environment:
every Industry module visibly populated, every lifecycle state represented,
dashboards and pipelines full, and search/filter demonstrable.

DESIGN RULES
------------
* ADDITIVE ONLY. Nothing existing is updated or deleted. Every row is
  matched on a stable natural key (owner + title, or the app/skill unique
  key) and inserted only when absent — so this script is safe to re-run.
* Goes through the real schema. Rows are inserted via PostgREST with the
  service-role key; all CHECK constraints, foreign keys, enums and BEFORE
  INSERT triggers (set_application_industry_id,
  set_collaboration_recipient_type, set_updated_at) still fire. No SQL is
  executed out of band.
* Only the six sanctioned demo accounts are ever touched:
    technova_demo, dataforge_demo  (owners)
    faculty_demo, institution_demo (collaboration recipients)
    student_demo_1, student_demo_2 (applicants / skill profiles)
  Every other account in the database (real hackathon participants) is
  left completely alone.
* All demo companies/people already carry a "(DEMO)" marker in their
  names; opportunity titles do not repeat "(DEMO)" (it would clutter the
  UI) — they are identifiable by their demo owner. Collaboration titles
  keep the "(DEMO)" suffix to match the existing 8.

USAGE
-----
    python database/seed/industry_demo_seed.py --check     # report only, no writes
    python database/seed/industry_demo_seed.py --apply     # idempotent insert
    python database/seed/industry_demo_seed.py --emit-sql   # write industry_demo.sql

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in backend/.env
(read automatically), or the same two as environment variables.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------
# Connection
# --------------------------------------------------------------------------

_ENV = Path(__file__).resolve().parents[2] / "backend" / ".env"


def _load_conn() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if (not url or not key) and _ENV.exists():
        text = _ENV.read_text()
        if not url:
            m = re.search(r"^SUPABASE_URL=(\S+)", text, re.M)
            url = m.group(1) if m else None
        if not key:
            m = re.search(r"^SUPABASE_SERVICE_ROLE_KEY=(\S+)", text, re.M)
            key = m.group(1) if m else None
    if not url or not key:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not found.")
    return url.rstrip("/"), key


SUPABASE_URL, SERVICE_KEY = _load_conn()
_HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}


def _req(method: str, path: str, body=None, extra_headers=None):
    headers = dict(_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def get(path: str):
    status, payload = _req("GET", path)
    if status != 200:
        raise RuntimeError(f"GET {path} -> {status}: {payload}")
    return payload


def insert(table: str, row: dict):
    status, payload = _req(
        "POST", table, [row], extra_headers={"Prefer": "return=representation"}
    )
    if status not in (200, 201):
        raise RuntimeError(f"INSERT {table} -> {status}: {payload}\nrow={row}")
    return payload[0] if isinstance(payload, list) and payload else payload


# --------------------------------------------------------------------------
# Sanctioned demo account ids (verified against the live profiles table)
# --------------------------------------------------------------------------

TECHNOVA = "8940129e-016a-404d-9838-56b5c890ffda"   # technova_demo   (INDUSTRY)
DATAFORGE = "a57eb1f2-30cc-4b91-9fac-4000898c8804"  # dataforge_demo  (INDUSTRY)
FACULTY = "d218a436-fbae-459f-95d0-714ac7ebd36f"    # faculty_demo    (FACULTY)
INSTITUTION = "4601e967-75e1-4b24-a9eb-17d400734838"  # institution_demo (INSTITUTION)
STUDENT_1 = "6189014d-6575-4f18-9e55-12a9c88afde2"  # student_demo_1  (STUDENT)
STUDENT_2 = "2436f8e9-c70f-4a10-8a5a-9ddc7706e9a8"  # student_demo_2  (STUDENT)

DEADLINE = "2026-12-15"
START = "2027-01-20"
MENTOR_DEADLINE = "2026-12-15T17:00:00+00:00"

BLR = "Bengaluru, Karnataka, India"
HYD = "Hyderabad, Telangana, India"
REMOTE_IN = "Remote (India)"


def _sk(name, level="Intermediate", importance="IMPORTANT"):
    return {"name": name, "required_level": level, "importance": importance}


# ==========================================================================
# DATASET
# ==========================================================================
# Each opportunity: owner, table, title, status, + schema-appropriate fields.
# `skills` (internships/jobs only) is a list of _sk(...) entries.
# Descriptions are structured (Overview / Responsibilities / You'll learn /
# Eligibility) so detail pages read like a real posting.

INTERNSHIPS = [
    # ---------- TechNova (+3) ----------
    dict(owner=TECHNOVA, title="Machine Learning Engineering Intern", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=6, stipend_amount=35000,
         openings=3, application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Pre-final / final-year students in CS, Data Science, or related; prior ML coursework or projects.",
         description=(
             "Overview: Join TechNova's Applied ML team and ship models that power our "
             "recommendation, search-ranking, and document-intelligence products.\n\n"
             "Responsibilities: build and evaluate training pipelines; run offline "
             "experiments and error analysis; help package models for the serving "
             "platform; write clear experiment reports.\n\n"
             "You'll learn: production ML workflow end to end — feature stores, "
             "experiment tracking, model packaging, and A/B evaluation.\n\n"
             "Eligibility: comfortable with Python and NumPy/pandas; exposure to "
             "PyTorch or scikit-learn; coursework in ML or statistics."),
         skills=[_sk("Python", "Advanced", "CORE"), _sk("Machine Learning", "Intermediate", "CORE"),
                 _sk("PyTorch", "Intermediate", "IMPORTANT"), _sk("Pandas", "Intermediate", "IMPORTANT")]),
    dict(owner=TECHNOVA, title="Cloud & DevOps Engineering Intern", status="PUBLISHED",
         location=BLR, work_mode="HYBRID", duration_months=6, stipend_amount=30000,
         openings=2, application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Final-year students in CS/IT with hands-on Linux and scripting experience.",
         description=(
             "Overview: Work with the Platform Engineering team that keeps TechNova's "
             "services reliable, observable, and cheap to run.\n\n"
             "Responsibilities: extend CI/CD pipelines; write Terraform for cloud "
             "infrastructure; build Grafana dashboards and alerts; participate in "
             "blameless incident reviews.\n\n"
             "You'll learn: infrastructure-as-code, container orchestration, and how a "
             "real on-call rotation works.\n\n"
             "Eligibility: solid Linux fundamentals; some Docker; curiosity about "
             "distributed systems."),
         skills=[_sk("Docker", "Intermediate", "CORE"), _sk("Linux", "Intermediate", "CORE"),
                 _sk("CI/CD", "Intermediate", "IMPORTANT"), _sk("Terraform", "Beginner", "IMPORTANT")]),
    dict(owner=TECHNOVA, title="Computer Vision Research Intern", status="DRAFT",
         location=BLR, work_mode="ONSITE", duration_months=4, stipend_amount=32000,
         openings=1,
         eligibility_criteria="Students with a computer-vision project or publication; strong linear algebra.",
         description=(
             "Overview (DRAFT — not yet published): Prototype visual-inspection and "
             "document-parsing models for TechNova's enterprise customers.\n\n"
             "Responsibilities: curate and label datasets; fine-tune detection and "
             "segmentation models; benchmark accuracy vs. latency trade-offs.\n\n"
             "You'll learn: the full research-to-prototype loop on real customer data.\n\n"
             "Eligibility: PyTorch, OpenCV, and a portfolio CV project."),
         skills=[_sk("Computer Vision", "Advanced", "CORE"), _sk("PyTorch", "Advanced", "CORE"),
                 _sk("Python", "Advanced", "IMPORTANT")]),

    # ---------- DataForge (+3) ----------
    dict(owner=DATAFORGE, title="DataForge Analytics Engineering Intern", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=6, stipend_amount=28000,
         openings=2, application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Students with strong SQL and an interest in the modern data stack.",
         description=(
             "Overview: Help DataForge Labs build the transformation layer that turns "
             "raw warehouse data into trustworthy analytics models.\n\n"
             "Responsibilities: write and test dbt models; document metrics; add data "
             "quality checks; support analysts with clean datasets.\n\n"
             "You'll learn: analytics engineering practice — modelling, testing, "
             "lineage, and semantic layers.\n\n"
             "Eligibility: fluent SQL; some Python; tidy, documented work."),
         skills=[_sk("SQL", "Advanced", "CORE"), _sk("Python", "Intermediate", "IMPORTANT"),
                 _sk("Data Analysis", "Intermediate", "IMPORTANT")]),
    dict(owner=DATAFORGE, title="DataForge BI & Visualization Intern", status="PUBLISHED",
         location=HYD, work_mode="HYBRID", duration_months=4, stipend_amount=25000,
         openings=2, application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Students comfortable with spreadsheets, SQL, and at least one BI tool.",
         description=(
             "Overview: Build dashboards that DataForge's client stakeholders actually "
             "use to make decisions.\n\n"
             "Responsibilities: gather reporting requirements; model data for BI; build "
             "Power BI / Tableau dashboards; run short enablement sessions.\n\n"
             "You'll learn: dashboard design, data storytelling, and stakeholder "
             "management.\n\n"
             "Eligibility: SQL basics; an eye for clear visual design."),
         skills=[_sk("Power BI", "Intermediate", "CORE"), _sk("SQL", "Intermediate", "CORE"),
                 _sk("Data Analysis", "Intermediate", "IMPORTANT")]),
    dict(owner=DATAFORGE, title="DataForge Data Platform Intern", status="DRAFT",
         location=HYD, work_mode="HYBRID", duration_months=6, stipend_amount=27000,
         openings=1,
         eligibility_criteria="Students with Python and an interest in data infrastructure.",
         description=(
             "Overview (DRAFT — not yet published): Support the team that runs "
             "DataForge's ingestion and orchestration platform.\n\n"
             "Responsibilities: build Airflow DAGs; add pipeline monitoring; help "
             "migrate batch jobs to incremental models.\n\n"
             "You'll learn: orchestration, warehouse cost management, and pipeline SLAs.\n\n"
             "Eligibility: Python; basic SQL; Linux comfort."),
         skills=[_sk("Python", "Intermediate", "CORE"), _sk("Apache Spark", "Beginner", "IMPORTANT"),
                 _sk("SQL", "Intermediate", "IMPORTANT")]),
]

JOBS = [
    # ---------- TechNova (+3) ----------
    dict(owner=TECHNOVA, title="Machine Learning Engineer", status="PUBLISHED",
         location=BLR, work_mode="HYBRID", employment_type="FULL_TIME",
         salary_min=1800000, salary_max=3200000, experience_min_years=2, openings=2,
         application_deadline=DEADLINE,
         eligibility_criteria="2+ years building ML systems in production.",
         description=(
             "Overview: Own ML features end to end for TechNova's AI products — from "
             "problem framing to a monitored production model.\n\n"
             "Responsibilities: design training and evaluation pipelines; ship models "
             "to the serving platform; set up drift and quality monitoring; mentor "
             "interns.\n\n"
             "Qualifications: strong Python; PyTorch or TensorFlow; experience with "
             "feature engineering and offline/online evaluation; comfort with cloud "
             "infrastructure."),
         skills=[_sk("Python", "Advanced", "CORE"), _sk("Machine Learning", "Advanced", "CORE"),
                 _sk("PyTorch", "Advanced", "IMPORTANT"), _sk("AWS", "Intermediate", "IMPORTANT")]),
    dict(owner=TECHNOVA, title="Site Reliability Engineer", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", employment_type="FULL_TIME",
         salary_min=2000000, salary_max=3600000, experience_min_years=3, openings=1,
         application_deadline=DEADLINE,
         eligibility_criteria="3+ years operating production distributed systems.",
         description=(
             "Overview: Keep TechNova's platform fast, reliable, and cost-efficient as "
             "it scales.\n\n"
             "Responsibilities: own SLOs and error budgets; improve CI/CD and rollout "
             "safety; drive incident response and postmortems; reduce cloud spend.\n\n"
             "Qualifications: deep Linux and networking; Kubernetes; Terraform; strong "
             "scripting; calm under incident pressure."),
         skills=[_sk("Kubernetes", "Advanced", "CORE"), _sk("Linux", "Advanced", "CORE"),
                 _sk("Terraform", "Intermediate", "IMPORTANT"), _sk("CI/CD", "Advanced", "IMPORTANT")]),
    dict(owner=TECHNOVA, title="AI Product Engineer", status="DRAFT",
         location=BLR, work_mode="HYBRID", employment_type="FULL_TIME",
         salary_min=1600000, salary_max=2800000, experience_min_years=2, openings=2,
         eligibility_criteria="Full-stack engineers who want to build LLM-powered product features.",
         description=(
             "Overview (DRAFT — not yet published): Build user-facing features on top "
             "of large language models — retrieval, agents, and evaluation harnesses.\n\n"
             "Responsibilities: design RAG and tool-use flows; build evaluation "
             "datasets; ship React front-ends and FastAPI services; measure quality "
             "in production.\n\n"
             "Qualifications: TypeScript + React; Python + FastAPI; prompt engineering; "
             "product sense."),
         skills=[_sk("TypeScript", "Advanced", "CORE"), _sk("React", "Advanced", "CORE"),
                 _sk("FastAPI", "Intermediate", "IMPORTANT"), _sk("Large Language Models", "Intermediate", "IMPORTANT")]),

    # ---------- DataForge (+3) ----------
    dict(owner=DATAFORGE, title="DataForge Senior Data Engineer", status="PUBLISHED",
         location=HYD, work_mode="HYBRID", employment_type="FULL_TIME",
         salary_min=2200000, salary_max=3800000, experience_min_years=4, openings=1,
         application_deadline=DEADLINE,
         eligibility_criteria="4+ years building batch and streaming data platforms.",
         description=(
             "Overview: Lead the design of DataForge's ingestion and transformation "
             "platform for enterprise analytics clients.\n\n"
             "Responsibilities: architect batch + streaming pipelines; own data "
             "contracts and SLAs; optimise warehouse cost and performance; mentor "
             "analytics engineers.\n\n"
             "Qualifications: expert SQL; Python; Spark; strong data-modelling "
             "fundamentals; cloud warehouse experience."),
         skills=[_sk("Apache Spark", "Advanced", "CORE"), _sk("SQL", "Advanced", "CORE"),
                 _sk("Python", "Advanced", "IMPORTANT"), _sk("ETL", "Advanced", "IMPORTANT")]),
    dict(owner=DATAFORGE, title="DataForge Machine Learning Engineer", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", employment_type="FULL_TIME",
         salary_min=1900000, salary_max=3300000, experience_min_years=3, openings=1,
         application_deadline=DEADLINE,
         eligibility_criteria="3+ years shipping ML models on tabular / time-series data.",
         description=(
             "Overview: Build forecasting and anomaly-detection models on top of "
             "DataForge's warehouse for client analytics products.\n\n"
             "Responsibilities: feature engineering on large tabular datasets; model "
             "training and evaluation; deployment as batch scoring jobs; monitoring.\n\n"
             "Qualifications: Python; scikit-learn; strong SQL; MLOps basics."),
         skills=[_sk("Python", "Advanced", "CORE"), _sk("Scikit-learn", "Advanced", "CORE"),
                 _sk("SQL", "Advanced", "IMPORTANT"), _sk("Machine Learning", "Advanced", "IMPORTANT")]),
    dict(owner=DATAFORGE, title="DataForge Cloud Data Architect", status="DRAFT",
         location=HYD, work_mode="HYBRID", employment_type="FULL_TIME",
         salary_min=2600000, salary_max=4200000, experience_min_years=6, openings=1,
         eligibility_criteria="6+ years designing cloud data platforms for regulated industries.",
         description=(
             "Overview (DRAFT — not yet published): Define the reference architecture "
             "for DataForge's next-generation client data platform.\n\n"
             "Responsibilities: design multi-tenant warehouse and lakehouse patterns; "
             "set governance and security standards; lead build-vs-buy decisions.\n\n"
             "Qualifications: deep cloud warehouse expertise; data governance; "
             "stakeholder leadership."),
         skills=[_sk("Google Cloud Platform", "Advanced", "CORE"), _sk("Data Warehousing", "Advanced", "CORE"),
                 _sk("SQL", "Advanced", "IMPORTANT")]),
]

PROJECTS = [
    # ---------- TechNova (+3) ----------
    dict(owner=TECHNOVA, title="AI-Powered Student Recommendation Engine", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=4, team_size=5,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Student teams with at least one ML-comfortable member.",
         description=(
             "Problem: campus placement cells struggle to match students to the right "
             "opportunities.\n\n"
             "Scope: build a recommendation service that ranks internships and jobs for "
             "a student from their skills, interests, and history. TechNova provides an "
             "anonymised dataset, a mentor, and weekly reviews.\n\n"
             "Deliverables: a working API, an offline evaluation report, and a short "
             "demo. Strong teams may be invited to internship interviews."),
         ),
    dict(owner=TECHNOVA, title="Real-Time Fraud Detection Prototype", status="PUBLISHED",
         location=BLR, work_mode="HYBRID", duration_months=5, team_size=4,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Teams comfortable with streaming data and basic ML.",
         description=(
             "Problem: detect suspicious transactions within seconds, not hours.\n\n"
             "Scope: design a streaming pipeline that scores events in real time and "
             "flags anomalies for review. TechNova supplies a synthetic event stream "
             "and a mentor from the Platform team.\n\n"
             "Deliverables: a running prototype, a latency/accuracy write-up, and a "
             "demo dashboard."),
         ),
    dict(owner=TECHNOVA, title="Developer Productivity Analytics Platform", status="DRAFT",
         location=BLR, work_mode="HYBRID", duration_months=4, team_size=4,
         eligibility_criteria="Teams interested in developer tooling and data visualisation.",
         description=(
             "Problem (DRAFT — not yet published): engineering leaders lack a clear, "
             "humane view of team health.\n\n"
             "Scope: build a dashboard from CI, review, and deployment signals that "
             "surfaces bottlenecks without turning into surveillance.\n\n"
             "Deliverables: a dashboard, a metrics rationale document, and a demo."),
         ),

    # ---------- DataForge (+3) ----------
    dict(owner=DATAFORGE, title="DataForge Streaming Ingestion Framework", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=5, team_size=4,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Teams with Python and some distributed-systems exposure.",
         description=(
             "Problem: onboarding a new client data source takes DataForge too long.\n\n"
             "Scope: build a config-driven framework that ingests a new streaming "
             "source with schema validation and dead-letter handling. A DataForge "
             "engineer mentors the team.\n\n"
             "Deliverables: the framework, tests, and documentation for adding a "
             "source."),
         ),
    dict(owner=DATAFORGE, title="DataForge Self-Serve BI Portal", status="PUBLISHED",
         location=HYD, work_mode="HYBRID", duration_months=4, team_size=5,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Teams that enjoy front-end work and data modelling.",
         description=(
             "Problem: business users file a ticket for every new report.\n\n"
             "Scope: build a portal where users explore governed datasets and build "
             "their own charts, with a semantic layer underneath.\n\n"
             "Deliverables: a working portal, a semantic-layer design, and a demo."),
         ),
    dict(owner=DATAFORGE, title="DataForge Data Quality Monitoring", status="DRAFT",
         location=HYD, work_mode="HYBRID", duration_months=3, team_size=3,
         eligibility_criteria="Teams interested in data reliability engineering.",
         description=(
             "Problem (DRAFT — not yet published): bad data reaches dashboards before "
             "anyone notices.\n\n"
             "Scope: build freshness, volume, and distribution checks with alerting "
             "and a simple incident view.\n\n"
             "Deliverables: the checks, an alerting integration, and a demo."),
         ),
]

TRAINING = [
    # ---------- TechNova (+3) ----------
    dict(owner=TECHNOVA, title="Machine Learning Foundations", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=2, capacity=40,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Students and early-career engineers with Python basics.",
         description=(
             "A 6-week, project-based introduction to practical machine learning run by "
             "TechNova engineers.\n\n"
             "Curriculum: the ML workflow; supervised learning; evaluation and "
             "leakage; feature engineering; a capstone on a real dataset.\n\n"
             "Format: weekly live sessions + guided exercises. Certificate of "
             "completion for those who finish the capstone."),
         ),
    dict(owner=TECHNOVA, title="Generative AI Engineering", status="PUBLISHED",
         location=BLR, work_mode="HYBRID", duration_months=2, capacity=30,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Engineers comfortable with Python and REST APIs.",
         description=(
             "Build real applications on large language models.\n\n"
             "Curriculum: prompting and evaluation; retrieval-augmented generation; "
             "tool use and agents; guardrails and cost control; a capstone RAG app.\n\n"
             "Format: hybrid — onsite labs in Bengaluru plus remote study groups."),
         ),
    dict(owner=TECHNOVA, title="Secure Software Development", status="DRAFT",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=1, capacity=35,
         eligibility_criteria="Working developers who ship web services.",
         description=(
             "(DRAFT — not yet published) A 4-week programme on building software that "
             "resists real attacks.\n\n"
             "Curriculum: the OWASP Top 10 in practice; authentication and session "
             "design; secrets management; dependency and supply-chain risk; secure "
             "code review."),
         ),

    # ---------- DataForge (+4) ----------
    dict(owner=DATAFORGE, title="DataForge Modern Data Stack Bootcamp", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=3, capacity=35,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Students and analysts with working SQL.",
         description=(
             "A 12-week bootcamp covering the tools DataForge uses every day: cloud "
             "warehouse, dbt, orchestration, and BI.\n\n"
             "Curriculum: dimensional modelling; dbt project structure and testing; "
             "orchestration with Airflow; dashboard design; a portfolio capstone."),
         ),
    dict(owner=DATAFORGE, title="DataForge SQL for Analytics", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=1, capacity=50,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Beginners welcome; no prior SQL required.",
         description=(
             "A 4-week intensive that takes you from SELECT to window functions and "
             "query tuning.\n\n"
             "Curriculum: joins and aggregation; subqueries and CTEs; window "
             "functions; query plans and indexing; analytics patterns."),
         ),
    dict(owner=DATAFORGE, title="DataForge dbt and Analytics Engineering", status="CLOSED",
         location=HYD, work_mode="HYBRID", duration_months=2, capacity=25,
         application_deadline="2026-08-01", start_date="2026-08-15",
         eligibility_criteria="Analysts who know SQL and want to adopt engineering practice.",
         description=(
             "A completed cohort on analytics engineering with dbt: modelling, "
             "testing, documentation, and CI. Kept visible as a reference; a new "
             "cohort will open later."),
         ),
    dict(owner=DATAFORGE, title="DataForge Data Governance Essentials", status="DRAFT",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=1, capacity=30,
         eligibility_criteria="Data practitioners and team leads.",
         description=(
             "(DRAFT — not yet published) A 3-week overview of practical data "
             "governance: cataloguing, ownership, access control, quality SLAs, and "
             "privacy basics."),
         ),
]

WORKSHOPS = [
    # ---------- TechNova (+3) ----------
    dict(owner=TECHNOVA, title="Building Your First RAG Application", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_days=1, capacity=80,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Anyone who can write basic Python.",
         description=(
             "A hands-on day: by the end you will have a working retrieval-augmented "
             "generation app.\n\n"
             "Agenda: embeddings and vector search; chunking strategies; grounding and "
             "citations; a simple evaluation harness; deployment notes."),
         ),
    dict(owner=TECHNOVA, title="Production API Design", status="PUBLISHED",
         location=BLR, work_mode="ONSITE", duration_days=1, capacity=40,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Backend developers with some REST experience.",
         description=(
             "A practical workshop on designing HTTP APIs that are pleasant to consume "
             "and safe to evolve.\n\n"
             "Agenda: resource modelling; pagination and filtering; errors and "
             "idempotency; versioning; auth patterns; documentation."),
         ),
    dict(owner=TECHNOVA, title="Prompt Engineering Workshop", status="DRAFT",
         location=REMOTE_IN, work_mode="REMOTE", duration_days=1, capacity=100,
         eligibility_criteria="No prerequisites.",
         description=(
             "(DRAFT — not yet published) A half-day on getting reliable results from "
             "language models: structured prompts, few-shot design, evaluation, and "
             "common failure modes."),
         ),

    # ---------- DataForge (+4) ----------
    dict(owner=DATAFORGE, title="DataForge Building Data Pipelines with Airflow", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_days=2, capacity=60,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Python basics and some SQL.",
         description=(
             "Two hands-on days building real orchestration.\n\n"
             "Agenda: DAG design and idempotency; backfills; retries and alerting; "
             "testing pipelines; incremental models."),
         ),
    dict(owner=DATAFORGE, title="DataForge Dashboards that Drive Decisions", status="PUBLISHED",
         location=HYD, work_mode="ONSITE", duration_days=1, capacity=35,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Analysts and anyone who builds reports.",
         description=(
             "A day on turning data into decisions.\n\n"
             "Agenda: choosing the right chart; layout and hierarchy; metric "
             "definitions; avoiding misleading visuals; a redesign clinic on your own "
             "dashboard."),
         ),
    dict(owner=DATAFORGE, title="DataForge Cost-Efficient Cloud Warehousing", status="CLOSED",
         location=REMOTE_IN, work_mode="REMOTE", duration_days=1, capacity=45,
         application_deadline="2026-07-20", start_date="2026-08-05",
         eligibility_criteria="Data engineers and platform owners.",
         description=(
             "A completed session on cutting cloud warehouse spend without hurting "
             "performance: partitioning, clustering, materialisation, and workload "
             "isolation. Kept visible as a reference."),
         ),
    dict(owner=DATAFORGE, title="DataForge Data Contracts Workshop", status="DRAFT",
         location=REMOTE_IN, work_mode="REMOTE", duration_days=1, capacity=50,
         eligibility_criteria="Teams that produce or consume shared datasets.",
         description=(
             "(DRAFT — not yet published) A half-day on defining and enforcing data "
             "contracts between producers and consumers: schemas, SLAs, versioning, "
             "and breaking-change process."),
         ),
]

MENTORSHIP = [
    # ---------- TechNova (+3) ----------
    dict(owner=TECHNOVA, title="Data Science Career Mentorship", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=6, capacity=8,
         application_deadline=MENTOR_DEADLINE,
         eligibility_criteria="Final-year students and recent graduates targeting data-science roles.",
         description=(
             "Six months of 1:1 mentorship with a senior TechNova data scientist.\n\n"
             "Focus: building a portfolio, interview preparation (stats, ML, case "
             "studies), and choosing between analytics, ML, and research tracks. "
             "Monthly goals and fortnightly check-ins."),
         ),
    dict(owner=TECHNOVA, title="Cloud Engineering Mentorship", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=6, capacity=6,
         application_deadline=MENTOR_DEADLINE,
         eligibility_criteria="Students and juniors who want to move into platform / infrastructure roles.",
         description=(
             "Pair with a TechNova platform engineer for six months.\n\n"
             "Focus: Linux and networking depth, infrastructure-as-code, on-call "
             "readiness, and building a home-lab portfolio project. Fortnightly "
             "sessions plus async review."),
         ),
    dict(owner=TECHNOVA, title="Women in Technology Mentorship", status="DRAFT",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=9, capacity=12,
         eligibility_criteria="Women students and early-career engineers in any technical track.",
         description=(
             "(DRAFT — not yet published) A nine-month cohort mentorship programme "
             "pairing participants with senior women engineers and leaders at "
             "TechNova, with group sessions on negotiation, visibility, and technical "
             "leadership alongside 1:1 mentoring."),
         ),

    # ---------- DataForge (+4) ----------
    dict(owner=DATAFORGE, title="DataForge Analytics Engineering Mentorship", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=6, capacity=6,
         application_deadline=MENTOR_DEADLINE,
         eligibility_criteria="Analysts and students moving toward analytics engineering.",
         description=(
             "Six months with a DataForge analytics engineer.\n\n"
             "Focus: SQL and modelling depth, dbt project craft, testing and "
             "documentation habits, and a portfolio project on a public dataset."),
         ),
    dict(owner=DATAFORGE, title="DataForge Data Science Mentorship", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=6, capacity=6,
         application_deadline=MENTOR_DEADLINE,
         eligibility_criteria="Students targeting applied data-science roles.",
         description=(
             "Pair with a DataForge data scientist for six months.\n\n"
             "Focus: framing business problems, tabular and time-series modelling, "
             "evaluation discipline, and communicating results to stakeholders."),
         ),
    dict(owner=DATAFORGE, title="DataForge Platform Engineering Mentorship", status="CLOSED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=6, capacity=4,
         application_deadline="2026-07-01",
         eligibility_criteria="Juniors moving into data-platform roles.",
         description=(
             "A completed mentorship cohort on data-platform engineering: "
             "orchestration, reliability, and cost. Kept visible as a reference; a "
             "new cohort will open later."),
         ),
    dict(owner=DATAFORGE, title="DataForge Research-to-Industry Data Mentorship", status="DRAFT",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=8, capacity=5,
         eligibility_criteria="Postgraduate students and researchers moving into industry data roles.",
         description=(
             "(DRAFT — not yet published) An eight-month programme helping researchers "
             "translate academic data skills into industry practice: productionising "
             "analysis, working with product teams, and industry interview prep."),
         ),
]

# Collaborations — recipient_type is set by trigger; we only pass recipient_id.
COLLABORATIONS = [
    # ---------- TechNova (+4): adds the missing DRAFT / SENT / ACCEPTED states ----------
    dict(owner=TECHNOVA, recipient=FACULTY, status="DRAFT",
         title="Undergraduate AI Research Fellowship (DEMO)",
         description=(
             "TechNova proposes funding two undergraduate research fellows per year to "
             "work with the faculty's lab on applied AI problems, with co-supervision "
             "and a stipend. Draft — still being scoped internally, not yet sent.")),
    dict(owner=TECHNOVA, recipient=INSTITUTION, status="SENT",
         title="Industry Capstone Project Partnership (DEMO)",
         description=(
             "A semester-long partnership where TechNova supplies real problem "
             "statements, datasets, and mentors for final-year capstone teams, and "
             "joins the evaluation panel. Sent to the institution for review.")),
    dict(owner=TECHNOVA, recipient=FACULTY, status="ACCEPTED",
         title="Applied NLP Joint Study Group (DEMO)",
         description=(
             "A fortnightly joint study group between TechNova's applied-NLP engineers "
             "and the faculty's students, alternating paper discussions and hands-on "
             "sessions. Accepted by the faculty; kickoff scheduling in progress.")),
    dict(owner=TECHNOVA, recipient=INSTITUTION, status="ACCEPTED",
         title="Campus Placement Pipeline Agreement (DEMO)",
         description=(
             "A structured recruiting pipeline: TechNova runs pre-placement talks, a "
             "skills workshop series, and priority interview slots for the "
             "institution's students. Accepted; rollout plan being finalised.")),

    # ---------- DataForge (+2): gives Industry B a collaboration history for isolation demos ----------
    dict(owner=DATAFORGE, recipient=FACULTY, status="SENT",
         title="DataForge Data Engineering Guest Lectures (DEMO)",
         description=(
             "DataForge Labs offers a four-session guest lecture series on the modern "
             "data stack for the faculty's data courses. Sent for review.")),
    dict(owner=DATAFORGE, recipient=INSTITUTION, status="ACTIVE",
         title="DataForge Analytics Curriculum Pilot (DEMO)",
         description=(
             "An active pilot co-developing an analytics-engineering elective with the "
             "institution, including shared lab materials and a DataForge teaching "
             "assistant. Currently running.")),
]

# Applications — industry_id is set by trigger from the referenced posting.
# Each references a NEW TechNova published posting (no clash with the 6 existing).
APPLICATIONS = [
    dict(student=STUDENT_1, opportunity_type="INTERNSHIP",
         posting_title="Machine Learning Engineering Intern", status="APPLIED",
         cover_note="Final-year CS student with two ML course projects and a Kaggle silver; keen to work on recommendation systems."),
    dict(student=STUDENT_2, opportunity_type="JOB",
         posting_title="Machine Learning Engineer", status="APPLIED",
         cover_note="Backend background moving into ML; strong Python and SQL, comfortable with scikit-learn and evaluation."),
    dict(student=STUDENT_1, opportunity_type="JOB",
         posting_title="Machine Learning Engineer", status="UNDER_REVIEW",
         cover_note="Interested in the full model lifecycle; have shipped a small FastAPI model service for a class project."),
    dict(student=STUDENT_2, opportunity_type="JOB",
         posting_title="Site Reliability Engineer", status="INTERVIEW_SCHEDULED",
         cover_note="Run a home Kubernetes lab; comfortable with Linux internals, Terraform, and on-call style debugging."),
]

# Student skills — additive. "System Design" is not in the curated skills
# catalog; student_demo_2 gets Apache Spark instead (data-engineering aligned).
STUDENT_SKILLS = [
    dict(student=STUDENT_1, skill="Machine Learning", proficiency_level="Intermediate"),
    dict(student=STUDENT_1, skill="FastAPI", proficiency_level="Intermediate"),
    dict(student=STUDENT_2, skill="AWS", proficiency_level="Intermediate"),
    dict(student=STUDENT_2, skill="Apache Spark", proficiency_level="Intermediate"),
]


# ==========================================================================
# APPLY
# ==========================================================================

OPP_TABLES = {
    "internships": ("internships", "internship_skills", "internship_id"),
    "jobs": ("jobs", "job_skills", "job_id"),
    "industry_projects": ("industry_projects", None, None),
    "industry_training": ("industry_training", None, None),
    "industry_workshops": ("industry_workshops", None, None),
    "industry_mentorship": ("industry_mentorship", None, None),
}

_OPP_FIELDS = {
    "internships": ("title", "description", "location", "work_mode", "duration_months",
                    "stipend_amount", "openings", "eligibility_criteria",
                    "application_deadline", "start_date", "status"),
    "jobs": ("title", "description", "location", "work_mode", "employment_type",
             "salary_min", "salary_max", "experience_min_years", "openings",
             "eligibility_criteria", "application_deadline", "status"),
    "industry_projects": ("title", "description", "location", "work_mode",
                          "duration_months", "team_size", "eligibility_criteria",
                          "application_deadline", "start_date", "status"),
    "industry_training": ("title", "description", "location", "work_mode",
                          "duration_months", "capacity", "eligibility_criteria",
                          "application_deadline", "start_date", "status"),
    "industry_workshops": ("title", "description", "location", "work_mode",
                           "duration_days", "capacity", "eligibility_criteria",
                           "application_deadline", "start_date", "status"),
    "industry_mentorship": ("title", "description", "location", "work_mode",
                            "duration_months", "capacity", "eligibility_criteria",
                            "application_deadline", "start_date", "status"),
}

_MODULE_LISTS = {
    "internships": INTERNSHIPS, "jobs": JOBS, "industry_projects": PROJECTS,
    "industry_training": TRAINING, "industry_workshops": WORKSHOPS,
    "industry_mentorship": MENTORSHIP,
}


class Stats:
    def __init__(self):
        self.created = {}
        self.skipped = {}

    def bump(self, key, created):
        d = self.created if created else self.skipped
        d[key] = d.get(key, 0) + 1

    def report(self):
        print("\n--- seed result ---")
        keys = sorted(set(self.created) | set(self.skipped))
        for k in keys:
            print(f"  {k:34s} created {self.created.get(k, 0):3d}   already present {self.skipped.get(k, 0):3d}")


def _skill_ids():
    rows = get("skills?select=id,name")
    return {r["name"].lower(): r["id"] for r in rows}


def _quote(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def run(apply: bool):
    stats = Stats()
    skills = _skill_ids()

    # ---- opportunities + their skill rows ----
    for module, items in _MODULE_LISTS.items():
        table, skill_table, fk = OPP_TABLES[module]
        fields = _OPP_FIELDS[module]
        for item in items:
            owner = item["owner"]
            title = item["title"]
            existing = get(
                f"{table}?industry_id=eq.{owner}&title=eq.{urllib.parse.quote(title)}&select=id"
            )
            if existing:
                stats.bump(module, created=False)
                row_id = existing[0]["id"]
            else:
                if not apply:
                    stats.bump(module, created=True)
                    continue
                payload = {"industry_id": owner}
                for f in fields:
                    if f in item:
                        payload[f] = item[f]
                created = insert(table, payload)
                row_id = created["id"]
                stats.bump(module, created=True)

            for sk in item.get("skills", []) or []:
                if not skill_table:
                    break
                sid = skills.get(sk["name"].lower())
                if not sid:
                    print(f"  WARN skill not in catalog: {sk['name']}")
                    continue
                found = get(f"{skill_table}?{fk}=eq.{row_id}&skill_id=eq.{sid}&select=id")
                if found:
                    stats.bump(f"{module}:skills", created=False)
                    continue
                if apply:
                    insert(skill_table, {
                        fk: row_id, "skill_id": sid,
                        "required_level": sk["required_level"],
                        "importance": sk["importance"],
                    })
                stats.bump(f"{module}:skills", created=True)

    # ---- collaborations ----
    for c in COLLABORATIONS:
        existing = get(
            f"industry_collaborations?industry_id=eq.{c['owner']}"
            f"&title=eq.{urllib.parse.quote(c['title'])}&select=id"
        )
        if existing:
            stats.bump("industry_collaborations", created=False)
            continue
        if apply:
            insert("industry_collaborations", {
                "industry_id": c["owner"], "recipient_id": c["recipient"],
                "recipient_type": c["recipient"] == FACULTY and "FACULTY" or "INSTITUTION",
                "title": c["title"], "description": c["description"], "status": c["status"],
            })
        stats.bump("industry_collaborations", created=True)

    # ---- applications ----
    for a in APPLICATIONS:
        if a["opportunity_type"] == "INTERNSHIP":
            postings = get(
                f"internships?industry_id=eq.{TECHNOVA}"
                f"&title=eq.{urllib.parse.quote(a['posting_title'])}&select=id"
            )
            fk, other = "internship_id", "job_id"
        else:
            postings = get(
                f"jobs?industry_id=eq.{TECHNOVA}"
                f"&title=eq.{urllib.parse.quote(a['posting_title'])}&select=id"
            )
            fk, other = "job_id", "internship_id"
        if not postings:
            print(f"  WARN application target not found (seed opportunities first): {a['posting_title']}")
            stats.bump("applications", created=False)
            continue
        pid = postings[0]["id"]
        existing = get(
            f"applications?student_id=eq.{a['student']}&{fk}=eq.{pid}&select=id"
        )
        if existing:
            stats.bump("applications", created=False)
            continue
        if apply:
            insert("applications", {
                "student_id": a["student"], "opportunity_type": a["opportunity_type"],
                fk: pid, "status": a["status"], "cover_note": a["cover_note"],
            })
        stats.bump("applications", created=True)

    # ---- student skills ----
    for s in STUDENT_SKILLS:
        sid = skills.get(s["skill"].lower())
        if not sid:
            print(f"  WARN student skill not in catalog: {s['skill']}")
            continue
        existing = get(
            f"student_skills?student_id=eq.{s['student']}&skill_id=eq.{sid}&select=id"
        )
        if existing:
            stats.bump("student_skills", created=False)
            continue
        if apply:
            insert("student_skills", {
                "student_id": s["student"], "skill_id": sid,
                "proficiency_level": s["proficiency_level"],
            })
        stats.bump("student_skills", created=True)

    stats.report()
    if not apply:
        print("\n(check mode — nothing was written)")


def emit_sql():
    """Write database/seed/industry_demo.sql — the human-readable, idempotent
    equivalent of this dataset (owner ids resolved by username, skill ids by
    name, every insert guarded by NOT EXISTS)."""
    out = Path(__file__).with_name("industry_demo.sql")
    L = []
    L.append("-- Industry Portal demonstration dataset (additive, idempotent).")
    L.append("-- Generated from industry_demo_seed.py — do not edit by hand.")
    L.append("-- Safe to run repeatedly: every INSERT is guarded by NOT EXISTS.")
    L.append("-- Apply with the Supabase SQL editor or `supabase db` against the")
    L.append("-- project that already has migrations 001-028.")
    L.append("")
    L.append("begin;")
    L.append("")
    uname = {
        TECHNOVA: "technova_demo", DATAFORGE: "dataforge_demo",
        FACULTY: "faculty_demo", INSTITUTION: "institution_demo",
        STUDENT_1: "student_demo_1", STUDENT_2: "student_demo_2",
    }

    def owner_sql(uid):
        return f"(select id from profiles where username = '{uname[uid]}')"

    for module, items in _MODULE_LISTS.items():
        table, skill_table, fk = OPP_TABLES[module]
        fields = _OPP_FIELDS[module]
        L.append(f"-- {table}")
        for item in items:
            cols = ["industry_id"] + [f for f in fields if f in item]
            vals = [owner_sql(item["owner"])] + [_quote(item[f]) for f in fields if f in item]
            L.append(f"insert into {table} ({', '.join(cols)})")
            L.append(f"select {', '.join(vals)}")
            L.append("where not exists (select 1 from {t} where industry_id = {o} and title = {ti});".format(
                t=table, o=owner_sql(item["owner"]), ti=_quote(item["title"])))
            for sk in item.get("skills", []) or []:
                L.append(f"insert into {skill_table} ({fk}, skill_id, required_level, importance)")
                L.append("select p.id, s.id, {lvl}, {imp}".format(
                    lvl=_quote(sk["required_level"]), imp=_quote(sk["importance"])))
                L.append(f"from {table} p, skills s")
                L.append("where p.industry_id = {o} and p.title = {ti} and s.name = {sn}".format(
                    o=owner_sql(item["owner"]), ti=_quote(item["title"]), sn=_quote(sk["name"])))
                L.append(f"and not exists (select 1 from {skill_table} x where x.{fk} = p.id and x.skill_id = s.id);")
            L.append("")

    L.append("-- industry_collaborations (recipient_type set by trigger)")
    for c in COLLABORATIONS:
        L.append("insert into industry_collaborations (industry_id, recipient_id, recipient_type, title, description, status)")
        L.append("select {o}, {r}, {rt}, {ti}, {de}, {st}".format(
            o=owner_sql(c["owner"]), r=owner_sql(c["recipient"]),
            rt=_quote("FACULTY" if c["recipient"] == FACULTY else "INSTITUTION"),
            ti=_quote(c["title"]), de=_quote(c["description"]), st=_quote(c["status"])))
        L.append("where not exists (select 1 from industry_collaborations where industry_id = {o} and title = {ti});".format(
            o=owner_sql(c["owner"]), ti=_quote(c["title"])))
        L.append("")

    L.append("-- applications (industry_id set by trigger)")
    for a in APPLICATIONS:
        tbl = "internships" if a["opportunity_type"] == "INTERNSHIP" else "jobs"
        fk = "internship_id" if a["opportunity_type"] == "INTERNSHIP" else "job_id"
        L.append(f"insert into applications (student_id, opportunity_type, {fk}, status, cover_note)")
        L.append("select {s}, {ot}, o.id, {st}, {cn}".format(
            s=owner_sql(a["student"]), ot=_quote(a["opportunity_type"]),
            st=_quote(a["status"]), cn=_quote(a["cover_note"])))
        L.append(f"from {tbl} o")
        L.append("where o.industry_id = {o} and o.title = {ti}".format(
            o=owner_sql(TECHNOVA), ti=_quote(a["posting_title"])))
        L.append(f"and not exists (select 1 from applications x where x.student_id = {owner_sql(a['student'])} and x.{fk} = o.id);")
        L.append("")

    L.append("-- student_skills (additive)")
    for s in STUDENT_SKILLS:
        L.append("insert into student_skills (student_id, skill_id, proficiency_level)")
        L.append("select {st}, sk.id, {lvl}".format(st=owner_sql(s["student"]), lvl=_quote(s["proficiency_level"])))
        L.append(f"from skills sk where sk.name = {_quote(s['skill'])}")
        L.append(f"and not exists (select 1 from student_skills x where x.student_id = {owner_sql(s['student'])} and x.skill_id = sk.id);")
        L.append("")

    L.append("commit;")
    out.write_bytes(("\n".join(L) + "\n").encode("utf-8"))  # LF, UTF-8
    print(f"wrote {out}  ({len(L)} lines)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode == "--check":
        run(apply=False)
    elif mode == "--apply":
        run(apply=True)
    elif mode == "--emit-sql":
        emit_sql()
    else:
        sys.exit(f"unknown mode {mode!r} (use --check | --apply | --emit-sql)")
