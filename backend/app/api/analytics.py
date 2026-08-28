"""API routes for analytics. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["analytics"])
