"""Business logic for the Institution Industry Connections module
(backend/app/api/institution.py, /institution/industry-connections...,
database/migrations/044_institution_industry_connections.sql).

PHASE 9. The canonical company identity is still `industry_profiles`
(017_industry_profiles.sql) -- resolved by industry_id via
`institution_industry_service._fetch_company_profiles`, the SAME company
lookup Phase 8's Industry Partners module uses. This module never stores
or duplicates company display fields (name/logo/sector) on its own rows.

A connection is a genuinely new piece of institution-private data (a
named contact person, their designation, and an institution-scoped
contact type) -- see the module's own migration docstring for why this
is not a duplicate of `industry_profiles.contact_phone` (a single
company-level number, Industry-owned).
"""

from supabase import Client

from app.services.institution_industry_service import _fetch_company_profiles

_CONNECTION_COLUMNS = (
    "id, institution_id, industry_id, contact_name, designation, contact_type, email, phone, notes, "
    "is_active, created_at, updated_at"
)


class IndustryProfileNotFoundError(Exception):
    """`industry_id` does not reference a company (no industry_profiles row)."""


def _shape(row: dict, company_profiles: dict[str, dict]) -> dict:
    profile = company_profiles.get(row["industry_id"], {})
    return {
        "id": row["id"],
        "industry_id": row["industry_id"],
        "company_name": profile.get("company_name"),
        "industry_sector": profile.get("industry_sector"),
        "logo_url": profile.get("logo_url"),
        "contact_name": row["contact_name"],
        "designation": row.get("designation"),
        "contact_type": row["contact_type"],
        "email": row.get("email"),
        "phone": row.get("phone"),
        "notes": row.get("notes"),
        "is_active": row["is_active"],
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def list_connections(
    client: Client,
    institution_id: str,
    *,
    search: str | None = None,
    contact_type: str | None = None,
    is_active: bool | None = None,
    industry_id: str | None = None,
) -> list[dict]:
    """Every connection the caller owns (RLS: institution_id = auth.uid()),
    newest change first. `search` matches company name OR contact name --
    applied after resolving company names, since that lookup isn't a
    column on this table. `industry_id` scopes to one company -- used by
    Company Detail's "Connections" section (Phase 8 integration)."""
    query = (
        client.table("institution_industry_connections")
        .select(_CONNECTION_COLUMNS)
        .eq("institution_id", institution_id)
    )
    if contact_type:
        query = query.eq("contact_type", contact_type)
    if is_active is not None:
        query = query.eq("is_active", is_active)
    if industry_id:
        query = query.eq("industry_id", industry_id)
    response = query.order("updated_at", desc=True).execute()
    rows = list(response.data or [])

    company_profiles = _fetch_company_profiles(client, list({r["industry_id"] for r in rows}))
    shaped = [_shape(r, company_profiles) for r in rows]

    if search and search.strip():
        needle = search.strip().lower()
        shaped = [
            r
            for r in shaped
            if needle in (r["company_name"] or "").lower() or needle in r["contact_name"].lower()
        ]
    return shaped


def get_connection(client: Client, institution_id: str, connection_id: str) -> dict | None:
    """One of the caller's own connections, or None -- another
    institution's connection is indistinguishable from one that doesn't
    exist."""
    response = (
        client.table("institution_industry_connections")
        .select(_CONNECTION_COLUMNS)
        .eq("id", connection_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response and response.data else None
    if not row:
        return None
    company_profiles = _fetch_company_profiles(client, [row["industry_id"]])
    return _shape(row, company_profiles)


def create_connection(client: Client, institution_id: str, fields: dict) -> dict:
    industry_id = fields["industry_id"]
    profile = client.table("industry_profiles").select("id").eq("id", industry_id).maybe_single().execute()
    if not (profile and profile.data):
        raise IndustryProfileNotFoundError("This company could not be found.")

    payload = {
        "institution_id": institution_id,
        "industry_id": industry_id,
        "contact_name": fields["contact_name"],
        "designation": fields.get("designation"),
        "contact_type": fields.get("contact_type") or "OTHER",
        "email": fields.get("email"),
        "phone": fields.get("phone"),
        "notes": fields.get("notes"),
        "is_active": True,
    }
    response = client.table("institution_industry_connections").insert(payload).execute()
    new_id = response.data[0]["id"]

    row = get_connection(client, institution_id, new_id)
    if row is None:
        raise RuntimeError("institution_industry_connections row could not be read back after create.")
    return row


def update_connection(client: Client, institution_id: str, connection_id: str, fields: dict) -> dict | None:
    """Partial update -- `contact_name` is NOT NULL at the database level,
    so an explicit clear-to-blank (normalised to None by the schema's
    validator) is dropped here rather than sent as a NULL update, matching
    institution_department_service.update_department's own convention."""
    existing = get_connection(client, institution_id, connection_id)
    if existing is None:
        return None

    payload = {k: v for k, v in fields.items() if not (k == "contact_name" and v is None)}
    if payload:
        (
            client.table("institution_industry_connections")
            .update(payload)
            .eq("id", connection_id)
            .eq("institution_id", institution_id)
            .execute()
        )
    return get_connection(client, institution_id, connection_id)
