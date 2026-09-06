"""Business logic for the Student "My Institution" portal
(backend/app/api/student_institution.py, /student/institution...,
database/migrations/047_student_institution_visibility.sql).

PHASE 12. Coordinates EXISTING entities only -- no new table:

  - `student_profiles.institution_id` is the ONE source of truth for
    "is this student verified by an institution" -- set/cleared ONLY by
    the institution_link_requests approval/unlink trigger (038). This
    module never writes it and never introduces a second verification
    flag.
  - `institution_internships` (status = 'ACTIVE') is the ONE source of
    truth for "which internships does my institution consider curated" --
    reused verbatim from the Institution-Curated Internships module (046).
    A PUBLISHED internship no institution_internships row references is
    never shown here.
  - `placement_drives` eligibility reuses
    institution_placement_service.compute_eligibility verbatim -- there
    is no second eligibility engine.
  - `institution_events` (status = 'PUBLISHED') carries no registration/
    attendance data because none exists anywhere in this schema --
    `is_relevant_to_me` is descriptive target_department_ids/
    target_batches metadata, never a participation record.
  - Applying reuses the EXISTING student_opportunity_service /
    applications table unchanged -- this module never writes an
    application itself, only reads the student's own rows to compute
    already_applied / application_status and the Activity feed.
"""

from datetime import UTC, datetime

from supabase import Client

from app.services.institution_placement_service import compute_eligibility
from app.services.institution_service import _fetch_company_names

_CURATION_NOTE = (
    "Placement drives, internships and events below are only the ones YOUR institution has announced or "
    "curated -- not every opportunity on the platform."
)
_ELIGIBILITY_NOTE = (
    "Eligibility for a placement drive uses the exact same rule your institution's TPO sees -- department, "
    "batch, minimum CGPA and required skills, only where the drive actually sets that criterion."
)
_REGISTRATION_NOTE = (
    "Registration and attendance tracking are not available in the current system -- events show "
    "information only."
)

_DRIVE_COLUMNS = (
    "id, job_id, title, description, status, application_deadline, drive_date, mode, venue, "
    "eligible_department_ids, eligible_batches, minimum_cgpa, eligible_skill_ids"
)
_INTERNSHIP_COLUMNS = (
    "id, industry_id, title, description, work_mode, duration_months, stipend_amount, stipend_currency, "
    "eligibility_criteria, application_deadline, start_date, status"
)
_EVENT_COLUMNS = (
    "id, industry_id, title, description, event_type, status, mode, venue, start_at, end_at, "
    "target_department_ids, target_batches"
)

_MAX_ACTIVITY_ITEMS = 20


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ============================================================
# identity / linkage
# ============================================================


