"""Pydantic schemas for Industry jobs.

Field names and constraints match database/migrations/019_jobs.sql exactly
(`jobs` + `job_skills`). Validation here mirrors that migration's CHECK
constraints so a bad value comes back as a friendly 422 instead of a raw
database error -- the database stays authoritative.

`jobs` differs from `internships`: it has `employment_type` and
`experience_min_years`, a salary *range* (`salary_min` / `salary_max` /
`salary_currency`), and no `duration_months` / `start_date` /
`stipend_*`.

Ownership (`industry_id`) and lifecycle (`status`) are never accepted from
the client -- `industry_id` is always the authenticated caller, and
`status` only changes through the explicit publish/close/archive
endpoints. `extra="forbid"` on the write models rejects any attempt to
smuggle either one in.
"""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

JobStatus = Literal["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"]
WorkMode = Literal["ONSITE", "REMOTE", "HYBRID"]
EmploymentType = Literal["FULL_TIME", "PART_TIME", "CONTRACT"]
RequiredLevel = Literal["Beginner", "Intermediate", "Advanced", "Expert"]
SkillImportance = Literal["CORE", "IMPORTANT", "OPTIONAL"]

JOB_STATUSES: tuple[str, ...] = ("DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED")
WORK_MODES: tuple[str, ...] = ("ONSITE", "REMOTE", "HYBRID")
EMPLOYMENT_TYPES: tuple[str, ...] = ("FULL_TIME", "PART_TIME", "CONTRACT")


def _blank_strings_to_none(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    return cleaned


# ---- skills (job_skills has the same columns as internship_skills) ----


class JobSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    required_level: RequiredLevel
    importance: SkillImportance = "IMPORTANT"


class JobSkillResponse(BaseModel):
    skill_id: str
    skill_name: str
    category_name: str | None = None
    required_level: str
    importance: str


# ---- jobs ----


class _JobEditableFields(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    location: str | None = Field(default=None, max_length=200)
    work_mode: WorkMode | None = None
    employment_type: EmploymentType | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=1, max_length=8)
    experience_min_years: float | None = Field(default=None, ge=0, le=99.9)
    openings: int | None = Field(default=None, ge=1)
    eligibility_criteria: str | None = Field(default=None, max_length=5_000)
    application_deadline: date | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_blanks(cls, data: object) -> object:
        return _blank_strings_to_none(data)

    @model_validator(mode="after")
    def _check_salary_range(self) -> "_JobEditableFields":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            raise ValueError("Maximum salary can't be lower than the minimum salary.")
        return self


class JobCreate(_JobEditableFields):
    """POST /api/v1/jobs. Always created as DRAFT -- there is no `status`
    field here, and no `industry_id`."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    skills: list[JobSkillInput] = Field(default_factory=list, max_length=50)


class JobUpdate(_JobEditableFields):
    """PUT /api/v1/jobs/{id}. Partial: only the fields actually sent are
    changed. `skills` omitted = leave the skill list alone; `skills`
    present = replace it wholesale. `status` cannot be changed here."""

    model_config = ConfigDict(extra="forbid")

    skills: list[JobSkillInput] | None = Field(default=None, max_length=50)


class JobResponse(BaseModel):
    id: str
    industry_id: str
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    experience_min_years: float | None = None
    openings: int | None = None
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    skills: list[JobSkillResponse] = Field(default_factory=list)


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
