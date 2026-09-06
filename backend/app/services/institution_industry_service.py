"""Business logic for the Institution Industry Partners module
(backend/app/api/institution.py, /institution/industry-partners...,
database/migrations/043_institution_industry_partners.sql).

PHASE 8. The canonical company identity is the EXISTING `industry_profiles`
table (017_industry_profiles.sql) -- this module never creates a second
company entity. It coordinates the SAME activity tables every earlier
institution module already reads:

  - "selected" / "placed"                    -> an `applications` row
                                                 with status = 'SELECTED'
                                                 (037_institution_tenancy.sql)
  - the institution's own students            -> institution_placement_service.
                                                 _fetch_institution_students
  - placement-drive rows (extended with        -> institution_placement_service.
    `industry_id`, Phase 8's only edit to        list_drives
    an existing service)
  - internship participation ESTIMATE          -> institution_internship_service.
    (ACTIVE/COMPLETED/NOT_STARTED/UNKNOWN)        _estimate_participation /
                                                    _fetch_published_internships /
                                                    _fetch_visible_internship_details
  - job/internship titles for a non-published   -> institution_visible_opportunity_titles
    posting the institution's students             RPC (039_institution_student_directory.sql)
    already applied to
  - company display fields                      -> industry_profiles (public read,
                                                    017_industry_profiles.sql)
  - collaboration summary                       -> industry_collaborations
                                                    (026_industry_collaborations.sql),
                                                    scoped to recipient_id = caller

`institution_industry_partners` (043) carries no activity data of its
own -- only an institution-private relationship_type/relationship_status/
notes tag on top of a company identity that may or may not have any
recorded activity yet (e.g. a manually-added PROSPECT).

Directory scope: the union of every company (industry_id) that has
EITHER an explicit relationship row OR real institution-scoped activity
(a job/internship application from one of the institution's own
students, a placement drive, or a collaboration addressed to this
institution). A company with neither never appears -- there is no
"browse the entire platform's companies" view here (that already exists
elsewhere, e.g. the internship/job discovery flows); this is a
relationship view, not a company catalog.
"""

from supabase import Client

from app.schemas.institution_industry import RELATIONSHIP_STATUSES, RELATIONSHIP_TYPES
from app.services.institution_internship_service import (
    _COMPLETED,
    _estimate_participation,
    _fetch_published_internships,
    _fetch_visible_internship_details,
    _today,
)
from app.services.institution_placement_service import _fetch_institution_students, list_drives
from app.services.institution_service import _percentage

_TENANCY_NOTE = (
    "Every activity figure below (jobs, internships, placement drives, students selected) covers only "
    "your institution's own linked students and your own placement drives -- another institution's "
    "activity with this same company is never included."
)

_PRIVACY_NOTE = (
    "Only aggregate counts and application status are shown -- no student contact information, no "
    "industry-private interview notes, and no other institution's relationship notes with this company."
)

_PARTNER_COLUMNS = (
    "id, institution_id, industry_id, relationship_type, relationship_status, notes, created_at, updated_at"
)
_COMPANY_COLUMNS = (
    "id, company_name, industry_sector, company_size, website_url, headquarters_location, "
    "company_description, logo_url, linkedin_url"
)
_COMPANY_SEARCH_COLUMNS = "id, company_name, industry_sector, logo_url, website_url, headquarters_location"

_MAX_TITLES = 8


class IndustryProfileNotFoundError(Exception):
    """`industry_id` does not reference a company the institution can see
    (no industry_profiles row)."""


class DuplicateRelationshipError(Exception):
    """This institution already has a relationship row for this company
    -- institution_industry_partners_unique_pair (043)."""


# ============================================================
# fetch helpers
# ============================================================


def _fetch_company_profiles(client: Client, industry_ids: list[str]) -> dict[str, dict]:
    if not industry_ids:
        return {}
    resp = client.table("industry_profiles").select(_COMPANY_COLUMNS).in_("id", industry_ids).execute()
    return {row["id"]: row for row in (resp.data or [])}


def _fetch_all_applications(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("applications")
        .select("id, student_id, status, opportunity_type, internship_id, job_id, industry_id, applied_at")
        .in_("student_id", student_ids)
        .execute()
    )
    return list(resp.data or [])


def _fetch_collaborations(client: Client, institution_id: str) -> list[dict]:
    resp = (
        client.table("industry_collaborations")
        .select("industry_id, title, status, updated_at")
        .eq("recipient_id", institution_id)
        .execute()
    )
    return list(resp.data or [])


