"""API routes for recommendations. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
