"""Business logic for Institution Placement Drive Management
(backend/app/api/institution.py, /institution/placements...,
database/migrations/041_institution_placement_drives.sql).

Coordinates EXISTING entities -- never a parallel recruitment system:
  - Job/company data comes from `jobs` + `industry_profiles` (Industry
    still owns both; this module never writes to either).
  - Applicant status comes from the existing `applications` table.
  - Interview info comes from the existing `interviews` table.
  - "Placed" reuses the exact `_placement_buckets`-style definition
    already established in institution_service.py: an application row
    with status = 'SELECTED'. This module does not define a second
    placement concept -- see PlacementOverviewResponse's own docstring
    for how its drive-SCOPED numbers relate to (not contradict) the
    Dashboard's institution-WIDE numbers.

Every function takes an already-built *user-scoped* Supabase client and
RLS (037/038/039/040/041_institution_*.sql) is the real access-control
boundary -- nothing here uses service_role. `_fetch_names` is imported
from institution_student_service and `fetch_departments` /
`_fetch_company_names` / `_percentage` from institution_service, not
redefined -- one source of truth for name resolution, department
listing, and percentage rounding across every institution module.
"""

from collections import Counter

from supabase import Client

from app.services.institution_service import _fetch_company_names, _percentage, fetch_departments
from app.services.institution_student_service import _fetch_names

_DRIVE_COLUMNS = (
    "id, job_id, title, description, status, application_deadline, drive_date, mode, venue, "
    "instructions, eligible_department_ids, eligible_batches, minimum_cgpa, eligible_skill_ids, "
    "created_at, updated_at"
)

# DRAFT -> OPEN -> IN_PROGRESS -> COMPLETED, with CANCELLED reachable
# from any non-terminal state. COMPLETED and CANCELLED are both terminal
# -- matches Part 6's example lifecycle exactly.
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"OPEN", "CANCELLED"},
    "OPEN": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


class JobNotAvailableError(Exception):
    """The selected job is not PUBLISHED -- a new drive may only be
    created from a currently-open company posting (Part 27)."""


class CrossInstitutionEligibilityError(Exception):
    """An eligible_department_ids entry does not belong to the calling
    institution -- the database trigger (041) is the authoritative
    backstop; this is the clean, pre-write error."""


class InvalidStatusTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a placement drive from {current} to {target}.")


# ---- shared fetch helpers ----


def _fetch_institution_students(client: Client, institution_id: str) -> list[dict]:
    resp = (
        client.table("student_profiles")
        .select("id, department_id, graduation_year, cgpa")
        .eq("institution_id", institution_id)
        .execute()
    )
    return list(resp.data or [])


def _fetch_skills_by_student(client: Client, student_ids: list[str]) -> dict[str, set[str]]:
    if not student_ids:
        return {}
    resp = (
        client.table("student_skills").select("student_id, skill_id").in_("student_id", student_ids).execute()
    )
    out: dict[str, set[str]] = {}
    for row in resp.data or []:
        out.setdefault(row["student_id"], set()).add(row["skill_id"])
    return out


def _fetch_skill_names(client: Client, skill_ids: list[str]) -> dict[str, str]:
    if not skill_ids:
        return {}
    resp = client.table("skills").select("id, name").in_("id", list(set(skill_ids))).execute()
    return {row["id"]: row["name"] for row in (resp.data or [])}


def _fetch_job_details(client: Client, job_ids: list[str]) -> dict[str, dict]:
    """Resolves job display fields regardless of the job's CURRENT
    status, via institution_visible_job_details() -- scoped to jobs one
    of the caller's own placement drives references (migration 041).
    Keeps historical drives readable even after the underlying job
    closes/archives (Part 27)."""
    if not job_ids:
        return {}
    resp = client.rpc("institution_visible_job_details", {"job_ids": list(set(job_ids))}).execute()
    rows = getattr(resp, "data", None) or []
    return {row["id"]: row for row in rows if isinstance(row, dict)}


def _fetch_applications_for_jobs(client: Client, job_ids: list[str], student_ids: list[str]) -> list[dict]:
    """Applications for the given jobs, restricted (defense in depth on
    top of RLS) to the institution's OWN students."""
    if not job_ids or not student_ids:
        return []
    resp = (
        client.table("applications")
        .select("id, student_id, job_id, status, applied_at")
        .in_("job_id", job_ids)
        .in_("student_id", student_ids)
        .execute()
    )
    return list(resp.data or [])


# ---- eligibility engine (Part 9: centralized, never duplicated) ----


