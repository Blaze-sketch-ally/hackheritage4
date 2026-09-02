"""Read-only Faculty-side access to `faculty_engagements`
(038_faculty_engagements.sql).

Faculty is a participant, never an owner, and has no lifecycle-mutating
action on an engagement in this phase (F4.1's approved scope) -- this
module is deliberately read-only. RLS ("Faculty can view their own
engagements") is the real access-control boundary; the explicit
`.eq("faculty_id", ...)` filter below is defence in depth, matching the
convention in every other service module.

A single table, unlike the EOI/opportunity discovery services -- no
service-layer union is needed here, which is one of the reasons Option A
(one faculty_engagements table with a source_kind discriminator) was
chosen over two separate per-source tables. See the migration's own
header for the full reasoning.
"""

from supabase import Client

_SELECT = (
    "id, source_kind, industry_eoi_id, institution_eoi_id, faculty_id, organization_id, "
    "status, start_date, end_date, notes, created_at, updated_at"
)


def list_own_engagements(client: Client, faculty_id: str) -> list[dict]:
    """The caller's own engagements, newest change first."""
    response = (
        client.table("faculty_engagements")
        .select(_SELECT)
        .eq("faculty_id", faculty_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return list(response.data or [])
