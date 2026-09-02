"""Pydantic schemas for the STUDENT Portfolio API
(database/migrations/034_student_portfolio.sql).

Four live tables back this: `student_projects`, `student_project_skills`
(optional project -> canonical `skills` edge), `student_certifications`,
and `student_achievements` -- all owner-only.

A project / certification / achievement is PORTFOLIO EVIDENCE ONLY. There
is no score / proficiency / verification field anywhere here. Associating
a skill with a project never touches `student_skills` and never verifies a
skill -- that stays exclusively the assessment scoring path
(015_assessment_verification.sql).

`student_id` is never a field on any request model. It is always
`current_user.id`, derived from the authenticated token by the route.
Every request model is `extra="forbid"`, so an attempt to smuggle in
`student_id` / `owner_id` / `id` / `created_at` / `is_verified` / … is a
422 before any handler runs.
"""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_MAX_TITLE = 200
_MAX_ORG = 200
_MAX_TEXT = 5_000
_MAX_URL = 2_000
_MAX_CRED_ID = 200


def _clean_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _validate_optional_url(value: str | None) -> str | None:
    trimmed = _clean_optional_str(value)
    if trimmed is None:
        return None
    if not trimmed.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    return trimmed


# ============================================================
# Projects
# ============================================================


class ProjectSkillRef(BaseModel):
    """One canonical skill a project shows evidence of -- resolved to its
    catalog name. Never a proficiency / verification signal."""

    skill_id: str
    skill_name: str
    category_name: str | None = None


class _ProjectFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    description: str | None = Field(default=None, max_length=_MAX_TEXT)
    project_url: str | None = Field(default=None, max_length=_MAX_URL)
    repo_url: str | None = Field(default=None, max_length=_MAX_URL)
    start_date: date | None = None
    end_date: date | None = None
    is_ongoing: bool = False
    # Optional canonical skill_ids. Deduplicated; each must resolve to a
    # real `skills` row (enforced by the service + the DB FK).
    skill_ids: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title is required.")
        return v

    @field_validator("description")
    @classmethod
    def _strip_description(cls, v: str | None) -> str | None:
        return _clean_optional_str(v)

    @field_validator("project_url", "repo_url")
    @classmethod
    def _check_url(cls, v: str | None) -> str | None:
        return _validate_optional_url(v)

    @field_validator("skill_ids")
    @classmethod
    def _dedupe_skill_ids(cls, v: list[str]) -> list[str]:
        seen: list[str] = []
        for s in v:
            s = s.strip()
            if s and s not in seen:
                seen.append(s)
        return seen

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.is_ongoing and self.end_date is not None:
            raise ValueError("An ongoing project cannot have an end date.")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before the start date.")
        return self


class ProjectCreate(_ProjectFields):
    """POST /api/v1/student/projects body."""


class ProjectUpdate(_ProjectFields):
    """PUT /api/v1/student/projects/{id} body -- full replacement, same
    shape as create."""


class ProjectResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    project_url: str | None = None
    repo_url: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_ongoing: bool = False
    skills: list[ProjectSkillRef] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


# ============================================================
# Certifications
# ============================================================


class _CertificationFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=_MAX_TITLE)
    issuing_organization: str | None = Field(default=None, max_length=_MAX_ORG)
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_id: str | None = Field(default=None, max_length=_MAX_CRED_ID)
    credential_url: str | None = Field(default=None, max_length=_MAX_URL)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required.")
        return v

    @field_validator("issuing_organization", "credential_id")
    @classmethod
    def _strip_optionals(cls, v: str | None) -> str | None:
        return _clean_optional_str(v)

    @field_validator("credential_url")
    @classmethod
    def _check_url(cls, v: str | None) -> str | None:
        return _validate_optional_url(v)

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.issue_date and self.expiry_date and self.expiry_date < self.issue_date:
            raise ValueError("Expiry date cannot be before the issue date.")
        return self


class CertificationCreate(_CertificationFields):
    """POST /api/v1/student/certifications body."""


class CertificationUpdate(_CertificationFields):
    """PUT /api/v1/student/certifications/{id} body."""


class CertificationResponse(BaseModel):
    id: str
    name: str
    issuing_organization: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_id: str | None = None
    credential_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CertificationListResponse(BaseModel):
    certifications: list[CertificationResponse]


# ============================================================
# Achievements
# ============================================================


class _AchievementFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    description: str | None = Field(default=None, max_length=_MAX_TEXT)
    achievement_date: date | None = None
    issuing_organization: str | None = Field(default=None, max_length=_MAX_ORG)
    url: str | None = Field(default=None, max_length=_MAX_URL)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title is required.")
        return v

    @field_validator("description", "issuing_organization")
    @classmethod
    def _strip_optionals(cls, v: str | None) -> str | None:
        return _clean_optional_str(v)

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str | None) -> str | None:
        return _validate_optional_url(v)


class AchievementCreate(_AchievementFields):
    """POST /api/v1/student/achievements body."""


class AchievementUpdate(_AchievementFields):
    """PUT /api/v1/student/achievements/{id} body."""


class AchievementResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    achievement_date: date | None = None
    issuing_organization: str | None = None
    url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AchievementListResponse(BaseModel):
    achievements: list[AchievementResponse]


# ============================================================
# Portfolio aggregate (read-only)
# ============================================================


class PortfolioSkillRef(BaseModel):
    """One of the student's own `student_skills` rows, surfaced read-only
    on the portfolio. `is_verified` is displayed, never set here."""

    skill_id: str
    skill_name: str
    category_name: str | None = None
    proficiency_level: str
    is_verified: bool


class PortfolioResponse(BaseModel):
    """A read-only aggregation of the authenticated student's portfolio --
    NOT a stored record. `skills` is a copy of the student's canonical
    `student_skills`, included so the portfolio page needs one round trip.
    """

    projects: list[ProjectResponse]
    certifications: list[CertificationResponse]
    achievements: list[AchievementResponse]
    skills: list[PortfolioSkillRef]
