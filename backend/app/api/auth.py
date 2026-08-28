"""API routes for auth. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
