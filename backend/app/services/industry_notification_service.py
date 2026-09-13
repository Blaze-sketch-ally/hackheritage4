"""Business logic for the INDUSTRY side of in-app notifications
(`industry_notifications`, database/migrations/055_industry_notifications.sql).

Exact mirror of app.services.student_notification_service, scoped to
`industry_id` instead of `student_id`. Every function takes an
already-built *user-scoped* Supabase client (app.core.security.
build_user_client) and the authenticated caller's own id (always
`current_user.id`). RLS is the real access-control boundary -- nothing
here uses service_role. There is NO insert policy, so this module cannot
create notifications; that is app.services.notification_producer's job
(system-context, service_role).
"""

from datetime import UTC, datetime

from supabase import Client

_SELECT = (
    "id, type, title, body, related_entity_type, related_entity_id, read_at, created_at"
)

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


def unread_count(client: Client, industry_id: str) -> int:
    response = (
        client.table("industry_notifications")
        .select("id", count="exact")
        .eq("industry_id", industry_id)
        .is_("read_at", "null")
        .execute()
    )
    return response.count or 0


def list_notifications(
    client: Client,
    industry_id: str,
    *,
    unread_only: bool = False,
    limit: int | None = None,
) -> list[dict]:
    query = (
        client.table("industry_notifications")
        .select(_SELECT)
        .eq("industry_id", industry_id)
    )
    if unread_only:
        query = query.is_("read_at", "null")
    rows = (
        query.order("created_at", desc=True).limit(_clamp_limit(limit)).execute().data or []
    )
    return [_shape(row) for row in rows]


def get_notification(client: Client, industry_id: str, notification_id: str) -> dict | None:
    response = (
        client.table("industry_notifications")
        .select(_SELECT)
        .eq("id", notification_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return _shape(row) if row else None


def set_read(
    client: Client,
    industry_id: str,
    notification_id: str,
    *,
    read: bool,
) -> dict | None:
    existing = get_notification(client, industry_id, notification_id)
    if existing is None:
        return None

    target = _now_iso() if read else None
    if existing["is_read"] == read:
        return existing

    (
        client.table("industry_notifications")
        .update({"read_at": target})
        .eq("id", notification_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_notification(client, industry_id, notification_id)


def mark_all_read(client: Client, industry_id: str) -> int:
    response = (
        client.table("industry_notifications")
        .update({"read_at": _now_iso()})
        .eq("industry_id", industry_id)
        .is_("read_at", "null")
        .execute()
    )
    return len(response.data or [])
