"""Pydantic schemas for Industry internships.

Field names and constraints match database/migrations/018_internships.sql
exactly (`internships` + `internship_skills`). Validation here mirrors
that migration's CHECK constraints so a bad value comes back as a
friendly 422 instead of a raw database error -- the database stays
authoritative.

Note: the migration models compensation as a single `stipend_amount` +
`stipend_currency` (not a min/max range), duration as `duration_months`
(1..24), and internship mode as `work_mode` (ONSITE/REMOTE/HYBRID). These
schemas follow the real columns.

Ownership (`industry_id`) and lifecycle (`status`) are never accepted from
the client: `industry_id` is always the authenticated caller, and
`status` only changes through the explicit publish/close/archive
endpoints. `extra="forbid"` on the write models is what structurally
rejects an attempt to smuggle either one in.
"""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

InternshipStatus = Literal["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"]
WorkMode = Literal["ONSITE", "REMOTE", "HYBRID"]
RequiredLevel = Literal["Beginner", "Intermediate", "Advanced", "Expert"]
SkillImportance = Literal["CORE", "IMPORTANT", "OPTIONAL"]

INTERNSHIP_STATUSES: tuple[str, ...] = ("DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED")
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


# ---- skills ----


class InternshipSkillInput(BaseModel):
    """One required skill on the create/update payload. `skill_id` must be
    an existing, active row in the `skills` catalog -- the service
    validates this before writing (a client cannot invent skill ids)."""

    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    required_level: RequiredLevel
    importance: SkillImportance = "IMPORTANT"


class InternshipSkillResponse(BaseModel):
    skill_id: str
    skill_name: str
    category_name: str | None = None
    required_level: str
    importance: str


# ---- internships ----


class _InternshipEditableFields(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    location: str | None = Field(default=None, max_length=200)
    work_mode: WorkMode | None = None
    duration_months: int | None = Field(default=None, ge=1, le=24)
    stipend_amount: float | None = Field(default=None, ge=0)
    stipend_currency: str | None = Field(default=None, min_length=1, max_length=8)
    openings: int | None = Field(default=None, ge=1)
    eligibility_criteria: str | None = Field(default=None, max_length=5_000)
    application_deadline: date | None = None
    start_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_blanks(cls, data: object) -> object:
        return _blank_strings_to_none(data)


class InternshipCreate(_InternshipEditableFields):
    """POST /api/v1/internships. Always created as DRAFT -- there is no
    `status` field here, and no `industry_id`."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    skills: list[InternshipSkillInput] = Field(default_factory=list, max_length=50)


class InternshipUpdate(_InternshipEditableFields):
    """PUT /api/v1/internships/{id}. Partial: only the fields actually sent
    are changed. `skills` omitted = leave the skill list alone; `skills`
    present = replace it wholesale. `status` cannot be changed here."""

    model_config = ConfigDict(extra="forbid")

    skills: list[InternshipSkillInput] | None = Field(default=None, max_length=50)


class InternshipResponse(BaseModel):
    id: str
    industry_id: str
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None
    duration_months: int | None = None
    stipend_amount: float | None = None
    stipend_currency: str | None = None
    openings: int | None = None
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    start_date: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    skills: list[InternshipSkillResponse] = Field(default_factory=list)


class InternshipListResponse(BaseModel):
    internships: list[InternshipResponse]
