"""API routes for notifications. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/notifications", tags=["notifications"])
