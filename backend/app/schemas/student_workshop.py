"""Pydantic schemas for the STUDENT side of Workshop discovery
(`industry_workshops`, database/migrations/024_industry_workshops.sql),
read-only, mirroring the shape of app.schemas.student_opportunity's
`OpportunityIndustry` / summary conventions.
"""

from pydantic import BaseModel


class StudentWorkshopIndustry(BaseModel):
    id: str
    company_name: str | None = None
    industry_sector: str | None = None
    logo_url: str | None = None


class StudentWorkshop(BaseModel):
    """One published workshop, normalized for the browse list and detail
    view (the same shape serves both -- workshops have no separate
    skills/match sub-resource)."""

    id: str
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None
    duration_days: int | None = None
    capacity: int | None = None
    eligibility_criteria: str | None = None
    application_deadline: str | None = None
    start_date: str | None = None
    status: str
    created_at: str | None = None
    industry: StudentWorkshopIndustry
    has_applied: bool


class StudentWorkshopListResponse(BaseModel):
    workshops: list[StudentWorkshop]
