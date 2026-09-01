"""Business logic for Industry collaborations (`industry_collaborations`,
database/migrations/026_industry_collaborations.sql).

Same shape as the other service modules: every function takes an
already-built *user-scoped* Supabase client (app.core.security.
build_user_client) and RLS is the real access-control boundary. Nothing
here uses service_role.

Unlike the posting modules (industry_project/industry_training/
industry_workshop/industry_mentorship), this is a bilateral relationship:
an INDUSTRY account (industry_id) and a FACULTY/INSTITUTION account
(recipient_id) each see and act on their own side of the same row.
Reads/writes are split into separate "own" (industry) and "incoming"
(recipient) functions -- each filters explicitly by the relevant identity
column (defence in depth on top of RLS, matching the convention in every
other service module), rather than one function trying to branch on
"which party is this".

Lifecycle: DRAFT -> SENT -> ACCEPTED/REJECTED -> ACTIVE -> COMPLETED/CANCELLED.
- Industry drives: send (DRAFT->SENT), activate (ACCEPTED->ACTIVE),
  complete (ACTIVE->COMPLETED), cancel (DRAFT/SENT/ACCEPTED/ACTIVE->CANCELLED).
- Recipient drives: accept (SENT->ACCEPTED), reject (SENT->REJECTED).
`create` always yields DRAFT; `status` is never editable through
`update_collaboration`, and edits are only allowed while still DRAFT --
the database trigger `restrict_recipient_collaboration_updates` is the
authoritative backstop for the recipient side, but the service layer
enforces the DRAFT-only rule for industry edits too.
"""

from supabase import Client

_SELECT = "id, industry_id, recipient_id, recipient_type, title, description, status, created_at, updated_at"

_EDITABLE_COLUMNS = frozenset({"title", "description"})

_SEND_FROM = frozenset({"DRAFT"})
_ACTIVATE_FROM = frozenset({"ACCEPTED"})
_COMPLETE_FROM = frozenset({"ACTIVE"})
_CANCEL_FROM = frozenset({"DRAFT", "SENT", "ACCEPTED", "ACTIVE"})
_ACCEPT_FROM = frozenset({"SENT"})
_REJECT_FROM = frozenset({"SENT"})


class InvalidRecipientError(Exception):
    """The given recipient could not be used -- either no such profile
    exists, or it isn't a FACULTY/INSTITUTION account. The database
    trigger (set_collaboration_recipient_type) is the authoritative
    enforcement; this is raised when that insert fails."""


class NotDraftError(Exception):
    """The collaboration can no longer be edited as a draft -- it has
    already been sent."""

    def __init__(self, current: str) -> None:
        self.current = current
        super().__init__(f"Cannot edit a collaboration once it is {current}.")


