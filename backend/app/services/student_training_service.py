"""Business logic for the STUDENT side of Training discovery and
applications (`industry_training` / `industry_training_applications`,
database/migrations/023_industry_training.sql /
059_training_applications.sql).

Exact mirror of app.services.student_workshop_service -- see that
module's docstring for the RLS reasoning this relies on.
"""

from postgrest.exceptions import APIError
from supabase import Client

_SUMMARY_COLUMNS = (
    "id, industry_id, title, description, location, work_mode, duration_months, "
    "capacity, eligibility_criteria, application_deadline, start_date, status, created_at"
)

_APPLICATION_SELECT = (
    "id, student_id, industry_id, training_id, status, applied_at, created_at, updated_at, "
    "training:industry_training(id, title, status)"
)


class DuplicateApplicationError(Exception):
    """The student has already applied to this training -- the DB's unique
    index rejected the insert."""


class TrainingNotPublishedError(Exception):
    """The referenced training exists but is not visible to the student
    (not PUBLISHED)."""


class ApplicationNotWithdrawableError(Exception):
    def __init__(self, current_status: str) -> None:
        self.current_status = current_status
        super().__init__(
            f"A training application at '{current_status}' can no longer be withdrawn."
        )


WITHDRAWABLE_STATUSES = frozenset({"APPLIED"})


def _fetch_industries(client: Client, industry_ids: list[str]) -> dict[str, dict]:
    ids = sorted({i for i in industry_ids if i})
    if not ids:
        return {}
    response = (
        client.table("industry_profiles")
        .select("id, company_name, industry_sector, logo_url")
        .in_("id", ids)
        .execute()
    )
    return {row["id"]: row for row in (response.data or [])}


def _industry_payload(industry_id: str, industries: dict[str, dict]) -> dict:
    profile = industries.get(industry_id) or {}
    return {
        "id": industry_id,
        "company_name": profile.get("company_name"),
        "industry_sector": profile.get("industry_sector"),
        "logo_url": profile.get("logo_url"),
    }


def _applied_training_ids(client: Client, student_id: str) -> set[str]:
    response = (
        client.table("industry_training_applications")
        .select("training_id")
        .eq("student_id", student_id)
        .execute()
    )
    return {r["training_id"] for r in (response.data or []) if r.get("training_id")}


def _shape_summary(row: dict, industries: dict[str, dict], *, applied: bool) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "location": row.get("location"),
        "work_mode": row.get("work_mode"),
        "duration_months": row.get("duration_months"),
        "capacity": row.get("capacity"),
        "eligibility_criteria": row.get("eligibility_criteria"),
        "application_deadline": row.get("application_deadline"),
        "start_date": row.get("start_date"),
        "status": row["status"],
        "created_at": row.get("created_at"),
        "industry": _industry_payload(row["industry_id"], industries),
        "has_applied": applied,
    }


def list_trainings(client: Client, student_id: str, *, search: str | None = None) -> list[dict]:
    query = client.table("industry_training").select(_SUMMARY_COLUMNS).eq("status", "PUBLISHED")
    if search and search.strip():
        query = query.ilike("title", f"%{search.strip()}%")
    rows = query.order("created_at", desc=True).execute().data or []

    applied_ids = _applied_training_ids(client, student_id)
    industries = _fetch_industries(client, [r["industry_id"] for r in rows])
    return [_shape_summary(r, industries, applied=r["id"] in applied_ids) for r in rows]


def get_training(client: Client, student_id: str, training_id: str) -> dict | None:
    response = (
        client.table("industry_training")
        .select(_SUMMARY_COLUMNS)
        .eq("id", training_id)
        .eq("status", "PUBLISHED")
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    applied_ids = _applied_training_ids(client, student_id)
    industries = _fetch_industries(client, [row["industry_id"]])
    return _shape_summary(row, industries, applied=row["id"] in applied_ids)


def _shape_application(row: dict) -> dict:
    training = row.pop("training", None)
    row["training"] = (
        {"id": training["id"], "title": training["title"], "status": training["status"]}
        if training
        else None
    )
    return row


def _get_own_application(client: Client, student_id: str, application_id: str) -> dict | None:
    response = (
        client.table("industry_training_applications")
        .select(_APPLICATION_SELECT)
        .eq("id", application_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return _shape_application(row) if row else None


def apply_to_training(client: Client, student_id: str, training_id: str) -> dict:
    try:
        response = (
            client.table("industry_training_applications")
            .insert({"student_id": student_id, "training_id": training_id})
            .execute()
        )
    except APIError as exc:
        if exc.code == "23505":
            raise DuplicateApplicationError(training_id) from exc
        if exc.code in ("42501", "23503"):
            raise TrainingNotPublishedError(training_id) from exc
        raise

    new_id = response.data[0]["id"]
    row = _get_own_application(client, student_id, new_id)
    if row is None:
        raise RuntimeError("training application row could not be read back after insert.")
    return row


def list_my_applications(client: Client, student_id: str) -> list[dict]:
    rows = (
        client.table("industry_training_applications")
        .select(_APPLICATION_SELECT)
        .eq("student_id", student_id)
        .order("applied_at", desc=True)
        .execute()
        .data
        or []
    )
    return [_shape_application(row) for row in rows]


def withdraw_application(client: Client, student_id: str, application_id: str) -> dict | None:
    existing = _get_own_application(client, student_id, application_id)
    if existing is None:
        return None

    current = existing["status"]
    if current not in WITHDRAWABLE_STATUSES:
        raise ApplicationNotWithdrawableError(current)

    (
        client.table("industry_training_applications")
        .update({"status": "WITHDRAWN"})
        .eq("id", application_id)
        .eq("student_id", student_id)
        .execute()
    )
    return _get_own_application(client, student_id, application_id)
