"""Business logic for the Institution Dashboard overview
(backend/app/api/institution.py, GET /api/v1/institution/overview).

One aggregation call, computed live through a user-scoped RLS client
(never service_role) -- same shape as analytics_service.py
(compute_industry_analytics). Every student-level read
(student_profiles/applications/student_skills/assessment_attempts/
interviews) is additionally filtered by `.eq("institution_id", ...)` /
joined through the linked student id set here, in the service layer, as
defence in depth on top of the RLS policies added in
database/migrations/037_institution_tenancy.sql -- matching the
"explicit ownership filter on top of RLS" convention already used by
every other service module in this project (e.g.
industry_collaboration_service's own/incoming split).

Honesty boundaries enforced here, not just documented:
  - No `eligible_students` field exists anywhere in this module's output
    -- see `_ELIGIBILITY_NOTE`. Nothing approximates it.
  - jobs/internships/workshops/industry_profiles reads are platform-wide
    (no institution-ownership relationship exists for them) and are
    always returned alongside `platform_wide: True` -- see each schema
    field's own docstring in app.schemas.institution.
  - Department grouping uses the real `departments` entity
    (student_profiles.department_id), not the free-text
    `student_profiles.department` string -- see `_group_by_department`
    and database/migrations/040_institution_departments.sql. A student
    with no department_id is grouped under "Unassigned", never dropped.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta

from supabase import Client

_TENANCY_NOTE = (
    "Student, department, and placement figures cover only students explicitly linked to your "
    "institution account (student_profiles.institution_id). No student is auto-assigned to any "
    "institution -- if these numbers look low, it is because linking has not happened yet, not "
    "because your students aren't on the platform."
)

_ELIGIBILITY_NOTE = (
    "\"Eligible students\" is not shown: the schema has no eligibility criteria "
    "(e.g. minimum CGPA, backlog status, attendance) on student_profiles or anywhere else. "
    "Showing a number here would be fabricated -- this metric can be added once eligibility "
    "rules are defined."
)

_PROFILE_COLUMNS = (
    "id, institution_name, institution_type, location, website_url, contact_phone, "
    "created_at, updated_at"
)

_RECENT_OPPORTUNITY_LIMIT = 5
_UPCOMING_EVENT_LIMIT = 5
_TOP_SKILLS_LIMIT = 5
_RECENT_ACTIVITY_WINDOW_DAYS = 30


def _now() -> datetime:
    return datetime.now(UTC)


def get_profile(client: Client, institution_id: str) -> dict | None:
    """The caller's own institution profile, or None if they haven't saved
    one yet. Same lazy-row shape as industry_service.get_profile. RLS
    ("Institution can view their own institution profile") already scopes
    this to the caller; the explicit .eq() is defense in depth, matching
    the convention in every other service module."""
    response = (
        client.table("institution_profiles")
        .select(_PROFILE_COLUMNS)
        .eq("id", institution_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def upsert_profile(client: Client, institution_id: str, fields: dict) -> dict:
    """Create (first save) or update the caller's own institution profile.
    `institution_id` is always current_user.id -- never a client-supplied
    value. RLS independently enforces `auth.uid() = id AND
    is_institution(auth.uid())` for both the INSERT and UPDATE paths the
    upsert can take."""
    payload = {"id": institution_id, **fields}
    client.table("institution_profiles").upsert(payload, on_conflict="id").execute()

    row = get_profile(client, institution_id)
    if row is None:
        raise RuntimeError("institution_profiles row could not be read back after save.")
    return row


def _unspecified(value: str | None) -> str:
    trimmed = (value or "").strip()
    return trimmed if trimmed else "Unspecified"


def _fetch_linked_students(client: Client, institution_id: str) -> list[dict]:
    resp = (
        client.table("student_profiles")
        .select("id, department, department_id")
        .eq("institution_id", institution_id)
        .execute()
    )
    return list(resp.data or [])


def fetch_departments(client: Client, institution_id: str) -> list[dict]:
    """The caller's own departments (any status) -- shared across
    institution_service (dashboard), institution_student_service
    (directory/detail), and institution_department_service (the
    Departments module itself), so all three read the exact same rows.
    RLS ("Institution can view their own departments",
    040_institution_departments.sql) already scopes this; the explicit
    .eq() is defense in depth, matching this project's convention."""
    resp = (
        client.table("departments")
        .select("id, name, code, description, is_active, created_at, updated_at")
        .eq("institution_id", institution_id)
        .execute()
    )
    return list(resp.data or [])


