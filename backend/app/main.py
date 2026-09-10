from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin_evaluator_assignments,
    admin_faculty,
    admin_mentorships,
    analytics,
    applications,
    assessments,
    attempts,
    career_roles,
    certificates,
    faculty,
    faculty_engagements,
    faculty_evaluations,
    faculty_mentorships,
    faculty_notifications,
    faculty_opportunities,
    faculty_reconciliation,
    industry,
    industry_collaborations,
    industry_faculty_opportunities,
    industry_job_training,
    industry_mentorship_opportunities,
    industry_projects,
    industry_trainings,
    industry_workshops,
    institution,
    institution_faculty_opportunities,
    institution_link_requests,
    internship_programs,
    internship_workspaces,
    internships,
    interviews,
    job_training_programs,
    jobs,
    portfolio,
    questions,
    skill_gap,
    student_events,
    student_institution,
    student_internship_workspaces,
    student_job_training,
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
app.include_router(faculty_notifications.router, prefix="/api/v1")
app.include_router(faculty_reconciliation.router, prefix="/api/v1")
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
app.include_router(industry_job_training.router, prefix="/api/v1")

# Institution portal + Job Training (integration pass)
app.include_router(institution.router, prefix="/api/v1")
app.include_router(institution_link_requests.router, prefix="/api/v1")
app.include_router(job_training_programs.router, prefix="/api/v1")
app.include_router(student_institution.router, prefix="/api/v1")
app.include_router(student_job_training.router, prefix="/api/v1")

# Skill Gap + Industry Analytics (implemented but previously unmounted)
app.include_router(skill_gap.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "AIC Portal API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
