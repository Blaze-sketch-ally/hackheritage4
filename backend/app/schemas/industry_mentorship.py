"""Pydantic schemas for Industry mentorship opportunities.

Field names and constraints match database/migrations/025_industry_mentorship.sql
exactly (`industry_mentorship`). Validation here mirrors that migration's
CHECK/NOT NULL constraints so a bad value comes back as a friendly 422
instead of a raw database error -- the database stays authoritative.

Named `industry_mentorship` (not `mentorship`/`mentorships`) to avoid
colliding with `backend/app/api/mentorship.py` (a dead, unregistered
generic stub a future Student or Collaboration feature may still claim)
and with the separate, unimplemented academia-industry Collaboration
feature (009_collaboration.sql) that also mentions "mentorship pairings".

Standalone entity (Model C, approved product decision): Industry creates
and manages mentorship opportunities; there is no mentor<->mentee
pairing, no request/enrollment table, and no skills/expertise subtable --
none of that is established anywhere else in this repository, and it is
explicitly deferred to a future Student/Collaboration phase.

Unlike industry_project/industry_training/industry_workshop,
`location`, `work_mode`, `duration_months`, and `capacity` are REQUIRED
at creation time (matching the migration's NOT NULL columns), not only
before publish. `application_deadline` is a full timestamp (matching the
migration's TIMESTAMPTZ column), not a date.

Ownership (`industry_id`) and lifecycle (`status`) are never accepted from
the client: `industry_id` is always the authenticated caller, and
`status` only changes through the explicit publish/close/archive
endpoints. `extra="forbid"` on the write models is what structurally
rejects an attempt to smuggle either one in.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MentorshipStatus = Literal["DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"]
WorkMode = Literal["ONSITE", "REMOTE", "HYBRID"]

MENTORSHIP_STATUSES: tuple[str, ...] = ("DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED")
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


class _MentorshipOptionalFields(BaseModel):
    """Fields that stay optional on both create and update -- nullable
    columns in the migration."""

    eligibility_criteria: str | None = Field(default=None, max_length=5_000)
    application_deadline: datetime | None = None
    start_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_blanks(cls, data: object) -> object:
        return _blank_strings_to_none(data)


class MentorshipCreate(_MentorshipOptionalFields):
    """POST /api/v1/mentorship-opportunities. Always created as DRAFT --
    there is no `status` field here, and no `industry_id`. `location`,
    `work_mode`, `duration_months`, and `capacity` are required, matching
    the migration's NOT NULL columns."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    location: str = Field(min_length=1, max_length=200)
    work_mode: WorkMode
    duration_months: int = Field(ge=1, le=24)
    capacity: int = Field(ge=1)


class MentorshipUpdate(_MentorshipOptionalFields):
    """PUT /api/v1/mentorship-opportunities/{id}. Partial: only the fields
    actually sent are changed. `status` cannot be changed here."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    work_mode: WorkMode | None = None
    duration_months: int | None = Field(default=None, ge=1, le=24)
    capacity: int | None = Field(default=None, ge=1)


class IndustryMentorship(BaseModel):
    id: str
    industry_id: str
    title: str
    description: str
    location: str
    work_mode: str
    duration_months: int
    capacity: int
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    start_date: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None


class MentorshipListResponse(BaseModel):
    mentorship_opportunities: list[IndustryMentorship]
