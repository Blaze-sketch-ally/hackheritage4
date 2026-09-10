"""Business logic for the Institution Events module
(backend/app/api/institution.py, /institution/events...,
database/migrations/045_institution_events.sql).

PHASE 10. See the migration's own docstring for the full audit finding:
`industry_workshops` (024) remains the ONLY entity a company uses to
post its own event, untouched by this module; `institution_events` (045)
is additive, for sessions the INSTITUTION itself organizes.

The directory (list_events) is the union of the institution's own
`institution_events` rows and platform-wide PUBLISHED
`industry_workshops` -- see EventRow.source / EventRow.platform_wide.
Company name resolution reuses institution_service._fetch_company_names;
department name resolution reuses institution_service.fetch_departments;
department-ownership validation reuses
institution_placement_service._validate_department_ownership -- the same
single source of truth Phase 5's placement drives already established,
not a second copy of that check.

No registration/attendance table exists anywhere in this schema -- see
the schema module's own docstring. Nothing here computes, stores, or
returns a registration/attendance number.
"""

from supabase import Client

from app.services.institution_placement_service import _validate_department_ownership
from app.services.institution_service import _fetch_company_names, fetch_departments

_TENANCY_NOTE = (
    "Events you organize are private to your institution. Published Industry workshops are shown "
    "platform-wide for awareness (marked accordingly) -- they are not organized by, or exclusive to, "
    "your institution, and your institution cannot edit or manage them."
)

_EVENT_COLUMNS = (
    "id, institution_id, industry_id, title, description, event_type, status, mode, venue, start_at, "
    "end_at, registration_deadline, target_department_ids, target_batches, includes_faculty, "
    "instructions, created_at, updated_at"
)

_WORKSHOP_COLUMNS = (
    "id, industry_id, title, description, location, work_mode, application_deadline, start_date, "
    "status, created_at"
)

_EDITABLE_COLUMNS = frozenset(
    {
        "title",
        "description",
        "event_type",
        "industry_id",
        "mode",
        "venue",
        "start_at",
        "end_at",
        "registration_deadline",
        "target_department_ids",
        "target_batches",
        "includes_faculty",
        "instructions",
    }
)

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PUBLISHED", "CANCELLED"},
    "PUBLISHED": {"ONGOING", "CANCELLED"},
    "ONGOING": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


class IndustryProfileNotFoundError(Exception):
    """`industry_id` does not reference a company (no industry_profiles row)."""


class InvalidStatusTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move an event from {current} to {target}.")


# ============================================================
# fetch helpers
# ============================================================


