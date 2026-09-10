"""Business logic for the Institution Analytics workspace
(backend/app/api/institution.py, GET /api/v1/institution/analytics).

PHASE 6. This module is a REUSE layer, not a new calculation engine --
per the phase task's own "Reusable Metric Engine" requirement, every
number that already has an authoritative implementation elsewhere is
called, never re-derived:

  - "placed" / "unplaced" / "not participating"       -> institution_service._placement_buckets
  - percentage-with-safe-zero-denominator              -> institution_service._percentage
  - the institution's own departments                  -> institution_service.fetch_departments
  - company name resolution                            -> institution_service._fetch_company_names
  - the institution's own students (id/department/     -> institution_placement_service._fetch_institution_students
    batch/cgpa)
  - per-department student/placement stats             -> institution_department_service.list_departments
    (the EXACT rows /institution/departments renders)
  - drive-scoped placement analytics (participating/    -> institution_placement_service.get_placement_overview
    placed/total_selected_offers/placement_rate/
    department_breakdown)
  - the per-drive table (title/company/eligible/        -> institution_placement_service.list_drives
    applied/selected), the same rows /institution/
    placements renders
  - monthly bucketing helpers                           -> analytics_service._month_key / _recent_month_keys
    (the same helpers Industry Analytics already uses)

New in this module (nothing here duplicates the above): institution-wide
skill coverage/skill-gap comparison, company hiring breakdown across ALL
applications (not just drive-coordinated ones), application-status
distribution, internship/assessment/interview summaries, and a monthly
trend view. All computed via user-scoped RLS reads (build_user_client),
never service_role -- see database/migrations/037_institution_tenancy.sql
for the SELECT policies (student_profiles/applications/student_skills/
assessment_attempts/interviews, all scoped to
`student_profiles.institution_id = auth.uid()`) that make this module's
reads safe without any new migration.

Filters (Part 20 of the phase task): `department_id` / `batch` narrow the
STUDENT set used for `overview`, `applications`, `skills`, `skill_gaps`
coverage, `internships`, `assessments`, and `interviews`. `date_from` /
`date_to` additionally narrow which applications count toward
`applications` and `internships.applications_total` /
`status_distribution`. They do NOT narrow `departments` (that table IS
the per-department breakdown a department filter would otherwise
re-derive), `placements` (drive eligibility already has its own criteria
model), or `companies` (an institution-wide breakdown, like `departments`)
-- seeing `filter_scope_note` on the response for the same explanation
surfaced to the frontend.

Skill-gap honesty (Part 14/15): `job_skills` (019_jobs.sql) DOES model
required skills, so this is a real, schema-backed comparison -- not
skipped. But the flags are two small DOCUMENTED constant thresholds
(`_SKILL_GAP_MIN_DEMAND`, `_SKILL_GAP_LOW_COVERAGE_PCT`), never an opaque
AI score, and the label is "High demand / Low coverage", never
"Critical shortage" (no such rule is defined). If zero currently-PUBLISHED
jobs declare any required skill, the comparison is honestly marked
unavailable rather than shown as an empty "no gaps" result (which would
misleadingly imply everything is fully covered).
"""

from collections import Counter
from datetime import UTC, datetime

from supabase import Client

from app.schemas.application import APPLICATION_STATUSES
from app.services.analytics_service import _month_key, _recent_month_keys
from app.services.institution_department_service import list_departments
from app.services.institution_placement_service import (
    _fetch_institution_students,
    get_placement_overview,
    list_drives,
)
from app.services.institution_service import (
    _fetch_company_names,
    _percentage,
    _placement_buckets,
    fetch_departments,
)

_TENANCY_NOTE = (
    "Every figure below covers only students explicitly linked to your institution account "
    "(student_profiles.institution_id). Company and placement-drive breakdowns are always "
    "institution-wide (unfiltered); the department/batch/date filters narrow the overview, "
    "application, skill, internship, assessment and interview sections only."
)

_ELIGIBILITY_NOTE = (
    "\"Eligible students\" is not shown anywhere in this workspace: the schema has no "
    "eligibility criteria (minimum CGPA, backlog status, attendance) on student_profiles "
    "beyond what a placement drive itself defines. Showing a platform-wide number here would "
    "be fabricated."
)

