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
from datetime import datetime as _dt
from datetime import timedelta as _timedelta
from datetime import timezone as _dt_tz
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


SUPABASE_URL = ""
SERVICE_KEY = ""
_HEADERS = {
    "Content-Type": "application/json",
}


def _configure_connection() -> None:
    """Load credentials only for modes which contact Supabase."""
    global SUPABASE_URL, SERVICE_KEY
    SUPABASE_URL, SERVICE_KEY = _load_conn()
    _HEADERS.update({
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
    })


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


def update(table: str, query: str, row: dict) -> None:
    status, payload = _req("PATCH", f"{table}?{query}", row)
    if status not in (200, 204):
        raise RuntimeError(f"UPDATE {table} -> {status}: {payload}\\nrow={row}")


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
# When a seeded PUBLISHED job training programme was "published" -- a fixed
# past timestamp so re-runs and emit-sql are deterministic.
JOB_PROGRAM_PUBLISHED_AT = "2026-11-03T09:00:00+00:00"

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
    # SELECTED for the SRE role -> the access anchor for the seeded Job
    # Training programme below (student_demo_2 already holds the SRE
    # INTERVIEW_SCHEDULED slot, so this is a free (student, job) pair).
    dict(student=STUDENT_1, opportunity_type="JOB",
         posting_title="Site Reliability Engineer", status="SELECTED",
         cover_note="Selected after the panel; strong Linux and Kubernetes fundamentals, keen to formalise on-call practice."),
]

# --------------------------------------------------------------------------
# Job Training programmes (Phase J3, database/migrations/052_job_training.sql)
# --------------------------------------------------------------------------
# ONE published programme so the Student Job Training UI has real, canonical
# content to show in the demo. Seeded straight into the canonical tables
# (job_programs / job_program_modules / job_program_items /
# job_program_skills) via PostgREST + service role -- no fake frontend data.
#
# The programme is built to satisfy the service-layer publish rules
# (job_training_program_service._publish_readiness): a non-blank title, at
# least one PUBLISHED module, and that module carrying at least one
# PUBLISHED item. status is set to PUBLISHED with published_at, exactly as
# publish_program() would leave it.
#
# A student can only SEE a published programme if they hold a non-REVOKED
# job_training_enrollment on the same job (public.student_can_access_job_program,
# 052). So JOB_TRAINING_ENROLLMENTS below selects student_demo_1's SELECTED
# SRE application (APPLICATIONS, above) and provisions the enrollment -- the
# same row the SELECTED transition creates in the product.
#
# NOTE / FUTURE WORK: there is no Industry-side Job Training *authoring* UI
# yet. Programmes are created here (or directly through the job_programs /
# _modules / _items endpoints). Building the Industry authoring surface
# remains future work and is out of scope for this demo seed.
JOB_PROGRAMS = [
    dict(owner=TECHNOVA, job_title="Site Reliability Engineer",
         title="Site Reliability Engineering Onboarding",
         summary=("A structured ramp for a newly selected SRE: reliability "
                  "fundamentals, the on-call workflow, and TechNova's incident "
                  "practice. Work through every module to complete the programme."),
         estimated_weeks=8, status="PUBLISHED",
         modules=[
             dict(title="Foundations of Reliability", order_index=0, is_published=True,
                  description="SLIs, SLOs, error budgets, and how TechNova measures reliability.",
                  items=[
                      dict(title="Reading: implementing SLOs", item_type="LINK",
                           content_url="https://sre.google/workbook/implementing-slos/",
                           order_index=0, is_published=True),
                      dict(title="TechNova reliability glossary", item_type="TEXT",
                           content_text=(
                               "SLI - a direct measure of service behaviour (availability, latency, "
                               "correctness).\n"
                               "SLO - the target for an SLI over a rolling window.\n"
                               "Error budget - 1 minus the SLO: how much unreliability is acceptable "
                               "before feature work pauses in favour of reliability work."),
                           order_index=1, is_published=True),
                  ]),
             dict(title="Incident Response and On-Call", order_index=1, is_published=True,
                  description="The on-call rotation, paging, and blameless postmortems.",
                  items=[
                      dict(title="Reading: managing incidents", item_type="LINK",
                           content_url="https://sre.google/sre-book/managing-incidents/",
                           order_index=0, is_published=True),
                      dict(title="On-call first-week checklist", item_type="TEXT",
                           content_text=(
                               "1. Confirm pager access and the escalation contacts for your service.\n"
                               "2. Read the last five postmortems for your service.\n"
                               "3. Shadow one on-call handover end to end.\n"
                               "4. Know how to open an incident channel and declare a severity."),
                           order_index=1, is_published=True),
                  ]),
         ],
         skills=[
             dict(name="Kubernetes", requirement="REQUIRED"),
             dict(name="Linux", requirement="REQUIRED"),
             dict(name="Terraform", requirement="OPTIONAL"),
         ]),
]