def _fetch_institution_events(client: Client, institution_id: str) -> list[dict]:
    resp = (
        client.table("institution_events")
        .select(_EVENT_COLUMNS)
        .eq("institution_id", institution_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return list(resp.data or [])


def _fetch_published_workshops(client: Client) -> list[dict]:
    resp = client.table("industry_workshops").select(_WORKSHOP_COLUMNS).eq("status", "PUBLISHED").execute()
    return list(resp.data or [])


def _shape_institution_event(row: dict, company_names: dict[str, str], department_names: dict[str, str]) -> dict:
    dept_ids = row.get("target_department_ids") or []
    return {
        "id": row["id"],
        "source": "INSTITUTION",
        "title": row["title"],
        "event_type": row["event_type"],
        "status": row["status"],
        "industry_id": row.get("industry_id"),
        "company_name": company_names.get(row.get("industry_id")) if row.get("industry_id") else None,
        "mode": row.get("mode"),
        "venue": row.get("venue"),
        "start_at": row.get("start_at"),
        "end_at": row.get("end_at"),
        "registration_deadline": row.get("registration_deadline"),
        "target_department_ids": dept_ids,
        "target_department_names": [department_names.get(d, "Unknown department") for d in dept_ids],
        "target_batches": row.get("target_batches") or [],
        "includes_faculty": bool(row.get("includes_faculty")),
        "platform_wide": False,
        "description": row.get("description"),
        "instructions": row.get("instructions"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _shape_workshop(row: dict, company_names: dict[str, str]) -> dict:
    return {
        "id": row["id"],
        "source": "INDUSTRY_WORKSHOP",
        "title": row["title"],
        "event_type": "WORKSHOP",
        "status": "PUBLISHED",
        "industry_id": row.get("industry_id"),
        "company_name": company_names.get(row.get("industry_id")),
        "mode": row.get("work_mode"),
        "venue": row.get("location"),
        "start_at": row.get("start_date"),
        "end_at": None,
        "registration_deadline": row.get("application_deadline"),
        "target_department_ids": [],
        "target_department_names": [],
        "target_batches": [],
        "includes_faculty": False,
        "platform_wide": True,
        "description": row.get("description"),
        "instructions": None,
        "created_at": row.get("created_at"),
        "updated_at": row.get("created_at"),
    }


def _all_rows(client: Client, institution_id: str) -> tuple[list[dict], dict[str, dict]]:
    """Returns (shaped_rows, index-by-(source,id)) for list/detail reuse."""
    events = _fetch_institution_events(client, institution_id)
    workshops = _fetch_published_workshops(client)

    industry_ids = {e["industry_id"] for e in events if e.get("industry_id")}
    industry_ids.update(w["industry_id"] for w in workshops if w.get("industry_id"))
    company_names = _fetch_company_names(client, list(industry_ids))
    department_names = {d["id"]: d["name"] for d in fetch_departments(client, institution_id)}

    rows = [_shape_institution_event(e, company_names, department_names) for e in events]
    rows += [_shape_workshop(w, company_names) for w in workshops]

    index = {(r["source"], r["id"]): r for r in rows}
    return rows, index


# ============================================================
# directory / detail
# ============================================================


def list_events(
    client: Client,
    institution_id: str,
    *,
    search: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
    mode: str | None = None,
    industry_id: str | None = None,
) -> dict:
    rows, _index = _all_rows(client, institution_id)

    if search and search.strip():
        needle = search.strip().lower()
        rows = [
            r for r in rows if needle in r["title"].lower() or needle in (r.get("company_name") or "").lower()
        ]
    if event_type:
        rows = [r for r in rows if r["event_type"] == event_type]
    if status:
        rows = [r for r in rows if r["status"] == status]
    if mode:
        rows = [r for r in rows if r["mode"] == mode]
    if industry_id:
        rows = [r for r in rows if r.get("industry_id") == industry_id]

    # Soonest start first; events with no start date sort last, then by
    # most-recently-updated.
    rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    rows.sort(key=lambda r: (r.get("start_at") is None, r.get("start_at") or ""))
    return {"events": rows}


def get_event_detail(client: Client, institution_id: str, event_id: str) -> dict | None:
    _rows, index = _all_rows(client, institution_id)
    return index.get(("INSTITUTION", event_id)) or index.get(("INDUSTRY_WORKSHOP", event_id))


# ============================================================
# writes (institution-organized events only -- industry_workshops has no
# institution write path at all, by design)
# ============================================================


def _validate_industry_id(client: Client, industry_id: str | None) -> None:
    if not industry_id:
        return
    profile = client.table("industry_profiles").select("id").eq("id", industry_id).maybe_single().execute()
    if not (profile and profile.data):
        raise IndustryProfileNotFoundError("This company could not be found.")


def create_event(client: Client, institution_id: str, fields: dict) -> dict:
    _validate_industry_id(client, fields.get("industry_id"))
    _validate_department_ownership(client, institution_id, fields.get("target_department_ids") or [])

    payload = {k: v for k, v in fields.items() if k in _EDITABLE_COLUMNS}
    payload["institution_id"] = institution_id
    payload["status"] = "DRAFT"
    payload["event_type"] = payload.get("event_type") or "OTHER"

    response = client.table("institution_events").insert(payload).execute()
    new_id = response.data[0]["id"]

    row = get_event_detail(client, institution_id, new_id)
    if row is None:
        raise RuntimeError("institution_events row could not be read back after create.")
    return row


def update_event(client: Client, institution_id: str, event_id: str, fields: dict) -> dict | None:
    existing = get_event_detail(client, institution_id, event_id)
    if existing is None or existing["source"] != "INSTITUTION":
        return None

    if "industry_id" in fields:
        _validate_industry_id(client, fields.get("industry_id"))
    if "target_department_ids" in fields:
        _validate_department_ownership(client, institution_id, fields.get("target_department_ids") or [])

    payload = {k: v for k, v in fields.items() if k in _EDITABLE_COLUMNS}
    if payload:
        (
            client.table("institution_events")
            .update(payload)
            .eq("id", event_id)
            .eq("institution_id", institution_id)
            .execute()
        )
    return get_event_detail(client, institution_id, event_id)


def update_event_status(client: Client, institution_id: str, event_id: str, new_status: str) -> dict | None:
    existing = (
        client.table("institution_events")
        .select("status")
        .eq("id", event_id)
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
        client.table("institution_events")
        .update({"status": new_status})
        .eq("id", event_id)
        .eq("institution_id", institution_id)
        .execute()
    )
    return get_event_detail(client, institution_id, event_id)


# ============================================================
# overview / KPIs
# ============================================================


def compute_event_overview(client: Client, institution_id: str) -> dict:
    rows, _index = _all_rows(client, institution_id)

    upcoming = sum(1 for r in rows if r["status"] == "PUBLISHED")
    ongoing = sum(1 for r in rows if r["status"] == "ONGOING")
    completed = sum(1 for r in rows if r["status"] == "COMPLETED")
    industry_events = sum(1 for r in rows if r.get("industry_id"))
    institution_organized = sum(1 for r in rows if r["source"] == "INSTITUTION")
    platform_workshops = sum(1 for r in rows if r["source"] == "INDUSTRY_WORKSHOP")

    return {
        "kpis": {
            "total_events": len(rows),
            "upcoming_events": upcoming,
            "ongoing_events": ongoing,
            "completed_events": completed,
            "industry_events": industry_events,
            "institution_organized_events": institution_organized,
            "platform_workshops": platform_workshops,
        },
        "tenancy_note": _TENANCY_NOTE,
    }
