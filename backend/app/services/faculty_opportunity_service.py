"""Read-only Faculty opportunity discovery (Phase F3.2, corrected in the
approved F3.4 architecture review).

CORRECTION FROM THE ORIGINAL F3.2 IMPLEMENTATION: this module originally
read from industry_projects/industry_training/industry_workshops/
industry_mentorship. The architecture design checkpoint established that
those four tables are explicitly Industry->STUDENT postings (documented
as such in their own migration headers) despite being RLS-readable by any
authenticated user -- treating them as "Faculty opportunities" was a
semantic error, not a technical one. This module now reads from the two
tables built specifically for this purpose instead:
industry_faculty_opportunities and institution_faculty_opportunities
(037_faculty_opportunities_and_expressions.sql). The Student-facing four
tables are untouched and no longer read by any Faculty-facing code path.

Every function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) -- RLS's existing "Authenticated
users can view published X" policies on both tables are the real
access-control boundary; this module only ever filters to
status='PUBLISHED' explicitly as defence in depth.
"""

from supabase import Client

_INDUSTRY_SELECT = (
    "id, industry_id, title, description, location, work_mode, capacity, "
    "eligibility_criteria, application_deadline, start_date, created_at, updated_at"
)
_INSTITUTION_SELECT = (
    "id, institution_id, title, description, location, work_mode, capacity, "
    "eligibility_criteria, application_deadline, start_date, created_at, updated_at"
)


def _normalize(source: str, row: dict, owner_column: str) -> dict:
    return {
        "id": row["id"],
        "source": source,
        "owner_id": row[owner_column],
        "owner_name": None,  # filled in by _attach_owner_names for INDUSTRY sources
        "title": row["title"],
        "description": row.get("description"),
        "location": row.get("location"),
        "work_mode": row.get("work_mode"),
        "capacity": row.get("capacity"),
        "eligibility_criteria": row.get("eligibility_criteria"),
        "application_deadline": row.get("application_deadline"),
        "start_date": row.get("start_date"),
        "status": "PUBLISHED",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _attach_industry_owner_names(client: Client, opportunities: list[dict]) -> None:
    """Best-effort company-name enrichment from industry_profiles (which
    has its own "any authenticated user can view" display-data policy),
    same pattern as industry_collaboration_service's counterpart-name
    enrichment. NOT available for INSTITUTION sources: no institution
    identity table with a comparable public-read policy exists anywhere
    in this repository (profiles' own SELECT policy is own-row-only), so
    an Institution opportunity's owner_name is honestly left None rather
    than built inconsistently. Mutates `opportunities` in place."""
    industry_ids = sorted(
        {o["owner_id"] for o in opportunities if o["source"] == "INDUSTRY" and o.get("owner_id")}
    )
    if not industry_ids:
        return
    names: dict[str, str | None] = {}
    try:
        response = (
            client.table("industry_profiles").select("id, company_name").in_("id", industry_ids).execute()
        )
        for row in response.data or []:
            if isinstance(row, dict) and row.get("id"):
                names[row["id"]] = row.get("company_name")
    except Exception:  # noqa: BLE001 -- names are optional enrichment, never fatal
        names = {}
    for opportunity in opportunities:
        if opportunity["source"] == "INDUSTRY":
            opportunity["owner_name"] = names.get(opportunity["owner_id"])


def list_published_opportunities(client: Client, sources: list[str] | None = None) -> list[dict]:
    """Every currently PUBLISHED Faculty opportunity across the requested
    sources (both INDUSTRY and INSTITUTION if `sources` is None/empty),
    newest first."""
    selected = sources or ["INDUSTRY", "INSTITUTION"]
    results: list[dict] = []

    if "INDUSTRY" in selected:
        response = (
            client.table("industry_faculty_opportunities")
            .select(_INDUSTRY_SELECT)
            .eq("status", "PUBLISHED")
            .execute()
        )
        results.extend(_normalize("INDUSTRY", row, "industry_id") for row in response.data or [])

    if "INSTITUTION" in selected:
        response = (
            client.table("institution_faculty_opportunities")
            .select(_INSTITUTION_SELECT)
            .eq("status", "PUBLISHED")
            .execute()
        )
        results.extend(_normalize("INSTITUTION", row, "institution_id") for row in response.data or [])

    _attach_industry_owner_names(client, results)
    results.sort(key=lambda o: o["created_at"] or "", reverse=True)
    return results


def get_published_opportunity(client: Client, source: str, opportunity_id: str) -> dict | None:
    """One published opportunity by source+id, or None. Used to validate
    an express-interest request targets a real, currently-published
    opportunity before creating an EOI against it."""
    if source == "INDUSTRY":
        response = (
            client.table("industry_faculty_opportunities")
            .select(_INDUSTRY_SELECT)
            .eq("id", opportunity_id)
            .eq("status", "PUBLISHED")
            .maybe_single()
            .execute()
        )
        row = response.data if response is not None else None
        return _normalize("INDUSTRY", row, "industry_id") if row else None

    response = (
        client.table("institution_faculty_opportunities")
        .select(_INSTITUTION_SELECT)
        .eq("id", opportunity_id)
        .eq("status", "PUBLISHED")
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return _normalize("INSTITUTION", row, "institution_id") if row else None
