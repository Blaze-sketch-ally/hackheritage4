"""Business logic for the Institution-Curated Internships module
(backend/app/api/institution.py, /institution/internships...,
database/migrations/046_institution_internships.sql).

Replaces the old Phase 7 "directory" (every currently-PUBLISHED
internship platform-wide, plus any internship one of the institution's
own students happened to apply to) with an EXPLICIT curation model:

    Industry posts an internship
        -> Institution browses AVAILABLE internships (PUBLISHED, not yet
           curated by this institution) via `list_available_internships`
        -> Institution explicitly `select_internship`s one
        -> it appears in the institution's CURATED list
           (`list_internships`, `compute_internship_overview`,
           `get_internship_detail`) -- the module's default view
        -> Institution can `remove_internship` (soft-deactivate; the
           canonical internship and every other institution's own
           curation of it are untouched)

There is still no `institution_internship_applications` table --
application/selection data is read live from the EXISTING `applications`
table (020_applications.sql), scoped to whichever internships this
institution has curated. "Selected" (a student) still means exactly what
it has meant since 037_institution_tenancy.sql: an application row with
opportunity_type = 'INTERNSHIP' and status = 'SELECTED'.
`institution_internships.status` (ACTIVE/INACTIVE) is a DIFFERENT
concept -- whether the INSTITUTION itself curated this internship -- and
is exposed as `association_status`, never conflated with a student's
`status` (application status) or the internship's own posting `status`.

Participation estimate (unchanged from Phase 7 -- this schema has NO
attendance/completion table): `_estimate_participation` derives a
best-effort NOT_STARTED / ACTIVE / COMPLETED / UNKNOWN from the
internship's own `start_date` + `duration_months` for a SELECTED
application. UNKNOWN is never silently folded into ACTIVE or COMPLETED.

Eligibility (unchanged): `internships` has only a free-text
`eligibility_criteria` column -- no per-student eligibility verdict is
computed here; only the raw text is ever surfaced.

Stipend (unchanged): the existing flat `internships.stipend_amount` /
`stipend_currency` columns -- there is no separate disbursement ledger
anywhere in this schema, so none is invented or exposed here.

`_fetch_published_internships`, `_fetch_visible_internship_details`,
`_estimate_participation`, `_COMPLETED`, `_today` are also imported by
institution_industry_service.py for the Company Detail page's own
"Internship Activity" card (applications-based, a different, still-valid
metric: "how many of our students have applied to / been selected for an
internship at this company", independent of curation) -- their names and
behavior are preserved unchanged.
"""

import calendar
from collections import Counter
from datetime import UTC, date, datetime

from supabase import Client

from app.schemas.application import APPLICATION_STATUSES
from app.services.institution_department_service import list_departments
from app.services.institution_placement_service import _fetch_institution_students
from app.services.institution_service import (
    _fetch_company_names,
    _percentage,
    fetch_departments,
)
from app.services.institution_student_service import _fetch_names

_TENANCY_NOTE = (
    "Applicant, selected, and participation figures cover only students explicitly linked to your "
    "institution (student_profiles.institution_id), among internships YOUR institution has curated. An "
    "internship your students applied to that your institution never added to its curated list is not "
    "counted here."
)

_CURATION_NOTE = (
    "This page shows only internships your institution has explicitly selected/curated -- not every "
    "internship on the platform. Use \"Browse Available Internships\" to add more."
)

_ELIGIBILITY_NOTE = (
    "Internships do not have the structured eligibility criteria placement drives have (no department/"
    "batch/CGPA/skill restrictions are modeled) -- only a free-text \"eligibility criteria\" field the "
    "company itself wrote. No per-student eligibility verdict is calculated or shown."
)

_PARTICIPATION_NOTE = (
    "\"Active\" / \"Completed\" are ESTIMATES computed from the internship's own start date and duration "
    "for each selected student -- there is no attendance or completion record anywhere in this schema. "
    "An internship missing a start date or duration is reported as \"Unknown\", never guessed."
)

