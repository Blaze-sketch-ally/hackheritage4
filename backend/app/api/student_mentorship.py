"""API routes for the STUDENT side of mentorship discovery.

Every route is guarded by require_student() and every read goes through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so Supabase RLS stays the real access-control boundary.
No `student_id` / `industry_id` / `owner_id` / `mentor_id` is ever read
from a request as an ownership mechanism: these are read-only list/detail
endpoints and there is no per-student state to scope.

This is a read adapter over the existing `industry_mentorship` table
(database/migrations/025_industry_mentorship.sql unchanged): no
`mentorship` table, no `mentor_id` column, no new status enum. A
student-facing "mentorship opportunity" is one PUBLISHED
`industry_mentorship` row.

There is deliberately NO request endpoint: the schema has no
request/pairing/enrollment table, and this phase does not invent one (an
Industry-side responder API/UI does not exist, so a request flow would be
a dead end). Mentorship is strictly read-only for students -- there is no
create/update/delete route here, and RLS on `industry_mentorship` gives a
student no write path regardless.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_mentorship import (
    StudentMentorshipDetail,
    StudentMentorshipListResponse,
    StudentMentorshipSummary,
)
from app.services import student_mentorship_service

router = APIRouter(prefix="/student", tags=["student-mentorship"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="This mentorship opportunity is not available.",
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/mentorship", response_model=StudentMentorshipListResponse)
def list_mentorship(
    work_mode: str | None = Query(default=None, description="ONSITE / REMOTE / HYBRID"),
    search: str | None = Query(default=None, max_length=200),
    current_user: CurrentUser = Depends(require_student),
) -> StudentMentorshipListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_mentorship_service.list_mentorships(
            client, work_mode=work_mode, search=search
        )
    except Exception as exc:
        raise _server_error("load mentorship opportunities") from exc
    return StudentMentorshipListResponse(
        mentorship_opportunities=[StudentMentorshipSummary(**row) for row in rows]
    )


@router.get("/mentorship/{mentorship_id}", response_model=StudentMentorshipDetail)
def get_mentorship(
    mentorship_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> StudentMentorshipDetail:
    client = build_user_client(current_user.access_token)
    try:
        row = student_mentorship_service.get_mentorship(client, str(mentorship_id))
    except Exception as exc:
        raise _server_error("load this mentorship opportunity") from exc
    if row is None:
        raise _not_found()
    return StudentMentorshipDetail(**row)
