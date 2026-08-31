"""API routes for the shared skill catalog.

GET /api/v1/skills -- read-only, available to any signed-in user (the
catalog is role-neutral reference data). Goes through
build_user_client(access_token) so the "Authenticated users can view
active skills" RLS policy stays the boundary.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, get_current_user
from app.core.security import build_user_client
from app.schemas.skill import SkillCatalogResponse
from app.services import skill_service

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=SkillCatalogResponse)
def list_skills(
    search: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
) -> SkillCatalogResponse:
    client = build_user_client(current_user.access_token)
    try:
        skills = skill_service.list_active_skills(client, search)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the skill catalog.",
        ) from exc
    return SkillCatalogResponse(skills=skills)
