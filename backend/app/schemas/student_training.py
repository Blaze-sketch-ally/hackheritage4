"""Pydantic schemas for the STUDENT side of Training discovery
(`industry_training`, database/migrations/023_industry_training.sql),
read-only. Mirrors app.schemas.student_workshop.
"""

from pydantic import BaseModel


class StudentTrainingIndustry(BaseModel):
    id: str
    company_name: str | None = None
    industry_sector: str | None = None
    logo_url: str | None = None


class StudentTraining(BaseModel):
    id: str
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None
    duration_months: int | None = None
    capacity: int | None = None
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    start_date: str | None = None
    status: str
    created_at: str | None = None
    industry: StudentTrainingIndustry
    has_applied: bool


class StudentTrainingListResponse(BaseModel):
    trainings: list[StudentTraining]
