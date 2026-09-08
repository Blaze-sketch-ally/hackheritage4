"""Business logic for the student <-> institution linking workflow
(`institution_link_requests`, database/migrations/
038_institution_link_requests.sql).

Same shape as industry_collaboration_service.py: every function takes an
already-built *user-scoped* Supabase client (build_user_client) and RLS
is the real access-control boundary -- nothing here uses service_role.
The actual `student_profiles.institution_id` write on approval/unlink
happens INSIDE THE DATABASE (apply_link_request_status_change, migration
038), triggered by the plain RLS-scoped UPDATE this module issues -- this
module never writes student_profiles directly.
"""

from supabase import Client

_SELECT = "id, student_id, institution_id, status, created_at, updated_at"

_LIVE_STATUSES = ("PENDING", "APPROVED")


class InvalidInstitutionError(Exception):
    """No INSTITUTION account matched the given identifier, or the
    referenced institution_id isn't a real INSTITUTION account."""


class AlreadyLinkedError(Exception):
    """The student already has a live (PENDING or APPROVED) request --
    matches institution_link_requests_one_live_per_student_idx. Surfaced
    before the insert is even attempted, not just caught as a DB error,
    so the message can name the current status."""

    def __init__(self, current_status: str) -> None:
        self.current_status = current_status
        super().__init__(f"You already have a {current_status.lower()} institution link.")