def _fetch_own_student_profile(client: Client, student_id: str) -> dict | None:
    resp = (
        client.table("student_profiles")
        .select("id, institution_id, department_id, graduation_year, cgpa")
        .eq("id", student_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def _fetch_institution_identity(client: Client, institution_id: str) -> dict | None:
    resp = (
        client.table("institution_profiles")
        .select("id, institution_name, institution_type, location, website_url")
        .eq("id", institution_id)
        .maybe_single()
        .execute()
    )
    if resp and resp.data:
        return resp.data
    # A lazily-created institution account (no institution_profiles row
    # filled in yet) is still a valid, verified link -- show the id-only
    # shell rather than treating "no profile row" as "not linked".
    return {"id": institution_id, "institution_name": None, "institution_type": None, "location": None, "website_url": None}


def _fetch_own_department_name(client: Client, department_id: str | None) -> str | None:
    if department_id is None:
        return None
    resp = client.table("departments").select("id, name").eq("id", department_id).maybe_single().execute()
    return (resp.data or {}).get("name") if resp and resp.data else None


def _fetch_verified_at(client: Client, student_id: str, institution_id: str) -> str | None:
    resp = (
        client.table("institution_link_requests")
        .select("updated_at")
        .eq("student_id", student_id)
        .eq("institution_id", institution_id)
        .eq("status", "APPROVED")
        .maybe_single()
        .execute()
    )
    return (resp.data or {}).get("updated_at") if resp and resp.data else None


# ============================================================
# placement drives
# ============================================================


def _fetch_drives(client: Client, institution_id: str) -> list[dict]:
    resp = client.table("placement_drives").select(_DRIVE_COLUMNS).eq("institution_id", institution_id).execute()
    return list(resp.data or [])


def _fetch_jobs(client: Client, job_ids: list[str]) -> dict[str, dict]:
    if not job_ids:
        return {}
    resp = client.table("jobs").select("id, industry_id").in_("id", job_ids).execute()
    return {row["id"]: row for row in (resp.data or [])}


def _fetch_own_skills(client: Client, student_id: str) -> set[str]:
    resp = client.table("student_skills").select("skill_id").eq("student_id", student_id).execute()
    return {row["skill_id"] for row in (resp.data or [])}


def _fetch_skill_names(client: Client, skill_ids: set[str]) -> dict[str, str]:
    if not skill_ids:
        return {}
    resp = client.table("skills").select("id, name").in_("id", list(skill_ids)).execute()
    return {row["id"]: row["name"] for row in (resp.data or [])}


def _build_placement_drives(
    client: Client,
    student: dict,
    institution_id: str,
    student_skill_ids: set[str],
    skill_names: dict[str, str],
    applications_by_job: dict[str, dict],
) -> list[dict]:
    drives = _fetch_drives(client, institution_id)
    job_ids = list({d["job_id"] for d in drives if d.get("job_id")})
    jobs_by_id = _fetch_jobs(client, job_ids)
    industry_ids = list({j["industry_id"] for j in jobs_by_id.values() if j.get("industry_id")})
    company_names = _fetch_company_names(client, industry_ids)

    rows = []
    for d in drives:
        is_eligible, reasons = compute_eligibility(student, student_skill_ids, d, skill_names)
        job = jobs_by_id.get(d.get("job_id"), {})
        application = applications_by_job.get(d.get("job_id"))
        rows.append(
            {
                "id": d["id"],
                "title": d["title"],
                "description": d.get("description"),
                "status": d["status"],
                "application_deadline": d.get("application_deadline"),
                "drive_date": d.get("drive_date"),
                "mode": d.get("mode"),
                "venue": d.get("venue"),
                "company_name": company_names.get(job.get("industry_id")),
                "job_id": d["job_id"],
                "is_eligible": is_eligible,
                "eligibility_reasons": reasons,
                "already_applied": application is not None,
                "application_status": application["status"] if application else None,
            }
        )
    rows.sort(key=lambda r: (r["status"] != "OPEN", r["title"].lower()))
    return rows


# ============================================================
# curated internships
# ============================================================


def _fetch_curated_internship_ids(client: Client, institution_id: str) -> list[str]:
    resp = (
        client.table("institution_internships")
        .select("internship_id")
        .eq("institution_id", institution_id)
        .eq("status", "ACTIVE")
        .execute()
    )
    return [row["internship_id"] for row in (resp.data or [])]


def _fetch_internships_by_ids(client: Client, internship_ids: list[str]) -> dict[str, dict]:
    if not internship_ids:
        return {}
    resp = client.table("internships").select(_INTERNSHIP_COLUMNS).in_("id", internship_ids).execute()
    return {row["id"]: row for row in (resp.data or [])}


def _build_internships(
    client: Client,
    institution_id: str,
    applications_by_internship: dict[str, dict],
) -> list[dict]:
    curated_ids = _fetch_curated_internship_ids(client, institution_id)
    # Only currently-PUBLISHED internships are actually readable to a
    # non-owner (018_internships.sql) -- a curated internship the company
    # has since closed simply does not appear here, same "students only
    # ever see live postings" boundary as the general Opportunities feed.
    internships_by_id = _fetch_internships_by_ids(client, curated_ids)

    industry_ids = list({v["industry_id"] for v in internships_by_id.values() if v.get("industry_id")})
    company_names = _fetch_company_names(client, industry_ids)

    rows = []
    for iid, internship in internships_by_id.items():
        application = applications_by_internship.get(iid)
        rows.append(
            {
                "id": iid,
                "title": internship["title"],
                "description": internship.get("description"),
                "company_name": company_names.get(internship.get("industry_id")),
                "work_mode": internship.get("work_mode"),
                "duration_months": internship.get("duration_months"),
                "stipend_amount": internship.get("stipend_amount"),
                "stipend_currency": internship.get("stipend_currency"),
                "application_deadline": internship.get("application_deadline"),
                "start_date": internship.get("start_date"),
                "eligibility_criteria": internship.get("eligibility_criteria"),
                "already_applied": application is not None,
                "application_status": application["status"] if application else None,
            }
        )
    rows.sort(key=lambda r: r["title"].lower())
    return rows


# ============================================================
# events
# ============================================================


def _build_events(client: Client, institution_id: str, department_id: str | None, batch: int | None) -> list[dict]:
    resp = (
        client.table("institution_events")
        .select(_EVENT_COLUMNS)
        .eq("institution_id", institution_id)
        .eq("status", "PUBLISHED")
        .execute()
    )
    events = list(resp.data or [])
    industry_ids = list({e["industry_id"] for e in events if e.get("industry_id")})
    company_names = _fetch_company_names(client, industry_ids)

    rows = []
    for e in events:
        target_depts = e.get("target_department_ids") or []
        target_batches = e.get("target_batches") or []
        relevant = (not target_depts or department_id in target_depts) and (not target_batches or batch in target_batches)
        rows.append(
            {
                "id": e["id"],
                "title": e["title"],
                "description": e.get("description"),
                "event_type": e["event_type"],
                "mode": e.get("mode"),
                "venue": e.get("venue"),
                "start_at": e.get("start_at"),
                "end_at": e.get("end_at"),
                "company_name": company_names.get(e.get("industry_id")),
                "is_relevant_to_me": relevant,
            }
        )
    rows.sort(key=lambda r: (not r["is_relevant_to_me"], r.get("start_at") or ""))
    return rows


# ============================================================
# applications (own, scoped)
# ============================================================


def _fetch_own_applications(client: Client, student_id: str) -> list[dict]:
    resp = (
        client.table("applications")
        .select("id, status, opportunity_type, internship_id, job_id, applied_at, updated_at")
        .eq("student_id", student_id)
        .execute()
    )
    return list(resp.data or [])


# ============================================================
# activity (derived only, no new table)
# ============================================================


def _build_activity(
    applications: list[dict],
    curated_internship_ids: set[str],
    drive_job_ids: set[str],
    internship_titles: dict[str, str],
    job_titles: dict[str, str],
    verified_at: str | None,
    institution_name: str | None,
) -> list[dict]:
    items: list[dict] = []

    if verified_at:
        items.append(
            {
                "type": "INSTITUTION_VERIFIED",
                "label": f"Verified by {institution_name or 'your institution'}",
                "occurred_at": verified_at,
            }
        )

    for a in applications:
        if a.get("opportunity_type") == "INTERNSHIP" and a.get("internship_id") in curated_internship_ids:
            title = internship_titles.get(a["internship_id"], "an internship")
            items.append({"type": "INTERNSHIP_APPLIED", "label": f"Applied to {title}", "occurred_at": a["applied_at"]})
            if a.get("status") == "SELECTED":
                items.append({"type": "SELECTED", "label": f"Selected for {title}", "occurred_at": a.get("updated_at") or a["applied_at"]})
        elif a.get("opportunity_type") == "JOB" and a.get("job_id") in drive_job_ids:
            title = job_titles.get(a["job_id"], "a placement drive")
            items.append({"type": "PLACEMENT_APPLIED", "label": f"Applied to {title}", "occurred_at": a["applied_at"]})
            if a.get("status") == "SELECTED":
                items.append({"type": "SELECTED", "label": f"Selected for {title}", "occurred_at": a.get("updated_at") or a["applied_at"]})

    items.sort(key=lambda i: i["occurred_at"] or "", reverse=True)
    return items[:_MAX_ACTIVITY_ITEMS]


# ============================================================
# entry point
# ============================================================


def _empty_response() -> dict:
    return {
        "linked": False,
        "institution": None,
        "profile": None,
        "kpis": {"placement_drives": 0, "internships": 0, "events": 0, "active_applications": 0},
        "placement_drives": [],
        "internships": [],
        "events": [],
        "activity": [],
        "curation_note": _CURATION_NOTE,
        "eligibility_note": _ELIGIBILITY_NOTE,
        "registration_note": _REGISTRATION_NOTE,
    }


def get_my_institution(client: Client, student_id: str) -> dict:
    student = _fetch_own_student_profile(client, student_id)
    institution_id = (student or {}).get("institution_id")
    if not student or not institution_id:
        return _empty_response()

    department_id = student.get("department_id")
    batch = student.get("graduation_year")

    identity = _fetch_institution_identity(client, institution_id)
    department_name = _fetch_own_department_name(client, department_id)
    verified_at = _fetch_verified_at(client, student_id, institution_id)

    applications = _fetch_own_applications(client, student_id)
    applications_by_job = {a["job_id"]: a for a in applications if a.get("job_id")}
    applications_by_internship = {a["internship_id"]: a for a in applications if a.get("internship_id")}

    student_skill_ids = _fetch_own_skills(client, student_id)
    skill_names = _fetch_skill_names(client, student_skill_ids)

    drives = _build_placement_drives(client, student, institution_id, student_skill_ids, skill_names, applications_by_job)
    internships = _build_internships(client, institution_id, applications_by_internship)
    events = _build_events(client, institution_id, department_id, batch)

    curated_internship_ids = {row["id"] for row in internships}
    drive_job_ids = {row["job_id"] for row in drives}
    internship_titles = {row["id"]: row["title"] for row in internships}
    job_titles = {row["job_id"]: row["title"] for row in drives}
    activity = _build_activity(
        applications,
        curated_internship_ids,
        drive_job_ids,
        internship_titles,
        job_titles,
        verified_at,
        (identity or {}).get("institution_name"),
    )

    active_applications = sum(
        1
        for a in applications
        if (a.get("internship_id") in curated_internship_ids or a.get("job_id") in drive_job_ids)
        and a.get("status") not in ("REJECTED", "WITHDRAWN")
    )

    return {
        "linked": True,
        "institution": identity,
        "profile": {
            "department_id": department_id,
            "department": department_name,
            "batch": batch,
            "cgpa": student.get("cgpa"),
            "verified_at": verified_at,
        },
        "kpis": {
            "placement_drives": len(drives),
            "internships": len(internships),
            "events": len(events),
            "active_applications": active_applications,
        },
        "placement_drives": drives,
        "internships": internships,
        "events": events,
        "activity": activity,
        "curation_note": _CURATION_NOTE,
        "eligibility_note": _ELIGIBILITY_NOTE,
        "registration_note": _REGISTRATION_NOTE,
    }
