"""Pydantic schemas for the shared skill catalog (GET /api/v1/skills).

Mirrors `skills` / `skill_categories` (database/migrations/003_skills.sql)
exactly -- read-only reference data, no invented fields. Every
authenticated role may read this (RLS: "Authenticated users can view
active skills"), matching the precedent in app.api.career_roles --
reference-data reads are not role-restricted.
"""

from pydantic import BaseModel


class SkillCatalogItem(BaseModel):
    id: str
    name: str
    category_name: str | None = None
    description: str | None = None


class SkillCatalogListResponse(BaseModel):
    skills: list[SkillCatalogItem]
