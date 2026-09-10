"""Pydantic schemas for the Institution Industry Partners module
(backend/app/api/institution.py, /institution/industry-partners...,
database/migrations/043_institution_industry_partners.sql).

PHASE 8. The canonical company identity is the EXISTING `industry_profiles`
table (017_industry_profiles.sql) -- there is no second company entity
here. `institution_industry_partners` (043) is a small, institution-
private ADDITIVE relationship tag (type/status/notes) on top of that
identity; it carries no activity data of its own. Every activity number
below (jobs/internships/drives/students selected) is computed live from
the SAME tables every other institution module already reads
(`applications`, `placement_drives`, `industry_collaborations`) --
"selected" still means exactly what it has meant since
037_institution_tenancy.sql: an application row with status = 'SELECTED'.

Honesty boundaries enforced here, not just documented:
  - `relationship_type` / `relationship_status` / `relationship_id` are
    all null when no institution_industry_partners row exists for this
    company yet -- `has_explicit_relationship` makes that explicit rather
    than defaulting to a fabricated "PROSPECT".
  - `last_activity_at` is the real max() of applied_at / drive timestamps
    / collaboration updated_at for this company -- never a placeholder.
    None when there has been no activity at all.
  - `collaborations` summarizes (never duplicates) `industry_collaborations`
    rows -- only count + latest status/title, no full proposal content.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IndustryPartnerRelationshipType = Literal[
    "RECRUITMENT", "INTERNSHIP", "INDUSTRY_INTERACTION", "COLLABORATION", "TRAINING", "OTHER"
]
IndustryPartnerStatus = Literal["PROSPECT", "ACTIVE", "INACTIVE"]

RELATIONSHIP_TYPES: tuple[str, ...] = (
    "RECRUITMENT",
    "INTERNSHIP",
    "INDUSTRY_INTERACTION",
    "COLLABORATION",
    "TRAINING",
    "OTHER",
)
RELATIONSHIP_STATUSES: tuple[str, ...] = ("PROSPECT", "ACTIVE", "INACTIVE")


def _blank_to_none(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    return cleaned


# ---- company picker (add-partner form) ----


class CompanyOption(BaseModel):
    """A real, existing company (industry_profiles row) -- the ONLY
    source a new relationship's `industry_id` may come from. Never a
    free-text company name."""

    id: str
    company_name: str | None
    industry_sector: str | None
    logo_url: str | None


class CompanyOptionListResponse(BaseModel):
    companies: list[CompanyOption]


# ---- explicit relationship create/update ----


class IndustryPartnerRelationshipCreate(BaseModel):
    """POST /institution/industry-partners. `industry_id` must be a real
    INDUSTRY account -- the database trigger
    (validate_partner_industry_id, 043) is the authoritative backstop;
    the service gives a clean 422 before that if the id isn't even an
    industry profile."""

    model_config = ConfigDict(extra="forbid")

    industry_id: str
    relationship_type: IndustryPartnerRelationshipType = "OTHER"
    relationship_status: IndustryPartnerStatus = "PROSPECT"
    notes: str | None = Field(default=None, max_length=3000)


class IndustryPartnerRelationshipUpdate(BaseModel):
    """PATCH /institution/industry-partners/{industry_id}/relationship.
    Partial -- only fields actually sent are changed. `industry_id`
    itself is never editable: to track a different company, create a new
    relationship for it."""

    model_config = ConfigDict(extra="forbid")

    relationship_type: IndustryPartnerRelationshipType | None = None
    relationship_status: IndustryPartnerStatus | None = None
    notes: str | None = Field(default=None, max_length=3000)


class IndustryPartnerRelationshipResponse(BaseModel):
    id: str
    industry_id: str
    relationship_type: str
    relationship_status: str
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


# ---- directory / list ----


class IndustryPartnerRow(BaseModel):
    """One company row in the Industry Partners directory. `id` is the
    company's own `industry_profiles.id` (= profiles.id) -- stable and
    dereferenceable, used for both the detail route and the explicit
    relationship endpoints."""

    id: str
    company_name: str | None
    industry_sector: str | None
    logo_url: str | None
    website_url: str | None
    headquarters_location: str | None

    relationship_id: str | None
    relationship_type: str | None
    relationship_status: str | None
    has_explicit_relationship: bool

    jobs_opportunities: int
    jobs_selected_students: int
    internship_opportunities: int
    internship_selected: int
    placement_drives_count: int
    # Unique students SELECTED via any JOB application to this company
    # (drive-coordinated or not) -- the company-wide placement outcome,
    # distinct from internship_selected.
    students_selected: int
    # None when there has been no recorded activity with this company at all.
    last_activity_at: str | None


class IndustryPartnerListResponse(BaseModel):
    partners: list[IndustryPartnerRow]
    type_options: list[str] = list(RELATIONSHIP_TYPES)
    status_options: list[str] = list(RELATIONSHIP_STATUSES)


# ---- detail ----


class JobActivitySummary(BaseModel):
    opportunities: int
    applicants: int
    selected_students: int
    # Recent job titles the institution's students applied to at this
    # company -- bounded, not a full job listing (that belongs to the
    # existing Jobs/Placement Drives modules).
    titles: list[str]


class InternshipActivitySummary(BaseModel):
    opportunities: int
    applicants: int
    # Count of SELECTED applications (offers) -- can exceed the number of
    # unique students if one student holds multiple selected internship
    # offers at this company. Same distinction Phase 6/7 already draw.
    selected: int
    completed: int
    titles: list[str]


class DriveRow(BaseModel):
    id: str
    title: str
    status: str
    applied_count: int
    selected_count: int
    selection_rate: float | None


class PlacementDriveActivitySummary(BaseModel):
    count: int
    unique_students_selected: int
    drives: list[DriveRow]


class CollaborationSummary(BaseModel):
    """Summarizes, never duplicates, `industry_collaborations`
    (026_industry_collaborations.sql) -- no proposal title/description
    beyond the single most recent one, and no full history."""

    count: int
    latest_status: str | None
    latest_title: str | None


class IndustryPartnerDetail(BaseModel):
    id: str
    company_name: str | None
    industry_sector: str | None
    company_size: str | None
    website_url: str | None
    headquarters_location: str | None
    company_description: str | None
    logo_url: str | None
    linkedin_url: str | None

    relationship_id: str | None
    relationship_type: str | None
    relationship_status: str | None
    notes: str | None
    has_explicit_relationship: bool

    jobs: JobActivitySummary
    internships: InternshipActivitySummary
    placement_drives: PlacementDriveActivitySummary
    collaborations: CollaborationSummary
    students_selected: int
    last_activity_at: str | None

    tenancy_note: str
    privacy_note: str


# ---- metrics ----


class IndustryPartnerMetrics(BaseModel):
    total_partners: int
    active_partners: int
    recruiting_partners: int
    internship_partners: int
    placement_drives_total: int
    students_selected_total: int
    internship_students_total: int


class IndustryPartnerMetricsResponse(BaseModel):
    metrics: IndustryPartnerMetrics
    tenancy_note: str
