"""API routes for applications. Endpoints implemented feature-by-feature."""
from fastapi import APIRouter

router = APIRouter(prefix="/applications", tags=["applications"])