def _fetch_explicit_partners(client: Client, institution_id: str) -> dict[str, dict]:
    resp = client.table("institution_industry_partners").select(_PARTNER_COLUMNS).eq("institution_id", institution_id).execute()
    return {row["industry_id"]: row for row in (resp.data or [])}


def _fetch_opportunity_titles(client: Client, internship_ids: list[str], job_ids: list[str]) -> dict[str, str]:
    if not internship_ids and not job_ids:
        return {}
    resp = client.rpc(
        "institution_visible_opportunity_titles", {"internship_ids": internship_ids, "job_ids": job_ids}
    ).execute()
    rows = getattr(resp, "data", None) or []
    return {row["id"]: row["title"] for row in rows if isinstance(row, dict)}


def _gather(client: Client, institution_id: str) -> dict:
    """One pass of the shared reads every Industry Partners endpoint
    needs -- avoids re-deriving the company set / activity data more
    than once per request."""
    students = _fetch_institution_students(client, institution_id)
    student_ids = [s["id"] for s in students]

    applications = _fetch_all_applications(client, student_ids)
    drives = list_drives(client, institution_id)
    collaborations = _fetch_collaborations(client, institution_id)
    explicit = _fetch_explicit_partners(client, institution_id)

    industry_ids: set[str] = set(explicit)
    industry_ids.update(a["industry_id"] for a in applications if a.get("industry_id"))
    industry_ids.update(d["industry_id"] for d in drives if d.get("industry_id"))
    industry_ids.update(c["industry_id"] for c in collaborations if c.get("industry_id"))

    company_profiles = _fetch_company_profiles(client, list(industry_ids))

    internship_ids = list({a["internship_id"] for a in applications if a.get("internship_id")})
    job_ids = list({a["job_id"] for a in applications if a.get("job_id")})
    titles = _fetch_opportunity_titles(client, internship_ids, job_ids)

    published_internships = _fetch_published_internships(client)
    historical_needed = [iid for iid in internship_ids if iid not in published_internships]
    historical_internships = _fetch_visible_internship_details(client, historical_needed)
    internships_by_id = {**historical_internships, **published_internships}

    return {
        "applications": applications,
        "drives": drives,
        "collaborations": collaborations,
        "explicit": explicit,
        "industry_ids": industry_ids,
        "company_profiles": company_profiles,
        "titles": titles,
        "internships_by_id": internships_by_id,
        "today": _today(),
    }


# ============================================================
# per-company activity aggregation
# ============================================================


def _company_activity(industry_id: str, data: dict) -> dict:
    apps = [a for a in data["applications"] if a.get("industry_id") == industry_id]
    job_apps = [a for a in apps if a["opportunity_type"] == "JOB"]
    internship_apps = [a for a in apps if a["opportunity_type"] == "INTERNSHIP"]

    job_ids = {a["job_id"] for a in job_apps if a.get("job_id")}
    job_applicants = {a["student_id"] for a in job_apps}
    job_selected = {a["student_id"] for a in job_apps if a["status"] == "SELECTED"}

    internship_ids = {a["internship_id"] for a in internship_apps if a.get("internship_id")}
    internship_applicants = {a["student_id"] for a in internship_apps}
    internship_selected_apps = [a for a in internship_apps if a["status"] == "SELECTED"]

    completed = 0
    for a in internship_selected_apps:
        internship = data["internships_by_id"].get(a["internship_id"])
        if internship and _estimate_participation(internship, data["today"]) == _COMPLETED:
            completed += 1

    company_drives = [d for d in data["drives"] if d.get("industry_id") == industry_id]
    drive_job_ids = {d["job_id"] for d in company_drives}
    drive_selected_students = {
        a["student_id"] for a in job_apps if a.get("job_id") in drive_job_ids and a["status"] == "SELECTED"
    }

    job_titles = sorted({data["titles"][jid] for jid in job_ids if data["titles"].get(jid)})[:_MAX_TITLES]
    internship_titles = sorted({data["titles"][iid] for iid in internship_ids if data["titles"].get(iid)})[
        :_MAX_TITLES
    ]

    company_collabs = [c for c in data["collaborations"] if c.get("industry_id") == industry_id]
    latest_collab = max(company_collabs, key=lambda c: c.get("updated_at") or "") if company_collabs else None

    timestamps = [a.get("applied_at") for a in apps if a.get("applied_at")]
    for d in company_drives:
        timestamps.extend([d.get("created_at"), d.get("updated_at")])
    timestamps.extend(c.get("updated_at") for c in company_collabs)
    timestamps = [t for t in timestamps if t]
    last_activity_at = max(timestamps) if timestamps else None

    return {
        "job_opportunities": len(job_ids),
        "job_applicants": len(job_applicants),
        "job_selected_students": len(job_selected),
        "job_titles": job_titles,
        "internship_opportunities": len(internship_ids),
        "internship_applicants": len(internship_applicants),
        "internship_selected": len(internship_selected_apps),
        "internship_completed": completed,
        "internship_titles": internship_titles,
        "drives": company_drives,
        "drives_unique_selected": len(drive_selected_students),
        "collaborations_count": len(company_collabs),
        "latest_collab": latest_collab,
        "last_activity_at": last_activity_at,
    }


