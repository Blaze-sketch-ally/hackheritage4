"""API routes for jobs. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])