_STIPEND_NOTE_UNAVAILABLE = "No internship your institution has curated currently declares a stipend amount."
_STIPEND_NOTE_AVAILABLE = (
    "Stipend is the amount the company itself entered on the posting -- there is no separate payment/"
    "disbursement ledger in this schema. Grouped by currency; amounts in different currencies are never "
    "averaged together."
)

_PRIVACY_NOTE = (
    "Only application status, department, CGPA and interview scheduling are shown -- no student contact "
    "information and no industry-private interview notes."
)

_INTERNSHIP_COLUMNS = (
    "id, industry_id, title, description, location, work_mode, duration_months, stipend_amount, "
    "stipend_currency, eligibility_criteria, application_deadline, start_date, status"
)
_ASSOCIATION_COLUMNS = "id, institution_id, internship_id, status, created_at, updated_at"

_NOT_STARTED, _ACTIVE, _COMPLETED, _UNKNOWN = "NOT_STARTED", "ACTIVE", "COMPLETED", "UNKNOWN"


class InternshipNotAvailableError(Exception):
    """`internship_id` does not reference an internship this institution
    may select -- it does not exist, or is not currently PUBLISHED (same
    visibility rule the database's own validate_internship_selection
    trigger, 046, enforces as the authoritative backstop)."""


class DuplicateAssociationError(Exception):
    """This institution has already curated this internship --
    institution_internships_unique_pair (046)."""


def _today() -> date:
    return datetime.now(UTC).date()


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _parse_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _estimate_participation(internship: dict, today: date) -> str:
    start = _parse_date(internship.get("start_date"))
    months = internship.get("duration_months")
    if start is None or not months:
        return _UNKNOWN
    end = _add_months(start, int(months))
    if today < start:
        return _NOT_STARTED
    if today <= end:
        return _ACTIVE
    return _COMPLETED


# ============================================================
# fetch helpers
# ============================================================


def _fetch_published_internships(client: Client) -> dict[str, dict]:
    resp = client.table("internships").select(_INTERNSHIP_COLUMNS).eq("status", "PUBLISHED").execute()
    return {row["id"]: row for row in (resp.data or [])}


def _fetch_internships_by_ids(client: Client, internship_ids: list[str]) -> dict[str, dict]:
    if not internship_ids:
        return {}
    resp = client.table("internships").select(_INTERNSHIP_COLUMNS).in_("id", internship_ids).execute()
    return {row["id"]: row for row in (resp.data or [])}


def _fetch_internship_applications(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("applications")
        .select("id, student_id, internship_id, status, applied_at")
        .eq("opportunity_type", "INTERNSHIP")
        .in_("student_id", student_ids)
        .execute()
    )
    return [row for row in (resp.data or []) if row.get("internship_id")]


def _fetch_visible_internship_details(client: Client, internship_ids: list[str]) -> dict[str, dict]:
    """Historical-visibility fallback keyed by STUDENT APPLICATION (042) --
    used only by institution_industry_service's own applications-based
    Company Detail activity card, never by the curated module below (which
    uses `_fetch_curated_internship_details` instead)."""
    if not internship_ids:
        return {}
    resp = client.rpc("institution_visible_internship_details", {"internship_ids": internship_ids}).execute()
    rows = getattr(resp, "data", None) or []
    return {row["id"]: row for row in rows if isinstance(row, dict)}


def _fetch_curated_internship_details(client: Client, internship_ids: list[str]) -> dict[str, dict]:
    """Historical-visibility fallback keyed by CURATION (046) -- for a
    curated internship that is no longer PUBLISHED, resolves its full
    display fields anyway, but ONLY for internships THIS institution has
    curated. See institution_curated_internship_details in
    046_institution_internships.sql."""
    if not internship_ids:
        return {}
    resp = client.rpc("institution_curated_internship_details", {"internship_ids": internship_ids}).execute()
    rows = getattr(resp, "data", None) or []
    return {row["id"]: row for row in rows if isinstance(row, dict)}


