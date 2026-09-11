import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    analytics,
    applications,
    assessments,
    attempts,
    certificates,
    industry,
    industry_collaborations,
    industry_job_training,
    industry_mentorship_opportunities,
    industry_projects,
    industry_trainings,
    industry_workshops,
    institution,
    institution_link_requests,
    internship_programs,
    internship_workspaces,
    internships,
    interviews,
    job_training_programs,
    jobs,
    skill_gap,
    skills,
    student_events,
    student_institution,
    student_internship_workspaces,
    student_job_training,
    student_learning,
    student_mentorship,
    student_notifications,
    student_opportunities,
    student_portfolio,
    student_recommendations,
)
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")

app = FastAPI(title="AIC Portal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler for anything a route/dependency didn't already
    turn into an HTTPException. Logs the real error server-side (visible in
    the deployment platform's logs) but never leaks it to the client --
    every other error path in this app already returns a safe, generic
    message (see frontend/lib/api.ts), and this keeps that guarantee even
    for a genuinely unexpected exception."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
    )

app.include_router(analytics.router, prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(assessments.router, prefix="/api/v1")
app.include_router(attempts.router, prefix="/api/v1")
app.include_router(certificates.router, prefix="/api/v1")
app.include_router(industry.router, prefix="/api/v1")
app.include_router(industry_collaborations.router, prefix="/api/v1")
app.include_router(industry_job_training.router, prefix="/api/v1")
app.include_router(industry_mentorship_opportunities.router, prefix="/api/v1")
app.include_router(industry_projects.router, prefix="/api/v1")
app.include_router(industry_trainings.router, prefix="/api/v1")
app.include_router(industry_workshops.router, prefix="/api/v1")
app.include_router(institution.router, prefix="/api/v1")
app.include_router(institution_link_requests.router, prefix="/api/v1")
app.include_router(internship_programs.router, prefix="/api/v1")
app.include_router(internship_workspaces.router, prefix="/api/v1")
app.include_router(internships.router, prefix="/api/v1")
app.include_router(interviews.router, prefix="/api/v1")
app.include_router(job_training_programs.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(skills.router, prefix="/api/v1")
app.include_router(skill_gap.router, prefix="/api/v1")
app.include_router(student_events.router, prefix="/api/v1")
app.include_router(student_institution.router, prefix="/api/v1")
app.include_router(student_internship_workspaces.router, prefix="/api/v1")
app.include_router(student_job_training.router, prefix="/api/v1")
app.include_router(student_learning.router, prefix="/api/v1")
app.include_router(student_mentorship.router, prefix="/api/v1")
app.include_router(student_notifications.router, prefix="/api/v1")
app.include_router(student_opportunities.router, prefix="/api/v1")
app.include_router(student_portfolio.router, prefix="/api/v1")
app.include_router(student_recommendations.router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "AIC Portal API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