def _fetch_applications_for(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("applications")
        .select("id, student_id, status, internship_id, job_id")
        .in_("student_id", student_ids)
        .execute()
    )
    return list(resp.data or [])


def _placement_buckets(
    student_ids: list[str], applications: list[dict]
) -> tuple[set[str], set[str], set[str]]:
    """Returns (placed, unplaced_active, not_participating) student-id sets.
    A student is placed if ANY of their applications is SELECTED;
    unplaced_active if they have at least one application but none
    SELECTED; not_participating if they have none at all."""
    by_student: dict[str, list[str]] = {}
    for row in applications:
        by_student.setdefault(row["student_id"], []).append(row.get("status") or "")

    placed = {sid for sid, statuses in by_student.items() if "SELECTED" in statuses}
    unplaced_active = {sid for sid in by_student if sid not in placed}
    not_participating = {sid for sid in student_ids if sid not in by_student}
    return placed, unplaced_active, not_participating


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 1)


_UNASSIGNED_DEPARTMENT_LABEL = "Unassigned"


def _group_by_department(students: list[dict], placed: set[str], department_names: dict[str, str]) -> list[dict]:
    """Groups by the real `departments` entity (student_profiles.department_id),
    NOT the free-text `student_profiles.department` string -- see
    040_institution_departments.sql. A student with no department_id (not
    yet assigned to a department) is grouped under "Unassigned", never
    silently dropped. `department_names` maps department_id -> name,
    from institution_service.fetch_departments -- the same rows the
    Departments module itself reads, so this can never disagree with it.
    """
    totals: Counter[str] = Counter()
    placed_counts: Counter[str] = Counter()
    ids: dict[str, str | None] = {}
    for s in students:
        dept_id = s.get("department_id")
        label = department_names.get(dept_id, _UNASSIGNED_DEPARTMENT_LABEL) if dept_id else _UNASSIGNED_DEPARTMENT_LABEL
        totals[label] += 1
        ids[label] = dept_id
        if s["id"] in placed:
            placed_counts[label] += 1

    return [
        {
            "department": label,
            "department_id": ids[label],
            "total_students": totals[label],
            "placed_students": placed_counts[label],
            "placement_percentage": _percentage(placed_counts[label], totals[label]),
        }
        for label in sorted(totals)
    ]


def _fetch_recent_published(client: Client, table: str, label: str) -> list[dict]:
    resp = (
        client.table(table)
        .select("id, title, industry_id, status, created_at")
        .eq("status", "PUBLISHED")
        .order("created_at", desc=True)
        .limit(_RECENT_OPPORTUNITY_LIMIT)
        .execute()
    )
    rows = list(resp.data or [])
    for row in rows:
        row["_opportunity_type"] = label
    return rows


def _fetch_company_names(client: Client, industry_ids: list[str]) -> dict[str, str]:
    if not industry_ids:
        return {}
    resp = (
        client.table("industry_profiles")
        .select("id, company_name")
        .in_("id", list(set(industry_ids)))
        .execute()
    )
    return {row["id"]: row.get("company_name") for row in (resp.data or [])}


