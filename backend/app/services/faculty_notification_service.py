"""Business logic for the FACULTY side of in-app notifications
(`faculty_notifications`, database/migrations/066_faculty_notifications.sql).

Mirrors app.services.student_notification_service exactly -- every
function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) and the authenticated caller's own
id (always `current_user.id`, never a client value). RLS is the real
access-control boundary and nothing here uses service_role:

* SELECT is scoped by "Faculty can view their own notifications"
  (`auth.uid() = faculty_id AND public.is_faculty(...)`); every function
  here ALSO filters explicitly by `faculty_id` (defence in depth,
  matching the other faculty_* service modules).
* UPDATE is scoped by "Faculty can mark their own notifications read",
  and a BEFORE UPDATE trigger rejects any change to a column other than
  `read_at` -- so the only write this module can perform is toggling the
  read timestamp.
* There is NO insert policy, so this module cannot create notifications
  and deliberately exposes no function that tries to -- see
  app.services.faculty_notification_producer for the system-context
  producer side.
"""

from datetime import UTC, datetime

from supabase import Client

# Columns a Faculty member is allowed to see. No internal bookkeeping
# (dedupe_key) is selected beyond these.
_SELECT = (
    "id, type, title, body, related_entity_type, related_entity_id, read_at, created_at"
)

# Same bounded-list stance as student_notification_service.
DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _shape(row: dict) -> dict:
    return {
        "id": row["id"],
        "type": row["type"],
        "title": row["title"],
        "body": row["body"],
        "related_entity_type": row.get("related_entity_type"),
        "related_entity_id": row.get("related_entity_id"),
        "read_at": row.get("read_at"),
        "is_read": row.get("read_at") is not None,
        "created_at": row.get("created_at"),
    }


def _clamp_limit(limit: int | None) -> int:
    if not limit or limit < 1:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)


def unread_count(client: Client, faculty_id: str) -> int:
    """How many of the caller's notifications are still unread. A single
    count(*) query -- never fetches rows merely to count them."""
    response = (
        client.table("faculty_notifications")
        .select("id", count="exact")
        .eq("faculty_id", faculty_id)
        .is_("read_at", "null")
        .execute()
    )
    return response.count or 0


def list_notifications(
    client: Client,
    faculty_id: str,
    *,
    unread_only: bool = False,
    limit: int | None = None,
) -> list[dict]:
    """The caller's own notifications, newest first, bounded by a safe
    server-side limit. RLS already restricts every row to the caller; the
    explicit `.eq("faculty_id", ...)` is defence in depth."""
    query = (
        client.table("faculty_notifications")
        .select(_SELECT)
        .eq("faculty_id", faculty_id)
    )
    if unread_only:
        query = query.is_("read_at", "null")
    rows = (
        query.order("created_at", desc=True).limit(_clamp_limit(limit)).execute().data or []
    )
    return [_shape(row) for row in rows]


def get_notification(client: Client, faculty_id: str, notification_id: str) -> dict | None:
    """One of the caller's own notifications, or None -- callers turn None
    into a 404, so another Faculty member's notification is
    indistinguishable from one that doesn't exist."""
    response = (
        client.table("faculty_notifications")
        .select(_SELECT)
        .eq("id", notification_id)
        .eq("faculty_id", faculty_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return _shape(row) if row else None


def set_read(
    client: Client,
    faculty_id: str,
    notification_id: str,
    *,
    read: bool,
) -> dict | None:
    """Toggle the caller's own notification read state. Returns the
    updated row, or None if it doesn't exist / isn't the caller's (-> 404).
    Idempotent: marking an already-read notification read (or an unread
    one unread) is a no-op that still returns the row.

    The ONLY column written is `read_at`; the DB trigger rejects anything
    else, and this function never builds a payload with anything else."""
    existing = get_notification(client, faculty_id, notification_id)
    if existing is None:
        return None

    target = _now_iso() if read else None
    if existing["is_read"] == read:
        return existing

    (
        client.table("faculty_notifications")
        .update({"read_at": target})
        .eq("id", notification_id)
        .eq("faculty_id", faculty_id)
        .execute()
    )
    return get_notification(client, faculty_id, notification_id)


def mark_all_read(client: Client, faculty_id: str) -> int:
    """Mark every unread notification of the caller's read. Returns how
    many rows changed."""
    response = (
        client.table("faculty_notifications")
        .update({"read_at": _now_iso()})
        .eq("faculty_id", faculty_id)
        .is_("read_at", "null")
        .execute()
    )
    return len(response.data or [])