# ============================================================
# company picker (add-partner form)
# ============================================================

_COMPANY_SEARCH_LIMIT = 20


def search_companies(client: Client, search: str | None = None) -> list[dict]:
    """Real companies (industry_profiles rows) a new relationship may
    reference -- the ONLY source the add-partner form's picker may
    select from, never a free-text name. `industry_profiles` is readable
    to any authenticated user (017_industry_profiles.sql), so this needs
    no new RLS."""
    query = client.table("industry_profiles").select(_COMPANY_SEARCH_COLUMNS)
    if search and search.strip():
        query = query.ilike("company_name", f"%{search.strip()}%")
    resp = query.limit(_COMPANY_SEARCH_LIMIT).execute()
    return list(resp.data or [])


# ============================================================
# directory
# ============================================================


def list_partners(
    client: Client,
    institution_id: str,
    *,
    search: str | None = None,
    relationship_type: str | None = None,
    relationship_status: str | None = None,
) -> dict:
    data = _gather(client, institution_id)

    rows = []
    for industry_id in data["industry_ids"]:
        profile = data["company_profiles"].get(industry_id, {})
        activity = _company_activity(industry_id, data)
        explicit = data["explicit"].get(industry_id)
        rows.append(
            {
                "id": industry_id,
                "company_name": profile.get("company_name"),
                "industry_sector": profile.get("industry_sector"),
                "logo_url": profile.get("logo_url"),
                "website_url": profile.get("website_url"),
                "headquarters_location": profile.get("headquarters_location"),
                "relationship_id": explicit["id"] if explicit else None,
                "relationship_type": explicit["relationship_type"] if explicit else None,
                "relationship_status": explicit["relationship_status"] if explicit else None,
                "has_explicit_relationship": explicit is not None,
                "jobs_opportunities": activity["job_opportunities"],
                "jobs_selected_students": activity["job_selected_students"],
                "internship_opportunities": activity["internship_opportunities"],
                "internship_selected": activity["internship_selected"],
                "placement_drives_count": len(activity["drives"]),
                "students_selected": activity["job_selected_students"],
                "last_activity_at": activity["last_activity_at"],
            }
        )

    if search and search.strip():
        needle = search.strip().lower()
        rows = [r for r in rows if needle in (r["company_name"] or "").lower()]
    if relationship_type:
        rows = [r for r in rows if r["relationship_type"] == relationship_type]
    if relationship_status:
        rows = [r for r in rows if r["relationship_status"] == relationship_status]

    # Most-recently-active companies first; companies with no recorded
    # activity at all (e.g. a manually-tagged PROSPECT) sort last,
    # alphabetically among themselves.
    rows.sort(key=lambda r: (r["company_name"] or "").lower())
    rows.sort(key=lambda r: r["last_activity_at"] or "", reverse=True)
    rows.sort(key=lambda r: r["last_activity_at"] is None)
    return {"partners": rows, "type_options": list(RELATIONSHIP_TYPES), "status_options": list(RELATIONSHIP_STATUSES)}


# ============================================================
# detail
# ============================================================


