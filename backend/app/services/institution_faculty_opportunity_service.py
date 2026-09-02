"""Business logic for Institution-owned Faculty opportunities
(`institution_faculty_opportunities`,
037_faculty_opportunities_and_expressions.sql).

Structural twin of app.services.industry_faculty_opportunity_service --
kept as an explicit, separate module rather than a generic/parameterized
one, same reasoning as industry_project_service.py vs
industry_training_service.py vs industry_workshop_service.py already
being separate near-identical files in this codebase: no dynamic
table-name SQL, ever.
"""

from supabase import Client

_SELECT = (
    "id, institution_id, title, description, location, work_mode, capacity, "
    "eligibility_criteria, application_deadline, start_date, status, created_at, updated_at"
)

_EDITABLE_COLUMNS = frozenset(
    {
        "title",
        "description",
        "location",
        "work_mode",
        "capacity",
        "eligibility_criteria",
        "application_deadline",
        "start_date",
    }
)

_PUBLISH_FROM = frozenset({"DRAFT", "CLOSED"})
_CLOSE_FROM = frozenset({"PUBLISHED"})


class InvalidStatusTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a Faculty opportunity from {current} to {target}.")


def list_opportunities(client: Client, institution_id: str, *, status: str | None = None) -> list[dict]:
    query = (
        client.table("institution_faculty_opportunities").select(_SELECT).eq("institution_id", institution_id)
    )
    if status:
        query = query.eq("status", status)
    response = query.order("updated_at", desc=True).execute()
    return list(response.data or [])


def get_opportunity(client: Client, institution_id: str, opportunity_id: str) -> dict | None:
    response = (
        client.table("institution_faculty_opportunities")
        .select(_SELECT)
        .eq("id", opportunity_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return dict(row) if row else None


def create_opportunity(client: Client, institution_id: str, data: dict) -> dict:
    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    payload["institution_id"] = institution_id
    payload["status"] = "DRAFT"

    response = client.table("institution_faculty_opportunities").insert(payload).execute()
    new_id = response.data[0]["id"]

    row = get_opportunity(client, institution_id, new_id)
    if row is None:
        raise RuntimeError("institution_faculty_opportunities row could not be read back after create.")
    return row


def update_opportunity(client: Client, institution_id: str, opportunity_id: str, data: dict) -> dict | None:
    existing = get_opportunity(client, institution_id, opportunity_id)
    if existing is None:
        return None

    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    if payload:
        (
            client.table("institution_faculty_opportunities")
            .update(payload)
            .eq("id", opportunity_id)
            .eq("institution_id", institution_id)
            .execute()
        )
    return get_opportunity(client, institution_id, opportunity_id)


def _transition(
    client: Client, institution_id: str, opportunity_id: str, target: str, allowed_from: frozenset[str]
) -> dict | None:
    existing = get_opportunity(client, institution_id, opportunity_id)
    if existing is None:
        return None
    if existing["status"] not in allowed_from:
        raise InvalidStatusTransitionError(existing["status"], target)
    (
        client.table("institution_faculty_opportunities")
        .update({"status": target})
        .eq("id", opportunity_id)
        .eq("institution_id", institution_id)
        .execute()
    )
    return get_opportunity(client, institution_id, opportunity_id)


def publish_opportunity(client: Client, institution_id: str, opportunity_id: str) -> dict | None:
    return _transition(client, institution_id, opportunity_id, "PUBLISHED", _PUBLISH_FROM)


def close_opportunity(client: Client, institution_id: str, opportunity_id: str) -> dict | None:
    return _transition(client, institution_id, opportunity_id, "CLOSED", _CLOSE_FROM)


# ---- EOI review (owner side) ----

_EOI_SELECT = (
    "id, faculty_id, opportunity_id, status, message, reviewed_by, reviewer_note, created_at, updated_at"
)


def list_eois_for_own_opportunities(client: Client, institution_id: str) -> list[dict]:
    """See industry_faculty_opportunity_service's twin for the
    opportunity-title enrichment rationale."""
    own_opportunities = (
        client.table("institution_faculty_opportunities")
        .select("id, title")
        .eq("institution_id", institution_id)
        .execute()
        .data
        or []
    )
    own_ids = [row["id"] for row in own_opportunities]
    titles = {row["id"]: row["title"] for row in own_opportunities}
    if not own_ids:
        return []
    response = (
        client.table("faculty_institution_opportunity_expressions")
        .select(_EOI_SELECT)
        .in_("opportunity_id", own_ids)
        .order("updated_at", desc=True)
        .execute()
    )
    return [{**row, "opportunity_title": titles.get(row["opportunity_id"])} for row in response.data or []]


class EoiInvalidStatusTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move an expression of interest from {current} to {target}.")


_REVIEW_TRANSITIONS = {
    "UNDER_REVIEW": frozenset({"SUBMITTED"}),
    "ACCEPTED": frozenset({"UNDER_REVIEW"}),
    "REJECTED": frozenset({"UNDER_REVIEW"}),
}


def review_eoi(
    client: Client, institution_id: str, eoi_id: str, new_status: str, reviewer_note: str | None
) -> dict | None:
    existing = (
        client.table("faculty_institution_opportunity_expressions")
        .select(_EOI_SELECT)
        .eq("id", eoi_id)
        .maybe_single()
        .execute()
    )
    row = existing.data if existing is not None else None
    if row is None:
        return None

    allowed_from = _REVIEW_TRANSITIONS.get(new_status)
    if allowed_from is not None and row["status"] not in allowed_from:
        raise EoiInvalidStatusTransitionError(row["status"], new_status)

    payload: dict = {"status": new_status}
    if reviewer_note is not None:
        payload["reviewer_note"] = reviewer_note

    (
        client.table("faculty_institution_opportunity_expressions")
        .update(payload)
        .eq("id", eoi_id)
        .execute()
    )
    response = (
        client.table("faculty_institution_opportunity_expressions")
        .select(_EOI_SELECT)
        .eq("id", eoi_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None
