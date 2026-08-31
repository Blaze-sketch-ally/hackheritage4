"""Business logic for the Career Role / Skill Gap API (Phase 1L).

Read-only reference-data queries (career_roles, career_role_skill_
requirements). No write path exists here -- career roles are
service_role-seeded reference data (see database/seed/career_roles.sql),
matching the existing skills/assessments precedent (see
022_career_roles_skill_gap.sql). Every function here takes an
already-constructed, user-scoped Supabase client (app.core.security.
build_user_client) -- RLS ("Authenticated users can view career roles" /
"...career role skill requirements") already permits any authenticated
role to read this data, so no service-role escalation is needed anywhere
in this module.
"""

from decimal import Decimal
from uuid import UUID

from supabase import Client

from app.services.skill_alignment_service import SkillRequirement

_CAREER_ROLE_COLUMNS = "id, title, description, category, created_at, updated_at"


def list_career_roles(client: Client) -> list[dict]:
    response = (
        client.table("career_roles").select(_CAREER_ROLE_COLUMNS).order("title").execute()
    )
    return response.data or []


def get_career_role(client: Client, career_role_id: UUID) -> dict | None:
    """One career role, or None if it doesn't exist. Callers must turn
    None into a 404."""
    response = (
        client.table("career_roles")
        .select(_CAREER_ROLE_COLUMNS)
        .eq("id", str(career_role_id))
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def get_career_role_requirements(client: Client, career_role_id: UUID) -> list[SkillRequirement]:
    """This role's required skills, with each skill's display name
    resolved via the embedded FK (skills.name) -- never re-queried
    separately. A row whose embedded skill comes back None (the skill was
    deactivated after this requirement was seeded -- skills' own SELECT
    policy is `is_active = true`) is skipped rather than surfaced with a
    placeholder name: an inactive skill should not appear in a student's
    skill-gap comparison at all, matching this project's general
    "deactivated catalog content stops appearing in NEW analysis, without
    rewriting anything historical" pattern (see
    docs/architecture/assessment-lifecycle.md's deactivation invariants
    for questions -- this is the same idea applied to skills, and this
    endpoint is current analysis, not a historical record, so silently
    excluding it here is correct, not a completeness bug)."""
    response = (
        client.table("career_role_skill_requirements")
        .select("skill_id, required_level, weight, skill:skills(name)")
        .eq("career_role_id", str(career_role_id))
        .execute()
    )
    requirements: list[SkillRequirement] = []
    for row in response.data or []:
        skill = row.get("skill")
        if not skill:
            continue
        requirements.append(
            SkillRequirement(
                skill_id=row["skill_id"],
                skill_name=skill["name"],
                required_level=Decimal(str(row["required_level"])),
                weight=Decimal(str(row["weight"])),
            )
        )
    return requirements
