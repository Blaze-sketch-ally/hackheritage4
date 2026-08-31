"""Pydantic schemas for the Portfolio API (Phase 1N).

Mirrors database/migrations/025_portfolio_projects_and_certifications.sql
exactly -- no invented columns. Two normalized resources (projects,
certifications), not a single generic "portfolio" shape -- see that
migration's own header comment for why they aren't merged.

No endpoint or service logic lives here -- schemas only.
"""

import re
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Deliberately simple (scheme + host), not a full RFC 3986 parser --
# good enough to reject an obviously-malformed value at the API
# boundary (422) without pulling in a URL-parsing dependency this
# project doesn't otherwise use. Kept as a plain `str` field (not
# Pydantic's AnyUrl/HttpUrl) so the value round-trips through the
# database and back to the frontend byte-for-byte, with no
# normalization surprises (e.g. an added trailing slash).
_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def _validate_optional_url(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not _URL_RE.match(value):
        raise ValueError("Must be a valid http(s) URL.")
    return value


# ============================================================
# portfolio_projects
# ============================================================


class ProjectCreateRequest(BaseModel):
    """student_id is never client-supplied -- always the authenticated
    caller's own id (see app/api/portfolio.py)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    technologies: list[str] = Field(default_factory=list)
    project_url: str | None = Field(default=None, max_length=2048)
    github_url: str | None = Field(default=None, max_length=2048)

    _validate_project_url = field_validator("project_url")(_validate_optional_url)
    _validate_github_url = field_validator("github_url")(_validate_optional_url)


class ProjectUpdateRequest(BaseModel):
    """Partial update -- every field optional. student_id has no field
    here at all; it can never be reassigned (see the migration's own
    RLS-symmetry note)."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    technologies: list[str] | None = None
    project_url: str | None = Field(default=None, max_length=2048)
    github_url: str | None = Field(default=None, max_length=2048)

    _validate_project_url = field_validator("project_url")(_validate_optional_url)
    _validate_github_url = field_validator("github_url")(_validate_optional_url)


class ProjectResponse(BaseModel):
    """Mirrors `portfolio_projects`."""

    id: UUID
    student_id: UUID
    title: str
    description: str
    technologies: list[str]
    project_url: str | None
    github_url: str | None
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


# ============================================================
# portfolio_certifications
# ============================================================


class CertificationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    issuer: str = Field(min_length=1, max_length=200)
    issue_date: date | None = None
    credential_url: str | None = Field(default=None, max_length=2048)

    _validate_credential_url = field_validator("credential_url")(_validate_optional_url)


class CertificationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    issuer: str | None = Field(default=None, min_length=1, max_length=200)
    issue_date: date | None = None
    credential_url: str | None = Field(default=None, max_length=2048)

    _validate_credential_url = field_validator("credential_url")(_validate_optional_url)


class CertificationResponse(BaseModel):
    """Mirrors `portfolio_certifications`."""

    id: UUID
    student_id: UUID
    name: str
    issuer: str
    issue_date: date | None
    credential_url: str | None
    created_at: datetime
    updated_at: datetime


class CertificationListResponse(BaseModel):
    certifications: list[CertificationResponse]


# ============================================================
# Combined view -- GET /portfolio and the industry applicant read
# (GET /applications/{id}/portfolio) both return this same shape, one
# function (portfolio_service.get_student_portfolio) serving both --
# RLS alone decides what each caller may see.
# ============================================================


class PortfolioResponse(BaseModel):
    student_id: UUID
    projects: list[ProjectResponse]
    certifications: list[CertificationResponse]
