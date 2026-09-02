"""Business logic for the STUDENT side of mentorship discovery.

Every function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) -- RLS is the real access-control
boundary and nothing here uses service_role.

What RLS already guarantees for a STUDENT caller, and this module relies
on rather than re-implements
(database/migrations/025_industry_mentorship.sql):

* `industry_mentorship`: "Authenticated users can view published
  mentorship opportunities" -- a student only ever sees
  `status = 'PUBLISHED'` rows. A DRAFT/CLOSED/ARCHIVED row is invisible
  (reads return no row -> callers 404). The owner-only policy is
  `to authenticated ... using (auth.uid() = industry_id AND
  public.is_industry(...))`, which never matches a student, so a student
  has no write path to this table at all.
* `industry_profiles`: "Authenticated users can view industry profiles"
  -- company display info only, never `profiles`.

This module is read-only: it issues SELECTs and nothing else. There is no
mentorship request/pairing table in the schema, so there is no
request/enrollment logic here to write.
"""

from supabase import Client

# Columns a student is allowed to see. `industry_id` is selected only so
# organiser display info can be joined in a second query; it is mapped
# into `organizer.id` and never surfaced as a bare owner id field.
_SELECT = (
    "id, industry_id, title, description, location, work_mode, duration_months, "
    "capacity, eligibility_criteria, application_deadline, start_date, status, created_at"
)

_WORK_MODES = ("ONSITE", "REMOTE", "HYBRID")


def _fetch_organizers(client: Client, industry_ids: list[str]) -> dict[str, dict]:
    """Batch-load company display info for a set of opportunity owners.
    Missing ids (an Industry account with no company profile row yet)
    simply don't appear in the result."""
    ids = sorted({i for i in industry_ids if i})
    if not ids:
        return {}
    response = (
        client.table("industry_profiles")
        .select("id, company_name, industry_sector, logo_url")
        .in_("id", ids)
        .execute()
    )
    return {row["id"]: row for row in (response.data or [])}


def _organizer_payload(industry_id: str, organizers: dict[str, dict]) -> dict:
    profile = organizers.get(industry_id) or {}
    return {
        "id": industry_id,
        "company_name": profile.get("company_name"),
        "industry_sector": profile.get("industry_sector"),
        "logo_url": profile.get("logo_url"),
    }


def _summary(row: dict, organizers: dict[str, dict]) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "location": row["location"],
        "work_mode": row["work_mode"],
        "duration_months": row["duration_months"],
        "capacity": row["capacity"],
        "start_date": row.get("start_date"),
        "application_deadline": row.get("application_deadline"),
        "organizer": _organizer_payload(row["industry_id"], organizers),
        "created_at": row.get("created_at"),
    }


def _detail(row: dict, organizers: dict[str, dict]) -> dict:
    base = _summary(row, organizers)
    base.update(
        {
            "eligibility_criteria": row.get("eligibility_criteria"),
            "requests_available": False,
        }
    )
    return base


def list_mentorships(
    client: Client,
    *,
    work_mode: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """Published industry mentorship opportunities, normalized, soonest
    start first (rows with no start date last). RLS already restricts
    every row to `status = 'PUBLISHED'`; the explicit
    `.eq("status", "PUBLISHED")` is defence in depth."""
    query = client.table("industry_mentorship").select(_SELECT).eq("status", "PUBLISHED")
    if work_mode in _WORK_MODES:
        query = query.eq("work_mode", work_mode)
    if search and search.strip():
        query = query.ilike("title", f"%{search.strip()}%")
    # Newest-created first from the DB; a stable sort below re-orders by
    # start date while keeping that as the tie-break within one date.
    rows = query.order("created_at", desc=True).execute().data or []

    organizers = _fetch_organizers(client, [r["industry_id"] for r in rows])
    shaped = [_summary(row, organizers) for row in rows]

    shaped.sort(key=lambda m: (m.get("start_date") is None, m.get("start_date") or ""))
    return shaped


def get_mentorship(client: Client, mentorship_id: str) -> dict | None:
    """One published mentorship opportunity, normalized, or None (callers
    turn None into a 404 -- a nonexistent opportunity and a
    DRAFT/CLOSED/ARCHIVED one are indistinguishable to a student, even one
    who knows the UUID)."""
    response = (
        client.table("industry_mentorship")
        .select(_SELECT)
        .eq("id", mentorship_id)
        .eq("status", "PUBLISHED")
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    organizers = _fetch_organizers(client, [row["industry_id"]])
    return _detail(row, organizers)
