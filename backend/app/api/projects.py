"""API routes for projects. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/projects", tags=["projects"])