_FILTER_SCOPE_NOTE = (
    "Department/batch/date filters apply to Overview, Applications, Skills, Skill Gaps, "
    "Internships, Assessments and Interviews. Departments, Placement Drives and Companies are "
    "always shown institution-wide -- each of those IS already the full breakdown a filter "
    "would otherwise just be re-deriving."
)

_TREND_MONTHS = 6

_TREND_NOTE = (
    "Time-series reflects when applications were submitted (applications.applied_at). The "
    "database stores only each application's CURRENT status, not when it changed, so "
    "\"selections\" approximates placements by the application's submission month, not the "
    "(unrecorded) date a student was actually selected. There is no separate placement-date "
    "field anywhere in the schema."
)

_TOP_SKILLS_LIMIT = 15
_SKILL_GAP_LIMIT = 20

# A skill must be required by at least this many currently-PUBLISHED jobs
# (platform-wide) to be flagged "high demand" -- avoids a single one-off
# posting skewing the signal. A plain, documented constant, not a model.
_SKILL_GAP_MIN_DEMAND = 3
# Coverage below this percentage of the (filtered) student body is
# flagged "low coverage" for a high-demand skill. Also a plain constant.
_SKILL_GAP_LOW_COVERAGE_PCT = 25.0
_PUBLISHED_JOBS_FETCH_CAP = 1000


def _now() -> datetime:
    return datetime.now(UTC)


# ============================================================
# fetch helpers -- new column shapes not already exposed elsewhere
# ============================================================


def _fetch_applications(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("applications")
        .select("id, student_id, status, opportunity_type, internship_id, job_id, industry_id, applied_at")
        .in_("student_id", student_ids)
        .execute()
    )
    return list(resp.data or [])


def _fetch_skill_rows(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("student_skills")
        .select("student_id, skill_id, skills(name)")
        .in_("student_id", student_ids)
        .execute()
    )
    return list(resp.data or [])


def _fetch_published_job_ids(client: Client) -> list[str]:
    resp = (
        client.table("jobs")
        .select("id")
        .eq("status", "PUBLISHED")
        .limit(_PUBLISHED_JOBS_FETCH_CAP)
        .execute()
    )
    return [r["id"] for r in (resp.data or [])]


def _fetch_job_skill_demand(client: Client, job_ids: list[str]) -> Counter:
    """One row per (job, skill) -- job_skills_unique_per_job (019_jobs.sql)
    -- so counting rows per skill name counts DISTINCT jobs requiring it."""
    if not job_ids:
        return Counter()
    resp = client.table("job_skills").select("skill_id, skills(name)").in_("job_id", job_ids).execute()
    counter: Counter = Counter()
    for row in resp.data or []:
        skill = row.get("skills")
        name = skill.get("name") if isinstance(skill, dict) else None
        if name:
            counter[name] += 1
    return counter


def _fetch_assessment_attempts(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("assessment_attempts")
        .select("student_id, status, percentage")
        .in_("student_id", student_ids)
        .execute()
    )
    return list(resp.data or [])


def _fetch_interviews(client: Client, student_ids: list[str]) -> list[dict]:
    """Deliberately excludes `notes` (industry-private preparation notes)
    -- same exclusion already used by institution_student_service /
    institution_placement_service."""
    if not student_ids:
        return []
    resp = (
        client.table("interviews")
        .select("id, student_id, status, scheduled_at")
        .in_("student_id", student_ids)
        .execute()
    )
    return list(resp.data or [])


# ============================================================
# scoping (department_id / batch / date range)
# ============================================================


def _scope_students(students: list[dict], department_id: str | None, batch: int | None) -> list[dict]:
    out = students
    if department_id is not None:
        if department_id == "unassigned":
            out = [s for s in out if not s.get("department_id")]
        else:
            out = [s for s in out if s.get("department_id") == department_id]
    if batch is not None:
        out = [s for s in out if s.get("graduation_year") == batch]
    return out


def _in_date_range(value: str | None, date_from: str | None, date_to: str | None) -> bool:
    if not value:
        return date_from is None and date_to is None
    day = value[:10]
    if date_from and day < date_from:
        return False
    return not (date_to and day > date_to)


# ============================================================
# section builders
# ============================================================