def _fetch_associations(client: Client, institution_id: str, *, status: str | None = None) -> list[dict]:
    query = client.table("institution_internships").select(_ASSOCIATION_COLUMNS).eq("institution_id", institution_id)
    if status:
        query = query.eq("status", status)
    resp = query.execute()
    return list(resp.data or [])


def _fetch_single_association(client: Client, institution_id: str, internship_id: str) -> dict | None:
    resp = (
        client.table("institution_internships")
        .select(_ASSOCIATION_COLUMNS)
        .eq("institution_id", institution_id)
        .eq("internship_id", internship_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def _gather(client: Client, institution_id: str) -> dict:
    """One pass of the shared reads every CURATED internship endpoint
    needs. Scope is always this institution's own ACTIVE curation --
    never every published internship, never another institution's
    curation."""
    associations = _fetch_associations(client, institution_id, status="ACTIVE")
    assoc_by_internship = {a["internship_id"]: a for a in associations}
    internship_ids = list(assoc_by_internship)

    resolved = _fetch_internships_by_ids(client, internship_ids)
    missing_ids = [i for i in internship_ids if i not in resolved]
    historical = _fetch_curated_internship_details(client, missing_ids)
    internships_by_id: dict[str, dict] = {**historical, **resolved}

    students = _fetch_institution_students(client, institution_id)
    students_by_id = {s["id"]: s for s in students}
    student_ids = list(students_by_id)

    applications_all = _fetch_internship_applications(client, student_ids)
    # Scoped to curated internships only -- an application to an
    # internship this institution never curated does not count toward
    # any curated-module metric.
    applications = [a for a in applications_all if a["internship_id"] in internships_by_id]
    apps_by_internship: dict[str, list[dict]] = {}
    for a in applications:
        apps_by_internship.setdefault(a["internship_id"], []).append(a)

    industry_ids = list({v["industry_id"] for v in internships_by_id.values() if v.get("industry_id")})
    company_names = _fetch_company_names(client, industry_ids)

    return {
        "associations": associations,
        "assoc_by_internship": assoc_by_internship,
        "internship_ids": internship_ids,
        "internships_by_id": internships_by_id,
        "students": students,
        "students_by_id": students_by_id,
        "applications": applications,
        "apps_by_internship": apps_by_internship,
        "company_names": company_names,
    }


# ============================================================
# available internships (browse -> select)
# ============================================================


def list_available_internships(
    client: Client,
    institution_id: str,
    *,
    search: str | None = None,
    mode: str | None = None,
    company_id: str | None = None,
) -> dict:
    """PUBLISHED internships (platform-wide, same visibility every
    authenticated user already has -- 018_internships.sql) that this
    institution has NOT currently, actively curated. A previously
    REMOVED (INACTIVE) internship reappears here -- removing is not
    permanent, matching this project's deactivate-don't-delete
    convention."""
    published = _fetch_published_internships(client)
    active_curated_ids = {a["internship_id"] for a in _fetch_associations(client, institution_id, status="ACTIVE")}
    available = {iid: row for iid, row in published.items() if iid not in active_curated_ids}

    industry_ids = list({v["industry_id"] for v in available.values() if v.get("industry_id")})
    company_names = _fetch_company_names(client, industry_ids)

    rows = [
        {
            "id": iid,
            "title": v["title"],
            "company_name": company_names.get(v.get("industry_id")),
            "industry_id": v.get("industry_id"),
            "work_mode": v.get("work_mode"),
            "duration_months": v.get("duration_months"),
            "stipend_amount": v.get("stipend_amount"),
            "stipend_currency": v.get("stipend_currency"),
            "application_deadline": v.get("application_deadline"),
            "start_date": v.get("start_date"),
            "status": v.get("status"),
        }
        for iid, v in available.items()
    ]

    mode_options = sorted({r["work_mode"] for r in rows if r["work_mode"]})

    if search and search.strip():
        needle = search.strip().lower()
        rows = [r for r in rows if needle in r["title"].lower() or needle in (r.get("company_name") or "").lower()]
    if mode:
        rows = [r for r in rows if r["work_mode"] == mode]
    if company_id:
        rows = [r for r in rows if r["industry_id"] == company_id]

    rows.sort(key=lambda r: r["title"].lower())
    return {"internships": rows, "mode_options": mode_options}


# ============================================================
# select / remove
# ============================================================


def select_internship(client: Client, institution_id: str, internship_id: str) -> dict:
    """Curate a real, currently-visible-to-this-institution internship.
    This runs through the institution's own RLS-scoped client, so
    `internships` would only return a row here when it is PUBLISHED
    (018_internships.sql's public policy) even without the explicit
    `.eq("status", "PUBLISHED")` below -- the explicit filter is defense
    in depth on top of RLS, same "explicit ownership/visibility filter
    on top of RLS" convention every other service module in this project
    already follows. A DRAFT/CLOSED/ARCHIVED or nonexistent id resolves
    to nothing, same as institution_industry_service.create_relationship's
    company-existence check. The database's own
    validate_internship_selection trigger (046) is the authoritative
    backstop even if this check is somehow bypassed."""
    internship_resp = (
        client.table("internships")
        .select("id")
        .eq("id", internship_id)
        .eq("status", "PUBLISHED")
        .maybe_single()
        .execute()
    )
    if not (internship_resp and internship_resp.data):
        raise InternshipNotAvailableError("This internship is not available to select.")

    existing = _fetch_single_association(client, institution_id, internship_id)
    if existing is not None:
        if existing["status"] == "ACTIVE":
            raise DuplicateAssociationError("This internship is already part of your curated list.")
        client.table("institution_internships").update({"status": "ACTIVE"}).eq("id", existing["id"]).execute()
    else:
        payload = {"institution_id": institution_id, "internship_id": internship_id, "status": "ACTIVE"}
        try:
            client.table("institution_internships").insert(payload).execute()
        except Exception as exc:
            raise DuplicateAssociationError("This internship is already part of your curated list.") from exc

    row = _fetch_single_association(client, institution_id, internship_id)
    if row is None:
        raise RuntimeError("institution_internships row could not be read back after select.")
    return row


def remove_internship(client: Client, institution_id: str, internship_id: str) -> dict | None:
    """Soft-remove: sets status = INACTIVE. The canonical internship, any
    other institution's own curation of it, and this institution's
    historical detail view of it are all untouched -- there is no delete
    endpoint (deactivate-don't-delete, same convention as every other
    institution-owned relationship table in this schema)."""
    existing = _fetch_single_association(client, institution_id, internship_id)
    if existing is None:
        return None
    if existing["status"] != "INACTIVE":
        client.table("institution_internships").update({"status": "INACTIVE"}).eq("id", existing["id"]).execute()
    return _fetch_single_association(client, institution_id, internship_id)


# ============================================================
# curated directory
# ============================================================


def _row_for(iid: str, data: dict) -> dict | None:
    internship = data["internships_by_id"].get(iid)
    if internship is None:
        return None
    assoc = data["assoc_by_internship"][iid]
    apps = data["apps_by_internship"].get(iid, [])
    applicant_ids = {a["student_id"] for a in apps}
    selected_ids = {a["student_id"] for a in apps if a["status"] == "SELECTED"}
    return {
        "id": iid,
        "title": internship["title"],
        "company_name": data["company_names"].get(internship.get("industry_id")),
        "industry_id": internship.get("industry_id"),
        "work_mode": internship.get("work_mode"),
        "duration_months": internship.get("duration_months"),
        "stipend_amount": internship.get("stipend_amount"),
        "stipend_currency": internship.get("stipend_currency"),
        "application_deadline": internship.get("application_deadline"),
        "start_date": internship.get("start_date"),
        "status": internship.get("status"),
        "association_id": assoc["id"],
        "association_status": assoc["status"],
        "added_at": assoc.get("created_at"),
        "applicants_from_institution": len(applicant_ids),
        "selected_from_institution": len(selected_ids),
    }


def list_internships(
    client: Client,
    institution_id: str,
    *,
    search: str | None = None,
    status: str | None = None,
    mode: str | None = None,
    company_id: str | None = None,
) -> dict:
    """The institution's CURATED internship list -- the module's default
    view. Never every platform internship; never another institution's
    curation. `status` filters the underlying POSTING's own status
    (PUBLISHED/CLOSED/...), not the curation state -- every row here is
    already ACTIVE curation by definition."""
    data = _gather(client, institution_id)
    rows = [r for r in (_row_for(iid, data) for iid in data["internship_ids"]) if r is not None]

    status_options = sorted({r["status"] for r in rows if r["status"]})
    mode_options = sorted({r["work_mode"] for r in rows if r["work_mode"]})

    if search and search.strip():
        needle = search.strip().lower()
        rows = [
            r
            for r in rows
            if needle in r["title"].lower() or needle in (r.get("company_name") or "").lower()
        ]
    if status:
        rows = [r for r in rows if r["status"] == status]
    if mode:
        rows = [r for r in rows if r["work_mode"] == mode]
    if company_id:
        rows = [r for r in rows if r["industry_id"] == company_id]

    rows.sort(key=lambda r: (-r["applicants_from_institution"], r["title"].lower()))
    return {"internships": rows, "mode_options": mode_options, "status_options": status_options}


# ============================================================
# detail
# ============================================================


def get_internship_detail(client: Client, institution_id: str, internship_id: str) -> dict | None:
    """An internship this institution has curated -- ANY association
    status (ACTIVE or INACTIVE/removed), so a removed internship remains
    viewable historically, same convention as every other soft-removed
    institution-owned record in this schema. An internship this
    institution never curated is indistinguishable from one that doesn't
    exist."""
    association = _fetch_single_association(client, institution_id, internship_id)
    if association is None:
        return None

    internship = _fetch_internships_by_ids(client, [internship_id]).get(internship_id)
    if internship is None:
        internship = _fetch_curated_internship_details(client, [internship_id]).get(internship_id)
    if internship is None:
        return None

    students = _fetch_institution_students(client, institution_id)
    students_by_id = {s["id"]: s for s in students}
    applications_all = _fetch_internship_applications(client, list(students_by_id))
    apps = [a for a in applications_all if a["internship_id"] == internship_id]

    names = _fetch_names(client, [a["student_id"] for a in apps])
    department_names = {d["id"]: d["name"] for d in fetch_departments(client, institution_id)}
    company_names = _fetch_company_names(client, [internship["industry_id"]] if internship.get("industry_id") else [])

    application_ids = [a["id"] for a in apps]
    interviews_by_application: dict[str, dict] = {}
    if application_ids:
        interviews_resp = (
            client.table("interviews")
            .select("application_id, scheduled_at, mode, status")
            .in_("application_id", application_ids)
            .execute()
        )
        for iv in interviews_resp.data or []:
            interviews_by_application[iv["application_id"]] = iv

    today = _today()
    participation_counter: Counter = Counter()
    applicants_out = []
    for a in apps:
        student = students_by_id.get(a["student_id"], {})
        name_row = names.get(a["student_id"], {})
        dept_id = student.get("department_id")
        estimate = None
        if a["status"] == "SELECTED":
            estimate = _estimate_participation(internship, today)
            participation_counter[estimate] += 1
        interview = interviews_by_application.get(a["id"])
        applicants_out.append(
            {
                "application_id": a["id"],
                "student_id": a["student_id"],
                "full_name": name_row.get("full_name"),
                "username": name_row.get("username"),
                "department": department_names.get(dept_id, "Unassigned") if dept_id else "Unassigned",
                "cgpa": student.get("cgpa"),
                "status": a["status"],
                "applied_at": a.get("applied_at"),
                "participation_estimate": estimate,
                "interview": (
                    {"scheduled_at": interview["scheduled_at"], "mode": interview["mode"], "status": interview["status"]}
                    if interview
                    else None
                ),
            }
        )

    status_counter = Counter(a["status"] for a in apps)

    return {
        "id": internship_id,
        "title": internship["title"],
        "description": internship.get("description"),
        "company_name": company_names.get(internship.get("industry_id")),
        "industry_id": internship.get("industry_id"),
        "location": internship.get("location"),
        "work_mode": internship.get("work_mode"),
        "duration_months": internship.get("duration_months"),
        "stipend_amount": internship.get("stipend_amount"),
        "stipend_currency": internship.get("stipend_currency"),
        "eligibility_criteria": internship.get("eligibility_criteria"),
        "application_deadline": internship.get("application_deadline"),
        "start_date": internship.get("start_date"),
        "status": internship.get("status"),
        "association_id": association["id"],
        "association_status": association["status"],
        "added_at": association.get("created_at"),
        "applicants_from_institution": len({a["student_id"] for a in apps}),
        "selected_from_institution": len({a["student_id"] for a in apps if a["status"] == "SELECTED"}),
        "participation": {
            "not_started": participation_counter.get(_NOT_STARTED, 0),
            "active": participation_counter.get(_ACTIVE, 0),
            "completed": participation_counter.get(_COMPLETED, 0),
            "unknown": participation_counter.get(_UNKNOWN, 0),
        },
        "status_distribution": [
            {"status": s, "count": int(status_counter.get(s, 0))} for s in APPLICATION_STATUSES
        ],
        "applicants": applicants_out,
        "eligibility_note": _ELIGIBILITY_NOTE,
        "participation_note": _PARTICIPATION_NOTE,
        "privacy_note": _PRIVACY_NOTE,
    }


# ============================================================
# overview / KPIs / analytics
# ============================================================


def _department_breakdown(client: Client, institution_id: str, data: dict, today: date) -> list[dict]:
    base_departments = list_departments(client, institution_id)

    participants_by_dept: dict[str, set[str]] = {}
    completed_by_dept: Counter = Counter()
    for a in data["applications"]:
        student = data["students_by_id"].get(a["student_id"], {})
        dept_id = student.get("department_id")
        if not dept_id:
            continue
        participants_by_dept.setdefault(dept_id, set()).add(a["student_id"])
        if a["status"] == "SELECTED":
            internship = data["internships_by_id"].get(a["internship_id"])
            if internship and _estimate_participation(internship, today) == _COMPLETED:
                completed_by_dept[dept_id] += 1

    out = []
    for d in base_departments:
        participants = len(participants_by_dept.get(d["id"], set()))
        out.append(
            {
                "id": d["id"],
                "name": d["name"],
                "student_count": d["student_count"],
                "participants": participants,
                "participation_rate": _percentage(participants, d["student_count"]),
                "selected_count": d["internship_selected_count"],
                "completed_count": completed_by_dept.get(d["id"], 0),
            }
        )
    return out


def _company_breakdown(data: dict, today: date) -> list[dict]:
    opportunities: Counter = Counter()
    applicants: dict[str, set[str]] = {}
    selected: Counter = Counter()
    completed: Counter = Counter()

    for iid, internship in data["internships_by_id"].items():
        name = data["company_names"].get(internship.get("industry_id"), "Unknown company")
        opportunities[name] += 1
        for a in data["apps_by_internship"].get(iid, []):
            applicants.setdefault(name, set()).add(a["student_id"])
            if a["status"] == "SELECTED":
                selected[name] += 1
                if _estimate_participation(internship, today) == _COMPLETED:
                    completed[name] += 1

    rows = [
        {
            "company_name": name,
            "opportunities": count,
            "applicants": len(applicants.get(name, set())),
            "selected": selected.get(name, 0),
            "completed": completed.get(name, 0),
        }
        for name, count in opportunities.items()
    ]
    rows.sort(key=lambda r: (-r["selected"], -r["applicants"], r["company_name"]))
    return rows


def _stipend_stats(data: dict) -> dict:
    by_currency: dict[str, list[float]] = {}
    for internship in data["internships_by_id"].values():
        amount = internship.get("stipend_amount")
        if amount is None:
            continue
        currency = internship.get("stipend_currency") or "INR"
        by_currency.setdefault(currency, []).append(float(amount))

    if not by_currency:
        return {"available": False, "note": _STIPEND_NOTE_UNAVAILABLE, "by_currency": []}

    rows = [
        {
            "currency": currency,
            "internship_count": len(amounts),
            "average_stipend": round(sum(amounts) / len(amounts), 2),
            "min_stipend": min(amounts),
            "max_stipend": max(amounts),
        }
        for currency, amounts in sorted(by_currency.items())
    ]
    return {"available": True, "note": _STIPEND_NOTE_AVAILABLE, "by_currency": rows}


def compute_internship_overview(client: Client, institution_id: str) -> dict:
    """KPIs/breakdowns over this institution's CURATED (ACTIVE) internship
    list only -- never every platform internship. `active_internships`
    below intentionally does NOT reuse
    institution_service._fetch_active_counts (platform-wide PUBLISHED
    count): here it means "curated AND still PUBLISHED", a different,
    narrower quantity that would be actively misleading if conflated with
    the platform-wide figure the Dashboard shows."""
    data = _gather(client, institution_id)
    today = _today()

    curated_ids = data["internship_ids"]
    active_internships = sum(
        1 for iid in curated_ids if data["internships_by_id"].get(iid, {}).get("status") == "PUBLISHED"
    )
    companies = len(
        {
            data["internships_by_id"][iid]["industry_id"]
            for iid in curated_ids
            if data["internships_by_id"].get(iid, {}).get("industry_id")
        }
    )

    applications = data["applications"]
    applicant_ids = {a["student_id"] for a in applications}
    selected_apps = [a for a in applications if a["status"] == "SELECTED"]
    selected_ids = {a["student_id"] for a in selected_apps}

    active_participant_ids: set[str] = set()
    completed_count = 0
    unknown_count = 0
    for a in selected_apps:
        internship = data["internships_by_id"].get(a["internship_id"])
        estimate = _estimate_participation(internship, today) if internship else _UNKNOWN
        if estimate == _ACTIVE:
            active_participant_ids.add(a["student_id"])
        elif estimate == _COMPLETED:
            completed_count += 1
        elif estimate == _UNKNOWN:
            unknown_count += 1

    kpis = {
        "curated_internships": len(curated_ids),
        "active_internships": active_internships,
        "companies": companies,
        "applicants": len(applicant_ids),
        "selected_students": len(selected_ids),
        "active_participants": len(active_participant_ids),
        "completed_internships": completed_count,
        "participation_unknown": unknown_count,
    }

    mode_counter = Counter(i.get("work_mode") for i in data["internships_by_id"].values() if i.get("work_mode"))
    posting_status_counter = Counter(i.get("status") for i in data["internships_by_id"].values())
    application_status_counter = Counter(a.get("status") for a in applications)

    return {
        "kpis": kpis,
        "departments": _department_breakdown(client, institution_id, data, today),
        "companies": _company_breakdown(data, today),
        "mode_distribution": [{"mode": m, "count": c} for m, c in sorted(mode_counter.items())],
        "status_distribution": [
            {"status": s, "count": int(posting_status_counter.get(s, 0))}
            for s in ("DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED")
        ],
        "application_status_distribution": [
            {"status": s, "count": int(application_status_counter.get(s, 0))} for s in APPLICATION_STATUSES
        ],
        "stipend": _stipend_stats(data),
        "tenancy_note": _TENANCY_NOTE,
        "eligibility_note": _ELIGIBILITY_NOTE,
        "participation_note": _PARTICIPATION_NOTE,
        "curation_note": _CURATION_NOTE,
    }
