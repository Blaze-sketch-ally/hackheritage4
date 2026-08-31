"""Business logic for the Opportunity API (Phase 1M).

Every function here takes an already-constructed, user-scoped Supabase
client (app.core.security.build_user_client) -- RLS
(024_opportunities_and_applications.sql) is the real enforcement; this
module's own checks are defense in depth, matching every other service
module in this project. No service-role usage anywhere in this file --
unlike Phase 1K's create_attempt()/score_attempt(), nothing here needs a
privileged, single-transaction write that RLS structurally forbids an
ordinary caller from making.
"""

from decimal import Decimal
from uuid import UUID

from supabase import Client

from app.services.skill_alignment_service import SkillRequirement

_OPPORTUNITY_COLUMNS = (
    "id, industry_id, title, description, opportunity_type, location, "
    "status, published_at, created_at, updated_at"
)


def list_opportunities(
    client: Client, opportunity_type: str | None = None, mine_only: bool = False
) -> list[dict]:
    """PUBLISHED opportunities visible to any authenticated caller, or
    (mine_only=True) the caller's own opportunities at any status --
    RLS's own two SELECT policies already draw this exact boundary; the
    explicit .eq("status", "PUBLISHED") below for the non-mine case is
    defense in depth, matching the pattern used throughout this project
    (e.g. assessment_service.list_active_assessments)."""
    query = client.table("opportunities").select(_OPPORTUNITY_COLUMNS)
    if not mine_only:
        query = query.eq("status", "PUBLISHED")
    if opportunity_type:
        query = query.eq("opportunity_type", opportunity_type)
    response = query.order("created_at", desc=True).execute()
    return response.data or []


def get_opportunity(client: Client, opportunity_id: UUID) -> dict | None:
    """One opportunity, or None if it doesn't exist / isn't visible to
    the caller (RLS already scopes this to PUBLISHED-for-anyone or
    own-at-any-status). Callers must turn None into a 404 -- never reveal
    whether a DRAFT/CLOSED opportunity belonging to someone else exists."""
    response = (
        client.table("opportunities")
        .select(_OPPORTUNITY_COLUMNS)
        .eq("id", str(opportunity_id))
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def create_opportunity(client: Client, industry_id: str, payload: dict) -> dict:
    """Always inserts a fresh DRAFT -- payload must never include status/
    published_at (OpportunityCreateRequest has no such fields at all, so
    there is nothing for a route to even forward); industry_id is always
    the authenticated caller's own id, never client-supplied. RLS's own
    INSERT policy ("...only as a fresh DRAFT") is the real enforcement of
    this -- this function's own shape is defense in depth."""
    response = (
        client.table("opportunities")
        .insert({**payload, "industry_id": industry_id, "status": "DRAFT"})
        .execute()
    )
    return response.data[0]


def update_opportunity(client: Client, opportunity_id: UUID, payload: dict) -> dict | None:
    """Partial metadata update -- ownership, the CLOSED-immutability rule,
    and the PUBLISHED-locks-opportunity_type rule are all enforced by the
    prevent_invalid_opportunity_transition trigger, not here. Returns
    None if the row doesn't exist or isn't owned by the caller (RLS
    yields zero matched rows in that case, not an error)."""
    response = (
        client.table("opportunities").update(payload).eq("id", str(opportunity_id)).execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def publish_opportunity(client: Client, opportunity_id: UUID) -> dict | None:
    """DRAFT -> PUBLISHED. The trigger validates this is a legal
    transition and stamps published_at automatically -- this function
    only requests it."""
    response = (
        client.table("opportunities")
        .update({"status": "PUBLISHED"})
        .eq("id", str(opportunity_id))
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def close_opportunity(client: Client, opportunity_id: UUID) -> dict | None:
    """DRAFT|PUBLISHED -> CLOSED. Same trigger-validated pattern as
    publish_opportunity."""
    response = (
        client.table("opportunities")
        .update({"status": "CLOSED"})
        .eq("id", str(opportunity_id))
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


# ------------------------------------------------------------
# opportunity_skill_requirements
# ------------------------------------------------------------


def get_requirements(client: Client, opportunity_id: UUID) -> list[SkillRequirement]:
    """This opportunity's required skills, shaped as the exact generic
    SkillRequirement dataclass app.services.skill_alignment_service
    consumes -- identical pattern to
    career_role_service.get_career_role_requirements(), the whole point
    being that both feed the same unmodified engine. A row whose embedded
    skill comes back None (the skill was deactivated after this
    requirement was set) is skipped, same reasoning as the career-role
    equivalent."""
    response = (
        client.table("opportunity_skill_requirements")
        .select("skill_id, required_level, weight, skill:skills(name)")
        .eq("opportunity_id", str(opportunity_id))
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


def replace_requirements(client: Client, opportunity_id: UUID, requirements: list[dict]) -> list[dict]:
    """Full replace, same contract as Phase 1K's blueprint upsert
    (question_bank_service.replace_blueprint): delete every existing
    requirement row for this opportunity, then insert the new set as one
    batch. RLS's own INSERT/UPDATE/DELETE policies on
    opportunity_skill_requirements ("...while opportunity is a draft")
    are what actually make this a no-op (0 rows affected, then an insert
    that fails the WITH CHECK) once the opportunity has left DRAFT -- this
    function does not re-check that itself, so the caller sees a clean
    RLS-driven failure either way, not a confusing partial success.
    """
    client.table("opportunity_skill_requirements").delete().eq(
        "opportunity_id", str(opportunity_id)
    ).execute()

    if not requirements:
        return []

    rows = [
        {
            "opportunity_id": str(opportunity_id),
            "skill_id": str(req["skill_id"]),
            "required_level": str(req["required_level"]),
            "weight": str(req["weight"]),
        }
        for req in requirements
    ]
    response = client.table("opportunity_skill_requirements").insert(rows).execute()
    return response.data or []
