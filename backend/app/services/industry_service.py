"""Business logic for the Industry company profile (`industry_profiles`).

Same shape as app.services.skill_gap_service / assessment_service: each
function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) and RLS is the real access-control
boundary. Nothing here uses service_role.

`industry_profiles`' own policies (017_industry_profiles.sql) already
scope every read/write to `auth.uid() = id AND public.is_industry(auth.uid())`.
The broad "Authenticated users can view industry profiles" SELECT policy
is for other roles reading a company's public info -- not used by this
module, which only ever touches the caller's own row.

The row is lazy: an INDUSTRY user has a `profiles` row from signup but no
`industry_profiles` row until the first save. get_profile returns None in
that window, and upsert_profile performs the first INSERT.
"""

from supabase import Client

_COLUMNS = (
    "id, company_name, industry_sector, company_size, website_url, "
    "company_description, headquarters_location, founded_year, contact_phone, "
    "linkedin_url, logo_url, created_at, updated_at"
)


def get_profile(client: Client, industry_id: str) -> dict | None:
    """The caller's own company profile, or None if they haven't saved one
    yet. RLS ("Industry can view their own industry profile") already
    scopes this to the caller; the explicit .eq() is defense in depth,
    matching the convention in the other service modules."""
    response = (
        client.table("industry_profiles")
        .select(_COLUMNS)
        .eq("id", industry_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def upsert_profile(client: Client, industry_id: str, fields: dict) -> dict:
    """Create (first save) or update the caller's own company profile.

    `industry_id` is always current_user.id -- never a client-supplied
    value. RLS independently enforces `auth.uid() = id AND
    is_industry(auth.uid())` for both the INSERT and UPDATE paths the
    upsert can take, so even a spoofed id would be rejected. `updated_at`
    is deliberately not sent: the column default covers INSERT and the
    industry_profiles_set_updated_at trigger covers UPDATE.
    """
    payload = {"id": industry_id, **fields}
    client.table("industry_profiles").upsert(payload, on_conflict="id").execute()

    row = get_profile(client, industry_id)
    if row is None:
        raise RuntimeError("industry_profiles row could not be read back after save.")
    return row
