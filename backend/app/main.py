from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    applications,
    assessments,
    attempts,
    industry,
    internships,
    jobs,
    skill_gap,
    skills,
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

app.include_router(applications.router, prefix="/api/v1")
app.include_router(assessments.router, prefix="/api/v1")
app.include_router(attempts.router, prefix="/api/v1")
app.include_router(industry.router, prefix="/api/v1")
app.include_router(internships.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(skills.router, prefix="/api/v1")
app.include_router(skill_gap.router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "AIC Portal API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
