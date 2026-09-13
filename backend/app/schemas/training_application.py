"""Pydantic schemas for Training applications
(`industry_training_applications`, database/migrations/059_training_applications.sql).

Exact mirror of app.schemas.workshop_application -- see that module's
docstring. "ACCEPTED" is the DB value; the UI label is "Enrolled" (see
frontend/types/training-application.ts) -- no separate ACTIVE status
exists in the database for this friendlier wording.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

TrainingApplicationStatus = Literal["APPLIED", "ACCEPTED", "REJECTED", "WITHDRAWN", "COMPLETED"]

TRAINING_APPLICATION_STATUSES: tuple[str, ...] = (
    "APPLIED",
    "ACCEPTED",
    "REJECTED",
    "WITHDRAWN",
    "COMPLETED",
)

IndustrySettableTrainingStatus = Literal["ACCEPTED", "REJECTED", "COMPLETED"]


class TrainingApplicationOpportunity(BaseModel):
    id: str
    title: str
    status: str


class TrainingApplicationResponse(BaseModel):
    id: str
    student_id: str
    student_name: str | None = None
    institution_name: str | None = None
    department: str | None = None
    graduation_year: int | None = None
    skills: list[str] | None = None
    industry_id: str
    training_id: str
    status: str
    applied_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    training: TrainingApplicationOpportunity | None = None


class TrainingApplicationListResponse(BaseModel):
    applications: list[TrainingApplicationResponse]


class TrainingApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrainingApplicationStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IndustrySettableTrainingStatus