def _build_recent_opportunities(
    client: Client, applications: list[dict]
) -> list[dict]:
    internships = _fetch_recent_published(client, "internships", "INTERNSHIP")
    jobs = _fetch_recent_published(client, "jobs", "JOB")
    combined = sorted(
        internships + jobs, key=lambda r: r.get("created_at") or "", reverse=True
    )[:_RECENT_OPPORTUNITY_LIMIT]

    company_names = _fetch_company_names(client, [r["industry_id"] for r in combined])

    applicants_by_internship = Counter(
        a["internship_id"] for a in applications if a.get("internship_id")
    )
    applicants_by_job = Counter(a["job_id"] for a in applications if a.get("job_id"))

    out = []
    for row in combined:
        opp_type = row["_opportunity_type"]
        applicant_count = (
            applicants_by_internship.get(row["id"], 0)
            if opp_type == "INTERNSHIP"
            else applicants_by_job.get(row["id"], 0)
        )
        out.append(
            {
                "id": row["id"],
                "title": row["title"],
                "opportunity_type": opp_type,
                "company_name": company_names.get(row["industry_id"]),
                "posted_at": row.get("created_at"),
                "applicants_from_your_institution": applicant_count,
            }
        )
    return out


def _fetch_active_counts(client: Client) -> tuple[int, int]:
    jobs_resp = client.table("jobs").select("id", count="exact").eq("status", "PUBLISHED").execute()
    internships_resp = (
        client.table("internships").select("id", count="exact").eq("status", "PUBLISHED").execute()
    )
    return (internships_resp.count or 0, jobs_resp.count or 0)


def _fetch_industry_overview(client: Client) -> dict:
    partners_resp = client.table("industry_profiles").select("id", count="exact").execute()
    since = (_now() - timedelta(days=_RECENT_ACTIVITY_WINDOW_DAYS)).isoformat()

    recent_count = 0
    for table in ("internships", "jobs", "industry_workshops"):
        resp = (
            client.table(table)
            .select("id", count="exact")
            .eq("status", "PUBLISHED")
            .gte("created_at", since)
            .execute()
        )
        recent_count += resp.count or 0

    return {
        "total_industry_partners": partners_resp.count or 0,
        "recent_postings_count": recent_count,
        "platform_wide": True,
    }


def _fetch_collaborations(client: Client, institution_id: str) -> dict:
    resp = (
        client.table("industry_collaborations")
        .select("status")
        .eq("recipient_id", institution_id)
        .execute()
    )
    rows = list(resp.data or [])
    counter = Counter(r.get("status") for r in rows)
    return {
        "pending": int(counter.get("SENT", 0)),
        "active": int(counter.get("ACTIVE", 0)),
        "total": len(rows),
    }


def _fetch_upcoming_workshops(client: Client) -> list[dict]:
    today = _now().date().isoformat()
    resp = (
        client.table("industry_workshops")
        .select("id, title, industry_id, start_date")
        .eq("status", "PUBLISHED")
        .gte("start_date", today)
        .order("start_date", desc=False)
        .limit(_UPCOMING_EVENT_LIMIT)
        .execute()
    )
    rows = list(resp.data or [])
    company_names = _fetch_company_names(client, [r["industry_id"] for r in rows])
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "event_type": "WORKSHOP",
            "start_date": r.get("start_date"),
            "organizer": company_names.get(r["industry_id"]),
            "platform_wide": True,
        }
        for r in rows
    ]


def _fetch_upcoming_institution_events(client: Client, institution_id: str) -> list[dict]:
    """Phase 10 (045_institution_events.sql): the institution's own
    upcoming/ongoing organized events -- never another institution's,
    and never a platform-wide workshop (that's _fetch_upcoming_workshops).
    Best-effort: if the table isn't present yet (migration not applied),
    the Dashboard degrades gracefully to workshops only."""
    today = _now().date().isoformat()
    try:
        resp = (
            client.table("institution_events")
            .select("id, title, event_type, industry_id, start_at, status")
            .eq("institution_id", institution_id)
            .in_("status", ["PUBLISHED", "ONGOING"])
            .gte("start_at", today)
            .order("start_at", desc=False)
            .limit(_UPCOMING_EVENT_LIMIT)
            .execute()
        )
    except Exception:  # noqa: BLE001 -- degrade gracefully, same pattern as _fetch_interview_rows
        return []
    rows = list(resp.data or [])
    company_names = _fetch_company_names(client, [r["industry_id"] for r in rows if r.get("industry_id")])
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "event_type": r.get("event_type") or "OTHER",
            "start_date": r.get("start_at"),
            "organizer": company_names.get(r.get("industry_id")) if r.get("industry_id") else None,
            "platform_wide": False,
        }
        for r in rows
    ]