def get_partner_detail(client: Client, institution_id: str, industry_id: str) -> dict | None:
    data = _gather(client, institution_id)
    if industry_id not in data["industry_ids"]:
        return None

    profile = data["company_profiles"].get(industry_id, {})
    activity = _company_activity(industry_id, data)
    explicit = data["explicit"].get(industry_id)
    latest_collab = activity["latest_collab"]

    return {
        "id": industry_id,
        "company_name": profile.get("company_name"),
        "industry_sector": profile.get("industry_sector"),
        "company_size": profile.get("company_size"),
        "website_url": profile.get("website_url"),
        "headquarters_location": profile.get("headquarters_location"),
        "company_description": profile.get("company_description"),
        "logo_url": profile.get("logo_url"),
        "linkedin_url": profile.get("linkedin_url"),
        "relationship_id": explicit["id"] if explicit else None,
        "relationship_type": explicit["relationship_type"] if explicit else None,
        "relationship_status": explicit["relationship_status"] if explicit else None,
        "notes": explicit["notes"] if explicit else None,
        "has_explicit_relationship": explicit is not None,
        "jobs": {
            "opportunities": activity["job_opportunities"],
            "applicants": activity["job_applicants"],
            "selected_students": activity["job_selected_students"],
            "titles": activity["job_titles"],
        },
        "internships": {
            "opportunities": activity["internship_opportunities"],
            "applicants": activity["internship_applicants"],
            "selected": activity["internship_selected"],
            "completed": activity["internship_completed"],
            "titles": activity["internship_titles"],
        },
        "placement_drives": {
            "count": len(activity["drives"]),
            "unique_students_selected": activity["drives_unique_selected"],
            "drives": [
                {
                    "id": d["id"],
                    "title": d["title"],
                    "status": d["status"],
                    "applied_count": d["applied_count"],
                    "selected_count": d["selected_count"],
                    "selection_rate": _percentage(d["selected_count"], d["applied_count"]),
                }
                for d in activity["drives"]
            ],
        },
        "collaborations": {
            "count": activity["collaborations_count"],
            "latest_status": latest_collab["status"] if latest_collab else None,
            "latest_title": latest_collab["title"] if latest_collab else None,
        },
        "students_selected": activity["job_selected_students"],
        "last_activity_at": activity["last_activity_at"],
        "tenancy_note": _TENANCY_NOTE,
        "privacy_note": _PRIVACY_NOTE,
    }


# ============================================================
# metrics
# ============================================================


def compute_metrics(client: Client, institution_id: str) -> dict:
    data = _gather(client, institution_id)
    applications = data["applications"]

    recruiting = {a["industry_id"] for a in applications if a["opportunity_type"] == "JOB" and a.get("industry_id")}
    internship_companies = {
        a["industry_id"] for a in applications if a["opportunity_type"] == "INTERNSHIP" and a.get("industry_id")
    }
    active_partners = sum(1 for e in data["explicit"].values() if e["relationship_status"] == "ACTIVE")
    students_selected_total = len(
        {a["student_id"] for a in applications if a["opportunity_type"] == "JOB" and a["status"] == "SELECTED"}
    )
    internship_students_total = len(
        {a["student_id"] for a in applications if a["opportunity_type"] == "INTERNSHIP" and a["status"] == "SELECTED"}
    )

    return {
        "metrics": {
            "total_partners": len(data["industry_ids"]),
            "active_partners": active_partners,
            "recruiting_partners": len(recruiting),
            "internship_partners": len(internship_companies),
            "placement_drives_total": len(data["drives"]),
            "students_selected_total": students_selected_total,
            "internship_students_total": internship_students_total,
        },
        "tenancy_note": _TENANCY_NOTE,
    }


# ============================================================
# explicit relationship CRUD
# ============================================================


def _get_relationship(client: Client, institution_id: str, industry_id: str) -> dict | None:
    resp = (
        client.table("institution_industry_partners")
        .select(_PARTNER_COLUMNS)
        .eq("institution_id", institution_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def create_relationship(client: Client, institution_id: str, fields: dict) -> dict:
    industry_id = fields["industry_id"]
    profile = client.table("industry_profiles").select("id").eq("id", industry_id).maybe_single().execute()
    if not (profile and profile.data):
        raise IndustryProfileNotFoundError("This company could not be found.")

    payload = {
        "institution_id": institution_id,
        "industry_id": industry_id,
        "relationship_type": fields.get("relationship_type") or "OTHER",
        "relationship_status": fields.get("relationship_status") or "PROSPECT",
        "notes": fields.get("notes"),
    }
    try:
        client.table("institution_industry_partners").insert(payload).execute()
    except Exception as exc:
        raise DuplicateRelationshipError("You are already tracking a relationship with this company.") from exc

    row = _get_relationship(client, institution_id, industry_id)
    if row is None:
        raise RuntimeError("institution_industry_partners row could not be read back after create.")
    return row


def update_relationship(client: Client, institution_id: str, industry_id: str, fields: dict) -> dict | None:
    existing = _get_relationship(client, institution_id, industry_id)
    if existing is None:
        return None

    if fields:
        (
            client.table("institution_industry_partners")
            .update(fields)
            .eq("institution_id", institution_id)
            .eq("industry_id", industry_id)
            .execute()
        )
    return _get_relationship(client, institution_id, industry_id)
