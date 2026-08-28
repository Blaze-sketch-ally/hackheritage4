"""API routes for students. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/students", tags=["students"])
