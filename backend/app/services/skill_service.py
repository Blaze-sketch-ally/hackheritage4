"""Business logic for the shared skill catalog (`skills` /
`skill_categories`, database/migrations/003_skills.sql).

Read-only. Takes a user-scoped Supabase client -- RLS ("Authenticated
users can view active skills") already limits this to active rows for any
signed-in caller. No service_role, no writes.
"""

from supabase import Client

_SELECT = "id, name, description, category:skill_categories(name)"


def list_active_skills(client: Client, search: str | None = None) -> list[dict]:
    """Every active catalog skill, each flattened to
    {id, name, category_name, description}. Optional case-insensitive
    substring match on the skill name."""
    query = client.table("skills").select(_SELECT).eq("is_active", True)
    if search and search.strip():
        query = query.ilike("name", f"%{search.strip()}%")
    response = query.order("name").execute()

    items: list[dict] = []
    for row in response.data or []:
        category = row.get("category") or {}
        items.append(
            {
                "id": row["id"],
                "name": row["name"],
                "category_name": category.get("name"),
                "description": row.get("description"),
            }
        )
    return items