def _build_overview(student_ids: list[str], applications: list[dict], drives: list[dict]) -> dict:
    placed, unplaced_active, not_participating = _placement_buckets(student_ids, applications)
    internship_participants = {
        a["student_id"] for a in applications if a.get("opportunity_type") == "INTERNSHIP"
    } & set(student_ids)

    active_drives = sum(1 for d in drives if d["status"] in ("OPEN", "IN_PROGRESS"))
    completed_drives = sum(1 for d in drives if d["status"] == "COMPLETED")

    return {
        "total_students": len(student_ids),
        "placed_students": len(placed),
        "unplaced_students": len(unplaced_active),
        "placement_rate": _percentage(len(placed), len(student_ids)),
        "students_with_applications": len(placed) + len(unplaced_active),
        "students_without_applications": len(not_participating),
        "internship_participants": len(internship_participants),
        "active_placement_drives": active_drives,
        "completed_placement_drives": completed_drives,
    }


def _build_placements(client: Client, institution_id: str) -> dict:
    """Institution-wide, never filtered -- see the module docstring."""
    drives = list_drives(client, institution_id)
    overview = get_placement_overview(client, institution_id)

    total_drives = len(drives)
    cancelled_drives = sum(1 for d in drives if d["status"] == "CANCELLED")
    draft_drives = sum(1 for d in drives if d["status"] == "DRAFT")
    applied_counts = [d["applied_count"] for d in drives]
    average_applicants = round(sum(applied_counts) / len(applied_counts), 1) if applied_counts else None

    drive_rows = [
        {
            "id": d["id"],
            "title": d["title"],
            "company_name": d.get("company_name"),
            "status": d["status"],
            "eligible_count": d["eligible_count"],
            "applied_count": d["applied_count"],
            "selected_count": d["selected_count"],
            "selection_rate": _percentage(d["selected_count"], d["applied_count"]),
        }
        for d in drives
    ]

    return {
        "total_drives": total_drives,
        "active_drives": overview["active_drives"],
        "completed_drives": overview["completed_drives"],
        "cancelled_drives": cancelled_drives,
        "draft_drives": draft_drives,
        "participating_students": overview["participating_students"],
        "placed_students": overview["placed_students"],
        "total_selected_offers": overview["total_selected_offers"],
        "placement_rate": overview["placement_rate"],
        "average_applicants_per_drive": average_applicants,
        "department_breakdown": overview["department_breakdown"],
        "drives": drive_rows,
    }


def _build_companies(client: Client, applications: list[dict]) -> list[dict]:
    """Institution-wide (ALL of the institution's students' applications,
    not just drive-coordinated ones -- a student can apply to a job
    directly), never filtered -- see the module docstring."""
    industry_ids = list({a["industry_id"] for a in applications if a.get("industry_id")})
    company_names = _fetch_company_names(client, industry_ids)

    applicants: dict[str, set[str]] = {}
    postings: dict[str, set[str]] = {}
    selected_count: Counter = Counter()
    placed_students: dict[str, set[str]] = {}

    for a in applications:
        name = company_names.get(a.get("industry_id"), "Unknown company")
        applicants.setdefault(name, set()).add(a["student_id"])
        posting_id = a.get("job_id") or a.get("internship_id")
        if posting_id:
            postings.setdefault(name, set()).add(posting_id)
        if a.get("status") == "SELECTED":
            selected_count[name] += 1
            placed_students.setdefault(name, set()).add(a["student_id"])

    rows = [
        {
            "company_name": name,
            "postings_count": len(postings.get(name, set())),
            "applicants": len(ids),
            "selected_offers": selected_count.get(name, 0),
            "unique_students_placed": len(placed_students.get(name, set())),
        }
        for name, ids in applicants.items()
    ]
    rows.sort(key=lambda c: (-c["selected_offers"], -c["applicants"], c["company_name"]))
    return rows


def _build_applications(applications: list[dict], student_ids: list[str]) -> dict:
    status_counter = Counter(a.get("status") for a in applications)
    students_with = {a["student_id"] for a in applications}
    students_without = len(student_ids) - len(students_with & set(student_ids))

    return {
        "total_applications": len(applications),
        "students_with_applications": len(students_with),
        "students_without_applications": max(students_without, 0),
        "applications_per_applying_student": (
            round(len(applications) / len(students_with), 1) if students_with else None
        ),
        "status_distribution": [
            {"status": s, "count": int(status_counter.get(s, 0))} for s in APPLICATION_STATUSES
        ],
    }


