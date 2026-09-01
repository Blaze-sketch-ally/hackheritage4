"""Pydantic schemas for Industry projects.

Field names and constraints match database/migrations/022_industry_projects.sql
exactly (`industry_projects`). Validation here mirrors that migration's
CHECK constraints so a bad value comes back as a friendly 422 instead of a
raw database error -- the database stays authoritative.

Named `industry_project` (not `project`) to avoid colliding with the
still-unbuilt Student Portfolio "projects" feature, which is a distinct,
unrelated feature area reserved for backend/app/schemas/project.py.

Unlike internships/jobs, there is no skills subtable here -- Projects has
no application/matching flow yet this phase.

Ownership (`industry_id`) and lifecycle (`status`) are never accepted from
the client: `industry_id` is always the authenticated caller, and
`status` only changes through the explicit publish/close/archive
endpoints. `extra="forbid"` on the write models is what structurally
rejects an attempt to smuggle either one in.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProjectStatus = Literal["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"]
WorkMode = Literal["ONSITE", "REMOTE", "HYBRID"]

PROJECT_STATUSES: tuple[str, ...] = ("DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED")
WORK_MODES: tuple[str, ...] = ("ONSITE", "REMOTE", "HYBRID")


def _blank_strings_to_none(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    return cleaned


class _ProjectEditableFields(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    location: str | None = Field(default=None, max_length=200)
    work_mode: WorkMode | None = None
    duration_months: int | None = Field(default=None, ge=1, le=24)
    team_size: int | None = Field(default=None, ge=1)
    eligibility_criteria: str | None = Field(default=None, max_length=5_000)
    application_deadline: date | None = None
    start_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_blanks(cls, data: object) -> object:
        return _blank_strings_to_none(data)


class ProjectCreate(_ProjectEditableFields):
    """POST /api/v1/projects. Always created as DRAFT -- there is no
    `status` field here, and no `industry_id`."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)


class ProjectUpdate(_ProjectEditableFields):
    """PUT /api/v1/projects/{id}. Partial: only the fields actually sent
    are changed. `status` cannot be changed here."""

    model_config = ConfigDict(extra="forbid")


class ProjectResponse(BaseModel):
    id: str
    industry_id: str
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None
    duration_months: int | None = None
    team_size: int | None = None
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    start_date: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
