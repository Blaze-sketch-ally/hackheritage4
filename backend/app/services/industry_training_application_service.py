"""Business logic for the INDUSTRY side of Training applications
(`industry_training_applications`, database/migrations/059_training_applications.sql).

Exact mirror of app.services.industry_workshop_application_service.
Status lifecycle: APPLIED -> ACCEPTED | REJECTED, ACCEPTED -> COMPLETED.
"""

from supabase import Client

from app.services import participation_workspace_service

_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "APPLIED": {"ACCEPTED", "REJECTED"},
    "ACCEPTED": {"COMPLETED", "REJECTED"},
    "REJECTED": set(),
    "WITHDRAWN": set(),
    "COMPLETED": set(),
}

_ALL_STATUSES: tuple[str, ...] = tuple(_STATUS_TRANSITIONS)

_SELECT = (
    "id, student_id, industry_id, training_id, status, applied_at, created_at, updated_at, "
    "training:industry_training(id, title, status)"
)


class InvalidStatusTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a training application from {current} to {target}.")


def _shape(row: dict) -> dict:
    training = row.pop("training", None)
    row["training"] = (
        {"id": training["id"], "title": training["title"], "status": training["status"]}
        if training
        else None
    )
    return row


def _attach_applicant_profiles(client: Client, rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    profiles: dict[str, dict] = {}
    try:
        response = client.rpc(
            "training_applicant_profiles", {"application_ids": [row["id"] for row in rows]}
        ).execute()
        profiles = {r["application_id"]: r for r in (response.data or [])}
    except Exception:  # noqa: BLE001 -- enrichment only, never fatal
        profiles = {}
    for row in rows:
        info = profiles.get(row["id"], {})
        row["student_name"] = info.get("student_name")
        row["institution_name"] = info.get("institution_name")
        row["department"] = info.get("department")
        row["graduation_year"] = info.get("graduation_year")
        row["skills"] = info.get("skills")
    return rows


def list_applications(
    client: Client,
    industry_id: str,
    *,
    status: str | None = None,
    training_id: str | None = None,
) -> list[dict]:
    query = (
        client.table("industry_training_applications")
        .select(_SELECT)
        .eq("industry_id", industry_id)
    )
    if status:
        query = query.eq("status", status)
    if training_id:
        query = query.eq("training_id", training_id)
    response = query.order("applied_at", desc=True).execute()
    return _attach_applicant_profiles(client, [_shape(row) for row in (response.data or [])])


def get_application(client: Client, industry_id: str, application_id: str) -> dict | None:
    response = (
        client.table("industry_training_applications")
        .select(_SELECT)
        .eq("id", application_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return _attach_applicant_profiles(client, [_shape(row)])[0] if row else None


def update_status(
    client: Client, industry_id: str, application_id: str, target_status: str
) -> dict | None:
    existing = get_application(client, industry_id, application_id)
    if existing is None:
        return None

    current = existing["status"]
    if target_status not in _STATUS_TRANSITIONS.get(current, set()):
        raise InvalidStatusTransitionError(current, target_status)

    (
        client.table("industry_training_applications")
        .update({"status": target_status})
        .eq("id", application_id)
        .eq("industry_id", industry_id)
        .execute()
    )

    # Best-effort: keep an already-provisioned participation workspace's
    # workspace_status in sync (COMPLETED only -- Training has no ACTIVE
    # application status). See participation_workspace_service.
    participation_workspace_service.sync_workspace_status(
        client, "TRAINING", application_id, target_status
    )

    return get_application(client, industry_id, application_id)
