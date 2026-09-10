"""Pydantic schemas for the Institution Industry Connections module
(backend/app/api/institution.py, /institution/industry-connections...,
database/migrations/044_institution_industry_connections.sql).

PHASE 9. The canonical company identity is still the EXISTING
`industry_profiles` table (017_industry_profiles.sql) -- a connection
never carries its own company name/logo/website; those are always
resolved live from `industry_profiles` by industry_id, exactly like
Phase 8's Industry Partners module.

`institution_industry_connections` is a genuinely new piece of data, not
a duplicate of anything: `industry_profiles.contact_phone` is a single
COMPANY-level phone number, owned and edited only by the Industry
account itself. It has no concept of a named person, a designation, or
an institution-specific contact "type" -- that data does not exist
anywhere else in this schema.

Privacy: every field here is written by, and only ever readable by, the
owning institution (database/migrations/044's own RLS) -- there is no
company-facing or cross-institution visibility into a connection at all.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ContactType = str  # validated against CONTACT_TYPES below; kept as str for forward-compat with new types

CONTACT_TYPES: tuple[str, ...] = ("RECRUITMENT", "ACADEMIC", "INTERNSHIP", "PARTNERSHIP", "TRAINING", "OTHER")

# Same permissive phone pattern already used by institution_profiles /
# industry_profiles (institution.py's own _PHONE_PATTERN).
_PHONE_PATTERN = r"^[0-9+\-\s()]{7,20}$"
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _blank_to_none(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    return cleaned


class _ConnectionEditableFields(BaseModel):
    contact_name: str | None = Field(default=None, min_length=1, max_length=200)
    designation: str | None = Field(default=None, max_length=200)
    contact_type: str | None = Field(default=None)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def _normalise_blanks(cls, data: object) -> object:
        return _blank_to_none(data)

    @field_validator("contact_type")
    @classmethod
    def _check_contact_type(cls, value: str | None) -> str | None:
        if value is not None and value not in CONTACT_TYPES:
            raise ValueError(f"contact_type must be one of: {', '.join(CONTACT_TYPES)}.")
        return value

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(_EMAIL_PATTERN, value) is None:
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(_PHONE_PATTERN, value) is None:
            raise ValueError("Enter a valid phone number: 7-20 characters using digits, spaces, and + - ( ) only.")
        return value


class IndustryConnectionCreate(_ConnectionEditableFields):
    """POST /institution/industry-connections. `industry_id` must be a
    real INDUSTRY account -- the database trigger
    (validate_connection_industry_id, 044) is the authoritative backstop;
    the service gives a clean 422 before that if the id isn't even an
    industry profile."""

    model_config = ConfigDict(extra="forbid")

    industry_id: str
    contact_name: str = Field(min_length=1, max_length=200)


class IndustryConnectionUpdate(_ConnectionEditableFields):
    """PATCH /institution/industry-connections/{id}. Partial -- only
    fields actually sent are changed. `industry_id` is never editable:
    to record a contact at a different company, create a new connection.
    `is_active=false` is how a connection is "removed" -- there is no
    delete endpoint."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_blanks(cls, data: object) -> object:
        # is_active is a bool, not a string -- _blank_to_none only
        # touches str values, so this is safe to share.
        return _blank_to_none(data)


class IndustryConnectionRow(BaseModel):
    id: str
    industry_id: str
    company_name: str | None
    industry_sector: str | None
    logo_url: str | None

    contact_name: str
    designation: str | None
    contact_type: str
    email: str | None
    phone: str | None
    notes: str | None
    is_active: bool

    created_at: str | None = None
    updated_at: str | None = None


class IndustryConnectionListResponse(BaseModel):
    connections: list[IndustryConnectionRow]
    type_options: list[str] = list(CONTACT_TYPES)