# Students selected for a job that has a seeded programme -- their
# enrollment is what makes that programme visible in the Student UI.
# job_training_enrollments derives student_id / industry_id / job_id from
# the referenced application via a BEFORE INSERT trigger; we pass only
# application_id.
JOB_TRAINING_ENROLLMENTS = [
    dict(student=STUDENT_1, opportunity_type="JOB", posting_title="Site Reliability Engineer"),
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
# PART 2 -- richer Applicant/Participant demo (added for the Industry
# Applicant/Participant Management presentation seed).
# ==========================================================================
#
# Everything below is ADDITIVE to the dataset above, on the SAME sanctioned
# TechNova account (no new demo company) and the SAME idempotent
# "match on a stable natural key, insert only if absent" pattern the rest
# of this file already uses. It adds:
#   * an optional, larger STUDENT roster (env-configurable -- see below)
#   * the 5 Job / 5 Internship / 4 Project / 4 Workshop / 4 Training
#     postings named in the demo brief (skipped if a title already exists
#     under TechNova -- "Machine Learning Engineer" already does)
#   * Project / Workshop / Training APPLICATIONS -- tables that did not
#     exist when the dataset above was written
#   * a couple of real `interviews` rows for the existing / new
#     INTERVIEW_SCHEDULED applications (fixes a pre-existing gap: the
#     original SRE INTERVIEW_SCHEDULED application above has no matching
#     interviews row yet)
#   * `internship_workspaces` for a few SELECTED internship applications
#   * `industry_notifications` / `student_notifications` rows
#
# ENV-CONFIGURABLE STUDENT ROSTER
# --------------------------------
# No code in this repo creates Supabase auth users programmatically, and
# this script does not start (auth admin calls are a materially different
# risk than inserting demo rows via PostgREST). Every extra student MUST
# already exist as a real STUDENT profile:
#
#   DEMO_STUDENT_USER_IDS=<uuid1,uuid2,...>   (optional; comma-separated)
#
# The roster is STUDENT_1, STUDENT_2 (always) plus whichever ids that env
# var supplies, in order. With none set, this section still runs -- using
# only student_demo_1/student_demo_2 -- but most of the demo's per-posting
# state DIVERSITY (the plans below list the most interesting/terminal
# status first specifically so a 2-student roster still shows SELECTED /
# ACCEPTED / COMPLETED examples, not just repeats of APPLIED) and the
# named "Aarav Sharma / Riya Sen / Rahul Verma apply to several modules"
# storylines from the brief need 5 real ids to attach to. Each id is
# TRUSTED as-is (matching how STUDENT_1/STUDENT_2 above are also plain
# constants, never re-verified) -- if one does not exist or is not a
# STUDENT profile, the insert that references it fails loudly with the
# real PostgREST error (a foreign-key violation), exactly like any other
# bad row in this file would.
#
# No auth user is ever created, updated, or deleted by this script.

EXTRA_STUDENT_IDS = [
    s.strip() for s in os.environ.get("DEMO_STUDENT_USER_IDS", "").split(",") if s.strip()
]
STUDENT_ROSTER = [STUDENT_1, STUDENT_2, *EXTRA_STUDENT_IDS]

# 20 fictional personas, cycled onto STUDENT_ROSTER[2:] (STUDENT_1/2 keep
# their existing "Demo Student One/Two" identity -- see PERSONA_PROFILES
# below, which only backfills their institution/department/skills, never
# their name). Only skills confirmed to exist in the live catalog
# (database/seed/skills.sql) are used here -- "IoT" / "Embedded Systems"
# are real posting-title words below but are NOT in the skills catalog, so
# they are never used as a structured student_skills tag.
DEMO_PERSONAS = [
    dict(name="Aarav Sharma", institution="Heritage Institute of Technology", department="CSE", graduation_year=2026,
         skills=["Python", "Machine Learning", "Data Analysis"]),
    dict(name="Riya Sen", institution="Jadavpur University", department="IT", graduation_year=2027,
         skills=["JavaScript", "React", "Next.js"]),
    dict(name="Arjun Mehta", institution="Techno India University", department="ECE", graduation_year=2026,
         skills=["C++", "Python"]),
    dict(name="Ananya Das", institution="IEM Kolkata", department="CSE", graduation_year=2025,
         skills=["Python", "SQL", "Data Analysis"]),
    dict(name="Rahul Verma", institution="NIT Durgapur", department="IT", graduation_year=2026,
         skills=["Node.js", "JavaScript", "FastAPI"]),
    dict(name="Ishita Roy", institution="IIEST Shibpur", department="EE", graduation_year=2027,
         skills=["Python", "Machine Learning"]),
    dict(name="Aditya Nair", institution="Heritage Institute of Technology", department="AI/ML", graduation_year=2026,
         skills=["Python", "Machine Learning", "Cloud Computing"]),
    dict(name="Sneha Gupta", institution="Jadavpur University", department="CSE", graduation_year=2028,
         skills=["Java", "SQL"]),
    dict(name="Rohan Bose", institution="Techno India University", department="IT", graduation_year=2027,
         skills=["React", "JavaScript", "Git"]),
    dict(name="Priya Singh", institution="IEM Kolkata", department="ECE", graduation_year=2026,
         skills=["C++", "Python"]),
    dict(name="Karan Patel", institution="NIT Durgapur", department="CSE", graduation_year=2025,
         skills=["Docker", "Cloud Computing", "Git"]),
    dict(name="Meera Iyer", institution="IIEST Shibpur", department="AI/ML", graduation_year=2027,
         skills=["Python", "Machine Learning", "Data Analysis"]),
    dict(name="Sayan Ghosh", institution="Heritage Institute of Technology", department="IT", graduation_year=2026,
         skills=["Node.js", "JavaScript"]),
    dict(name="Nisha Kapoor", institution="Jadavpur University", department="EE", graduation_year=2028,
         skills=["Python", "SQL"]),
    dict(name="Vikram Rao", institution="Techno India University", department="CSE", graduation_year=2026,
         skills=["Java", "Docker"]),
    dict(name="Diya Banerjee", institution="IEM Kolkata", department="AI/ML", graduation_year=2027,
         skills=["Python", "Machine Learning"]),
    dict(name="Abhishek Jain", institution="NIT Durgapur", department="ECE", graduation_year=2025,
         skills=["C++", "Git"]),
    dict(name="Tanisha Dutta", institution="IIEST Shibpur", department="IT", graduation_year=2026,
         skills=["React", "Next.js", "JavaScript"]),
    dict(name="Neel Shah", institution="Heritage Institute of Technology", department="CSE", graduation_year=2027,
         skills=["Python", "FastAPI", "SQL"]),
    dict(name="Pooja Menon", institution="Jadavpur University", department="AI/ML", graduation_year=2026,
         skills=["Python", "Machine Learning", "Cloud Computing"]),
]

# (student_id, institution, department, graduation_year, skills[]) for
# every roster member that gets a persona. These are additive hints only:
# existing profile names and student-profile rows are never overwritten.
PERSONA_PROFILES = []
if len(STUDENT_ROSTER) > 0:
    PERSONA_PROFILES.append(dict(student=STUDENT_1, name=None, **{k: v for k, v in DEMO_PERSONAS[0].items() if k != "name"}))
if len(STUDENT_ROSTER) > 1:
    PERSONA_PROFILES.append(dict(student=STUDENT_2, name=None, **{k: v for k, v in DEMO_PERSONAS[1].items() if k != "name"}))
for _i, _sid in enumerate(EXTRA_STUDENT_IDS):
    _persona = DEMO_PERSONAS[_i % len(DEMO_PERSONAS)]
    PERSONA_PROFILES.append(dict(student=_sid, name=None, **{k: v for k, v in _persona.items() if k != "name"}))

# Named storylines from the brief -- only attached to a real account when
# at least 5 roster members exist (STUDENT_1, STUDENT_2, + 3 extras).
# Below that, the general per-posting plans (further down) still populate
# every state; these three roster slots just don't get a *named* arc.
_HAS_STORY = len(STUDENT_ROSTER) >= 5
AARAV = STUDENT_ROSTER[2] if _HAS_STORY else None
RIYA = STUDENT_ROSTER[3] if _HAS_STORY else None
RAHUL = STUDENT_ROSTER[4] if _HAS_STORY else None

_offset = [0]


def _apps_for(posting_title, opportunity_type, plan):
    """Distributes `plan` (a list of statuses, most-interesting-first) over
    STUDENT_ROSTER, one distinct student per status -- never the same
    student twice against the same posting (the DB's own unique
    (student, posting) index would reject that anyway). Capped to
    len(STUDENT_ROSTER): with a 2-student roster, only the first two
    (most interesting) statuses in `plan` are actually created."""
    n = min(len(plan), len(STUDENT_ROSTER))
    start = _offset[0]
    _offset[0] += 1
    out = []
    for i in range(n):
        student = STUDENT_ROSTER[(start + i) % len(STUDENT_ROSTER)]
        status = plan[i]
        out.append(dict(student=student, opportunity_type=opportunity_type,
                         posting_title=posting_title, status=status,
                         cover_note=f"Demo {status.replace('_', ' ').title()} application."))
    return out


def _mod_apps_for(posting_title, plan):
    """Same as _apps_for but for the Project/Workshop/Training application
    tables (no opportunity_type column -- the table itself is the type)."""
    n = min(len(plan), len(STUDENT_ROSTER))
    start = _offset[0]
    _offset[0] += 1
    out = []
    for i in range(n):
        student = STUDENT_ROSTER[(start + i) % len(STUDENT_ROSTER)]
        out.append(dict(student=student, posting_title=posting_title, status=plan[i]))
    return out


# ---- new postings (skipped automatically if a title already exists) ----

INTERNSHIPS.extend([
    dict(owner=TECHNOVA, title="AI/ML Intern", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=6, stipend_amount=30000,
         openings=3, application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Pre-final/final-year students with an ML/DL course or project.",
         description="Work with TechNova's AI team on real applied-ML problems: data prep, "
                      "model training, and evaluation on production-scale datasets."),
    dict(owner=TECHNOVA, title="Full Stack Development Intern", status="PUBLISHED",
         location=BLR, work_mode="HYBRID", duration_months=6, stipend_amount=28000,
         openings=2, application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Comfortable with a modern JS framework and a backend language.",
         description="Build and ship end-to-end features across TechNova's React front-end "
                      "and FastAPI services, alongside a senior full-stack engineer."),
    dict(owner=TECHNOVA, title="Data Science Intern", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=4, stipend_amount=27000,
         openings=2, application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Strong Python and statistics fundamentals.",
         description="Analyze product data, build predictive models, and present findings "
                      "to the product team as part of TechNova's data science pod."),
    dict(owner=TECHNOVA, title="IoT & Embedded Systems Intern", status="PUBLISHED",
         location=BLR, work_mode="ONSITE", duration_months=4, stipend_amount=25000,
         openings=1, application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Coursework or projects in embedded C/C++ and sensor hardware.",
         description="Prototype firmware and sensor integrations for TechNova's Industry 4.0 "
                      "device line, working closely with the hardware team."),
    dict(owner=TECHNOVA, title="Cloud Engineering Intern", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=6, stipend_amount=29000,
         openings=2, application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Familiar with a major cloud provider and containerization basics.",
         description="Help build and harden TechNova's cloud infrastructure -- CI/CD, "
                      "container platforms, and cost/observability tooling."),
])

JOBS.extend([
    dict(owner=TECHNOVA, title="Frontend Developer", status="PUBLISHED",
         location=BLR, work_mode="HYBRID", employment_type="FULL_TIME",
         salary_min=900000, salary_max=1600000, experience_min_years=1, openings=2,
         application_deadline=DEADLINE,
         eligibility_criteria="1+ years building production React applications.",
         description="Own user-facing features across TechNova's product suite, working "
                      "closely with design and backend engineering."),
    dict(owner=TECHNOVA, title="Backend Developer", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", employment_type="FULL_TIME",
         salary_min=1000000, salary_max=1800000, experience_min_years=1, openings=2,
         application_deadline=DEADLINE,
         eligibility_criteria="1+ years with a backend language and relational databases.",
         description="Design and operate the APIs and services behind TechNova's core "
                      "product, with an emphasis on correctness and performance."),
    dict(owner=TECHNOVA, title="Data Analyst", status="PUBLISHED",
         location=BLR, work_mode="HYBRID", employment_type="FULL_TIME",
         salary_min=800000, salary_max=1400000, experience_min_years=0, openings=2,
         application_deadline=DEADLINE,
         eligibility_criteria="Strong SQL and spreadsheet skills; a BI tool is a plus.",
         description="Turn TechNova's product and business data into dashboards and "
                      "recommendations the leadership team acts on."),
    dict(owner=TECHNOVA, title="Graduate Software Engineer", status="PUBLISHED",
         location=BLR, work_mode="ONSITE", employment_type="FULL_TIME",
         salary_min=700000, salary_max=1200000, experience_min_years=0, openings=3,
         application_deadline=DEADLINE,
         eligibility_criteria="Recent graduates with solid CS fundamentals.",
         description="A rotational graduate program across TechNova's product teams, with "
                      "structured mentorship in the first year."),
])

PROJECTS.extend([
    dict(owner=TECHNOVA, title="Smart Manufacturing Analytics", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=4, team_size=4,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Comfortable with Python and basic data analysis.",
         description="Build analytics dashboards on top of a manufacturing partner's "
                      "production-line sensor data to surface throughput and quality trends."),
    dict(owner=TECHNOVA, title="Predictive Maintenance Platform", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=5, team_size=3,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Some exposure to time-series data or ML is helpful.",
         description="Prototype a predictive-maintenance model that flags at-risk industrial "
                      "equipment ahead of failure, using historical sensor readings."),
    dict(owner=TECHNOVA, title="Industry RAG Knowledge Assistant", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=3, team_size=3,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Python + an interest in LLM applications.",
         description="Build a retrieval-augmented assistant over TechNova's internal "
                      "documentation, with a small React front-end for querying it."),
    dict(owner=TECHNOVA, title="IoT Energy Monitoring System", status="PUBLISHED",
         location=BLR, work_mode="HYBRID", duration_months=4, team_size=3,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Interest in embedded systems and dashboards.",
         description="Instrument a small facility with energy-usage sensors and build a "
                      "live monitoring dashboard for consumption trends."),
])

WORKSHOPS.extend([
    dict(owner=TECHNOVA, title="Modern React Development", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_days=2, capacity=40,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Basic JavaScript knowledge.",
         description="A hands-on two-day workshop covering modern React patterns, hooks, "
                      "and component architecture used in TechNova's own products."),
    dict(owner=TECHNOVA, title="Building Production APIs with FastAPI", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_days=1, capacity=35,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Basic Python.",
         description="Learn to design, test, and document production-grade APIs with "
                      "FastAPI, based on TechNova's own service conventions."),
    dict(owner=TECHNOVA, title="Introduction to Generative AI", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_days=1, capacity=50,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="No prior AI experience required.",
         description="A practical introduction to LLMs, prompting, and retrieval-augmented "
                      "generation, with live demos from TechNova's applied-AI team."),
    dict(owner=TECHNOVA, title="Industry 4.0 & IoT", status="PUBLISHED",
         location=BLR, work_mode="ONSITE", duration_days=1, capacity=30,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Basic electronics/programming familiarity.",
         description="An on-site session on industrial IoT: sensors, connectivity, and "
                      "how TechNova's device line collects and reports data."),
])

TRAINING.extend([
    dict(owner=TECHNOVA, title="Python for Industry", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=2, capacity=40,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="No prior Python experience required.",
         description="An 8-week upskilling program covering Python fundamentals through "
                      "building small real-world tools, mentored by TechNova engineers."),
    dict(owner=TECHNOVA, title="Data Analytics Bootcamp", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=2, capacity=35,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Basic spreadsheet/SQL familiarity.",
         description="A hands-on bootcamp in SQL, data analysis, and dashboarding, using "
                      "anonymized TechNova datasets as practice material."),
    dict(owner=TECHNOVA, title="Cloud Fundamentals", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=1, capacity=40,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Comfortable with the command line.",
         description="A foundational course on cloud computing concepts, containers, and "
                      "deployment basics, taught by TechNova's platform team."),
    dict(owner=TECHNOVA, title="Applied Machine Learning", status="PUBLISHED",
         location=REMOTE_IN, work_mode="REMOTE", duration_months=2, capacity=30,
         application_deadline=DEADLINE, start_date=START,
         eligibility_criteria="Python fundamentals.",
         description="A project-based ML training program: classical models, evaluation, "
                      "and a capstone mini-project reviewed by TechNova's ML team."),
])

# ---- extra Job/Internship applications (reuses the APPLICATIONS loop
# already in run(), further down) ----

APPLICATIONS.extend([
    *_apps_for("AI/ML Intern", "INTERNSHIP",
               ["SELECTED", "SHORTLISTED", "INTERVIEW_SCHEDULED", "SHORTLISTED", "APPLIED", "APPLIED", "REJECTED"]),
    *_apps_for("Full Stack Development Intern", "INTERNSHIP",
               ["SELECTED", "SHORTLISTED", "WITHDRAWN", "APPLIED", "REJECTED"]),
    *_apps_for("Data Science Intern", "INTERNSHIP",
               ["SHORTLISTED", "INTERVIEW_SCHEDULED", "APPLIED", "REJECTED"]),
    *_apps_for("IoT & Embedded Systems Intern", "INTERNSHIP", ["SHORTLISTED", "APPLIED", "REJECTED"]),
    *_apps_for("Cloud Engineering Intern", "INTERNSHIP", ["SELECTED", "SHORTLISTED", "APPLIED"]),
    # One more SELECTED on the pre-existing REMOTE internship, so
    # internship_workspaces below has a 4th, distinct example.
    dict(student=STUDENT_2, opportunity_type="INTERNSHIP",
         posting_title="Machine Learning Engineering Intern", status="SELECTED",
         cover_note="Demo Selected application."),

    *_apps_for("Frontend Developer", "JOB",
               ["SHORTLISTED", "SELECTED", "INTERVIEW_SCHEDULED", "SHORTLISTED", "APPLIED", "APPLIED",
                "UNDER_REVIEW", "REJECTED", "REJECTED"]),
    *_apps_for("Backend Developer", "JOB",
               ["INTERVIEW_SCHEDULED", "SHORTLISTED", "SELECTED", "APPLIED", "APPLIED", "WITHDRAWN"]),
    *_apps_for("Data Analyst", "JOB", ["SELECTED", "SHORTLISTED", "APPLIED", "APPLIED", "REJECTED"]),
    *_apps_for("Graduate Software Engineer", "JOB", ["SHORTLISTED", "APPLIED", "REJECTED"]),
])

# Named storylines get the *specific* status the brief calls for, replacing
# whichever generic entry _apps_for assigned that roster slot (safe: same
# natural key, so this just overwrites the intent before insertion -- the
# list is deduplicated by (student, posting) at insert time regardless).
if _HAS_STORY:
    APPLICATIONS.extend([
        dict(student=AARAV, opportunity_type="INTERNSHIP", posting_title="AI/ML Intern",
             status="SELECTED", cover_note="Aarav Sharma -- demo Selected application."),
        dict(student=RIYA, opportunity_type="JOB", posting_title="Frontend Developer",
             status="SHORTLISTED", cover_note="Riya Sen -- demo Shortlisted application."),
        dict(student=RAHUL, opportunity_type="JOB", posting_title="Backend Developer",
             status="INTERVIEW_SCHEDULED", cover_note="Rahul Verma -- demo Interview application."),
    ])

# ---- Project / Workshop / Training applications (new tables) ----

PROJECT_APPLICATIONS = [
    *_mod_apps_for("Smart Manufacturing Analytics",
                   ["ACTIVE", "SELECTED", "SHORTLISTED", "APPLIED", "APPLIED", "REJECTED"]),
    *_mod_apps_for("Predictive Maintenance Platform", ["COMPLETED", "SELECTED", "SHORTLISTED", "APPLIED"]),
    *_mod_apps_for("Industry RAG Knowledge Assistant",
                   ["SELECTED", "SHORTLISTED", "APPLIED", "APPLIED", "REJECTED"]),
    *_mod_apps_for("IoT Energy Monitoring System", ["ACTIVE", "COMPLETED", "SHORTLISTED", "APPLIED", "WITHDRAWN"]),
]
if _HAS_STORY:
    PROJECT_APPLICATIONS.extend([
        dict(student=AARAV, posting_title="Smart Manufacturing Analytics", status="ACTIVE"),
        dict(student=RIYA, posting_title="Industry RAG Knowledge Assistant", status="SELECTED"),
    ])

WORKSHOP_APPLICATIONS = [
    *_mod_apps_for("Modern React Development", ["ACCEPTED", "ACCEPTED", "COMPLETED", "APPLIED", "APPLIED", "REJECTED"]),
    *_mod_apps_for("Building Production APIs with FastAPI", ["ACCEPTED", "COMPLETED", "APPLIED", "WITHDRAWN"]),
    *_mod_apps_for("Introduction to Generative AI", ["COMPLETED", "ACCEPTED", "COMPLETED", "APPLIED", "REJECTED"]),
    *_mod_apps_for("Industry 4.0 & IoT", ["ACCEPTED", "APPLIED", "REJECTED"]),
]
if _HAS_STORY:
    WORKSHOP_APPLICATIONS.extend([
        dict(student=RAHUL, posting_title="Building Production APIs with FastAPI", status="ACCEPTED"),
        dict(student=AARAV, posting_title="Introduction to Generative AI", status="COMPLETED"),
    ])

TRAINING_APPLICATIONS = [
    *_mod_apps_for("Python for Industry",
                   ["ACCEPTED", "ACCEPTED", "COMPLETED", "COMPLETED", "APPLIED", "APPLIED", "REJECTED"]),
    *_mod_apps_for("Data Analytics Bootcamp", ["ACCEPTED", "COMPLETED", "APPLIED", "WITHDRAWN"]),
    *_mod_apps_for("Cloud Fundamentals", ["ACCEPTED", "APPLIED", "REJECTED"]),
    *_mod_apps_for("Applied Machine Learning", ["ACCEPTED", "COMPLETED", "APPLIED"]),
]
if _HAS_STORY:
    TRAINING_APPLICATIONS.append(
        dict(student=RIYA, posting_title="Python for Industry", status="ACCEPTED")
    )


def _last_application_intent(entries):
    """Keep one final intent per student/posting before any rows are inserted.

    Named demo storylines are deliberately appended after the broad status
    coverage.  Without this consolidation the first generic row would win
    the database's unique constraint and the storyline would silently be
    skipped.
    """
    by_key = {}
    for entry in entries:
        by_key[(entry["student"], entry["posting_title"])] = entry
    return list(by_key.values())


APPLICATIONS[:] = _last_application_intent(APPLICATIONS)
PROJECT_APPLICATIONS[:] = _last_application_intent(PROJECT_APPLICATIONS)
WORKSHOP_APPLICATIONS[:] = _last_application_intent(WORKSHOP_APPLICATIONS)
TRAINING_APPLICATIONS[:] = _last_application_intent(TRAINING_APPLICATIONS)

# ---- interviews (real rows for INTERVIEW_SCHEDULED applications) ----
# scheduled_at is computed relative to "now" so it is always future-safe.

_NOW = _dt.now(_dt_tz.utc)
# Resolved purely by posting (not a specific student): run() finds
# whichever application on that posting already holds a SHORTLISTED or
# INTERVIEW_SCHEDULED status (set above -- required by
# set_interview_derived_ids, 030) and attaches the interview to it. This
# is deliberately posting-based, not roster-index-based: which roster slot
# ends up with that status depends on how many students are configured.
INTERVIEWS = [
    dict(opportunity_type="JOB", posting_title="Site Reliability Engineer",
         scheduled_at=(_NOW + _timedelta(days=2, hours=3)).isoformat(),
         duration_minutes=45, mode="ONLINE", location="https://meet.example.com/technova-sre-demo"),
    dict(opportunity_type="JOB", posting_title="Backend Developer",
         scheduled_at=(_NOW + _timedelta(days=1, hours=2)).isoformat(),
         duration_minutes=45, mode="ONLINE", location="https://meet.example.com/technova-backend-demo"),
    dict(opportunity_type="INTERNSHIP", posting_title="AI/ML Intern",
         scheduled_at=(_NOW + _timedelta(days=4)).isoformat(),
         duration_minutes=30, mode="ONLINE", location="https://meet.example.com/technova-aiml-demo"),
    dict(opportunity_type="INTERNSHIP", posting_title="Data Science Intern",
         scheduled_at=(_NOW + _timedelta(days=3, hours=5)).isoformat(),
         duration_minutes=30, mode="ONLINE", location="https://meet.example.com/technova-ds-demo"),
]

# ---- internship workspaces (for SELECTED, REMOTE/HYBRID internships) ----

INTERNSHIP_WORKSPACES = [
    dict(opportunity_type="INTERNSHIP", posting_title="AI/ML Intern", target_status="IN_PROGRESS"),
    dict(opportunity_type="INTERNSHIP", posting_title="Cloud Engineering Intern", target_status="ACCEPTED"),
    dict(opportunity_type="INTERNSHIP", posting_title="Machine Learning Engineering Intern", target_status="COMPLETED"),
    dict(opportunity_type="INTERNSHIP", posting_title="Full Stack Development Intern", target_status=None),
]

# ---- notifications ----
# Only the vocabularies from 055/060 (industry_notifications) and
# 035/039/052/058/060 (student_notifications) are used -- nothing invented.

INDUSTRY_NOTIFICATIONS = [
    dict(kind="NEW_APPLICATION", opp_kind="JOB", posting_title="Frontend Developer",
         title="New application for Frontend Developer",
         body="A student applied to your Frontend Developer job.", read=False),
    dict(kind="NEW_APPLICATION", opp_kind="INTERNSHIP", posting_title="AI/ML Intern",
         title="New application for AI/ML Intern",
         body="A student applied to your AI/ML Intern internship.", read=False),
    dict(kind="WITHDRAWAL", opp_kind="JOB", posting_title="Backend Developer",
         title="Applicant withdrew (Backend Developer)",
         body="A student withdrew their application for Backend Developer.", read=True),
    dict(kind="NEW_APPLICATION", opp_kind="JOB", posting_title="Data Analyst",
         title="New application for Data Analyst",
         body="A student applied to your Data Analyst job.", read=True),
    dict(kind="NEW_APPLICATION", opp_kind="PROJECT", posting_title="Smart Manufacturing Analytics",
         title="New project application",
         body="A student applied to your Smart Manufacturing Analytics project.", read=False),
    dict(kind="NEW_APPLICATION", opp_kind="PROJECT", posting_title="Industry RAG Knowledge Assistant",
         title="New project application",
         body="A student applied to your Industry RAG Knowledge Assistant project.", read=True),
    dict(kind="NEW_APPLICATION", opp_kind="WORKSHOP", posting_title="Modern React Development",
         title="New workshop registration",
         body="A student registered for your Modern React Development workshop.", read=False),
    dict(kind="NEW_APPLICATION", opp_kind="WORKSHOP", posting_title="Introduction to Generative AI",
         title="New workshop registration",
         body="A student registered for your Introduction to Generative AI workshop.", read=True),
    dict(kind="NEW_APPLICATION", opp_kind="TRAINING", posting_title="Python for Industry",
         title="New training registration",
         body="A student registered for your Python for Industry program.", read=False),
    dict(kind="NEW_APPLICATION", opp_kind="TRAINING", posting_title="Cloud Fundamentals",
         title="New training registration",
         body="A student registered for your Cloud Fundamentals program.", read=True),
    dict(kind="WITHDRAWAL", opp_kind="WORKSHOP", posting_title="Building Production APIs with FastAPI",
         title="Applicant withdrew (Building Production APIs with FastAPI)",
         body="A student withdrew their registration.", read=True),
]

STUDENT_NOTIFICATIONS = [
    dict(student=None, kind="APPLICATION_STATUS", posting_title="Frontend Developer", opp_kind="JOB",
         status_for="SHORTLISTED",
         title="You've been shortlisted", body='Your application for "Frontend Developer" has been shortlisted.',
         entity_type="APPLICATION"),
    dict(student=None, kind="APPLICATION_STATUS", posting_title="AI/ML Intern", opp_kind="INTERNSHIP",
         status_for="SELECTED",
         title="You've been selected", body='Your application for "AI/ML Intern" was selected.',
         entity_type="APPLICATION"),
    dict(student=None, kind="APPLICATION_STATUS", posting_title="Smart Manufacturing Analytics", opp_kind="PROJECT",
         status_for="ACTIVE",
         title="Project active", body='Your project application for "Smart Manufacturing Analytics" is now active.',
         entity_type="PROJECT"),
    dict(student=None, kind="APPLICATION_STATUS", posting_title="Building Production APIs with FastAPI", opp_kind="WORKSHOP",
         status_for="ACCEPTED",
         title="You've been enrolled", body='You have been enrolled in "Building Production APIs with FastAPI".',
         entity_type="WORKSHOP"),
    dict(student=None, kind="APPLICATION_STATUS", posting_title="Introduction to Generative AI", opp_kind="WORKSHOP",
         status_for="COMPLETED",
         title="Workshop completed", body='Your workshop "Introduction to Generative AI" is marked completed.',
         entity_type="WORKSHOP"),
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
}

_MODULE_LISTS = {
    "internships": INTERNSHIPS, "jobs": JOBS, "industry_projects": PROJECTS,
    "industry_training": TRAINING, "industry_workshops": WORKSHOPS,
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

    # ---- job training programmes (job_programs + modules + items + skills) ----
    for prog in JOB_PROGRAMS:
        owner = prog["owner"]
        jobs_found = get(
            f"jobs?industry_id=eq.{owner}"
            f"&title=eq.{urllib.parse.quote(prog['job_title'])}&select=id"
        )
        if not jobs_found:
            print(f"  WARN job training target job not found (seed jobs first): {prog['job_title']}")
            stats.bump("job_programs", created=False)
            continue
        job_id = jobs_found[0]["id"]

        existing = get(f"job_programs?job_id=eq.{job_id}&select=id")
        if existing:
            stats.bump("job_programs", created=False)
            program_id = existing[0]["id"]
        elif not apply:
            stats.bump("job_programs", created=True)
            program_id = None
        else:
            payload = {
                "job_id": job_id,
                "title": prog["title"],
                "summary": prog.get("summary"),
                "estimated_weeks": prog.get("estimated_weeks"),
                "status": prog["status"],
            }
            if prog["status"] == "PUBLISHED":
                payload["published_at"] = JOB_PROGRAM_PUBLISHED_AT
            program_id = insert("job_programs", payload)["id"]
            stats.bump("job_programs", created=True)

        for m in prog.get("modules", []) or []:
            module_id = None
            if program_id is not None:
                found_m = get(
                    f"job_program_modules?program_id=eq.{program_id}"
                    f"&title=eq.{urllib.parse.quote(m['title'])}&select=id"
                )
                if found_m:
                    stats.bump("job_program_modules", created=False)
                    module_id = found_m[0]["id"]
            if module_id is None:
                if apply and program_id is not None:
                    module_id = insert("job_program_modules", {
                        "program_id": program_id,
                        "title": m["title"],
                        "description": m.get("description"),
                        "order_index": m.get("order_index", 0),
                        "is_published": m.get("is_published", False),
                    })["id"]
                stats.bump("job_program_modules", created=True)

            for it in m.get("items", []) or []:
                if module_id is not None:
                    found_it = get(
                        f"job_program_items?module_id=eq.{module_id}"
                        f"&title=eq.{urllib.parse.quote(it['title'])}&select=id"
                    )
                    if found_it:
                        stats.bump("job_program_items", created=False)
                        continue
                if apply and module_id is not None:
                    insert("job_program_items", {
                        "module_id": module_id,
                        "title": it["title"],
                        "item_type": it["item_type"],
                        "content_url": it.get("content_url"),
                        "content_text": it.get("content_text"),
                        "order_index": it.get("order_index", 0),
                        "is_published": it.get("is_published", False),
                    })
                stats.bump("job_program_items", created=True)

        for sk in prog.get("skills", []) or []:
            sid = skills.get(sk["name"].lower())
            if not sid:
                print(f"  WARN job program skill not in catalog: {sk['name']}")
                continue
            if program_id is not None:
                found_s = get(
                    f"job_program_skills?program_id=eq.{program_id}&skill_id=eq.{sid}&select=id"
                )
                if found_s:
                    stats.bump("job_program_skills", created=False)
                    continue
            if apply and program_id is not None:
                insert("job_program_skills", {
                    "program_id": program_id, "skill_id": sid,
                    "requirement": sk["requirement"],
                })
            stats.bump("job_program_skills", created=True)

    # ---- job training enrollments (the student's access anchor) ----
    for e in JOB_TRAINING_ENROLLMENTS:
        postings = get(
            f"jobs?industry_id=eq.{TECHNOVA}"
            f"&title=eq.{urllib.parse.quote(e['posting_title'])}&select=id"
        )
        if not postings:
            print(f"  WARN job training enrollment target job not found: {e['posting_title']}")
            stats.bump("job_training_enrollments", created=False)
            continue
        job_id = postings[0]["id"]
        apps = get(
            f"applications?student_id=eq.{e['student']}&job_id=eq.{job_id}"
            "&status=eq.SELECTED&select=id"
        )
        if not apps:
            print(f"  WARN no SELECTED job application to enroll for: {e['posting_title']}")
            stats.bump("job_training_enrollments", created=False)
            continue
        app_id = apps[0]["id"]
        if get(f"job_training_enrollments?application_id=eq.{app_id}&select=id"):
            stats.bump("job_training_enrollments", created=False)
            continue
        if apply:
            insert("job_training_enrollments", {"application_id": app_id})
        stats.bump("job_training_enrollments", created=True)

    # ---- Part 2: persona profiles (add missing student_profiles + skills) ----
    for p in PERSONA_PROFILES:
        sid = p["student"]
        profile = get(f"profiles?id=eq.{sid}&select=id,role")
        if not profile or profile[0].get("role") != "STUDENT":
            print(f"  WARN not a STUDENT profile, skipping persona: {sid}")
            stats.bump("student_profiles", created=False)
            continue
        sp = get(f"student_profiles?id=eq.{sid}&select=id,institution_name")
        payload = {
            "institution_name": p["institution"], "department": p["department"],
            "graduation_year": p["graduation_year"],
        }
        if sp:
            stats.bump("student_profiles", created=False)
        elif apply:
            insert("student_profiles", {"id": sid, **payload})
            stats.bump("student_profiles", created=True)
        else:
            stats.bump("student_profiles", created=True)

        for skill_name in p.get("skills", []):
            sid2 = skills.get(skill_name.lower())
            if not sid2:
                print(f"  WARN persona skill not in catalog: {skill_name}")
                continue
            found = get(f"student_skills?student_id=eq.{sid}&skill_id=eq.{sid2}&select=id")
            if found:
                stats.bump("student_skills", created=False)
                continue
            if apply:
                insert("student_skills", {
                    "student_id": sid, "skill_id": sid2, "proficiency_level": "Intermediate",
                })
            stats.bump("student_skills", created=True)

    # ---- Part 2: Project / Workshop / Training applications ----
    _MOD_APP_TABLES = {
        "industry_projects": ("industry_project_applications", "project_id", PROJECT_APPLICATIONS, "project_applications"),
        "industry_workshops": ("industry_workshop_applications", "workshop_id", WORKSHOP_APPLICATIONS, "workshop_applications"),
        "industry_training": ("industry_training_applications", "training_id", TRAINING_APPLICATIONS, "training_applications"),
    }
    for posting_table, (app_table, fk, entries, tag) in _MOD_APP_TABLES.items():
        for a in entries:
            postings = get(
                f"{posting_table}?industry_id=eq.{TECHNOVA}"
                f"&title=eq.{urllib.parse.quote(a['posting_title'])}&select=id"
            )
            if not postings:
                print(f"  WARN {tag} target not found (seed postings first): {a['posting_title']}")
                stats.bump(tag, created=False)
                continue
            pid = postings[0]["id"]
            existing = get(f"{app_table}?student_id=eq.{a['student']}&{fk}=eq.{pid}&select=id")
            if existing:
                stats.bump(tag, created=False)
                continue
            if apply:
                insert(app_table, {"student_id": a["student"], fk: pid, "status": a["status"]})
            stats.bump(tag, created=True)

    # ---- Part 2: interviews (real rows for SHORTLISTED/INTERVIEW_SCHEDULED applications) ----
    for iv in INTERVIEWS:
        if iv["opportunity_type"] == "INTERNSHIP":
            postings = get(
                f"internships?industry_id=eq.{TECHNOVA}"
                f"&title=eq.{urllib.parse.quote(iv['posting_title'])}&select=id"
            )
            fk = "internship_id"
        else:
            postings = get(
                f"jobs?industry_id=eq.{TECHNOVA}"
                f"&title=eq.{urllib.parse.quote(iv['posting_title'])}&select=id"
            )
            fk = "job_id"
        if not postings:
            print(f"  WARN interview target posting not found: {iv['posting_title']}")
            stats.bump("interviews", created=False)
            continue
        pid = postings[0]["id"]
        apps = get(
            f"applications?{fk}=eq.{pid}&status=in.(SHORTLISTED,INTERVIEW_SCHEDULED)"
            "&select=id&order=status.desc&limit=1"
        )
        if not apps:
            print(f"  WARN no SHORTLISTED/INTERVIEW_SCHEDULED application for interview: {iv['posting_title']}")
            stats.bump("interviews", created=False)
            continue
        app_id = apps[0]["id"]
        existing = get(f"interviews?application_id=eq.{app_id}&status=eq.SCHEDULED&select=id")
        if existing:
            stats.bump("interviews", created=False)
            continue
        if apply:
            insert("interviews", {
                "application_id": app_id, "scheduled_at": iv["scheduled_at"],
                "duration_minutes": iv["duration_minutes"], "mode": iv["mode"],
                "location": iv["location"],
            })
            # The application is likely already INTERVIEW_SCHEDULED (seeded
            # directly above); if this posting's slot only reached
            # SHORTLISTED, advance it now that a real interview exists.
            update("applications", f"id=eq.{app_id}", {"status": "INTERVIEW_SCHEDULED"})
        stats.bump("interviews", created=True)

    # ---- Part 2: internship workspaces ----
    for w in INTERNSHIP_WORKSPACES:
        postings = get(
            f"internships?industry_id=eq.{TECHNOVA}"
            f"&title=eq.{urllib.parse.quote(w['posting_title'])}&select=id,work_mode"
        )
        if not postings:
            print(f"  WARN workspace target internship not found: {w['posting_title']}")
            stats.bump("internship_workspaces", created=False)
            continue
        if postings[0]["work_mode"] not in ("REMOTE", "HYBRID"):
            print(f"  WARN internship is not REMOTE/HYBRID, no workspace possible: {w['posting_title']}")
            stats.bump("internship_workspaces", created=False)
            continue
        iid = postings[0]["id"]
        apps = get(
            f"applications?internship_id=eq.{iid}&status=eq.SELECTED&select=id&limit=1"
        )
        if not apps:
            print(f"  WARN no SELECTED application to provision a workspace for: {w['posting_title']}")
            stats.bump("internship_workspaces", created=False)
            continue
        app_id = apps[0]["id"]
        existing = get(f"internship_workspaces?application_id=eq.{app_id}&select=id,workspace_status")
        if existing:
            stats.bump("internship_workspaces", created=False)
            ws_id = existing[0]["id"]
            workspace_created = False
        elif not apply:
            stats.bump("internship_workspaces", created=True)
            ws_id = None
            workspace_created = False
        else:
            ws_id = insert("internship_workspaces", {"application_id": app_id})["id"]
            stats.bump("internship_workspaces", created=True)
            workspace_created = True

        if ws_id and workspace_created and w["target_status"] and apply:
            patch = {"workspace_status": w["target_status"]}
            if w["target_status"] == "ACCEPTED":
                patch["accepted_at"] = _NOW.isoformat()
            elif w["target_status"] == "IN_PROGRESS":
                patch["accepted_at"] = _NOW.isoformat()
                patch["started_at"] = _NOW.isoformat()
            elif w["target_status"] == "COMPLETED":
                patch["accepted_at"] = _NOW.isoformat()
                patch["started_at"] = _NOW.isoformat()
                patch["completed_at"] = _NOW.isoformat()
            update("internship_workspaces", f"id=eq.{ws_id}", patch)

    # ---- Part 2: industry notifications ----
    _NOTIF_POSTING_TABLE = {
        "JOB": ("jobs", "job_id", "JOB_APPLICATION"),
        "INTERNSHIP": ("internships", "internship_id", "INTERNSHIP_APPLICATION"),
        "PROJECT": ("industry_projects", "project_id", "PROJECT_APPLICATION"),
        "WORKSHOP": ("industry_workshops", "workshop_id", "WORKSHOP_APPLICATION"),
        "TRAINING": ("industry_training", "training_id", "TRAINING_APPLICATION"),
    }
    for n in INDUSTRY_NOTIFICATIONS:
        posting_table, fk, entity_type = _NOTIF_POSTING_TABLE[n["opp_kind"]]
        postings = get(
            f"{posting_table}?industry_id=eq.{TECHNOVA}"
            f"&title=eq.{urllib.parse.quote(n['posting_title'])}&select=id"
        )
        if not postings:
            print(f"  WARN notification target posting not found: {n['posting_title']}")
            stats.bump("industry_notifications", created=False)
            continue
        pid = postings[0]["id"]
        if n["opp_kind"] in ("JOB", "INTERNSHIP"):
            apps = get(f"applications?{fk}=eq.{pid}&select=id&limit=1")
            related_id = apps[0]["id"] if apps else None
        else:
            related_id = pid
        if not related_id:
            stats.bump("industry_notifications", created=False)
            continue
        existing = get(
            f"industry_notifications?industry_id=eq.{TECHNOVA}"
            f"&title=eq.{urllib.parse.quote(n['title'])}"
            f"&related_entity_id=eq.{related_id}&select=id"
        )
        if existing:
            stats.bump("industry_notifications", created=False)
            continue
        if apply:
            payload = {
                "industry_id": TECHNOVA, "type": n["kind"], "title": n["title"], "body": n["body"],
                "related_entity_type": entity_type, "related_entity_id": related_id,
            }
            if n["read"]:
                payload["read_at"] = _NOW.isoformat()
            insert("industry_notifications", payload)
        stats.bump("industry_notifications", created=True)

    # ---- Part 2: student notifications (a small, illustrative set) ----
    for n in STUDENT_NOTIFICATIONS:
        posting_table, fk, _ = _NOTIF_POSTING_TABLE[n["opp_kind"]]
        postings = get(
            f"{posting_table}?industry_id=eq.{TECHNOVA}"
            f"&title=eq.{urllib.parse.quote(n['posting_title'])}&select=id"
        )
        if not postings:
            stats.bump("student_notifications", created=False)
            continue
        pid = postings[0]["id"]
        if n["opp_kind"] in ("JOB", "INTERNSHIP"):
            apps = get(f"applications?{fk}=eq.{pid}&status=eq.{n['status_for']}&select=id,student_id&limit=1")
            if not apps:
                stats.bump("student_notifications", created=False)
                continue
            student_id, related_id = apps[0]["student_id"], apps[0]["id"]
        else:
            app_table = {"PROJECT": "industry_project_applications", "WORKSHOP": "industry_workshop_applications",
                         "TRAINING": "industry_training_applications"}[n["opp_kind"]]
            apps = get(f"{app_table}?{fk}=eq.{pid}&status=eq.{n['status_for']}&select=id,student_id&limit=1")
            if not apps:
                stats.bump("student_notifications", created=False)
                continue
            student_id, related_id = apps[0]["student_id"], pid
        existing = get(
            f"student_notifications?student_id=eq.{student_id}&title=eq.{urllib.parse.quote(n['title'])}"
            f"&related_entity_id=eq.{related_id}&select=id"
        )
        if existing:
            stats.bump("student_notifications", created=False)
            continue
        if apply:
            insert("student_notifications", {
                "student_id": student_id, "type": n["kind"], "title": n["title"], "body": n["body"],
                "related_entity_type": n["entity_type"], "related_entity_id": related_id,
            })
        stats.bump("student_notifications", created=True)

    stats.report()
    if not apply:
        print("\n(check mode — nothing was written)")
        print(f"\nRoster: {len(STUDENT_ROSTER)} students "
              f"({len(EXTRA_STUDENT_IDS)} from DEMO_STUDENT_USER_IDS). "
              + ("Named storylines (Aarav/Riya/Rahul) are attached to real accounts."
                 if _HAS_STORY else
                 "Set DEMO_STUDENT_USER_IDS with 3+ ids for the named Aarav/Riya/Rahul "
                 "storylines and fuller per-posting state coverage."))


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

    L.append("-- job training programmes (job_programs + modules + items + skills)")
    L.append("-- NOTE: no Industry-side Job Training authoring UI exists yet -- that")
    L.append("-- remains future work. Programmes are seeded here / via the API.")
    for prog in JOB_PROGRAMS:
        o = owner_sql(prog["owner"])
        jt = _quote(prog["job_title"])
        published_at = (
            _quote(JOB_PROGRAM_PUBLISHED_AT) if prog["status"] == "PUBLISHED" else "null"
        )
        L.append("insert into job_programs (job_id, title, summary, estimated_weeks, status, published_at)")
        L.append("select j.id, {ti}, {su}, {wk}, {st}, {pa}".format(
            ti=_quote(prog["title"]), su=_quote(prog.get("summary")),
            wk=_quote(prog.get("estimated_weeks")), st=_quote(prog["status"]), pa=published_at))
        L.append(f"from jobs j where j.industry_id = {o} and j.title = {jt}")
        L.append("and not exists (select 1 from job_programs p where p.job_id = j.id);")
        for m in prog.get("modules", []) or []:
            mt = _quote(m["title"])
            L.append("insert into job_program_modules (program_id, title, description, order_index, is_published)")
            L.append("select p.id, {ti}, {de}, {oi}, {pub}".format(
                ti=mt, de=_quote(m.get("description")), oi=_quote(m.get("order_index", 0)),
                pub=_quote(bool(m.get("is_published", False)))))
            L.append(f"from job_programs p join jobs j on j.id = p.job_id")
            L.append(f"where j.industry_id = {o} and j.title = {jt}")
            L.append(f"and not exists (select 1 from job_program_modules x where x.program_id = p.id and x.title = {mt});")
            for it in m.get("items", []) or []:
                itt = _quote(it["title"])
                L.append("insert into job_program_items (module_id, title, item_type, content_url, content_text, order_index, is_published)")
                L.append("select m.id, {ti}, {ty}, {cu}, {ct}, {oi}, {pub}".format(
                    ti=itt, ty=_quote(it["item_type"]), cu=_quote(it.get("content_url")),
                    ct=_quote(it.get("content_text")), oi=_quote(it.get("order_index", 0)),
                    pub=_quote(bool(it.get("is_published", False)))))
                L.append("from job_program_modules m join job_programs p on p.id = m.program_id")
                L.append("join jobs j on j.id = p.job_id")
                L.append(f"where j.industry_id = {o} and j.title = {jt} and m.title = {mt}")
                L.append(f"and not exists (select 1 from job_program_items x where x.module_id = m.id and x.title = {itt});")
        for sk in prog.get("skills", []) or []:
            L.append("insert into job_program_skills (program_id, skill_id, requirement)")
            L.append("select p.id, s.id, {rq}".format(rq=_quote(sk["requirement"])))
            L.append("from job_programs p join jobs j on j.id = p.job_id, skills s")
            L.append(f"where j.industry_id = {o} and j.title = {jt} and s.name = {_quote(sk['name'])}")
            L.append("and not exists (select 1 from job_program_skills x where x.program_id = p.id and x.skill_id = s.id);")
        L.append("")

    L.append("-- job training enrollments (student access anchor; derived ids set by trigger)")
    for e in JOB_TRAINING_ENROLLMENTS:
        L.append("insert into job_training_enrollments (application_id)")
        L.append("select a.id from applications a join jobs j on j.id = a.job_id")
        L.append("where a.student_id = {s} and j.industry_id = {o} and j.title = {ti} and a.status = 'SELECTED'".format(
            s=owner_sql(e["student"]), o=owner_sql(TECHNOVA), ti=_quote(e["posting_title"])))
        L.append("and not exists (select 1 from job_training_enrollments x where x.application_id = a.id);")
        L.append("")

    L.append("commit;")
    out.write_bytes(("\n".join(L) + "\n").encode("utf-8"))  # LF, UTF-8
    print(f"wrote {out}  ({len(L)} lines)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode in ("--help", "-h"):
        print("usage: python database/seed/industry_demo_seed.py [--check | --apply]")
        print("  --check  inspect the live demo rows and report planned inserts; writes nothing")
        print("  --apply  add missing demo rows only; never deletes or updates existing rows")
    elif mode == "--check":
        _configure_connection()
        run(apply=False)
    elif mode == "--apply":
        _configure_connection()
        run(apply=True)
    elif mode == "--emit-sql":
        sys.exit("--emit-sql is retired: its legacy export omits the current application/workspace data. Use --apply.")
    else:
        sys.exit(f"unknown mode {mode!r} (use --check | --apply)")
