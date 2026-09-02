"""Pydantic schemas for the Faculty academic profile (`faculty_profiles`,
database/migrations/036_faculty_profiles.sql).

Same shape as app.schemas.industry's IndustryProfile* models: field names
match the migration's columns exactly, validation mirrors its CHECK
constraints so a bad value comes back as a friendly 422 instead of a raw
database error -- the database constraints stay authoritative, this is
not a competing source of truth.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# database/migrations/036_faculty_profiles.sql: faculty_profiles_phone_format
_PHONE_PATTERN = r"^[0-9+\-\s()]{7,20}$"


class FacultyProfileFields(BaseModel):
    """The editable Faculty profile fields, shared by the update request
    and the response.

    Every field is optional: a FACULTY account has a `profiles` row from
    signup but no `faculty_profiles` row until the first save, and any
    single field may legitimately be left blank.
    """

    designation: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    institution_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    bio: str | None = Field(default=None, max_length=5000)
    expertise_areas: list[str] = Field(default_factory=list)
    # 0..60 mirrors the migration's years_of_experience CHECK.
    years_of_experience: int | None = Field(default=None, ge=0, le=60)

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data: object) -> object:
        """Trim strings and treat "" / whitespace-only (what an empty form
        field submits) as NULL, before field validation runs -- so an
        empty phone field never trips the phone pattern."""
        if not isinstance(data, dict):
            return data
        cleaned: dict = {}
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip() or None
            cleaned[key] = value
        return cleaned

    @field_validator("expertise_areas")
    @classmethod
    def _clean_expertise_areas(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) > 25:
            raise ValueError("Enter at most 25 expertise areas.")
        for item in cleaned:
            if len(item) > 80:
                raise ValueError("Each expertise area must be 80 characters or fewer.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(_PHONE_PATTERN, value) is None:
            raise ValueError(
                "Enter a valid phone number: 7-20 characters using digits, spaces, "
                "and + - ( ) only."
            )
        return value


class FacultyProfileUpdate(FacultyProfileFields):
    """PUT /api/v1/faculty/profile body.

    A full profile representation: the edit form always submits every
    field, and an omitted or blanked field is stored as NULL/empty. `id`
    is never accepted here -- ownership is the authenticated caller,
    resolved server-side from the access token. `extra="forbid"` is what
    structurally stops a client from smuggling an `id` (or anything else)
    into the payload.
    """

    model_config = ConfigDict(extra="forbid")


class FacultyProfileResponse(FacultyProfileFields):
    """GET / PUT response.

    `id` is always the authenticated caller's own `profiles` id.
    `created_at` / `updated_at` are None only in the no-row-yet window (a
    GET before the first save). `completeness` is derived, never stored
    (see 036_faculty_profiles.sql's own header) -- the fraction (0-1) of
    the profile's optional fields that are actually filled in.
    """

    id: str
    created_at: str | None = None
    updated_at: str | None = None
    completeness: float = 0.0


# Fields that count toward profile completeness -- deliberately excludes
# nothing on FacultyProfileFields today, but named explicitly (not
# "every field on the model") so a later field addition must be a
# conscious decision about whether it should count.
_COMPLETENESS_FIELDS: tuple[str, ...] = (
    "designation",
    "department",
    "institution_name",
    "phone",
    "bio",
    "expertise_areas",
    "years_of_experience",
)


def compute_completeness(fields: dict) -> float:
    filled = 0
    for name in _COMPLETENESS_FIELDS:
        value = fields.get(name)
        if isinstance(value, list):
            if value:
                filled += 1
        elif value is not None:
            filled += 1
    return round(filled / len(_COMPLETENESS_FIELDS), 2)
