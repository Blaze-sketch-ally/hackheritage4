from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin_evaluator_assignments,
    admin_faculty,
    admin_mentorships,
    applications,
    assessments,
    attempts,
    career_roles,
    certificates,
    faculty,
    faculty_engagements,
    faculty_evaluations,
    faculty_mentorships,
    faculty_opportunities,
    industry,
    industry_collaborations,
    industry_faculty_opportunities,
    industry_mentorship_opportunities,
    industry_projects,
    industry_trainings,
    industry_workshops,
    institution_faculty_opportunities,
    internship_programs,
    internship_workspaces,
    internships,
    interviews,
    jobs,
    portfolio,
    questions,
    student_events,
    student_internship_workspaces,
    student_learning,
    student_mentorship_opportunities,
    student_mentorships,
    student_notifications,
    student_opportunities,
    student_recommendations,
)
from app.core.config import settings

app = FastAPI(title="AIC Portal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assessments.router, prefix="/api/v1")
app.include_router(attempts.router, prefix="/api/v1")
app.include_router(questions.router, prefix="/api/v1")
app.include_router(faculty.router, prefix="/api/v1")
app.include_router(admin_faculty.router, prefix="/api/v1")
app.include_router(admin_evaluator_assignments.router, prefix="/api/v1")
app.include_router(faculty_opportunities.router, prefix="/api/v1")
app.include_router(faculty_engagements.router, prefix="/api/v1")
app.include_router(faculty_evaluations.router, prefix="/api/v1")
app.include_router(faculty_mentorships.router, prefix="/api/v1")
app.include_router(student_mentorships.router, prefix="/api/v1")
app.include_router(student_mentorship_opportunities.router, prefix="/api/v1")
app.include_router(admin_mentorships.router, prefix="/api/v1")
app.include_router(industry_faculty_opportunities.router, prefix="/api/v1")
app.include_router(institution_faculty_opportunities.router, prefix="/api/v1")
app.include_router(career_roles.router, prefix="/api/v1")
app.include_router(internships.router, prefix="/api/v1")
app.include_router(internship_programs.router, prefix="/api/v1")
app.include_router(internship_workspaces.router, prefix="/api/v1")
app.include_router(student_internship_workspaces.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(interviews.router, prefix="/api/v1")
app.include_router(student_opportunities.router, prefix="/api/v1")
app.include_router(student_events.router, prefix="/api/v1")
app.include_router(student_learning.router, prefix="/api/v1")
app.include_router(student_recommendations.router, prefix="/api/v1")
app.include_router(student_notifications.router, prefix="/api/v1")
app.include_router(certificates.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(industry.router, prefix="/api/v1")
app.include_router(industry_projects.router, prefix="/api/v1")
app.include_router(industry_trainings.router, prefix="/api/v1")
app.include_router(industry_workshops.router, prefix="/api/v1")
app.include_router(industry_mentorship_opportunities.router, prefix="/api/v1")
app.include_router(industry_collaborations.router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "AIC Portal API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
