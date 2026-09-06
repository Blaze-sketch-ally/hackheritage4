"""Business logic for the Institution Student Directory
(backend/app/api/institution.py, GET /institution/students,
GET /institution/students/{student_id}).

Same shape as institution_service.py: every function takes an
already-built *user-scoped* Supabase client and RLS
(037/038/039/040_institution_*.sql) is the real access-control boundary
-- nothing here uses service_role. `_placement_buckets` /
`fetch_departments` are imported from institution_service, not
redefined -- the Dashboard, this Directory, and the Departments module
(institution_department_service.py) must never disagree about what
"placed" means or which departments exist for an institution.

Department grouping/filtering uses the real `departments` entity
(student_profiles.department_id, database/migrations/
040_institution_departments.sql), not the free-text
`student_profiles.department` string. A student with no department_id
is labeled "Unassigned", never dropped from the list. The free-text
`department` column is still read ONLY for `_profile_completion` parity
with the student's own /student/profile page (unrelated to this
Institution-side entity), and surfaced read-only on the detail response
as `self_reported_department`.

Performance note (see this phase's own report for the full tradeoff):
list_students fetches the institution's FULL linked roster in a small,
fixed number of flat queries (student_profiles, one RPC for names, one
query each for skills/applications), then filters/sorts/paginates in
Python. This avoids N+1 (no per-student query), but is not a true
DB-side paginated query -- appropriate for realistic TPO cohort sizes
(hundreds to low thousands), not unbounded scale. A DB-level filtered
query would need student name/email duplicated onto student_profiles or
a materialized view, either a bigger schema change than this phase scope
allows.
"""

from supabase import Client

from app.services.institution_service import _placement_buckets, fetch_departments

_UNASSIGNED = "Unassigned"
_UNASSIGNED_FILTER_VALUE = "unassigned"

# `department` (free text) is kept ONLY for _profile_completion parity
# with the student's own /student/profile page (that page's completion
# check has always looked at this column, unrelated to the Institution's
# department entity). `department_id` is the authoritative
# Institution-portal relationship -- see 040_institution_departments.sql.
_STUDENT_PROFILE_COLUMNS = (
    "id, department, department_id, graduation_year, cgpa, percentage, degree, phone, date_of_birth, "
    "gender, location, institution_name, career_goals, preferred_roles, preferred_locations, interests"
)

_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100
_TOP_SKILLS_PER_STUDENT = 5

_COMPLETION_FIELD_COUNT = 16


def _profile_completion(name_row: dict | None, student_row: dict) -> int:
    """Ports frontend/lib/student/profile.ts's getProfileCompletion()
    check-for-check -- see that file's own COMPLETION_CHECKS array. Kept
    in sync deliberately: this must never report a different percentage
    than the student sees on their own /student/profile page."""
    name_row = name_row or {}
    checks = [
        bool(name_row.get("full_name")),
        bool(name_row.get("username")),
        bool(name_row.get("avatar_url")),
        bool(student_row.get("phone")),
        bool(student_row.get("date_of_birth")),
        bool(student_row.get("gender")),
        bool(student_row.get("location")),
        bool(student_row.get("institution_name")),
        bool(student_row.get("department")),
        bool(student_row.get("degree")),
        bool(student_row.get("graduation_year")),
        student_row.get("cgpa") is not None or student_row.get("percentage") is not None,
        bool(student_row.get("career_goals")),
        len(student_row.get("preferred_roles") or []) > 0,
        len(student_row.get("preferred_locations") or []) > 0,
        len(student_row.get("interests") or []) > 0,
    ]
    assert len(checks) == _COMPLETION_FIELD_COUNT
    return round(sum(1 for c in checks if c) / _COMPLETION_FIELD_COUNT * 100)


def _fetch_linked_students(client: Client, institution_id: str) -> list[dict]:
    resp = (
        client.table("student_profiles")
        .select(_STUDENT_PROFILE_COLUMNS)
        .eq("institution_id", institution_id)
        .execute()
    )
    return list(resp.data or [])