def compute_eligibility(
    student: dict,
    student_skill_ids: set[str],
    drive: dict,
    skill_names: dict[str, str],
) -> tuple[bool, list[str]]:
    """Returns (is_eligible, reasons). `reasons` is empty exactly when
    is_eligible is True -- an eligibility verdict is never opaque. Only
    evaluates criteria that are actually set on the drive (empty/None =
    no restriction for that criterion)."""
    reasons: list[str] = []

    dept_ids = drive.get("eligible_department_ids") or []
    if dept_ids and student.get("department_id") not in dept_ids:
        reasons.append("Department not eligible")

    batches = drive.get("eligible_batches") or []
    if batches and student.get("graduation_year") not in batches:
        reasons.append("Batch not eligible")

    minimum_cgpa = drive.get("minimum_cgpa")
    if minimum_cgpa is not None:
        cgpa = student.get("cgpa")
        if cgpa is None or cgpa < minimum_cgpa:
            reasons.append(f"CGPA below {minimum_cgpa}")

    skill_ids = drive.get("eligible_skill_ids") or []
    if skill_ids:
        missing = [sid for sid in skill_ids if sid not in student_skill_ids]
        if missing:
            names = ", ".join(skill_names.get(sid, "Unknown skill") for sid in missing)
            reasons.append(f"Missing required skill(s): {names}")

    return (len(reasons) == 0, reasons)


# ---- job picker ----


def list_available_jobs(client: Client, search: str | None = None) -> list[dict]:
    resp = (
        client.table("jobs")
        .select(
            "id, title, industry_id, work_mode, employment_type, location, application_deadline, "
            "salary_min, salary_max, salary_currency"
        )
        .eq("status", "PUBLISHED")
        .order("created_at", desc=True)
        .execute()
    )
    rows = list(resp.data or [])
    company_names = _fetch_company_names(client, [r["industry_id"] for r in rows])
    for r in rows:
        r["company_name"] = company_names.get(r["industry_id"])

    if search and search.strip():
        needle = search.strip().lower()
        rows = [
            r
            for r in rows
            if needle in r["title"].lower() or needle in (r.get("company_name") or "").lower()
        ]
    return rows


# ---- drive assembly ----


def _assemble_summaries(client: Client, institution_id: str, drives: list[dict]) -> list[dict]:
    if not drives:
        return []

    job_ids = list({d["job_id"] for d in drives})
    job_details = _fetch_job_details(client, job_ids)
    company_names = _fetch_company_names(client, [j["industry_id"] for j in job_details.values() if j.get("industry_id")])

    department_names = {d["id"]: d["name"] for d in fetch_departments(client, institution_id)}

    all_skill_ids: set[str] = set()
    for d in drives:
        all_skill_ids.update(d.get("eligible_skill_ids") or [])
    skill_names = _fetch_skill_names(client, list(all_skill_ids))

    students = _fetch_institution_students(client, institution_id)
    student_ids = [s["id"] for s in students]
    skills_by_student = _fetch_skills_by_student(client, student_ids)
    applications = _fetch_applications_for_jobs(client, job_ids, student_ids)
    apps_by_job: dict[str, list[dict]] = {}
    for a in applications:
        apps_by_job.setdefault(a["job_id"], []).append(a)

    out = []
    for d in drives:
        job = job_details.get(d["job_id"], {})
        job_apps = apps_by_job.get(d["job_id"], [])
        applied_ids = {a["student_id"] for a in job_apps}
        selected_ids = {a["student_id"] for a in job_apps if a["status"] == "SELECTED"}

        eligible_count = sum(
            1
            for s in students
            if compute_eligibility(s, skills_by_student.get(s["id"], set()), d, skill_names)[0]
        )

        out.append(
            {
                "id": d["id"],
                "job_id": d["job_id"],
                "job_title": job.get("title"),
                "industry_id": job.get("industry_id"),
                "company_name": company_names.get(job.get("industry_id")),
                "location": job.get("location"),
                "work_mode": job.get("work_mode"),
                "employment_type": job.get("employment_type"),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "salary_currency": job.get("salary_currency"),
                "job_status": job.get("status"),
                "job_description": job.get("description"),
                "title": d["title"],
                "description": d.get("description"),
                "status": d["status"],
                "application_deadline": d.get("application_deadline"),
                "drive_date": d.get("drive_date"),
                "mode": d.get("mode"),
                "venue": d.get("venue"),
                "instructions": d.get("instructions"),
                "eligible_department_ids": d.get("eligible_department_ids") or [],
                "eligible_department_names": [
                    department_names.get(did, "Unknown department") for did in (d.get("eligible_department_ids") or [])
                ],
                "eligible_batches": d.get("eligible_batches") or [],
                "minimum_cgpa": d.get("minimum_cgpa"),
                "eligible_skill_ids": d.get("eligible_skill_ids") or [],
                "eligible_skill_names": [
                    skill_names.get(sid, "Unknown skill") for sid in (d.get("eligible_skill_ids") or [])
                ],
                "eligible_count": eligible_count,
                "applied_count": len(applied_ids),
                "selected_count": len(selected_ids),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
            }
        )
    return out


