"""Additive, idempotent demo data for the existing Medit Services account.

This seed never creates or edits users/company profiles.  It resolves the
company and student identities from the live database, then inserts only
missing postings, applications, interviews, workspaces, and notifications.
Use ``--check`` for a read-only plan and ``--apply`` only after reviewing it.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / "backend" / ".env"
SUPABASE_URL = ""
SERVICE_KEY = ""
HEADERS = {"Content-Type": "application/json"}


def _load_connection() -> tuple[str, str]:
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\S+)\s*$", line)
            if match:
                values[match.group(1)] = match.group(2)
    url = os.environ.get("SUPABASE_URL") or values.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or values.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not found.")
    return url.rstrip("/"), key


def configure() -> None:
    global SUPABASE_URL, SERVICE_KEY
    SUPABASE_URL, SERVICE_KEY = _load_connection()
    HEADERS.update({"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"})


def request(method: str, path: str, body=None, *, representation: bool = False):
    headers = dict(HEADERS)
    if representation:
        headers["Prefer"] = "return=representation"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    # Do not inherit a broken machine-wide localhost proxy.  This is scoped to
    # this request opener only; no persistent proxy setting is changed.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=30) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def get(path: str):
    status, payload = request("GET", path)
    if status != 200:
        raise RuntimeError(f"GET {path} -> {status}: {payload}")
    return payload


def insert(table: str, row: dict) -> dict:
    status, payload = request("POST", table, [row], representation=True)
    if status not in (200, 201):
        raise RuntimeError(f"INSERT {table} -> {status}: {payload}")
    return payload[0] if isinstance(payload, list) and payload else payload


def update(table: str, query: str, row: dict) -> None:
    status, payload = request("PATCH", f"{table}?{query}", row)
    if status not in (200, 204):
        raise RuntimeError(f"UPDATE {table} -> {status}: {payload}")


class Stats:
    def __init__(self) -> None:
        self.created: dict[str, int] = {}
        self.existing: dict[str, int] = {}

    def bump(self, key: str, created: bool) -> None:
        target = self.created if created else self.existing
        target[key] = target.get(key, 0) + 1

    def report(self) -> None:
        print("\n--- Medit Services demo seed result ---")
        for key in sorted(set(self.created) | set(self.existing)):
            print(f"  {key:30s} created {self.created.get(key, 0):3d}   existing {self.existing.get(key, 0):3d}")


DEADLINE = "2027-02-28"
START = "2027-03-15"
REMOTE = "Remote (India)"
KOLKATA = "Kolkata, West Bengal, India"
HYBRID = "Hybrid - Kolkata"


def skill(name: str, level: str = "Intermediate", importance: str = "IMPORTANT") -> dict:
    return {"name": name, "required_level": level, "importance": importance}


JOBS = [
    {"title": "Junior Software Engineer", "description": "Build and maintain patient-facing web features and internal care-operations tools with Medit Services engineering teams.", "location": KOLKATA, "work_mode": "HYBRID", "employment_type": "FULL_TIME", "salary_min": 600000, "salary_max": 900000, "experience_min_years": 0, "openings": 2, "eligibility_criteria": "0-2 years; sound programming fundamentals and interest in healthcare technology.", "application_deadline": DEADLINE, "status": "PUBLISHED", "skills": [skill("Python"), skill("React"), skill("Git", "Beginner", "OPTIONAL")]},
    {"title": "Healthcare Data Analyst", "description": "Turn clinical operations and service-delivery data into reliable dashboards and decisions for Medit Services teams.", "location": KOLKATA, "work_mode": "HYBRID", "employment_type": "FULL_TIME", "salary_min": 700000, "salary_max": 1100000, "experience_min_years": 1, "openings": 2, "eligibility_criteria": "SQL proficiency, analytical thinking, and comfort explaining findings to non-technical stakeholders.", "application_deadline": DEADLINE, "status": "PUBLISHED", "skills": [skill("SQL", "Intermediate", "CORE"), skill("Data Analysis", "Intermediate", "CORE"), skill("PostgreSQL", "Beginner", "IMPORTANT")]},
    {"title": "Backend Developer - Health Platform", "description": "Design secure, observable APIs that support scheduling, patient records, and partner integrations across the health platform.", "location": REMOTE, "work_mode": "REMOTE", "employment_type": "FULL_TIME", "salary_min": 900000, "salary_max": 1500000, "experience_min_years": 1, "openings": 2, "eligibility_criteria": "Experience with Python services, REST APIs, and relational databases.", "application_deadline": DEADLINE, "status": "PUBLISHED", "skills": [skill("FastAPI", "Intermediate", "CORE"), skill("PostgreSQL", "Intermediate", "IMPORTANT")]},
    {"title": "AI/ML Engineer - Healthcare Analytics", "description": "Prototype explainable models for healthcare analytics and help productionize data pipelines with appropriate validation and monitoring.", "location": REMOTE, "work_mode": "REMOTE", "employment_type": "FULL_TIME", "salary_min": 1200000, "salary_max": 2000000, "experience_min_years": 2, "openings": 1, "eligibility_criteria": "Applied machine learning experience and a careful approach to model evaluation in sensitive domains.", "application_deadline": DEADLINE, "status": "PUBLISHED", "skills": [skill("Python", "Advanced", "CORE"), skill("Machine Learning", "Intermediate", "CORE"), skill("Data Analysis", "Intermediate", "IMPORTANT")]},
]

INTERNSHIPS = [
    {"title": "AI/ML Healthcare Intern", "description": "Work with the analytics team on data preparation, model evaluation, and explainability experiments for healthcare use cases.", "location": REMOTE, "work_mode": "REMOTE", "duration_months": 6, "stipend_amount": 30000, "openings": 2, "eligibility_criteria": "Python fundamentals and coursework or projects in machine learning.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED", "skills": [skill("Python"), skill("Machine Learning"), skill("Data Analysis")]},
    {"title": "Full Stack Development Intern", "description": "Ship accessible React and FastAPI features for internal care-coordination workflows under the guidance of Medit engineers.", "location": HYBRID, "work_mode": "HYBRID", "duration_months": 6, "stipend_amount": 26000, "openings": 2, "eligibility_criteria": "JavaScript fundamentals and interest in full-stack product development.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED", "skills": [skill("React"), skill("Next.js", "Beginner", "IMPORTANT"), skill("FastAPI", "Beginner", "OPTIONAL")]},
    {"title": "Healthcare Data Analytics Intern", "description": "Explore service and operations data, build quality checks, and present concise insights to healthcare program managers.", "location": KOLKATA, "work_mode": "HYBRID", "duration_months": 4, "stipend_amount": 24000, "openings": 2, "eligibility_criteria": "SQL, spreadsheets, and an interest in evidence-based healthcare decisions.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED", "skills": [skill("SQL"), skill("Data Analysis"), skill("PostgreSQL", "Beginner", "OPTIONAL")]},
    {"title": "IoT / Medical Device Intern", "description": "Prototype telemetry and monitoring flows for connected medical-device demonstrations with hardware and software mentors.", "location": HYBRID, "work_mode": "HYBRID", "duration_months": 4, "stipend_amount": 25000, "openings": 1, "eligibility_criteria": "Programming fundamentals and curiosity about sensors, connectivity, and reliable data capture.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED", "skills": [skill("Python"), skill("Git", "Beginner", "OPTIONAL")]},
]

PROJECTS = [
    {"title": "Patient Risk Prediction System", "description": "Build a responsible prototype that flags potential follow-up risk from de-identified patient and service data, with clear evaluation notes.", "location": REMOTE, "work_mode": "REMOTE", "duration_months": 5, "team_size": 4, "eligibility_criteria": "Python, data analysis, and interest in interpretable ML.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED"},
    {"title": "Smart Hospital Resource Dashboard", "description": "Create an operational dashboard showing bed, appointment, and staff-resource trends for hospital administrators.", "location": HYBRID, "work_mode": "HYBRID", "duration_months": 4, "team_size": 4, "eligibility_criteria": "Frontend development and practical data visualization skills.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED"},
    {"title": "Medical Document RAG Assistant", "description": "Prototype a retrieval-augmented assistant for navigating approved medical operations documents with citations and safe failure behavior.", "location": REMOTE, "work_mode": "REMOTE", "duration_months": 4, "team_size": 3, "eligibility_criteria": "Python, APIs, and interest in trustworthy information retrieval.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED"},
    {"title": "IoT Patient Monitoring Prototype", "description": "Design a small connected-monitoring prototype that streams device readings into a dependable visualization and alerting flow.", "location": HYBRID, "work_mode": "HYBRID", "duration_months": 5, "team_size": 3, "eligibility_criteria": "Programming fundamentals and interest in IoT or healthcare devices.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED"},
]

TRAINING = [
    {"title": "Python for Healthcare Data", "description": "An applied programme covering Python, data cleaning, privacy-aware analysis, and small healthcare operations projects.", "location": REMOTE, "work_mode": "REMOTE", "duration_months": 2, "capacity": 30, "eligibility_criteria": "Open to students with basic computer literacy.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED"},
    {"title": "Applied Machine Learning for Medical Analytics", "description": "Hands-on training in feature design, evaluation, explainability, and responsible use of models for medical analytics.", "location": REMOTE, "work_mode": "REMOTE", "duration_months": 3, "capacity": 25, "eligibility_criteria": "Python and introductory statistics.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED"},
    {"title": "Healthcare API Development with FastAPI", "description": "Learn to design, test, document, and secure production-style FastAPI services for healthcare workflows.", "location": HYBRID, "work_mode": "HYBRID", "duration_months": 2, "capacity": 25, "eligibility_criteria": "Basic Python and HTTP concepts.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED"},
    {"title": "Data Visualization & BI for Healthcare", "description": "Build decision-ready dashboards, choose meaningful metrics, and communicate healthcare operations insights responsibly.", "location": KOLKATA, "work_mode": "HYBRID", "duration_months": 2, "capacity": 30, "eligibility_criteria": "Interest in analytics; SQL familiarity is helpful.", "application_deadline": DEADLINE, "start_date": START, "status": "PUBLISHED"},
]

# Student indexes and statuses are deterministic.  They intentionally overlap
# across opportunities to make the Industry Participants page useful.
JOB_PLANS = [[(0, "SHORTLISTED"), (1, "INTERVIEW_SCHEDULED"), (2, "SELECTED"), (3, "APPLIED"), (4, "REJECTED"), (5, "WITHDRAWN")], [(2, "SELECTED"), (3, "SHORTLISTED"), (4, "INTERVIEW_SCHEDULED"), (5, "APPLIED"), (6, "REJECTED")], [(4, "REJECTED"), (5, "SHORTLISTED"), (6, "APPLIED"), (7, "WITHDRAWN"), (8, "SELECTED")], [(7, "APPLIED"), (8, "SHORTLISTED"), (9, "REJECTED"), (0, "APPLIED"), (2, "SELECTED")]]
INTERNSHIP_PLANS = [[(0, "SELECTED"), (1, "SHORTLISTED"), (2, "INTERVIEW_SCHEDULED"), (3, "SELECTED"), (4, "SELECTED"), (5, "REJECTED")], [(1, "APPLIED"), (2, "SHORTLISTED"), (3, "SELECTED"), (6, "APPLIED"), (7, "REJECTED"), (8, "SELECTED")], [(3, "SELECTED"), (4, "SHORTLISTED"), (5, "INTERVIEW_SCHEDULED"), (6, "SELECTED"), (7, "APPLIED"), (9, "REJECTED")], [(4, "SELECTED"), (5, "INTERVIEW_SCHEDULED"), (6, "SHORTLISTED"), (8, "SELECTED"), (9, "APPLIED"), (0, "REJECTED")]]
PROJECT_PLANS = [[(0, "ACTIVE"), (1, "SELECTED"), (2, "SHORTLISTED"), (3, "APPLIED"), (4, "COMPLETED"), (5, "REJECTED")], [(1, "SHORTLISTED"), (3, "SELECTED"), (5, "ACTIVE"), (6, "APPLIED"), (7, "COMPLETED"), (8, "REJECTED")], [(2, "COMPLETED"), (4, "SELECTED"), (6, "SHORTLISTED"), (8, "APPLIED"), (9, "REJECTED")], [(3, "ACTIVE"), (5, "SELECTED"), (7, "SHORTLISTED"), (9, "APPLIED"), (0, "REJECTED")]]
TRAINING_PLANS = [[(0, "ACCEPTED"), (1, "COMPLETED"), (2, "APPLIED"), (3, "ACCEPTED"), (4, "REJECTED"), (5, "WITHDRAWN")], [(1, "COMPLETED"), (2, "ACCEPTED"), (4, "APPLIED"), (6, "REJECTED"), (7, "ACCEPTED")], [(2, "ACCEPTED"), (3, "APPLIED"), (5, "COMPLETED"), (8, "REJECTED"), (9, "ACCEPTED")], [(3, "ACCEPTED"), (4, "APPLIED"), (6, "COMPLETED"), (8, "REJECTED"), (0, "ACCEPTED")]]


def q(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def main(apply: bool) -> None:
    stats = Stats()
    medit_rows = get("industry_profiles?company_name=eq.Medit%20Services&select=id,company_name")
    if len(medit_rows) != 1:
        raise RuntimeError(f"Expected exactly one Medit Services company profile; found {len(medit_rows)}")
    medit_id = medit_rows[0]["id"]
    profile = get(f"profiles?id=eq.{medit_id}&select=id,role,full_name")
    if len(profile) != 1 or profile[0].get("role") != "INDUSTRY":
        raise RuntimeError("Medit Services profile is missing or is not an INDUSTRY account.")

    all_students = get("profiles?role=eq.STUDENT&select=id,full_name&order=created_at.asc")
    students = all_students[:10]
    if not students:
        raise RuntimeError("No existing STUDENT profiles are available.")
    if len(students) < 8:
        print(f"WARN: only {len(students)} existing STUDENT profiles are available; using all of them.")
    ids = [row["id"] for row in students]
    print(f"Resolved Medit Services ({medit_id}); existing STUDENT profiles: {len(all_students)}; using: {len(ids)}")

    skills = {row["name"].lower(): row["id"] for row in get("skills?select=id,name")}
    posting_ids: dict[str, dict[str, str]] = {"jobs": {}, "internships": {}, "industry_projects": {}, "industry_training": {}}

    def seed_postings(table: str, rows: list[dict]) -> None:
        fields = {"jobs": {"title", "description", "location", "work_mode", "employment_type", "salary_min", "salary_max", "experience_min_years", "openings", "eligibility_criteria", "application_deadline", "status"}, "internships": {"title", "description", "location", "work_mode", "duration_months", "stipend_amount", "openings", "eligibility_criteria", "application_deadline", "start_date", "status"}, "industry_projects": {"title", "description", "location", "work_mode", "duration_months", "team_size", "eligibility_criteria", "application_deadline", "start_date", "status"}, "industry_training": {"title", "description", "location", "work_mode", "duration_months", "capacity", "eligibility_criteria", "application_deadline", "start_date", "status"}}[table]
        for row in rows:
            found = get(f"{table}?industry_id=eq.{medit_id}&title=eq.{q(row['title'])}&select=id")
            if found:
                posting_ids[table][row["title"]] = found[0]["id"]
                stats.bump(table, False)
            elif apply:
                payload = {"industry_id": medit_id, **{key: value for key, value in row.items() if key in fields}}
                posting_ids[table][row["title"]] = insert(table, payload)["id"]
                stats.bump(table, True)
            else:
                posting_ids[table][row["title"]] = f"__planned__{table}__{q(row['title'])}"
                stats.bump(table, True)

    seed_postings("jobs", JOBS)
    seed_postings("internships", INTERNSHIPS)
    seed_postings("industry_projects", PROJECTS)
    seed_postings("industry_training", TRAINING)

    def seed_posting_skills(table: str, skill_table: str, rows: list[dict]) -> None:
        for row in rows:
            pid = posting_ids[table].get(row["title"])
            if not pid:
                continue
            for required in row.get("skills", []):
                sid = skills.get(required["name"].lower())
                if not sid:
                    print(f"WARN: canonical skill not found, skipped mapping: {required['name']}")
                    continue
                if pid.startswith("__planned__"):
                    stats.bump(f"{table}:skills", True)
                    continue
                exists = get(f"{skill_table}?{table[:-1] if table.endswith('s') else table}_id=eq.{pid}&skill_id=eq.{sid}&select=id")
                if exists:
                    stats.bump(f"{table}:skills", False)
                elif apply:
                    insert(skill_table, {f"{table[:-1] if table.endswith('s') else table}_id": pid, "skill_id": sid, "required_level": required["required_level"], "importance": required["importance"]})
                    stats.bump(f"{table}:skills", True)
                else:
                    stats.bump(f"{table}:skills", True)

    seed_posting_skills("jobs", "job_skills", JOBS)
    seed_posting_skills("internships", "internship_skills", INTERNSHIPS)

    def seed_applications(table: str, fk: str, rows: list[dict], plans: list[list[tuple[int, str]]], stat_key: str) -> None:
        for opportunity, plan in zip(rows, plans):
            pid = posting_ids[table].get(opportunity["title"])
            if not pid:
                continue
            for student_index, status in plan:
                if student_index >= len(ids):
                    continue
                student_id = ids[student_index]
                if pid.startswith("__planned__"):
                    stats.bump(stat_key, True)
                    continue
                found = get(f"{stat_key}?student_id=eq.{student_id}&{fk}=eq.{pid}&select=id")
                if found:
                    stats.bump(stat_key, False)
                elif apply:
                    payload = {"student_id": student_id, fk: pid, "status": status}
                    if stat_key == "applications":
                        payload.update({"opportunity_type": "INTERNSHIP" if table == "internships" else "JOB", "cover_note": f"Medit Services demo application - {status.replace('_', ' ').title()}."})
                    insert(stat_key, payload)
                    stats.bump(stat_key, True)
                else:
                    stats.bump(stat_key, True)

    seed_applications("jobs", "job_id", JOBS, JOB_PLANS, "applications")
    seed_applications("internships", "internship_id", INTERNSHIPS, INTERNSHIP_PLANS, "applications")
    seed_applications("industry_projects", "project_id", PROJECTS, PROJECT_PLANS, "industry_project_applications")
    seed_applications("industry_training", "training_id", TRAINING, TRAINING_PLANS, "industry_training_applications")

    now = datetime.now(timezone.utc)
    interview_targets = [("jobs", JOBS[0]["title"], 0), ("jobs", JOBS[1]["title"], 4), ("jobs", JOBS[2]["title"], 1), ("jobs", JOBS[3]["title"], 1), ("internships", INTERNSHIPS[0]["title"], 2), ("internships", INTERNSHIPS[2]["title"], 2), ("internships", INTERNSHIPS[3]["title"], 1)]
    for table, title, student_index in interview_targets:
        pid = posting_ids[table].get(title)
        if not pid or student_index >= len(ids):
            continue
        if pid.startswith("__planned__"):
            stats.bump("interviews", True)
            continue
        fk = "job_id" if table == "jobs" else "internship_id"
        apps = get(f"applications?{fk}=eq.{pid}&student_id=eq.{ids[student_index]}&status=in.(SHORTLISTED,INTERVIEW_SCHEDULED)&select=id")
        if not apps:
            print(f"WARN: no interview-eligible application for {title}")
            continue
        app_id = apps[0]["id"]
        existing = get(f"interviews?application_id=eq.{app_id}&status=eq.SCHEDULED&select=id")
        if existing:
            stats.bump("interviews", False)
        elif apply:
            insert("interviews", {"application_id": app_id, "scheduled_at": (now + timedelta(days=2 + len(stats.created))).isoformat(), "duration_minutes": 45 if table == "jobs" else 30, "mode": "ONLINE", "location": "https://meet.example.com/medit-services-demo"})
            stats.bump("interviews", True)
        else:
            stats.bump("interviews", True)

    # Provision up to two workspaces per internship, only for SELECTED apps.
    for opportunity in INTERNSHIPS:
        pid = posting_ids["internships"].get(opportunity["title"])
        if not pid:
            continue
        if pid.startswith("__planned__"):
            selected_count = sum(1 for index, status in INTERNSHIP_PLANS[INTERNSHIPS.index(opportunity)] if status == "SELECTED" and index < len(ids))
            for _ in range(min(2, selected_count)):
                stats.bump("internship_workspaces", True)
            continue
        selected = get(f"applications?internship_id=eq.{pid}&status=eq.SELECTED&select=id&limit=2")
        for app in selected:
            existing = get(f"internship_workspaces?application_id=eq.{app['id']}&select=id,workspace_status")
            if existing:
                stats.bump("internship_workspaces", False)
                continue
            if not apply:
                stats.bump("internship_workspaces", True)
                continue
            workspace = insert("internship_workspaces", {"application_id": app["id"]})
            target = "COMPLETED" if len(stats.created) % 3 == 0 else ("IN_PROGRESS" if len(stats.created) % 2 == 0 else "ACCEPTED")
            patch = {"workspace_status": target}
            if target in ("ACCEPTED", "IN_PROGRESS", "COMPLETED"):
                patch["accepted_at"] = now.isoformat()
            if target in ("IN_PROGRESS", "COMPLETED"):
                patch["started_at"] = now.isoformat()
            if target == "COMPLETED":
                patch["completed_at"] = now.isoformat()
            update("internship_workspaces", f"id=eq.{workspace['id']}", patch)
            stats.bump("internship_workspaces", True)

    entity_map = {"jobs": ("JOB_APPLICATION", "applications", "job_id"), "internships": ("INTERNSHIP_APPLICATION", "applications", "internship_id"), "industry_projects": ("PROJECT_APPLICATION", "industry_project_applications", "project_id"), "industry_training": ("TRAINING_APPLICATION", "industry_training_applications", "training_id")}
    notification_specs = [("jobs", JOBS[0]["title"], "New job application"), ("jobs", JOBS[1]["title"], "New healthcare data application"), ("jobs", JOBS[2]["title"], "New health-platform application"), ("jobs", JOBS[3]["title"], "New AI healthcare application"), ("internships", INTERNSHIPS[0]["title"], "New AI/ML internship application"), ("internships", INTERNSHIPS[1]["title"], "New full-stack internship application"), ("internships", INTERNSHIPS[2]["title"], "New analytics internship application"), ("internships", INTERNSHIPS[3]["title"], "New medical-device internship application"), ("industry_projects", PROJECTS[0]["title"], "New patient-risk project application"), ("industry_projects", PROJECTS[1]["title"], "New hospital-dashboard project application"), ("industry_projects", PROJECTS[2]["title"], "New medical-RAG project application"), ("industry_projects", PROJECTS[3]["title"], "New monitoring project application"), ("industry_training", TRAINING[0]["title"], "New Python training registration"), ("industry_training", TRAINING[1]["title"], "New ML training registration"), ("industry_training", TRAINING[2]["title"], "New FastAPI training registration"), ("industry_training", TRAINING[3]["title"], "New BI training registration"), ("jobs", JOBS[0]["title"], "Interview scheduled for Junior Software Engineer"), ("internships", INTERNSHIPS[0]["title"], "Interview scheduled for AI/ML Healthcare Intern")]
    for table, title, text in notification_specs:
        pid = posting_ids[table].get(title)
        if not pid:
            continue
        entity_type, app_table, fk = entity_map[table]
        if pid.startswith("__planned__"):
            stats.bump("industry_notifications", True)
            continue
        found = get(f"industry_notifications?industry_id=eq.{medit_id}&title=eq.{q(text)}&related_entity_id=eq.{pid}&select=id")
        if found:
            stats.bump("industry_notifications", False)
        elif apply:
            insert("industry_notifications", {"industry_id": medit_id, "type": "NEW_APPLICATION", "title": text, "body": f"Medit Services has a new applicant for {title}.", "related_entity_type": entity_type, "related_entity_id": pid})
            stats.bump("industry_notifications", True)
        else:
            stats.bump("industry_notifications", True)

    student_specs = [("jobs", JOBS[0]["title"], 0, "SHORTLISTED", "You were shortlisted"), ("jobs", JOBS[0]["title"], 1, "INTERVIEW_SCHEDULED", "Your interview is scheduled"), ("internships", INTERNSHIPS[0]["title"], 0, "SELECTED", "You were selected for an internship"), ("industry_projects", PROJECTS[0]["title"], 0, "ACTIVE", "Your project is active"), ("industry_training", TRAINING[0]["title"], 0, "ACCEPTED", "You are enrolled in training"), ("industry_projects", PROJECTS[2]["title"], 2, "COMPLETED", "Project completed"), ("industry_training", TRAINING[1]["title"], 1, "COMPLETED", "Training completed"), ("jobs", JOBS[2]["title"], 4, "REJECTED", "Application update")]
    student_entity = {"jobs": ("APPLICATION", "applications", "job_id"), "internships": ("APPLICATION", "applications", "internship_id"), "industry_projects": ("PROJECT", "industry_project_applications", "project_id"), "industry_training": ("TRAINING", "industry_training_applications", "training_id")}
    for table, title, student_index, status, text in student_specs:
        pid = posting_ids[table].get(title)
        if not pid or student_index >= len(ids):
            continue
        entity_type, app_table, fk = student_entity[table]
        if pid.startswith("__planned__"):
            stats.bump("student_notifications", True)
            continue
        apps = get(f"{app_table}?{fk}=eq.{pid}&student_id=eq.{ids[student_index]}&status=eq.{status}&select=id")
        if not apps:
            continue
        related_id = apps[0]["id"] if table in ("jobs", "internships") else pid
        found = get(f"student_notifications?student_id=eq.{ids[student_index]}&title=eq.{q(text)}&related_entity_id=eq.{related_id}&select=id")
        if found:
            stats.bump("student_notifications", False)
        elif apply:
            insert("student_notifications", {"student_id": ids[student_index], "type": "APPLICATION_STATUS", "title": text, "body": f"Medit Services updated your status for {title}.", "related_entity_type": entity_type, "related_entity_id": related_id})
            stats.bump("student_notifications", True)
        else:
            stats.bump("student_notifications", True)

    stats.report()
    if not apply:
        print("\n(check mode - no writes performed)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode in ("--help", "-h"):
        print("usage: python database/seed/medit_services_demo_seed.py [--check | --apply]")
        print("  --check  resolve Medit/students and report planned inserts; writes nothing")
        print("  --apply  insert missing Medit demo rows; never delete or edit existing rows")
    elif mode in ("--check", "--apply"):
        configure()
        main(mode == "--apply")
    else:
        raise SystemExit(f"unknown mode {mode!r} (use --check | --apply)")
