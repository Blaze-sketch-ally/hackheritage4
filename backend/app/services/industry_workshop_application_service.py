"""Business logic for the INDUSTRY side of Workshop applications
(`industry_workshop_applications`, database/migrations/056_workshop_applications.sql).

Same shape as app.services.application_service. Ownership is enforced by
RLS ("Industry can view/update applications to their own workshops") plus
an explicit `.eq("industry_id", industry_id)` on every function here
(defence in depth). `industry_id` is derived server-side by the
`set_workshop_application_industry_id` trigger and is never client-
supplied; the `prevent_workshop_application_identity_change` trigger
blocks any change to student/workshop/owner.

Status lifecycle: APPLIED -> ACCEPTED | REJECTED, ACCEPTED -> COMPLETED.
No interview stage -- Workshops never had one. WITHDRAWN is student-owned
(never an Industry-settable target, enforced both here and by the
`prevent_workshop_student_status_override` trigger from the other side).
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
    "id, student_id, industry_id, workshop_id, status, applied_at, created_at, updated_at, "
    "workshop:industry_workshops(id, title, status)"
)


class InvalidStatusTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a workshop application from {current} to {target}.")


def _shape(row: dict) -> dict:
    workshop = row.pop("workshop", None)
    row["workshop"] = (
        {"id": workshop["id"], "title": workshop["title"], "status": workshop["status"]}
        if workshop
        else None
    )
    return row


def _attach_applicant_profiles(client: Client, rows: list[dict]) -> list[dict]:
    """Best-effort attach student_name/institution_name/department/
    graduation_year/skills via public.workshop_applicant_profiles (056) --
    a SECURITY DEFINER function scoped to the exact same ownership
    predicate as this table's own RLS SELECT policy. Never raises: a
    lookup failure just leaves these fields None on every row."""
    if not rows:
        return rows
    profiles: dict[str, dict] = {}
    try:
        response = client.rpc(
            "workshop_applicant_profiles", {"application_ids": [row["id"] for row in rows]}
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
    workshop_id: str | None = None,
) -> list[dict]:
    query = (
        client.table("industry_workshop_applications")
        .select(_SELECT)
        .eq("industry_id", industry_id)
    )
    if status:
        query = query.eq("status", status)
    if workshop_id:
        query = query.eq("workshop_id", workshop_id)
    response = query.order("applied_at", desc=True).execute()
    return _attach_applicant_profiles(client, [_shape(row) for row in (response.data or [])])


def get_application(client: Client, industry_id: str, application_id: str) -> dict | None:
    response = (
        client.table("industry_workshop_applications")
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
        client.table("industry_workshop_applications")
        .update({"status": target_status})
        .eq("id", application_id)
        .eq("industry_id", industry_id)
        .execute()
    )

    # Best-effort: keep an already-provisioned participation workspace's
    # workspace_status in sync (COMPLETED only -- Workshops have no ACTIVE
    # application status). See participation_workspace_service.
    participation_workspace_service.sync_workspace_status(
        client, "WORKSHOP", application_id, target_status
    )

    return get_application(client, industry_id, application_id)
