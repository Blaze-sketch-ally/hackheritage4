"""Pydantic schemas for Institution Placement Drive Management
(backend/app/api/institution.py, /institution/placements...,
database/migrations/041_institution_placement_drives.sql).

A placement drive coordinates EXISTING entities -- it never duplicates
them. `job_id`/`job_title`/`company_name`/salary/location come from the
existing `jobs` + `industry_profiles` tables (Industry still owns all of
it); applicant status comes from the existing `applications` table;
interview info comes from the existing `interviews` table.
"placed" reuses the EXACT SAME definition as the Institution Dashboard
and Student Directory: an application with status = 'SELECTED'.

`eligible_department_ids` / `eligible_batches` / `eligible_skill_ids`
being empty means "no restriction on that criterion" -- see the
migration's own comment.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DriveStatus = Literal["DRAFT", "OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
DriveMode = Literal["ONSITE", "REMOTE", "HYBRID"]

DRIVE_STATUSES: tuple[str, ...] = ("DRAFT", "OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED")


def _blank_to_none(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    return cleaned


# ---- job picker (create-drive form) ----


class AvailableJobOption(BaseModel):
    """A currently PUBLISHED job -- platform-wide content, not owned by
    this institution. The create-drive form picks from this list instead
    of retyping a company's job description."""

    id: str
    title: str
    company_name: str | None
    work_mode: str | None
    employment_type: str | None
    location: str | None
    application_deadline: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None


class AvailableJobListResponse(BaseModel):
    jobs: list[AvailableJobOption]


# ---- create / update ----


class PlacementDriveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    application_deadline: date | None = None
    drive_date: date | None = None
    mode: DriveMode | None = None
    venue: str | None = Field(default=None, max_length=300)
    instructions: str | None = Field(default=None, max_length=3000)
    eligible_department_ids: list[str] = Field(default_factory=list)
    eligible_batches: list[int] = Field(default_factory=list)
    minimum_cgpa: float | None = Field(default=None, ge=0, le=10)
    eligible_skill_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data: object) -> object:
        return _blank_to_none(data)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Drive title cannot be blank.")
        return value


class PlacementDriveUpdate(BaseModel):
    """PUT /institution/placements/{id}. Partial -- only fields the
    client actually sent are changed. `job_id` and `status` are never
    editable here: the job a drive coordinates is fixed at creation, and
    status changes go through the dedicated
    PATCH /institution/placements/{id}/status endpoint so every
    transition passes through one validated code path."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    application_deadline: date | None = None
    drive_date: date | None = None
    mode: DriveMode | None = None
    venue: str | None = Field(default=None, max_length=300)
    instructions: str | None = Field(default=None, max_length=3000)
    eligible_department_ids: list[str] | None = None
    eligible_batches: list[int] | None = None
    minimum_cgpa: float | None = Field(default=None, ge=0, le=10)
    eligible_skill_ids: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data: object) -> object:
        return _blank_to_none(data)


class PlacementDriveStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DriveStatus


# ---- reads ----


class PlacementDriveSummary(BaseModel):
    id: str
    job_id: str
    job_title: str | None
    company_name: str | None
    location: str | None
    work_mode: str | None
    employment_type: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    job_status: str | None  # the underlying job's CURRENT status -- may
    # no longer be PUBLISHED for a historical drive (Part 27).

    title: str
    status: DriveStatus
    application_deadline: str | None
    drive_date: str | None
    mode: str | None
    venue: str | None

    eligible_department_ids: list[str]
    eligible_department_names: list[str]
    eligible_batches: list[int]
    minimum_cgpa: float | None
    eligible_skill_ids: list[str]
    eligible_skill_names: list[str]

    eligible_count: int
    applied_count: int
    selected_count: int

    created_at: str | None = None
    updated_at: str | None = None


class PlacementDriveDetail(PlacementDriveSummary):
    description: str | None
    instructions: str | None
    job_description: str | None


class PlacementDriveListResponse(BaseModel):
    drives: list[PlacementDriveSummary]


class EligibleStudent(BaseModel):
    """One of the institution's OWN linked students, with a fully
    explained eligibility verdict -- never an opaque true/false. Reasons
    is empty exactly when is_eligible is true."""

    id: str
    full_name: str | None
    username: str | None
    avatar_url: str | None
    department: str
    batch: int | None
    cgpa: float | None
    is_eligible: bool
    reasons: list[str]
    # None if this student has not applied to the drive's job at all.
    application_status: str | None


class DriveStudentsResponse(BaseModel):
    students: list[EligibleStudent]
    eligible_count: int
    applied_count: int


class DriveApplicantInterview(BaseModel):
    """Deliberately excludes `notes` (industry-private preparation
    notes) -- same exclusion as StudentInterviewSummary
    (institution_student.py)."""

    scheduled_at: str
    mode: str
    status: str


class DriveApplicant(BaseModel):
    application_id: str
    student_id: str
    full_name: str | None
    username: str | None
    department: str
    cgpa: float | None
    status: str
    applied_at: str | None
    interview: DriveApplicantInterview | None


class DriveApplicantsResponse(BaseModel):
    applicants: list[DriveApplicant]


class DepartmentPlacementBreakdown(BaseModel):
    department: str
    placed_count: int


class CompanyPlacementBreakdown(BaseModel):
    company_name: str
    selected_count: int


class PlacementOverviewResponse(BaseModel):
    """Drive-scoped placement analytics -- deliberately distinct from the
    Institution Dashboard's institution-wide student_metrics (which
    covers every application, not just drive-coordinated ones). Same
    underlying "placed = SELECTED" definition throughout; different
    scope, not a different definition. See this module's own docstring
    and the phase report for the exact boundary."""

    active_drives: int
    completed_drives: int
    # Unique institution students who applied to ANY drive-linked job.
    participating_students: int
    # Unique institution students SELECTED for any drive-linked job.
    placed_students: int
    # Count of SELECTED applications across drive-linked jobs -- can
    # exceed placed_students only if a student holds multiple selected
    # offers across DIFFERENT drives (Part 20) -- never conflated with it.
    total_selected_offers: int
    placement_rate: float | None
    department_breakdown: list[DepartmentPlacementBreakdown]
    company_breakdown: list[CompanyPlacementBreakdown]
