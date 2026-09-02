"""Pydantic schemas for the Industry- and Institution-owned Faculty
opportunity postings (037_faculty_opportunities_and_expressions.sql):
`industry_faculty_opportunities` and `institution_faculty_opportunities`.

Both tables are identically shaped (see the migration's own comment on
why Institution mirrors Industry's shape rather than inventing a
different one), so one set of schemas serves both routers -- the owner
id field name (`industry_id` vs `institution_id`) is the only difference,
handled by each router's own response construction, not by these models.

Field names/constraints match the migration exactly, same convention as
schemas/industry_project.py. Status/lifecycle (`status`) is never
accepted from the client on create -- always starts DRAFT -- and only
changes through the explicit publish/close endpoints.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OpportunityStatus = Literal["DRAFT", "PUBLISHED", "CLOSED"]
WorkMode = Literal["ONSITE", "REMOTE", "HYBRID"]


def _blank_strings_to_none(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    return cleaned


class _FacultyOpportunityPostingEditableFields(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    location: str | None = Field(default=None, max_length=200)
    work_mode: WorkMode | None = None
    capacity: int | None = Field(default=None, ge=1)
    eligibility_criteria: str | None = Field(default=None, max_length=5_000)
    application_deadline: str | None = None
    start_date: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_blanks(cls, data: object) -> object:
        return _blank_strings_to_none(data)


class FacultyOpportunityPostingCreate(_FacultyOpportunityPostingEditableFields):
    """POST body. Always created as DRAFT -- no `status`, no owner id."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)


class FacultyOpportunityPostingUpdate(_FacultyOpportunityPostingEditableFields):
    """PUT body. Partial: only fields actually sent are changed. `status`
    cannot be changed here -- only through publish/close."""

    model_config = ConfigDict(extra="forbid")


class FacultyOpportunityPostingResponse(BaseModel):
    id: str
    owner_id: str
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None
    capacity: int | None = None
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    start_date: str | None = None
    status: OpportunityStatus
    created_at: str | None = None
    updated_at: str | None = None


class FacultyOpportunityPostingListResponse(BaseModel):
    opportunities: list[FacultyOpportunityPostingResponse]
