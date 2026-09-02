"""Student-side Faculty <-> Student mentorship routes (Phase F4.2,
`faculty_student_mentorships`, 040_faculty_student_mentorships.sql).

No capability gate on this side -- faculty_mentor only gates the Faculty
participant; a Student needs no special permission to request, accept,
decline, withdraw, activate, complete, or end their own mentorships (RLS
still independently re-verifies the target Faculty holds faculty_mentor
at request-creation time). This router never exposes any mentee-data
bundle -- that concept only exists for the Faculty side (GET /faculty/
mentorships/{id}/student); a Student already has full access to their
own data through the existing Student-facing endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.faculty_student_mentorship import (
    CreateMentorshipRequest,
    FacultyStudentMentorshipListResponse,
    FacultyStudentMentorshipResponse,
    UpdateMentorshipStatusRequest,
)
from app.services import faculty_student_mentorship_service as service

router = APIRouter(prefix="/student/mentorships", tags=["student-mentorships"])


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=FacultyStudentMentorshipListResponse)
def list_my_mentorships(
    current_user: CurrentUser = Depends(require_student),
) -> FacultyStudentMentorshipListResponse:
    try:
        client = build_user_client(current_user.access_token)
        rows = service.list_for_student(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your mentorships") from exc
    return FacultyStudentMentorshipListResponse(mentorships=[FacultyStudentMentorshipResponse(**r) for r in rows])


@router.post("", response_model=FacultyStudentMentorshipResponse, status_code=status.HTTP_201_CREATED)
def request_mentorship(
    body: CreateMentorshipRequest,
    current_user: CurrentUser = Depends(require_student),
) -> FacultyStudentMentorshipResponse:
    """Request a specific Faculty member as mentor. `target_id` must be a
    real FACULTY account that currently holds faculty_mentor -- both
    re-verified independently by RLS."""
    try:
        client = build_user_client(current_user.access_token)
        row = service.create_student_request(client, current_user.id, body.target_id, body.focus_area)
    except service.DuplicateMentorshipError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except service.MentorshipAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("create this mentorship request") from exc
    return FacultyStudentMentorshipResponse(**row)


@router.get("/{mentorship_id}", response_model=FacultyStudentMentorshipResponse)
def get_mentorship(
    mentorship_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> FacultyStudentMentorshipResponse:
    try:
        client = build_user_client(current_user.access_token)
        row = service.get_mentorship(client, current_user.id, mentorship_id)
    except Exception as exc:
        raise _server_error("load this mentorship") from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentorship not found.")
    return FacultyStudentMentorshipResponse(**row)


@router.patch("/{mentorship_id}/status", response_model=FacultyStudentMentorshipResponse)
def update_mentorship_status(
    mentorship_id: str,
    body: UpdateMentorshipStatusRequest,
    current_user: CurrentUser = Depends(require_student),
) -> FacultyStudentMentorshipResponse:
    try:
        client = build_user_client(current_user.access_token)
        row = service.update_status(client, current_user.id, mentorship_id, body.status)
    except service.MentorshipInvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except service.MentorshipSelfActionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("update this mentorship") from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentorship not found.")
    return FacultyStudentMentorshipResponse(**row)
