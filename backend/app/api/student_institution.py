"""API routes for the Student "My Institution" portal.

Every route is guarded by require_student() and every read goes through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so Supabase RLS (including the new student-facing SELECT
policies added by database/migrations/
047_student_institution_visibility.sql) stays the real access-control
boundary. `student_id` is always current_user.id, never read from a
request body or query parameter.

One consolidated endpoint, matching this project's own "prefer a small
number of consolidated endpoints" convention (Institution Overview,
Institution Internship Overview, etc.) rather than one route per section
-- the whole My Institution workspace is one page, one server-side
aggregation call.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_institution import StudentInstitutionResponse
from app.services import student_institution_service

router = APIRouter(prefix="/student", tags=["student-institution"])


@router.get("/institution", response_model=StudentInstitutionResponse)
def get_my_institution(
    current_user: CurrentUser = Depends(require_student),
) -> StudentInstitutionResponse:
    """Everything the authenticated student's own institution has
    curated/announced for them: identity, placement drives, curated
    internships, events and a derived activity feed. Returns
    `linked: false` with empty sections (never a 404/error) when the
    student has no verified institution yet -- the frontend then shows
    the existing connect/pending UI (institution_link_requests) instead."""
    client = build_user_client(current_user.access_token)
    try:
        data = student_institution_service.get_my_institution(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your institution. Please try again.",
        ) from exc
    return StudentInstitutionResponse(**data)
