"""API routes for courses. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/courses", tags=["courses"])