class InvalidStatusTransitionError(Exception):
    """The requested lifecycle transition isn't allowed from the current status."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a collaboration from {current} to {target}.")


# ---- recipient resolution ----


def resolve_recipient(client: Client, identifier: str) -> dict | None:
    """Looks up a FACULTY/INSTITUTION account by username via the
    resolve_collaboration_recipient() Postgres function -- returns only
    id/role/full_name, or None if no eligible account matches."""
    response = client.rpc("resolve_collaboration_recipient", {"identifier": identifier}).execute()
    rows = response.data or []
    return dict(rows[0]) if rows else None


# ---- counterparty display names ----


def _attach_counterparty_names(client: Client, rows: list[dict]) -> list[dict]:
    """Fill in each row's `industry_name` / `recipient_name` (the display
    identity of the OTHER party) via the collaboration_counterparty_names()
    Postgres function -- the read-side counterpart of
    resolve_collaboration_recipient(). That function re-derives the same
    visibility 026's RLS grants, so it can only ever name a collaboration
    the caller could already GET; the query stays user-scoped.

    Best-effort: if the function is absent (migration 029 not yet applied)
    or errors, the names are left as None and the caller's list/detail
    response is unchanged -- the UI falls back to the recipient-type
    label. `rows` is mutated in place and returned for convenience.
    """
    ids = [r["id"] for r in rows if isinstance(r, dict) and r.get("id")]
    if not ids:
        return rows

    names: dict[str, dict] = {}
    try:
        response = client.rpc(
            "collaboration_counterparty_names", {"collaboration_ids": ids}
        ).execute()
        data = getattr(response, "data", None)
        if isinstance(data, list):
            names = {
                row["collaboration_id"]: row
                for row in data
                if isinstance(row, dict) and row.get("collaboration_id")
            }
    except Exception:  # noqa: BLE001 -- names are optional enrichment, never fatal
        names = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        entry = names.get(row.get("id"), {})
        row["industry_name"] = entry.get("industry_name")
        row["recipient_name"] = entry.get("recipient_name")
    return rows


# ---- industry-side reads ----


def list_collaborations(
    client: Client,
    industry_id: str,
    *,
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """The caller's own initiated collaborations (every status by
    default), newest change first. Optional exact `status` filter and
    case-insensitive title `search`."""
    query = client.table("industry_collaborations").select(_SELECT).eq("industry_id", industry_id)
    if status:
        query = query.eq("status", status)
    if search and search.strip():
        query = query.ilike("title", f"%{search.strip()}%")
    response = query.order("updated_at", desc=True).execute()
    return _attach_counterparty_names(client, list(response.data or []))


def get_own_collaboration(client: Client, industry_id: str, collaboration_id: str) -> dict | None:
    """One of the caller's own initiated collaborations, or None --
    callers turn None into a 404, so another Industry account's
    collaboration is indistinguishable from one that doesn't exist."""
    response = (
        client.table("industry_collaborations")
        .select(_SELECT)
        .eq("id", collaboration_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    return _attach_counterparty_names(client, [dict(row)])[0]


# ---- recipient-side reads ----


def list_incoming_collaborations(
    client: Client,
    recipient_id: str,
    *,
    status: str | None = None,
) -> list[dict]:
    """Collaborations addressed to the caller (DRAFT rows are never
    visible to a recipient -- excluded explicitly here on top of RLS),
    newest change first. Optional exact `status` filter."""
    query = (
        client.table("industry_collaborations")
        .select(_SELECT)
        .eq("recipient_id", recipient_id)
        .neq("status", "DRAFT")
    )
    if status:
        query = query.eq("status", status)
    response = query.order("updated_at", desc=True).execute()
    return _attach_counterparty_names(client, list(response.data or []))


def get_incoming_collaboration(client: Client, recipient_id: str, collaboration_id: str) -> dict | None:
    """One of the collaborations addressed to the caller, or None."""
    response = (
        client.table("industry_collaborations")
        .select(_SELECT)
        .eq("id", collaboration_id)
        .eq("recipient_id", recipient_id)
        .neq("status", "DRAFT")
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    return _attach_counterparty_names(client, [dict(row)])[0]


# ---- industry-side writes ----


def create_collaboration(client: Client, industry_id: str, data: dict) -> dict:
    """Always creates a DRAFT owned by `industry_id` (the authenticated
    caller). `recipient_type` is never sent -- the database trigger
    derives it from `recipient_id`'s real role and rejects the insert
    entirely if that role isn't FACULTY/INSTITUTION, which this function
    surfaces as InvalidRecipientError."""
    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS | {"recipient_id"}}
    payload["industry_id"] = industry_id
    payload["status"] = "DRAFT"

    try:
        response = client.table("industry_collaborations").insert(payload).execute()
    except Exception as exc:
        raise InvalidRecipientError(
            "The selected recipient does not exist or is not a Faculty/Institution account."
        ) from exc
    new_id = response.data[0]["id"]

    row = get_own_collaboration(client, industry_id, new_id)
    if row is None:
        raise RuntimeError("collaboration row could not be read back after create.")
    return row


def update_collaboration(
    client: Client,
    industry_id: str,
    collaboration_id: str,
    data: dict,
) -> dict | None:
    """Edit the caller's own collaboration -- only while it is still
    DRAFT. `recipient_id`/`recipient_type`/`status` are never touched
    here."""
    existing = get_own_collaboration(client, industry_id, collaboration_id)
    if existing is None:
        return None
    if existing["status"] != "DRAFT":
        raise NotDraftError(existing["status"])

    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    if payload:
        (
            client.table("industry_collaborations")
            .update(payload)
            .eq("id", collaboration_id)
            .eq("industry_id", industry_id)
            .execute()
        )

    return get_own_collaboration(client, industry_id, collaboration_id)


def _industry_transition(
    client: Client,
    industry_id: str,
    collaboration_id: str,
    target: str,
    allowed_from: frozenset[str],
) -> dict | None:
    existing = get_own_collaboration(client, industry_id, collaboration_id)
    if existing is None:
        return None
    if existing["status"] not in allowed_from:
        raise InvalidStatusTransitionError(existing["status"], target)
    (
        client.table("industry_collaborations")
        .update({"status": target})
        .eq("id", collaboration_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_own_collaboration(client, industry_id, collaboration_id)


def send_collaboration(client: Client, industry_id: str, collaboration_id: str) -> dict | None:
    """DRAFT -> SENT."""
    return _industry_transition(client, industry_id, collaboration_id, "SENT", _SEND_FROM)


def activate_collaboration(client: Client, industry_id: str, collaboration_id: str) -> dict | None:
    """ACCEPTED -> ACTIVE. Explicit, industry-only -- the recipient
    accepting does not automatically start the collaboration."""
    return _industry_transition(client, industry_id, collaboration_id, "ACTIVE", _ACTIVATE_FROM)


def complete_collaboration(client: Client, industry_id: str, collaboration_id: str) -> dict | None:
    """ACTIVE -> COMPLETED."""
    return _industry_transition(client, industry_id, collaboration_id, "COMPLETED", _COMPLETE_FROM)


def cancel_collaboration(client: Client, industry_id: str, collaboration_id: str) -> dict | None:
    """DRAFT/SENT/ACCEPTED/ACTIVE -> CANCELLED. Industry-only -- the
    recipient cannot cancel, only accept or reject."""
    return _industry_transition(client, industry_id, collaboration_id, "CANCELLED", _CANCEL_FROM)


# ---- recipient-side writes ----


def _recipient_transition(
    client: Client,
    recipient_id: str,
    collaboration_id: str,
    target: str,
    allowed_from: frozenset[str],
) -> dict | None:
    existing = get_incoming_collaboration(client, recipient_id, collaboration_id)
    if existing is None:
        return None
    if existing["status"] not in allowed_from:
        raise InvalidStatusTransitionError(existing["status"], target)
    (
        client.table("industry_collaborations")
        .update({"status": target})
        .eq("id", collaboration_id)
        .eq("recipient_id", recipient_id)
        .execute()
    )
    return get_incoming_collaboration(client, recipient_id, collaboration_id)


def accept_collaboration(client: Client, recipient_id: str, collaboration_id: str) -> dict | None:
    """SENT -> ACCEPTED."""
    return _recipient_transition(client, recipient_id, collaboration_id, "ACCEPTED", _ACCEPT_FROM)


def reject_collaboration(client: Client, recipient_id: str, collaboration_id: str) -> dict | None:
    """SENT -> REJECTED."""
    return _recipient_transition(client, recipient_id, collaboration_id, "REJECTED", _REJECT_FROM)
