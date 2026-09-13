"""Pydantic schemas for Project applications
(`industry_project_applications`, database/migrations/057_project_applications.sql).

Same shape as app.schemas.workshop_application. Projects intentionally
skip the Internship/Job interview workflow: Apply -> Shortlist -> Select
-> Active -> Completed, with Reject reachable from Applied/Shortlisted and
Withdraw owned by the student.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ProjectApplicationStatus = Literal[
    "APPLIED", "SHORTLISTED", "SELECTED", "ACTIVE", "REJECTED", "WITHDRAWN", "COMPLETED"
]

PROJECT_APPLICATION_STATUSES: tuple[str, ...] = (
    "APPLIED",
    "SHORTLISTED",
    "SELECTED",
    "ACTIVE",
    "REJECTED",
    "WITHDRAWN",
    "COMPLETED",
)

# Values an INDUSTRY account is allowed to set. WITHDRAWN belongs to the
# student; APPLIED is the initial state only.
IndustrySettableProjectStatus = Literal["SHORTLISTED", "SELECTED", "ACTIVE", "REJECTED", "COMPLETED"]


class ProjectApplicationOpportunity(BaseModel):
    id: str
    title: str
    status: str


class ProjectApplicationResponse(BaseModel):
    id: str
    student_id: str
    student_name: str | None = None
    institution_name: str | None = None
    department: str | None = None
    graduation_year: int | None = None
    skills: list[str] | None = None
    industry_id: str
    project_id: str
    status: str
    applied_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    project: ProjectApplicationOpportunity | None = None


class ProjectApplicationListResponse(BaseModel):
    applications: list[ProjectApplicationResponse]


class ProjectApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectApplicationStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IndustrySettableProjectStatus