def _build_skills(skill_rows: list[dict], total_students: int) -> tuple[dict, Counter]:
    counter: Counter = Counter()
    for row in skill_rows:
        skill = row.get("skills")
        name = skill.get("name") if isinstance(skill, dict) else None
        if name:
            counter[name] += 1

    top = [
        {
            "skill_name": name,
            "student_count": count,
            "coverage_percentage": _percentage(count, total_students),
        }
        for name, count in counter.most_common(_TOP_SKILLS_LIMIT)
    ]
    return {"total_students_considered": total_students, "top_skills": top}, counter


def _build_skill_gaps(client: Client, coverage_counter: Counter, total_students: int) -> dict:
    published_job_ids = _fetch_published_job_ids(client)
    demand_counter = _fetch_job_skill_demand(client, published_job_ids)

    if sum(demand_counter.values()) == 0:
        return {
            "available": False,
            "note": (
                "Skill-demand comparison unavailable: no currently-PUBLISHED job on the "
                "platform declares any required skill (job_skills) right now."
            ),
            "items": [],
        }

    items = []
    for name, demand in demand_counter.most_common():
        coverage_count = coverage_counter.get(name, 0)
        coverage_pct = _percentage(coverage_count, total_students)
        items.append(
            {
                "skill_name": name,
                "student_coverage_count": coverage_count,
                "student_coverage_percentage": coverage_pct,
                "job_demand_count": demand,
                "high_demand": demand >= _SKILL_GAP_MIN_DEMAND,
                "low_coverage": coverage_pct is None or coverage_pct < _SKILL_GAP_LOW_COVERAGE_PCT,
            }
        )
    items.sort(key=lambda i: (-i["job_demand_count"], i["student_coverage_count"]))

    return {
        "available": True,
        "note": (
            f"\"High demand\" = required by at least {_SKILL_GAP_MIN_DEMAND} currently-PUBLISHED "
            f"jobs (platform-wide). \"Low coverage\" = fewer than {_SKILL_GAP_LOW_COVERAGE_PCT:.0f}% "
            "of the students in scope have this skill on file. These are descriptive indicators "
            "from fixed thresholds, not a prediction or an AI-generated score."
        ),
        "items": items[:_SKILL_GAP_LIMIT],
    }


def _build_internships(applications: list[dict], total_students: int) -> dict:
    internship_apps = [a for a in applications if a.get("opportunity_type") == "INTERNSHIP"]
    participants = {a["student_id"] for a in internship_apps}
    status_counter = Counter(a.get("status") for a in internship_apps)

    return {
        "available": True,
        "note": (
            "Reflects the internship application lifecycle only -- there is no attendance or "
            "duration tracking anywhere in the schema, so \"Selected\" does not distinguish an "
            "ongoing internship from a completed one."
        ),
        "participants": len(participants),
        "applications_total": len(internship_apps),
        "participation_rate": _percentage(len(participants), total_students),
        "status_distribution": [
            {"status": s, "count": int(status_counter.get(s, 0))} for s in APPLICATION_STATUSES
        ],
    }


def _build_assessments(attempts: list[dict]) -> dict:
    completed = [a for a in attempts if a.get("status") == "COMPLETED"]
    percentages = [a["percentage"] for a in completed if a.get("percentage") is not None]
    students_assessed = {a["student_id"] for a in attempts}

    return {
        "students_assessed": len(students_assessed),
        "total_attempts": len(attempts),
        "average_score": round(sum(percentages) / len(percentages), 1) if percentages else None,
    }


def _build_interviews(interviews: list[dict]) -> dict:
    counter = Counter(i.get("status") for i in interviews)
    now = _now()
    upcoming = 0
    for row in interviews:
        if row.get("status") != "SCHEDULED":
            continue
        try:
            when = datetime.fromisoformat(str(row["scheduled_at"]))
        except (ValueError, KeyError, TypeError):
            continue
        if when >= now:
            upcoming += 1

    return {
        "total": len(interviews),
        "students_interviewed": len({i["student_id"] for i in interviews}),
        "scheduled": int(counter.get("SCHEDULED", 0)),
        "completed": int(counter.get("COMPLETED", 0)),
        "cancelled": int(counter.get("CANCELLED", 0)),
        "upcoming": upcoming,
    }