def _fetch_link_request_ids(client: Client, institution_id: str, student_ids: list[str]) -> dict[str, str]:
    """Maps student_id -> their current APPROVED institution_link_requests.id
    -- lets the directory/detail views call the existing unlink endpoint
    (POST /institution-links/{id}/unlink) without a second round trip.
    At most one APPROVED row per student
    (institution_link_requests_one_live_per_student_idx, migration 038)."""
    if not student_ids:
        return {}
    resp = (
        client.table("institution_link_requests")
        .select("id, student_id")
        .eq("institution_id", institution_id)
        .eq("status", "APPROVED")
        .in_("student_id", student_ids)
        .execute()
    )
    return {row["student_id"]: row["id"] for row in (resp.data or [])}


def _fetch_names(client: Client, student_ids: list[str]) -> dict[str, dict]:
    if not student_ids:
        return {}
    resp = client.rpc("institution_student_names", {"student_ids": student_ids}).execute()
    rows = getattr(resp, "data", None) or []
    return {r["student_id"]: r for r in rows if isinstance(r, dict) and r.get("student_id")}


def _fetch_skills(client: Client, student_ids: list[str]) -> dict[str, list[dict]]:
    if not student_ids:
        return {}
    resp = (
        client.table("student_skills")
        .select("student_id, proficiency_level, is_verified, skills(name)")
        .in_("student_id", student_ids)
        .execute()
    )
    out: dict[str, list[dict]] = {}
    for row in resp.data or []:
        skill = row.get("skills")
        name = skill.get("name") if isinstance(skill, dict) else None
        if not name:
            continue
        out.setdefault(row["student_id"], []).append(
            {
                "skill_name": name,
                "proficiency_level": row.get("proficiency_level"),
                "is_verified": bool(row.get("is_verified")),
            }
        )
    return out


_PROFICIENCY_RANK = {"Expert": 4, "Advanced": 3, "Intermediate": 2, "Beginner": 1}


def _top_skill_names(skills: list[dict], limit: int = _TOP_SKILLS_PER_STUDENT) -> list[str]:
    ranked = sorted(skills, key=lambda s: _PROFICIENCY_RANK.get(s["proficiency_level"], 0), reverse=True)
    return [s["skill_name"] for s in ranked[:limit]]


def _fetch_applications(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("applications")
        .select("id, student_id, status, opportunity_type, internship_id, job_id, applied_at, industry_id")
        .in_("student_id", student_ids)
        .execute()
    )
    return list(resp.data or [])


def _internship_status(student_id: str, applications: list[dict]) -> str:
    internship_apps = [a for a in applications if a["student_id"] == student_id and a["opportunity_type"] == "INTERNSHIP"]
    if any(a["status"] == "SELECTED" for a in internship_apps):
        return "SELECTED"
    if internship_apps:
        return "APPLYING"
    return "NONE"


def _placement_status_for(student_id: str, placed: set[str], unplaced_active: set[str]) -> str:
    if student_id in placed:
        return "PLACED"
    if student_id in unplaced_active:
        return "APPLYING"
    return "NOT_PARTICIPATING"


