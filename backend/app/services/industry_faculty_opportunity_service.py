"""Business logic for Industry-owned Faculty opportunities
(`industry_faculty_opportunities`,
037_faculty_opportunities_and_expressions.sql).

Same shape as app.services.industry_project_service: every function
takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) and RLS is the real access-control
boundary. Nothing here uses service_role. Every function also filters
explicitly by `industry_id` (defence in depth) and forces `industry_id` /
`status` server-side.

Lifecycle: DRAFT -> PUBLISHED -> CLOSED. `create` always yields DRAFT;
`status` is never editable through `update_opportunity`.
"""

from supabase import Client

_SELECT = (
    "id, industry_id, title, description, location, work_mode, capacity, "
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
    """The requested lifecycle transition isn't allowed from the current status."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a Faculty opportunity from {current} to {target}.")


def list_opportunities(client: Client, industry_id: str, *, status: str | None = None) -> list[dict]:
    """The caller's own Faculty opportunities (every status by default), newest change first."""
    query = client.table("industry_faculty_opportunities").select(_SELECT).eq("industry_id", industry_id)
    if status:
        query = query.eq("status", status)
    response = query.order("updated_at", desc=True).execute()
    return list(response.data or [])


def get_opportunity(client: Client, industry_id: str, opportunity_id: str) -> dict | None:
    """One of the caller's own Faculty opportunities, or None -- callers
    turn None into a 404, so another Industry account's opportunity is
    indistinguishable from one that doesn't exist."""
    response = (
        client.table("industry_faculty_opportunities")
        .select(_SELECT)
        .eq("id", opportunity_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return dict(row) if row else None


def create_opportunity(client: Client, industry_id: str, data: dict) -> dict:
    """Always creates a DRAFT owned by `industry_id`."""
    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    payload["industry_id"] = industry_id
    payload["status"] = "DRAFT"

    response = client.table("industry_faculty_opportunities").insert(payload).execute()
    new_id = response.data[0]["id"]

    row = get_opportunity(client, industry_id, new_id)
    if row is None:
        raise RuntimeError("industry_faculty_opportunities row could not be read back after create.")
    return row


def update_opportunity(client: Client, industry_id: str, opportunity_id: str, data: dict) -> dict | None:
    """Edit the caller's own Faculty opportunity. `status` is never touched here."""
    existing = get_opportunity(client, industry_id, opportunity_id)
    if existing is None:
        return None

    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    if payload:
        (
            client.table("industry_faculty_opportunities")
            .update(payload)
            .eq("id", opportunity_id)
            .eq("industry_id", industry_id)
            .execute()
        )
    return get_opportunity(client, industry_id, opportunity_id)


def _transition(client: Client, industry_id: str, opportunity_id: str, target: str, allowed_from: frozenset[str]) -> dict | None:
    existing = get_opportunity(client, industry_id, opportunity_id)
    if existing is None:
        return None
    if existing["status"] not in allowed_from:
        raise InvalidStatusTransitionError(existing["status"], target)
    (
        client.table("industry_faculty_opportunities")
        .update({"status": target})
        .eq("id", opportunity_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_opportunity(client, industry_id, opportunity_id)


def publish_opportunity(client: Client, industry_id: str, opportunity_id: str) -> dict | None:
    """DRAFT/CLOSED -> PUBLISHED."""
    return _transition(client, industry_id, opportunity_id, "PUBLISHED", _PUBLISH_FROM)


def close_opportunity(client: Client, industry_id: str, opportunity_id: str) -> dict | None:
    """PUBLISHED -> CLOSED."""
    return _transition(client, industry_id, opportunity_id, "CLOSED", _CLOSE_FROM)


# ---- EOI review (owner side) ----

_EOI_SELECT = (
    "id, faculty_id, opportunity_id, status, message, reviewed_by, reviewer_note, created_at, updated_at"
)


def list_eois_for_own_opportunities(client: Client, industry_id: str) -> list[dict]:
    """Every EOI submitted against one of the caller's own Faculty
    opportunities, with each row's opportunity title attached for display
    (a plain Python-side join over already-RLS-scoped reads, not a new
    database relationship). RLS ("Industry can view EOIs for their own
    faculty opportunities") already scopes the EOI read; the explicit
    filter below is defence in depth, matching every other service
    module's convention."""
    own_opportunities = (
        client.table("industry_faculty_opportunities").select("id, title").eq("industry_id", industry_id).execute().data
        or []
    )
    own_ids = [row["id"] for row in own_opportunities]
    titles = {row["id"]: row["title"] for row in own_opportunities}
    if not own_ids:
        return []
    response = (
        client.table("faculty_industry_opportunity_expressions")
        .select(_EOI_SELECT)
        .in_("opportunity_id", own_ids)
        .order("updated_at", desc=True)
        .execute()
    )
    return [{**row, "opportunity_title": titles.get(row["opportunity_id"])} for row in response.data or []]


class EoiInvalidStatusTransitionError(Exception):
    """Mirrors InvalidStatusTransitionError for the EOI review action."""

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
    client: Client, industry_id: str, eoi_id: str, new_status: str, reviewer_note: str | None
) -> dict | None:
    """Transition one EOI submitted against one of the caller's own
    opportunities. Returns None if the EOI doesn't exist or doesn't belong
    to one of the caller's own opportunities (RLS-invisible either way,
    same "None means not found or not yours" convention as get_opportunity).
    The actual transition legality and `reviewed_by` attribution are
    enforced by the database trigger (guard_faculty_industry_eoi_update)
    regardless of what reaches this function -- the check here exists so
    the route layer can return a clean 409 instead of a raw DB error.
    """
    existing = (
        client.table("faculty_industry_opportunity_expressions")
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
        client.table("faculty_industry_opportunity_expressions")
        .update(payload)
        .eq("id", eoi_id)
        .execute()
    )
    response = (
        client.table("faculty_industry_opportunity_expressions")
        .select(_EOI_SELECT)
        .eq("id", eoi_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None
