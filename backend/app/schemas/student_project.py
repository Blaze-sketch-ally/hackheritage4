"""Pydantic schemas for the STUDENT side of Project discovery
(`industry_projects`, database/migrations/022_industry_projects.sql),
read-only. Mirrors app.schemas.student_workshop.
"""

from pydantic import BaseModel


class StudentProjectIndustry(BaseModel):
    id: str
    company_name: str | None = None
    industry_sector: str | None = None
    logo_url: str | None = None


class StudentProject(BaseModel):
    id: str
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None
    duration_months: int | None = None
    team_size: int | None = None
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    start_date: str | None = None
    status: str
    created_at: str | None = None
    industry: StudentProjectIndustry
    has_applied: bool


class StudentProjectListResponse(BaseModel):
    projects: list[StudentProject]