class InvalidStatusTransitionError(Exception):
    """The requested lifecycle transition isn't allowed from the current status."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a link request from {current} to {target}.")


# ---- resolution ----


def resolve_institution(client: Client, identifier: str) -> dict | None:
    """Looks up an INSTITUTION account by username via
    resolve_institution_by_username() -- returns only id/full_name, or
    None if no eligible account matches."""
    response = client.rpc("resolve_institution_by_username", {"identifier": identifier}).execute()
    rows = response.data or []
    return dict(rows[0]) if rows else None


# ---- display-name enrichment ----


def _attach_student_names(client: Client, rows: list[dict]) -> list[dict]:
    """Institution-side reads: fill in `student_name`/`student_username`
    via institution_link_request_student_names(), the read-side
    counterpart of resolve_institution_by_username(). Best-effort -- a
    failure leaves names as None rather than failing the whole list."""
    ids = [r["id"] for r in rows if isinstance(r, dict) and r.get("id")]
    if not ids:
        return rows

    names: dict[str, dict] = {}
    try:
        response = client.rpc(
            "institution_link_request_student_names", {"request_ids": ids}
        ).execute()
        data = getattr(response, "data", None)
        if isinstance(data, list):
            names = {
                row["request_id"]: row for row in data if isinstance(row, dict) and row.get("request_id")
            }
    except Exception:  # noqa: BLE001 -- names are optional enrichment, never fatal
        names = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        entry = names.get(row.get("id"), {})
        row["student_name"] = entry.get("student_name")
        row["student_username"] = entry.get("student_username")
    return rows


def _attach_institution_names(client: Client, rows: list[dict]) -> list[dict]:
    """Student-side reads: fill in `institution_name`. Unlike the student
    name lookup above, this needs no SECURITY DEFINER helper --
    institution_profiles has a broad "Authenticated users can view
    institution profiles" policy (037_institution_tenancy.sql), so a
    plain scoped read already works for any authenticated caller."""
    ids = list({r["institution_id"] for r in rows if isinstance(r, dict) and r.get("institution_id")})
    if not ids:
        return rows

    response = (
        client.table("institution_profiles").select("id, institution_name").in_("id", ids).execute()
    )
    names = {row["id"]: row.get("institution_name") for row in (response.data or [])}

    for row in rows:
        if not isinstance(row, dict):
            continue
        row["institution_name"] = names.get(row.get("institution_id"))
    return rows


# ---- student-side ----


def list_my_requests(client: Client, student_id: str) -> list[dict]:
    """Every link request the caller has ever made, newest first."""
    response = (
        client.table("institution_link_requests")
        .select(_SELECT)
        .eq("student_id", student_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return _attach_institution_names(client, list(response.data or []))


def get_own_request(client: Client, student_id: str, request_id: str) -> dict | None:
    response = (
        client.table("institution_link_requests")
        .select(_SELECT)
        .eq("id", request_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    return _attach_institution_names(client, [dict(row)])[0]


def create_request(client: Client, student_id: str, institution_id: str) -> dict:
    """Submits a PENDING join request. Checked explicitly against the live
    requests the caller already has (defense in depth on top of
    institution_link_requests_one_live_per_student_idx, matching the
    "check before write" convention used elsewhere in this project, e.g.
    update_collaboration's NotDraftError check) so a duplicate attempt
    gets a clear AlreadyLinkedError instead of a raw constraint-violation
    500. `institution_id` must already be a resolved, real INSTITUTION
    account id (see resolve_institution) -- the database trigger
    (validate_link_request_institution) is the authoritative backstop and
    raises InvalidInstitutionError if it isn't."""
    existing_live = (
        client.table("institution_link_requests")
        .select("status")
        .eq("student_id", student_id)
        .in_("status", _LIVE_STATUSES)
        .execute()
    )
    if existing_live.data:
        raise AlreadyLinkedError(existing_live.data[0]["status"])

    payload = {"student_id": student_id, "institution_id": institution_id, "status": "PENDING"}
    try:
        response = client.table("institution_link_requests").insert(payload).execute()
    except Exception as exc:
        raise InvalidInstitutionError(
            "The selected institution does not exist or is not an Institution account."
        ) from exc
    new_id = response.data[0]["id"]

    row = get_own_request(client, student_id, new_id)
    if row is None:
        raise RuntimeError("institution_link_requests row could not be read back after create.")
    return row


def cancel_own_request(client: Client, student_id: str, request_id: str) -> dict | None:
    """PENDING -> CANCELLED. restrict_link_request_transitions (migration
    038) is the authoritative backstop; this pre-check gives a clean
    InvalidStatusTransitionError instead of a raw 42501 from the DB."""
    existing = get_own_request(client, student_id, request_id)
    if existing is None:
        return None
    if existing["status"] != "PENDING":
        raise InvalidStatusTransitionError(existing["status"], "CANCELLED")

    (
        client.table("institution_link_requests")
        .update({"status": "CANCELLED"})
        .eq("id", request_id)
        .eq("student_id", student_id)
        .execute()
    )
    return get_own_request(client, student_id, request_id)


# ---- institution-side ----


def list_incoming(client: Client, institution_id: str, *, status: str | None = None) -> list[dict]:
    """Requests addressed to the caller, newest change first. Optional
    exact `status` filter (e.g. "PENDING" for the action-needed list,
    "APPROVED" for the linked-students list)."""
    query = client.table("institution_link_requests").select(_SELECT).eq("institution_id", institution_id)
    if status:
        query = query.eq("status", status)
    response = query.order("updated_at", desc=True).execute()
    return _attach_student_names(client, list(response.data or []))


def get_incoming_request(client: Client, institution_id: str, request_id: str) -> dict | None:
    response = (
        client.table("institution_link_requests")
        .select(_SELECT)
        .eq("id", request_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    return _attach_student_names(client, [dict(row)])[0]


def _institution_transition(
    client: Client,
    institution_id: str,
    request_id: str,
    target: str,
    allowed_from: frozenset[str],
) -> dict | None:
    existing = get_incoming_request(client, institution_id, request_id)
    if existing is None:
        return None
    if existing["status"] not in allowed_from:
        raise InvalidStatusTransitionError(existing["status"], target)

    (
        client.table("institution_link_requests")
        .update({"status": target})
        .eq("id", request_id)
        .eq("institution_id", institution_id)
        .execute()
    )
    return get_incoming_request(client, institution_id, request_id)


def approve_request(client: Client, institution_id: str, request_id: str) -> dict | None:
    """PENDING -> APPROVED. The AFTER UPDATE trigger
    (apply_link_request_status_change) is what actually sets
    student_profiles.institution_id -- this function only performs the
    RLS-scoped status update that triggers it."""
    return _institution_transition(client, institution_id, request_id, "APPROVED", frozenset({"PENDING"}))


def reject_request(client: Client, institution_id: str, request_id: str) -> dict | None:
    return _institution_transition(client, institution_id, request_id, "REJECTED", frozenset({"PENDING"}))


def unlink_request(client: Client, institution_id: str, request_id: str) -> dict | None:
    """APPROVED -> REMOVED. The AFTER UPDATE trigger clears
    student_profiles.institution_id back to NULL for this student."""
    return _institution_transition(client, institution_id, request_id, "REMOVED", frozenset({"APPROVED"}))
