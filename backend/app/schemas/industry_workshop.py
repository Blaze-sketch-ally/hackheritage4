"""Pydantic schemas for Industry workshops.

Field names and constraints match database/migrations/024_industry_workshops.sql
exactly (`industry_workshops`). Validation here mirrors that migration's
CHECK constraints so a bad value comes back as a friendly 422 instead of a
raw database error -- the database stays authoritative.

Named `industry_workshop` (not `workshop`/`workshops`) to avoid colliding
with the separate, unimplemented academia-industry Collaboration feature
(009_collaboration.sql) that also mentions workshops as part of a
broader, unrelated concept.

Standalone entity, same precedent as industry_project/industry_training:
no skills subtable and no certificate fields -- neither is established
anywhere else in this repository, and Workshops has no
application/matching flow this phase.

`duration_days` (not `duration_months`) reflects that a workshop is a
short event, not a long-running engagement -- an approved deviation from
otherwise-identical schema parity with industry_project/industry_training.

Ownership (`industry_id`) and lifecycle (`status`) are never accepted from
the client: `industry_id` is always the authenticated caller, and
`status` only changes through the explicit publish/close/archive
endpoints. `extra="forbid"` on the write models is what structurally
rejects an attempt to smuggle either one in.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

WorkshopStatus = Literal["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"]
WorkMode = Literal["ONSITE", "REMOTE", "HYBRID"]

WORKSHOP_STATUSES: tuple[str, ...] = ("DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED")
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


class _WorkshopEditableFields(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    location: str | None = Field(default=None, max_length=200)
    work_mode: WorkMode | None = None
    duration_days: int | None = Field(default=None, ge=1, le=365)
    capacity: int | None = Field(default=None, ge=1)
    eligibility_criteria: str | None = Field(default=None, max_length=5_000)
    application_deadline: date | None = None
    start_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_blanks(cls, data: object) -> object:
        return _blank_strings_to_none(data)


class WorkshopCreate(_WorkshopEditableFields):
    """POST /api/v1/workshops. Always created as DRAFT -- there is no
    `status` field here, and no `industry_id`."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)


class WorkshopUpdate(_WorkshopEditableFields):
    """PUT /api/v1/workshops/{id}. Partial: only the fields actually sent
    are changed. `status` cannot be changed here."""

    model_config = ConfigDict(extra="forbid")


class WorkshopResponse(BaseModel):
    id: str
    industry_id: str
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None
    duration_days: int | None = None
    capacity: int | None = None
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    start_date: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None


class WorkshopListResponse(BaseModel):
    workshops: list[WorkshopResponse]