def _build_trends(applications: list[dict]) -> dict:
    if not applications:
        return {"has_sufficient_data": False, "months": [], "historical_note": _TREND_NOTE}

    months = _recent_month_keys(_TREND_MONTHS)
    apps_by_month: Counter = Counter()
    selections_by_month: Counter = Counter()
    internship_apps_by_month: Counter = Counter()
    for a in applications:
        key = _month_key(a.get("applied_at"))
        if not key:
            continue
        apps_by_month[key] += 1
        if a.get("status") == "SELECTED":
            selections_by_month[key] += 1
        if a.get("opportunity_type") == "INTERNSHIP":
            internship_apps_by_month[key] += 1

    month_points = [
        {
            "period": m,
            "applications": int(apps_by_month.get(m, 0)),
            "selections": int(selections_by_month.get(m, 0)),
            "internship_applications": int(internship_apps_by_month.get(m, 0)),
        }
        for m in months
    ]
    has_data = any(p["applications"] > 0 for p in month_points)
    return {
        "has_sufficient_data": has_data,
        "months": month_points if has_data else [],
        "historical_note": _TREND_NOTE,
    }


# ============================================================
# entry point
# ============================================================


def compute_institution_analytics(
    client: Client,
    institution_id: str,
    *,
    department_id: str | None = None,
    batch: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    all_students = _fetch_institution_students(client, institution_id)
    all_student_ids = [s["id"] for s in all_students]

    departments = fetch_departments(client, institution_id)
    department_options = sorted(
        [{"id": d["id"], "name": d["name"]} for d in departments], key=lambda d: d["name"].lower()
    )
    all_batches = sorted({s["graduation_year"] for s in all_students if s.get("graduation_year") is not None})

    scoped_students = _scope_students(all_students, department_id, batch)
    scoped_student_ids = [s["id"] for s in scoped_students]

    scoped_applications = _fetch_applications(client, scoped_student_ids)
    date_filtered_applications = [
        a for a in scoped_applications if _in_date_range(a.get("applied_at"), date_from, date_to)
    ]

    drives = (
        client.table("placement_drives").select("id, status").eq("institution_id", institution_id).execute().data
        or []
    )

    overview = _build_overview(scoped_student_ids, scoped_applications, drives)
    department_analytics = list_departments(client, institution_id)
    placements = _build_placements(client, institution_id)

    all_applications = _fetch_applications(client, all_student_ids)
    companies = _build_companies(client, all_applications)

    applications_section = _build_applications(date_filtered_applications, scoped_student_ids)

    skill_rows = _fetch_skill_rows(client, scoped_student_ids)
    skills_section, coverage_counter = _build_skills(skill_rows, len(scoped_student_ids))
    skill_gaps = _build_skill_gaps(client, coverage_counter, len(scoped_student_ids))

    internships = _build_internships(date_filtered_applications, len(scoped_student_ids))

    attempts = _fetch_assessment_attempts(client, scoped_student_ids)
    assessments = _build_assessments(attempts)

    interviews = _fetch_interviews(client, scoped_student_ids)
    interviews_section = _build_interviews(interviews)

    trends = _build_trends(scoped_applications)

    institution_row = (
        client.table("institution_profiles")
        .select("institution_name")
        .eq("id", institution_id)
        .maybe_single()
        .execute()
    )
    institution_name = (
        (institution_row.data or {}).get("institution_name") if institution_row and institution_row.data else None
    )

    return {
        "generated_at": _now().isoformat(),
        "institution_name": institution_name,
        "filters_applied": {
            "department_id": department_id,
            "batch": batch,
            "date_from": date_from,
            "date_to": date_to,
        },
        "filter_options": {"departments": department_options, "batches": all_batches},
        "overview": overview,
        "departments": [
            {
                "id": d["id"],
                "name": d["name"],
                "code": d.get("code"),
                "is_active": d["is_active"],
                "student_count": d["student_count"],
                "placed_count": d["placed_count"],
                "unplaced_count": d["unplaced_count"],
                "no_applications_count": d["no_applications_count"],
                "placement_rate": d["placement_rate"],
                "internship_selected_count": d["internship_selected_count"],
            }
            for d in department_analytics
        ],
        "placements": placements,
        "companies": companies,
        "applications": applications_section,
        "skills": skills_section,
        "skill_gaps": skill_gaps,
        "internships": internships,
        "assessments": assessments,
        "interviews": interviews_section,
        "trends": trends,
        "tenancy_note": _TENANCY_NOTE,
        "eligibility_note": _ELIGIBILITY_NOTE,
        "filter_scope_note": _FILTER_SCOPE_NOTE,
    }
