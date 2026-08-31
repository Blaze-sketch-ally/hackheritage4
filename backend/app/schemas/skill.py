"""Pydantic schemas for the shared skill catalog (`skills` +
`skill_categories`, database/migrations/003_skills.sql).

Read-only reference data: every signed-in user can browse the active
catalog (the "Authenticated users can view active skills" RLS policy).
Nothing here writes -- the catalog is curated, not user-generated.
"""

from pydantic import BaseModel


class SkillCatalogItem(BaseModel):
    id: str
    name: str
    category_name: str | None = None
    description: str | None = None


class SkillCatalogResponse(BaseModel):
    skills: list[SkillCatalogItem]
