"""API routes for assessments. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/assessments", tags=["assessments"])