def list_students(
    client: Client,
    institution_id: str,
    *,
    search: str | None = None,
    department: str | None = None,
    batch: int | None = None,
    cgpa_min: float | None = None,
    cgpa_max: float | None = None,
    placement_status: str | None = None,
    internship_status: str | None = None,
    skill: str | None = None,
    sort_by: str = "name",
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> dict:
    page_size = max(1, min(page_size, _MAX_PAGE_SIZE))
    page = max(1, page)

    students = _fetch_linked_students(client, institution_id)
    student_ids = [s["id"] for s in students]

    departments = fetch_departments(client, institution_id)
    department_options = sorted(
        [{"id": d["id"], "name": d["name"]} for d in departments], key=lambda d: d["name"].lower()
    )
    department_names = {d["id"]: d["name"] for d in departments}
    all_batches = sorted({s["graduation_year"] for s in students if s.get("graduation_year") is not None})

    if not student_ids:
        return {
            "students": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "filters": {"departments": department_options, "batches": all_batches},
            "summary": {
                "total_students": 0,
                "placed": 0,
                "unplaced": 0,
                "no_applications": 0,
                "internship_selected": 0,
            },
        }

    names = _fetch_names(client, student_ids)
    link_request_ids = _fetch_link_request_ids(client, institution_id, student_ids)
    skills_by_student = _fetch_skills(client, student_ids)
    applications = _fetch_applications(client, student_ids)
    placed, unplaced_active, not_participating = _placement_buckets(student_ids, applications)
    internship_selected_count = sum(
        1 for sid in student_ids if _internship_status(sid, applications) == "SELECTED"
    )
    summary = {
        "total_students": len(student_ids),
        "placed": len(placed),
        "unplaced": len(unplaced_active),
        "no_applications": len(not_participating),
        "internship_selected": internship_selected_count,
    }

    rows: list[dict] = []
    for s in students:
        sid = s["id"]
        name_row = names.get(sid, {})
        student_skills = skills_by_student.get(sid, [])
        dept_id = s.get("department_id")
        rows.append(
            {
                "id": sid,
                "full_name": name_row.get("full_name"),
                "username": name_row.get("username"),
                "avatar_url": name_row.get("avatar_url"),
                "link_request_id": link_request_ids.get(sid),
                "department_id": dept_id,
                "department": department_names.get(dept_id, _UNASSIGNED) if dept_id else _UNASSIGNED,
                "batch": s.get("graduation_year"),
                "cgpa": s.get("cgpa"),
                "percentage": s.get("percentage"),
                "placement_status": _placement_status_for(sid, placed, unplaced_active),
                "internship_status": _internship_status(sid, applications),
                "top_skills": _top_skill_names(student_skills),
                "profile_completion": _profile_completion(name_row, s),
                "_skill_names_lower": {sk["skill_name"].lower() for sk in student_skills},
            }
        )

    # ---- filters ----
    if search and search.strip():
        needle = search.strip().lower()
        rows = [
            r
            for r in rows
            if needle in (r["full_name"] or "").lower() or needle in (r["username"] or "").lower()
        ]
    if department:
        if department == _UNASSIGNED_FILTER_VALUE:
            rows = [r for r in rows if r["department_id"] is None]
        else:
            rows = [r for r in rows if r["department_id"] == department]
    if batch is not None:
        rows = [r for r in rows if r["batch"] == batch]
    if cgpa_min is not None:
        rows = [r for r in rows if r["cgpa"] is not None and r["cgpa"] >= cgpa_min]
    if cgpa_max is not None:
        rows = [r for r in rows if r["cgpa"] is not None and r["cgpa"] <= cgpa_max]
    if placement_status:
        rows = [r for r in rows if r["placement_status"] == placement_status]
    if internship_status:
        rows = [r for r in rows if r["internship_status"] == internship_status]
    if skill and skill.strip():
        needle = skill.strip().lower()
        rows = [r for r in rows if any(needle in name for name in r["_skill_names_lower"])]

    # ---- sort ----
    # cgpa is nullable: a student with no CGPA on file sorts LAST
    # regardless of direction (asc or desc) -- reversing a `(is_none,
    # value)` tuple key would otherwise push None-valued rows to the
    # FRONT on a desc sort, which reads as "these students top the
    # ranking" and is actively misleading.
    reverse = sort_dir == "desc"
    if sort_by == "cgpa":
        with_cgpa = [r for r in rows if r["cgpa"] is not None]
        without_cgpa = [r for r in rows if r["cgpa"] is None]
        with_cgpa.sort(key=lambda r: r["cgpa"], reverse=reverse)
        rows = with_cgpa + without_cgpa
    else:
        sort_keys = {
            "name": lambda r: (r["full_name"] or "").lower(),
            "department": lambda r: r["department"],
            "placement_status": lambda r: r["placement_status"],
        }
        key_fn = sort_keys.get(sort_by, sort_keys["name"])
        rows.sort(key=key_fn, reverse=reverse)

    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    for r in page_rows:
        r.pop("_skill_names_lower", None)

    return {
        "students": page_rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "filters": {"departments": department_options, "batches": all_batches},
        "summary": summary,
    }


def get_student_detail(client: Client, institution_id: str, student_id: str) -> dict | None:
    resp = (
        client.table("student_profiles")
        .select(
            "id, department, department_id, graduation_year, cgpa, percentage, degree, phone, "
            "date_of_birth, gender, location, institution_name, career_goals, preferred_roles, "
            "preferred_locations, interests"
        )
        .eq("id", student_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
    )
    student = resp.data if resp is not None else None
    if not student:
        return None

    department_names = {d["id"]: d["name"] for d in fetch_departments(client, institution_id)}
    dept_id = student.get("department_id")

    name_row = _fetch_names(client, [student_id]).get(student_id, {})
    link_request_id = _fetch_link_request_ids(client, institution_id, [student_id]).get(student_id)

    skills_resp = (
        client.table("student_skills")
        .select("proficiency_level, is_verified, skills(name)")
        .eq("student_id", student_id)
        .execute()
    )
    skills = [
        {
            "skill_name": (row.get("skills") or {}).get("name"),
            "proficiency_level": row.get("proficiency_level"),
            "is_verified": bool(row.get("is_verified")),
        }
        for row in (skills_resp.data or [])
        if isinstance(row.get("skills"), dict) and row["skills"].get("name")
    ]

    projects_resp = (
        client.table("student_projects")
        .select("id, title, description, project_url, repo_url, is_ongoing")
        .eq("student_id", student_id)
        .execute()
    )
    projects = list(projects_resp.data or [])
    project_ids = [p["id"] for p in projects]
    project_skills: dict[str, list[str]] = {}
    if project_ids:
        ps_resp = (
            client.table("student_project_skills")
            .select("project_id, skills(name)")
            .in_("project_id", project_ids)
            .execute()
        )
        for row in ps_resp.data or []:
            skill = row.get("skills")
            name = skill.get("name") if isinstance(skill, dict) else None
            if name:
                project_skills.setdefault(row["project_id"], []).append(name)
    projects_out = [
        {
            "id": p["id"],
            "title": p["title"],
            "description": p.get("description"),
            "project_url": p.get("project_url"),
            "repo_url": p.get("repo_url"),
            "is_ongoing": bool(p.get("is_ongoing")),
            "skills": project_skills.get(p["id"], []),
        }
        for p in projects
    ]

    certifications_resp = (
        client.table("student_certifications")
        .select("id, name, issuing_organization, issue_date, credential_url")
        .eq("student_id", student_id)
        .execute()
    )
    achievements_resp = (
        client.table("student_achievements")
        .select("id, title, description, achievement_date, issuing_organization")
        .eq("student_id", student_id)
        .execute()
    )

    applications = list(
        client.table("applications")
        .select("id, student_id, status, opportunity_type, internship_id, job_id, applied_at, industry_id")
        .eq("student_id", student_id)
        .execute()
        .data
        or []
    )
    internship_ids = [a["internship_id"] for a in applications if a.get("internship_id")]
    job_ids = [a["job_id"] for a in applications if a.get("job_id")]
    titles: dict[str, str] = {}
    if internship_ids or job_ids:
        titles_resp = client.rpc(
            "institution_visible_opportunity_titles",
            {"internship_ids": internship_ids, "job_ids": job_ids},
        ).execute()
        for row in getattr(titles_resp, "data", None) or []:
            titles[row["id"]] = row["title"]

    industry_ids = list({a["industry_id"] for a in applications if a.get("industry_id")})
    company_names: dict[str, str | None] = {}
    if industry_ids:
        companies_resp = (
            client.table("industry_profiles").select("id, company_name").in_("id", industry_ids).execute()
        )
        company_names = {row["id"]: row.get("company_name") for row in (companies_resp.data or [])}

    applications_out = [
        {
            "id": a["id"],
            "opportunity_type": a["opportunity_type"],
            "opportunity_title": titles.get(a.get("internship_id") or a.get("job_id")),
            "company_name": company_names.get(a.get("industry_id")),
            "status": a["status"],
            "applied_at": a.get("applied_at"),
        }
        for a in applications
    ]

    placed, unplaced_active, _not_participating = _placement_buckets([student_id], applications)
    placement_status = _placement_status_for(student_id, placed, unplaced_active)
    internship_status = _internship_status(student_id, applications)

    attempts = list(
        client.table("assessment_attempts")
        .select("assessment_id, status, percentage, submitted_at")
        .eq("student_id", student_id)
        .execute()
        .data
        or []
    )
    assessment_ids = list({a["assessment_id"] for a in attempts})
    assessment_meta: dict[str, dict] = {}
    if assessment_ids:
        meta_resp = (
            client.table("assessments").select("id, title, skill_id").in_("id", assessment_ids).execute()
        )
        assessment_meta = {row["id"]: row for row in (meta_resp.data or [])}
        skill_ids = list({m["skill_id"] for m in assessment_meta.values() if m.get("skill_id")})
        skill_names: dict[str, str] = {}
        if skill_ids:
            sk_resp = client.table("skills").select("id, name").in_("id", skill_ids).execute()
            skill_names = {row["id"]: row["name"] for row in (sk_resp.data or [])}
        for m in assessment_meta.values():
            m["skill_name"] = skill_names.get(m.get("skill_id"))

    completed = [a for a in attempts if a["status"] == "COMPLETED"]
    percentages = [a["percentage"] for a in completed if a.get("percentage") is not None]
    average_percentage = round(sum(percentages) / len(percentages), 1) if percentages else None

    assessments_out = [
        {
            "assessment_title": assessment_meta.get(a["assessment_id"], {}).get("title"),
            "skill_name": assessment_meta.get(a["assessment_id"], {}).get("skill_name"),
            "status": a["status"],
            "percentage": a.get("percentage"),
            "submitted_at": a.get("submitted_at"),
        }
        for a in attempts
    ]

    application_ids = [a["id"] for a in applications]
    interviews_out: list[dict] = []
    if application_ids:
        # Deliberately selects only these columns -- `notes` (industry-
        # private preparation notes) is never fetched here even though
        # the institution's own SELECT policy technically covers the
        # whole row; see StudentInterviewSummary's own docstring.
        interviews_resp = (
            client.table("interviews")
            .select("id, application_id, scheduled_at, mode, status")
            .in_("application_id", application_ids)
            .execute()
        )
        app_by_id = {a["id"]: a for a in applications}
        for iv in interviews_resp.data or []:
            app = app_by_id.get(iv["application_id"], {})
            opp_id = app.get("internship_id") or app.get("job_id")
            interviews_out.append(
                {
                    "id": iv["id"],
                    "opportunity_title": titles.get(opp_id),
                    "scheduled_at": iv["scheduled_at"],
                    "mode": iv["mode"],
                    "status": iv["status"],
                }
            )

    notes = [
        "No resume/file storage exists in this schema -- a resume link is not shown.",
        "GitHub/LinkedIn are not tracked as student-profile fields -- only per-project links, shown under Projects.",
        "\"Eligible students\" / backlog information is not tracked anywhere in this schema.",
        (
            "Internship status reflects the application lifecycle only (no attendance/duration tracking "
            "exists) -- \"Selected\" does not distinguish an ongoing internship from a completed one."
        ),
    ]

    return {
        "id": student_id,
        "full_name": name_row.get("full_name"),
        "username": name_row.get("username"),
        "avatar_url": name_row.get("avatar_url"),
        "link_request_id": link_request_id,
        "department_id": dept_id,
        "department": department_names.get(dept_id, _UNASSIGNED) if dept_id else _UNASSIGNED,
        "self_reported_department": (student.get("department") or "").strip() or None,
        "batch": student.get("graduation_year"),
        "degree": student.get("degree"),
        "cgpa": student.get("cgpa"),
        "percentage": student.get("percentage"),
        "profile_completion": _profile_completion(name_row, student),
        "skills": skills,
        "projects": projects_out,
        "certifications": list(certifications_resp.data or []),
        "achievements": list(achievements_resp.data or []),
        "applications": applications_out,
        "placement_status": placement_status,
        "internship_status": internship_status,
        "assessments_completed": len(completed),
        "average_assessment_percentage": average_percentage,
        "assessments": assessments_out,
        "interviews": interviews_out,
        "notes": notes,
    }