def _fetch_upcoming_events(client: Client, institution_id: str) -> list[dict]:
    """Merges the institution's own upcoming events (Phase 10) with
    platform-wide published Industry workshops, soonest first, capped at
    _UPCOMING_EVENT_LIMIT overall -- one combined "what's coming up"
    feed for the Dashboard, never two separate fabricated lists."""
    merged = _fetch_upcoming_institution_events(client, institution_id) + _fetch_upcoming_workshops(client)
    merged.sort(key=lambda e: (e.get("start_date") is None, e.get("start_date") or ""))
    return merged[:_UPCOMING_EVENT_LIMIT]


def _fetch_top_skills(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("student_skills")
        .select("skill_id, skills(name)")
        .in_("student_id", student_ids)
        .execute()
    )
    rows = list(resp.data or [])
    counter: Counter[str] = Counter()
    for row in rows:
        skill = row.get("skills")
        name = skill.get("name") if isinstance(skill, dict) else None
        if name:
            counter[name] += 1
    return [
        {"skill_name": name, "student_count": count}
        for name, count in counter.most_common(_TOP_SKILLS_LIMIT)
    ]


def _fetch_assessment_insights(client: Client, student_ids: list[str]) -> dict:
    if not student_ids:
        return {"assessments_completed": 0, "average_assessment_percentage": None}
    resp = (
        client.table("assessment_attempts")
        .select("percentage, status")
        .in_("student_id", student_ids)
        .eq("status", "COMPLETED")
        .execute()
    )
    rows = list(resp.data or [])
    percentages = [r["percentage"] for r in rows if r.get("percentage") is not None]
    avg = round(sum(percentages) / len(percentages), 1) if percentages else None
    return {"assessments_completed": len(rows), "average_assessment_percentage": avg}


def _fetch_institution_name(client: Client, institution_id: str) -> str | None:
    resp = (
        client.table("institution_profiles")
        .select("institution_name")
        .eq("id", institution_id)
        .maybe_single()
        .execute()
    )
    return (resp.data or {}).get("institution_name") if resp and resp.data else None


def compute_institution_overview(client: Client, institution_id: str) -> dict:
    students = _fetch_linked_students(client, institution_id)
    student_ids = [s["id"] for s in students]
    applications = _fetch_applications_for(client, student_ids)

    placed, unplaced_active, not_participating = _placement_buckets(student_ids, applications)
    total_linked = len(student_ids)

    student_metrics = {
        "total_linked_students": total_linked,
        "placed": len(placed),
        "unplaced_active": len(unplaced_active),
        "not_participating": len(not_participating),
        "placement_percentage": _percentage(len(placed), total_linked),
    }

    department_names = {d["id"]: d["name"] for d in fetch_departments(client, institution_id)}
    department_metrics = _group_by_department(students, placed, department_names)
    recent_opportunities = _build_recent_opportunities(client, applications)
    active_internships, active_jobs = _fetch_active_counts(client)

    opportunities = {
        "active_jobs": active_jobs,
        "active_internships": active_internships,
        "recent": recent_opportunities,
        "platform_wide": True,
    }

    student_insights = {
        "students_with_no_applications": len(not_participating),
        "students_actively_applying": len(unplaced_active),
        "top_skills": _fetch_top_skills(client, student_ids),
        **_fetch_assessment_insights(client, student_ids),
    }

    return {
        "generated_at": _now().isoformat(),
        "institution_name": _fetch_institution_name(client, institution_id),
        "student_metrics": student_metrics,
        "department_metrics": department_metrics,
        "opportunities": opportunities,
        "industry": _fetch_industry_overview(client),
        "collaborations": _fetch_collaborations(client, institution_id),
        "upcoming_events": _fetch_upcoming_events(client, institution_id),
        "student_insights": student_insights,
        "tenancy_note": _TENANCY_NOTE,
        "eligibility_note": _ELIGIBILITY_NOTE,
    }
