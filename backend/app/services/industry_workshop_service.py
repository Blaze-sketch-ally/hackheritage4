"""Business logic for Industry workshops (`industry_workshops`,
database/migrations/024_industry_workshops.sql).

Same shape as the other service modules: every function takes an
already-built *user-scoped* Supabase client (app.core.security.
build_user_client) and RLS is the real access-control boundary. Nothing
here uses service_role.

`industry_workshops`'s policies (024_industry_workshops.sql) scope every
write to `auth.uid() = industry_id AND public.is_industry(auth.uid())`.
On top of that, every function here also filters explicitly by
`industry_id` (defence in depth, matching the convention in the other
service modules) and forces `industry_id` / `status` server-side -- a
client value for either is never trusted.

Lifecycle: DRAFT -> PUBLISHED -> CLOSED -> ARCHIVED (with ARCHIVED also
reachable directly from DRAFT / PUBLISHED). `create` always yields DRAFT;
`status` is never editable through `update_workshop`.
"""

from supabase import Client

_SELECT = (
    "id, industry_id, title, description, location, work_mode, duration_days, "
    "capacity, eligibility_criteria, application_deadline, start_date, status, "
    "created_at, updated_at"
)

_EDITABLE_COLUMNS = frozenset(
    {
        "title",
        "description",
        "location",
        "work_mode",
        "duration_days",
        "capacity",
        "eligibility_criteria",
        "application_deadline",
        "start_date",
    }
)

# Fields that must be present before a workshop can be published.
# title/description are NOT NULL columns so they are always present already.
_PUBLISH_REQUIRED = ("location", "work_mode", "duration_days", "application_deadline")

_CLOSE_FROM = frozenset({"PUBLISHED"})
_ARCHIVE_FROM = frozenset({"DRAFT", "PUBLISHED", "CLOSED"})


class PublishValidationError(Exception):
    """The workshop is missing fields required to publish."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("Missing before publish: " + ", ".join(missing))


class InvalidStatusTransitionError(Exception):
    """The requested lifecycle transition isn't allowed from the current status."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a workshop from {current} to {target}.")


# ---- reads ----


def list_workshops(
    client: Client,
    industry_id: str,
    *,
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """The caller's own workshops (every status by default), newest change
    first. Optional exact `status` filter and case-insensitive title
    `search`."""
    query = client.table("industry_workshops").select(_SELECT).eq("industry_id", industry_id)
    if status:
        query = query.eq("status", status)
    if search and search.strip():
        query = query.ilike("title", f"%{search.strip()}%")
    response = query.order("updated_at", desc=True).execute()
    return list(response.data or [])


def get_workshop(client: Client, industry_id: str, workshop_id: str) -> dict | None:
    """One of the caller's own workshops, or None -- callers turn None
    into a 404, so another Industry account's workshop is
    indistinguishable from one that doesn't exist."""
    response = (
        client.table("industry_workshops")
        .select(_SELECT)
        .eq("id", workshop_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return dict(row) if row else None


# ---- writes ----


def create_workshop(client: Client, industry_id: str, data: dict) -> dict:
    """Always creates a DRAFT owned by `industry_id` (the authenticated
    caller). Any `status` / `industry_id` / `id` in `data` is overridden."""
    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    payload["industry_id"] = industry_id
    payload["status"] = "DRAFT"

    response = client.table("industry_workshops").insert(payload).execute()
    new_id = response.data[0]["id"]

    row = get_workshop(client, industry_id, new_id)
    if row is None:
        raise RuntimeError("workshop row could not be read back after create.")
    return row


def update_workshop(
    client: Client,
    industry_id: str,
    workshop_id: str,
    data: dict,
) -> dict | None:
    """Edit the caller's own workshop. `status` is never touched here."""
    existing = get_workshop(client, industry_id, workshop_id)
    if existing is None:
        return None

    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    if payload:
        (
            client.table("industry_workshops")
            .update(payload)
            .eq("id", workshop_id)
            .eq("industry_id", industry_id)
            .execute()
        )

    return get_workshop(client, industry_id, workshop_id)


def publish_workshop(client: Client, industry_id: str, workshop_id: str) -> dict | None:
    """DRAFT/CLOSED -> PUBLISHED, only if the fields needed to publish are
    present."""
    existing = get_workshop(client, industry_id, workshop_id)
    if existing is None:
        return None

    missing = [field for field in _PUBLISH_REQUIRED if not existing.get(field)]
    if missing:
        raise PublishValidationError(missing)

    if existing["status"] not in {"DRAFT", "CLOSED"}:
        raise InvalidStatusTransitionError(existing["status"], "PUBLISHED")

    (
        client.table("industry_workshops")
        .update({"status": "PUBLISHED"})
        .eq("id", workshop_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_workshop(client, industry_id, workshop_id)


def _transition(
    client: Client,
    industry_id: str,
    workshop_id: str,
    target: str,
    allowed_from: frozenset[str],
) -> dict | None:
    existing = get_workshop(client, industry_id, workshop_id)
    if existing is None:
        return None
    if existing["status"] not in allowed_from:
        raise InvalidStatusTransitionError(existing["status"], target)
    (
        client.table("industry_workshops")
        .update({"status": target})
        .eq("id", workshop_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_workshop(client, industry_id, workshop_id)


def close_workshop(client: Client, industry_id: str, workshop_id: str) -> dict | None:
    """PUBLISHED -> CLOSED (stop accepting new registration interest)."""
    return _transition(client, industry_id, workshop_id, "CLOSED", _CLOSE_FROM)


def archive_workshop(client: Client, industry_id: str, workshop_id: str) -> dict | None:
    """DRAFT/PUBLISHED/CLOSED -> ARCHIVED. This is the closest thing to a
    delete -- rows are never physically removed."""
    return _transition(client, industry_id, workshop_id, "ARCHIVED", _ARCHIVE_FROM)
