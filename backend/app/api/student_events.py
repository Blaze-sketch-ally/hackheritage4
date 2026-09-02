"""API routes for the STUDENT side of event discovery.

Every route is guarded by require_student() and every read goes through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so Supabase RLS stays the real access-control boundary.
No `student_id` / `industry_id` / `owner_id` is ever read from a request:
these are read-only list/detail endpoints and there is no per-student
state to scope.

This is a read adapter over the existing `industry_workshops` table
(database/migrations/024_industry_workshops.sql unchanged): no `events`
table, no `event_id` column, no new status enum. A student-facing "event"
is one PUBLISHED industry workshop.

There is deliberately NO registration endpoint: the schema has no
registration/attendance table, and this phase does not invent one. Events
are strictly read-only for students -- there is no create/update/delete
route here, and RLS on `industry_workshops` gives a student no write path
regardless.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_event import (
    StudentEventDetail,
    StudentEventListResponse,
    StudentEventSummary,
)
from app.services import student_event_service

router = APIRouter(prefix="/student", tags=["student-events"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="This event is not available."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/events", response_model=StudentEventListResponse)
def list_events(
    work_mode: str | None = Query(default=None, description="ONSITE / REMOTE / HYBRID"),
    search: str | None = Query(default=None, max_length=200),
    current_user: CurrentUser = Depends(require_student),
) -> StudentEventListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_event_service.list_events(client, work_mode=work_mode, search=search)
    except Exception as exc:
        raise _server_error("load events") from exc
    return StudentEventListResponse(events=[StudentEventSummary(**row) for row in rows])


@router.get("/events/{event_id}", response_model=StudentEventDetail)
def get_event(
    event_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> StudentEventDetail:
    client = build_user_client(current_user.access_token)
    try:
        row = student_event_service.get_event(client, str(event_id))
    except Exception as exc:
        raise _server_error("load this event") from exc
    if row is None:
        raise _not_found()
    return StudentEventDetail(**row)
