"""API routes for the shared skill catalog.

GET /skills is open to any authenticated role -- RLS itself never
role-restricts this reference data (same precedent as
app.api.career_roles.list_career_roles / app.api.assessments.
list_active_assessments). Used by the Industry/Institution internship &
job skill-requirements pickers (frontend/lib/industry/skills.ts);
students read the same table directly via Supabase
(frontend/lib/student/skills.ts) rather than through this route.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, get_current_user
from app.core.security import build_user_client
from app.schemas.skill import SkillCatalogListResponse
from app.services import skill_service

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=SkillCatalogListResponse)
def list_skills(
    search: str | None = Query(
        default=None, description="Case-insensitive substring match on skill name."
    ),
    current_user: CurrentUser = Depends(get_current_user),
) -> SkillCatalogListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = skill_service.list_active_skills(client, search=search)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the skill catalog.",
        ) from exc
    return SkillCatalogListResponse(skills=rows)
