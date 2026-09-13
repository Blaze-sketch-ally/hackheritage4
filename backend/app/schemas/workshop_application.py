"""Pydantic schemas for Workshop applications
(`industry_workshop_applications`, database/migrations/056_workshop_applications.sql).

Field names and constraints match that migration exactly. An application
row is created by a STUDENT registering for a PUBLISHED workshop.
Industry's involvement is read + a single mutable field: `status`.
`student_name`/`institution_name`/`department`/`graduation_year`/`skills`
are resolved server-side through `public.workshop_applicant_profiles`, a
SECURITY DEFINER function scoped to the same ownership predicate as this
table's own RLS SELECT policy -- never a raw student_id shown as identity.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

WorkshopApplicationStatus = Literal["APPLIED", "ACCEPTED", "REJECTED", "WITHDRAWN", "COMPLETED"]

WORKSHOP_APPLICATION_STATUSES: tuple[str, ...] = (
    "APPLIED",
    "ACCEPTED",
    "REJECTED",
    "WITHDRAWN",
    "COMPLETED",
)

# Values an INDUSTRY account is allowed to set. WITHDRAWN belongs to the
# student; APPLIED is the initial state only.
IndustrySettableWorkshopStatus = Literal["ACCEPTED", "REJECTED", "COMPLETED"]


class WorkshopApplicationOpportunity(BaseModel):
    id: str
    title: str
    status: str


class WorkshopApplicationResponse(BaseModel):
    id: str
    student_id: str
    student_name: str | None = None
    institution_name: str | None = None
    department: str | None = None
    graduation_year: int | None = None
    skills: list[str] | None = None
    industry_id: str
    workshop_id: str
    status: str
    applied_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    workshop: WorkshopApplicationOpportunity | None = None


class WorkshopApplicationListResponse(BaseModel):
    applications: list[WorkshopApplicationResponse]


class WorkshopApplyRequest(BaseModel):
    """POST body for a student registering for a workshop. Empty on
    purpose -- there is no cover note field on this table (unlike
    `applications`); kept as a model (not an empty POST) so the route
    shape matches the rest of the API and can grow a field later without
    breaking callers."""

    model_config = ConfigDict(extra="forbid")


class WorkshopApplicationStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IndustrySettableWorkshopStatus
