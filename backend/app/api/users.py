"""API routes for users. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])
