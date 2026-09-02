"""Business logic for the Faculty-initiated side of expressions of
interest ("EOI") -- `faculty_industry_opportunity_expressions` /
`faculty_institution_opportunity_expressions`
(037_faculty_opportunities_and_expressions.sql).

Every function takes an already-built *user-scoped* Supabase client.
RLS + the guard_faculty_*_eoi_update() triggers are the real
access-control/lifecycle boundary; this module never uses service_role
and never trusts a client-supplied faculty_id.

Deliberately separate from app.services.faculty_opportunity_service
(discovery, read-only, no ownership) and from
app.services.industry_faculty_opportunity_service /
institution_faculty_opportunity_service (the owner/reviewer side) -- this
module is exclusively the Faculty submitter's own actions.
"""

from supabase import Client

_EOI_SELECT = (
    "id, faculty_id, opportunity_id, status, message, reviewed_by, reviewer_note, created_at, updated_at"
)

_TABLES = {
    "INDUSTRY": "faculty_industry_opportunity_expressions",
    "INSTITUTION": "faculty_institution_opportunity_expressions",
}


class DuplicateExpressionError(Exception):
    """Raised when the caller already has an EOI against this opportunity
    -- surfaces as postgrest APIError 23505 (unique_violation) against
    the table's own (faculty_id, opportunity_id) unique constraint."""


def _table(source: str) -> str:
    return _TABLES[source]


def express_interest(client: Client, source: str, faculty_id: str, opportunity_id: str, message: str | None) -> dict:
    """Creates the EOI as DRAFT, then immediately transitions it to
    SUBMITTED -- a real two-step lifecycle transition happens (both the
    INSERT's own WITH CHECK and the UPDATE's guard trigger fire), this
    just spares the Faculty caller a separate "save draft, come back
    later" round trip for V1. `faculty_id` is always the authenticated
    caller -- never accepted from the request body."""
    table = _table(source)
    insert_payload = {
        "faculty_id": faculty_id,
        "opportunity_id": opportunity_id,
        "status": "DRAFT",
        "message": message,
    }
    response = client.table(table).insert(insert_payload).execute()
    new_id = response.data[0]["id"]

    client.table(table).update({"status": "SUBMITTED"}).eq("id", new_id).execute()

    row = (
        client.table(table).select(_EOI_SELECT).eq("id", new_id).maybe_single().execute()
    )
    data = row.data if row is not None else None
    if data is None:
        raise RuntimeError(f"{table} row could not be read back after create.")
    return {**data, "source": source}


def list_own_expressions(client: Client, faculty_id: str) -> list[dict]:
    """The caller's own EOIs across BOTH sources, newest change first.
    Union is done here in Python -- same pattern as
    faculty_opportunity_service's own cross-table union for discovery --
    not via a shared registry table."""
    results: list[dict] = []
    for source, table in _TABLES.items():
        response = (
            client.table(table)
            .select(_EOI_SELECT)
            .eq("faculty_id", faculty_id)
            .order("updated_at", desc=True)
            .execute()
        )
        results.extend({**row, "source": source} for row in response.data or [])
    results.sort(key=lambda e: e["updated_at"] or "", reverse=True)
    return results


def withdraw_expression(client: Client, source: str, faculty_id: str, eoi_id: str) -> dict | None:
    """SUBMITTED/UNDER_REVIEW -> WITHDRAWN. Returns None if the EOI
    doesn't exist or isn't the caller's own (RLS-invisible either way).
    The actual transition legality is enforced by the database trigger
    regardless of what reaches this function."""
    table = _table(source)
    existing = (
        client.table(table)
        .select(_EOI_SELECT)
        .eq("id", eoi_id)
        .eq("faculty_id", faculty_id)
        .maybe_single()
        .execute()
    )
    if existing is None or existing.data is None:
        return None

    client.table(table).update({"status": "WITHDRAWN"}).eq("id", eoi_id).execute()

    row = client.table(table).select(_EOI_SELECT).eq("id", eoi_id).maybe_single().execute()
    data = row.data if row is not None else None
    return {**data, "source": source} if data else None