def list_drives(
    client: Client,
    institution_id: str,
    *,
    search: str | None = None,
    status: str | None = None,
) -> list[dict]:
    resp = (
        client.table("placement_drives")
        .select(_DRIVE_COLUMNS)
        .eq("institution_id", institution_id)
        .order("created_at", desc=True)
        .execute()
    )
    drives = list(resp.data or [])
    summaries = _assemble_summaries(client, institution_id, drives)

    if status:
        summaries = [s for s in summaries if s["status"] == status]
    if search and search.strip():
        needle = search.strip().lower()
        summaries = [
            s
            for s in summaries
            if needle in s["title"].lower()
            or needle in (s.get("company_name") or "").lower()
            or needle in (s.get("job_title") or "").lower()
        ]
    return summaries


def get_drive(client: Client, institution_id: str, drive_id: str) -> dict | None:
    resp = (
        client.table("placement_drives")
        .select(_DRIVE_COLUMNS)
        .eq("id", drive_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
    )
    row = resp.data if resp is not None else None
    if not row:
        return None
    return _assemble_summaries(client, institution_id, [row])[0]


def _validate_department_ownership(client: Client, institution_id: str, department_ids: list[str]) -> None:
    if not department_ids:
        return
    owned = (
        client.table("departments")
        .select("id")
        .eq("institution_id", institution_id)
        .in_("id", department_ids)
        .execute()
        .data
        or []
    )
    if len({r["id"] for r in owned}) != len(set(department_ids)):
        raise CrossInstitutionEligibilityError("All eligible departments must belong to your own institution.")


def create_drive(client: Client, institution_id: str, fields: dict) -> dict:
    job_id = fields["job_id"]
    job = client.table("jobs").select("id, status").eq("id", job_id).maybe_single().execute().data
    if not job or job.get("status") != "PUBLISHED":
        raise JobNotAvailableError("The selected job is not available for a new placement drive.")

    _validate_department_ownership(client, institution_id, fields.get("eligible_department_ids") or [])

    payload = {"institution_id": institution_id, "status": "DRAFT", **fields}
    response = client.table("placement_drives").insert(payload).execute()
    new_id = response.data[0]["id"]

    row = get_drive(client, institution_id, new_id)
    if row is None:
        raise RuntimeError("placement_drives row could not be read back after create.")
    return row


def update_drive(client: Client, institution_id: str, drive_id: str, fields: dict) -> dict | None:
    existing = get_drive(client, institution_id, drive_id)
    if existing is None:
        return None

    if "eligible_department_ids" in fields:
        _validate_department_ownership(client, institution_id, fields.get("eligible_department_ids") or [])

    if fields:
        (
            client.table("placement_drives")
            .update(fields)
            .eq("id", drive_id)
            .eq("institution_id", institution_id)
            .execute()
        )
    return get_drive(client, institution_id, drive_id)


def update_drive_status(client: Client, institution_id: str, drive_id: str, new_status: str) -> dict | None:
    existing = (
        client.table("placement_drives")
        .select("status")
        .eq("id", drive_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
        .data
    )
    if not existing:
        return None

    current = existing["status"]
    if new_status not in _VALID_TRANSITIONS.get(current, set()):
        raise InvalidStatusTransitionError(current, new_status)

    (
        client.table("placement_drives")
        .update({"status": new_status})
        .eq("id", drive_id)
        .eq("institution_id", institution_id)
        .execute()
    )
    return get_drive(client, institution_id, drive_id)


# ---- eligible students / applicants ----


def get_drive_students(client: Client, institution_id: str, drive_id: str) -> dict | None:
    drive = (
        client.table("placement_drives")
        .select("job_id, eligible_department_ids, eligible_batches, minimum_cgpa, eligible_skill_ids")
        .eq("id", drive_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
        .data
    )
    if not drive:
        return None

    students = _fetch_institution_students(client, institution_id)
    student_ids = [s["id"] for s in students]
    names = _fetch_names(client, student_ids)
    skills_by_student = _fetch_skills_by_student(client, student_ids)
    skill_names = _fetch_skill_names(client, drive.get("eligible_skill_ids") or [])
    department_names = {d["id"]: d["name"] for d in fetch_departments(client, institution_id)}

    applications = _fetch_applications_for_jobs(client, [drive["job_id"]], student_ids)
    status_by_student = {a["student_id"]: a["status"] for a in applications}

    out = []
    eligible_count = 0
    applied_count = 0
    for s in students:
        sid = s["id"]
        is_eligible, reasons = compute_eligibility(s, skills_by_student.get(sid, set()), drive, skill_names)
        if is_eligible:
            eligible_count += 1
        app_status = status_by_student.get(sid)
        if app_status:
            applied_count += 1
        name_row = names.get(sid, {})
        out.append(
            {
                "id": sid,
                "full_name": name_row.get("full_name"),
                "username": name_row.get("username"),
                "avatar_url": name_row.get("avatar_url"),
                "department": department_names.get(s.get("department_id"), "Unassigned")
                if s.get("department_id")
                else "Unassigned",
                "batch": s.get("graduation_year"),
                "cgpa": s.get("cgpa"),
                "is_eligible": is_eligible,
                "reasons": reasons,
                "application_status": app_status,
            }
        )

    return {"students": out, "eligible_count": eligible_count, "applied_count": applied_count}


def get_drive_applicants(client: Client, institution_id: str, drive_id: str) -> dict | None:
    drive = (
        client.table("placement_drives")
        .select("job_id")
        .eq("id", drive_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
        .data
    )
    if not drive:
        return None

    students = _fetch_institution_students(client, institution_id)
    student_ids = [s["id"] for s in students]
    students_by_id = {s["id"]: s for s in students}
    department_names = {d["id"]: d["name"] for d in fetch_departments(client, institution_id)}

    applications = _fetch_applications_for_jobs(client, [drive["job_id"]], student_ids)
    names = _fetch_names(client, [a["student_id"] for a in applications])

    interviews_by_application: dict[str, dict] = {}
    application_ids = [a["id"] for a in applications]
    if application_ids:
        # Deliberately excludes `notes` (industry-private preparation
        # notes) -- same exclusion as institution_student_service.
        interviews_resp = (
            client.table("interviews")
            .select("application_id, scheduled_at, mode, status")
            .in_("application_id", application_ids)
            .execute()
        )
        for iv in interviews_resp.data or []:
            interviews_by_application[iv["application_id"]] = iv

    out = []
    for a in applications:
        student = students_by_id.get(a["student_id"], {})
        name_row = names.get(a["student_id"], {})
        interview = interviews_by_application.get(a["id"])
        out.append(
            {
                "application_id": a["id"],
                "student_id": a["student_id"],
                "full_name": name_row.get("full_name"),
                "username": name_row.get("username"),
                "department": department_names.get(student.get("department_id"), "Unassigned")
                if student.get("department_id")
                else "Unassigned",
                "cgpa": student.get("cgpa"),
                "status": a["status"],
                "applied_at": a.get("applied_at"),
                "interview": (
                    {
                        "scheduled_at": interview["scheduled_at"],
                        "mode": interview["mode"],
                        "status": interview["status"],
                    }
                    if interview
                    else None
                ),
            }
        )
    return {"applicants": out}


# ---- placement analytics (Part 21) ----


def get_placement_overview(client: Client, institution_id: str) -> dict:
    drives = (
        client.table("placement_drives")
        .select("id, job_id, status")
        .eq("institution_id", institution_id)
        .execute()
        .data
        or []
    )
    active_drives = sum(1 for d in drives if d["status"] in ("OPEN", "IN_PROGRESS"))
    completed_drives = sum(1 for d in drives if d["status"] == "COMPLETED")

    job_ids = list({d["job_id"] for d in drives})
    students = _fetch_institution_students(client, institution_id)
    student_ids = [s["id"] for s in students]
    students_by_id = {s["id"]: s for s in students}
    department_names = {d["id"]: d["name"] for d in fetch_departments(client, institution_id)}

    applications = _fetch_applications_for_jobs(client, job_ids, student_ids)
    participating_ids = {a["student_id"] for a in applications}
    selected_apps = [a for a in applications if a["status"] == "SELECTED"]
    placed_ids = {a["student_id"] for a in selected_apps}

    dept_counter: Counter[str] = Counter()
    for a in selected_apps:
        student = students_by_id.get(a["student_id"], {})
        dept_id = student.get("department_id")
        label = department_names.get(dept_id, "Unassigned") if dept_id else "Unassigned"
        dept_counter[label] += 1

    job_details = _fetch_job_details(client, job_ids)
    company_names = _fetch_company_names(client, [j["industry_id"] for j in job_details.values() if j.get("industry_id")])
    company_counter: Counter[str] = Counter()
    for a in selected_apps:
        job = job_details.get(a["job_id"], {})
        name = company_names.get(job.get("industry_id"), "Unknown company")
        company_counter[name] += 1

    return {
        "active_drives": active_drives,
        "completed_drives": completed_drives,
        "participating_students": len(participating_ids),
        "placed_students": len(placed_ids),
        "total_selected_offers": len(selected_apps),
        "placement_rate": _percentage(len(placed_ids), len(participating_ids)),
        "department_breakdown": [
            {"department": dept, "placed_count": count} for dept, count in sorted(dept_counter.items())
        ],
        "company_breakdown": [
            {"company_name": name, "selected_count": count}
            for name, count in company_counter.most_common()
        ],
    }
