"""Business logic for the shared skill catalog (`skills` /
`skill_categories`, database/migrations/003_skills.sql).

Read-only. RLS ("Authenticated users can view active skills") already
permits any authenticated role to read the active catalog, so every
function here takes an already-built user-scoped Supabase client
(app.core.security.build_user_client) -- never service_role.

This is the one shared catalog: the student skill selector reads the
same table directly via Supabase (frontend/lib/student/skills.ts), while
Industry/Institution's internship & job skill-requirements pickers go
through this service via GET /api/v1/skills
(frontend/lib/industry/skills.ts) -- matching the rest of their surface,
which is entirely FastAPI-backed. Do not add a second catalog read
elsewhere; extend this one.
"""

from supabase import Client

_SELECT = "id, name, description, category:skill_categories(name)"


def list_active_skills(client: Client, search: str | None = None) -> list[dict]:
    """The active skill catalog, optionally filtered by a case-insensitive
    substring match on name. Never returns inactive/deprecated skills --
    the same is_active = true scope RLS itself enforces, kept here too as
    defence in depth (matches every other catalog read in this project,
    e.g. app.services.career_role_service.list_career_roles)."""
    query = client.table("skills").select(_SELECT).eq("is_active", True)
    if search:
        query = query.ilike("name", f"%{search}%")
    response = query.order("name").execute()
    return [_shape(row) for row in (response.data or [])]


def _shape(row: dict) -> dict:
    """Flatten the nested `category` embed into a plain `category_name`."""
    category = row.pop("category", None) or {}
    row["category_name"] = category.get("name")
    return row
