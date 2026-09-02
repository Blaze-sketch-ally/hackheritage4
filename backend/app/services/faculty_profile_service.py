"""Business logic for the Faculty academic profile (`faculty_profiles`,
database/migrations/036_faculty_profiles.sql).

Same shape as app.services.industry_service: each function takes an
already-built *user-scoped* Supabase client (app.core.security.
build_user_client) and RLS is the real access-control boundary. Nothing
here uses service_role.

`faculty_profiles`' own policies already scope every read/write to
`auth.uid() = id AND public.is_faculty(auth.uid())` -- there is no
broader read policy at all (unlike industry_profiles' public-to-
authenticated display data), since nothing outside a Faculty member's own
session needs to read this yet.

The row is lazy: a FACULTY user has a `profiles` row from signup but no
`faculty_profiles` row until the first save. get_profile returns None in
that window, and upsert_profile performs the first INSERT.
"""

from supabase import Client

_COLUMNS = (
    "id, designation, department, institution_name, phone, bio, "
    "expertise_areas, years_of_experience, created_at, updated_at"
)


def get_profile(client: Client, faculty_id: str) -> dict | None:
    """The caller's own Faculty profile, or None if they haven't saved one
    yet. RLS ("Faculty can view their own faculty profile") already scopes
    this to the caller; the explicit .eq() is defense in depth, matching
    the convention in every other service module."""
    response = (
        client.table("faculty_profiles")
        .select(_COLUMNS)
        .eq("id", faculty_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def upsert_profile(client: Client, faculty_id: str, fields: dict) -> dict:
    """Create (first save) or update the caller's own Faculty profile.

    `faculty_id` is always current_user.id -- never a client-supplied
    value. RLS independently enforces `auth.uid() = id AND
    is_faculty(auth.uid())` for both the INSERT and UPDATE paths the
    upsert can take, so even a spoofed id would be rejected. `updated_at`
    is deliberately not sent: the column default covers INSERT and the
    faculty_profiles_set_updated_at trigger covers UPDATE.
    """
    payload = {"id": faculty_id, **fields}
    client.table("faculty_profiles").upsert(payload, on_conflict="id").execute()

    row = get_profile(client, faculty_id)
    if row is None:
        raise RuntimeError("faculty_profiles row could not be read back after save.")
    return row
