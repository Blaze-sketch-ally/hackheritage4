"""Pydantic schemas for the Institution Events module
(backend/app/api/institution.py, /institution/events...,
database/migrations/045_institution_events.sql).

PHASE 10. `industry_workshops` (024_industry_workshops.sql) remains the
ONLY entity a company itself uses to post an event -- this module never
duplicates it. `institution_events` (045) is an ADDITIVE, institution-
owned entity for sessions the INSTITUTION itself organizes (a Placement
Orientation, a Career Session, or a company-featuring Industry Talk/
Guest Lecture the institution itself is hosting) -- something no
existing entity could represent, since `industry_workshops` grants no
INSTITUTION write path at all.

The Institution Events directory (list_events) is the UNION of:
  - the institution's own `institution_events` rows (any status --
    including DRAFT, since the institution manages its own drafts), and
  - platform-wide PUBLISHED `industry_workshops` (read-only, exactly the
    same rows the Dashboard's `upcoming_events` and the Student event
    feed already surface, marked `source: "INDUSTRY_WORKSHOP"` and
    `platform_wide: true`).
A row's `source` field tells the frontend whether institution-side
edit/status actions apply (INSTITUTION) or not (INDUSTRY_WORKSHOP,
strictly read-only here, same as everywhere else in this schema).

Honesty boundaries enforced here, not just documented:
  - There is NO registration or attendance table anywhere in this
    schema (024's own header comment: "no application/registration
    table"; student_event_service.py's own docstring: "There is no
    registration table in the schema"). No registration_count,
    registered_count, attended_count, or attendance_rate field exists
    anywhere in this module's responses -- `registration_note` explains
    this once, at the top level, rather than a fabricated per-event
    number.
  - `target_department_ids` / `target_batches` are DESCRIPTIVE audience
    metadata only -- no eligibility/registration engine is computed from
    them (there is nothing to register against).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EventType = Literal[
    "SEMINAR",
    "WORKSHOP",
    "GUEST_LECTURE",
    "INDUSTRY_TALK",
    "TRAINING",
    "FDP",
    "CAREER_SESSION",
    "PLACEMENT_ORIENTATION",
    "OTHER",
]
EventStatus = Literal["DRAFT", "PUBLISHED", "ONGOING", "COMPLETED", "CANCELLED"]
EventMode = Literal["ONSITE", "REMOTE", "HYBRID"]
EventSource = Literal["INSTITUTION", "INDUSTRY_WORKSHOP"]

EVENT_TYPES: tuple[str, ...] = (
    "SEMINAR",
    "WORKSHOP",
    "GUEST_LECTURE",
    "INDUSTRY_TALK",
    "TRAINING",
    "FDP",
    "CAREER_SESSION",
    "PLACEMENT_ORIENTATION",
    "OTHER",
)
EVENT_STATUSES: tuple[str, ...] = ("DRAFT", "PUBLISHED", "ONGOING", "COMPLETED", "CANCELLED")
EVENT_MODES: tuple[str, ...] = ("ONSITE", "REMOTE", "HYBRID")

_REGISTRATION_NOTE = (
    "There is no registration or attendance tracking anywhere in this system -- registration counts, "
    "attendee lists, and attendance rates are not shown because that data does not exist, not because "
    "it was left out."
)


def _blank_to_none(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    return cleaned


class _EventEditableFields(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    event_type: EventType | None = None
    industry_id: str | None = None
    mode: EventMode | None = None
    venue: str | None = Field(default=None, max_length=300)
    start_at: datetime | None = None
    end_at: datetime | None = None
    registration_deadline: datetime | None = None
    target_department_ids: list[str] | None = None
    target_batches: list[int] | None = None
    includes_faculty: bool | None = None
    instructions: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="before")
    @classmethod
    def _normalise_blanks(cls, data: object) -> object:
        return _blank_to_none(data)


class InstitutionEventCreate(_EventEditableFields):
    """POST /institution/events. Always created as DRAFT -- no `status`
    field here. `event_type` defaults to OTHER (never left NULL) --
    matches institution_industry.py's IndustryPartnerRelationshipCreate
    defaulting `relationship_type` the same way."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    event_type: EventType = "OTHER"


class InstitutionEventUpdate(_EventEditableFields):
    """PUT /institution/events/{id}. Partial -- only fields actually sent
    are changed. `status` is never editable here -- see the dedicated
    PATCH .../status endpoint so every lifecycle transition passes
    through one validated code path."""

    model_config = ConfigDict(extra="forbid")


class InstitutionEventStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EventStatus


class EventRow(BaseModel):
    id: str
    source: EventSource
    title: str
    event_type: str
    status: str
    industry_id: str | None
    company_name: str | None
    mode: str | None
    venue: str | None
    start_at: str | None
    end_at: str | None
    registration_deadline: str | None
    target_department_ids: list[str]
    target_department_names: list[str]
    target_batches: list[int]
    includes_faculty: bool
    # True for a platform-wide industry_workshops row -- never organized
    # by, or exclusive to, this institution.
    platform_wide: bool
    created_at: str | None = None
    updated_at: str | None = None


class EventListResponse(BaseModel):
    events: list[EventRow]
    type_options: list[str] = list(EVENT_TYPES)
    status_options: list[str] = list(EVENT_STATUSES)
    mode_options: list[str] = list(EVENT_MODES)
    registration_note: str = _REGISTRATION_NOTE


class EventDetail(EventRow):
    description: str | None
    instructions: str | None
    registration_note: str = _REGISTRATION_NOTE


class EventKpis(BaseModel):
    total_events: int
    upcoming_events: int
    ongoing_events: int
    completed_events: int
    # Any event (institution-organized or platform workshop) that features
    # a real company (industry_id set).
    industry_events: int
    institution_organized_events: int
    platform_workshops: int


class EventOverviewResponse(BaseModel):
    kpis: EventKpis
    tenancy_note: str
    registration_note: str = _REGISTRATION_NOTE
