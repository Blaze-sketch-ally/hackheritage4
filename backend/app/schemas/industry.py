"""Pydantic schemas for the Industry portal.

- IndustryIdentityResponse: the GET /industry/me probe (Phase 2).
- IndustryProfile* : the company profile stored in `industry_profiles`
  (Phase 4).

Company-profile field names match the columns in
database/migrations/017_industry_profiles.sql exactly. Validation here
mirrors that migration's CHECK constraints so a bad value comes back as a
friendly 422 instead of a raw database error -- the database constraints
stay authoritative, this is not a competing source of truth. The URL
columns have no CHECK in the migration, so they are only length-bounded
here, never format-locked.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IndustryIdentityResponse(BaseModel):
    """Minimal identity echo for GET /industry/me.

    Confirms the caller both authenticated and resolved to the INDUSTRY
    role. Deliberately carries only non-sensitive identity fields -- never
    the access token or anything else off CurrentUser.
    """

    id: str
    email: str | None
    role: str


# database/migrations/017_industry_profiles.sql: company_size CHECK
CompanySize = Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
COMPANY_SIZES: tuple[str, ...] = (
    "1-10",
    "11-50",
    "51-200",
    "201-500",
    "501-1000",
    "1000+",
)

# database/migrations/017_industry_profiles.sql: industry_profiles_phone_format
_PHONE_PATTERN = r"^[0-9+\-\s()]{7,20}$"


class IndustryProfileFields(BaseModel):
    """The editable company-profile fields, shared by the update request
    and the response.

    Every field is optional: an INDUSTRY account has a `profiles` row from
    signup but no `industry_profiles` row until the first save, and any
    single field may legitimately be left blank.
    """

    company_name: str | None = Field(default=None, max_length=200)
    industry_sector: str | None = Field(default=None, max_length=120)
    company_size: CompanySize | None = None
    website_url: str | None = Field(default=None, max_length=2048)
    company_description: str | None = Field(default=None, max_length=5000)
    headquarters_location: str | None = Field(default=None, max_length=200)
    # 1800..2100 mirrors the migration's founded_year CHECK.
    founded_year: int | None = Field(default=None, ge=1800, le=2100)
    contact_phone: str | None = Field(default=None, max_length=20)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    logo_url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data: object) -> object:
        """Trim strings and treat "" / whitespace-only (what an empty form
        field submits) as NULL, before field validation runs -- so an
        empty phone field never trips the phone pattern and an empty
        company_size never trips the Literal."""
        if not isinstance(data, dict):
            return data
        cleaned: dict = {}
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip() or None
            cleaned[key] = value
        return cleaned

    @field_validator("contact_phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(_PHONE_PATTERN, value) is None:
            raise ValueError(
                "Enter a valid phone number: 7-20 characters using digits, spaces, "
                "and + - ( ) only."
            )
        return value


class IndustryProfileUpdate(IndustryProfileFields):
    """PUT /api/v1/industry/profile body.

    A full company-profile representation: the edit form always submits
    every field, and an omitted or blanked field is stored as NULL. `id`
    is never accepted here -- ownership is the authenticated caller,
    resolved server-side from the access token. `extra="forbid"` is what
    structurally stops a client from smuggling an `id` (or anything else)
    into the payload.
    """

    model_config = ConfigDict(extra="forbid")


class IndustryProfileResponse(IndustryProfileFields):
    """GET / PUT response.

    `id` is always the authenticated caller's own `profiles` id.
    `created_at` / `updated_at` are None only in the no-row-yet window
    (a GET before the first save).
    """

    id: str
    created_at: str | None = None
    updated_at: str | None = None
