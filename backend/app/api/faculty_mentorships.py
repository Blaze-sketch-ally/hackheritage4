"""Faculty-side Faculty <-> Student mentorship routes (Phase F4.2,
`faculty_student_mentorships`, 040_faculty_student_mentorships.sql).

Every route goes through build_user_client(current_user.access_token) --
never get_supabase()/service_role -- so RLS stays the real access-control
boundary; require_faculty()/require_mentor_capability() are the app-layer
complement, not a replacement. Listing/reading a caller's own mentorships
only needs require_faculty() (a Faculty member can see their own
historical mentorships even if their capability was later revoked);
every route that creates or mutates a mentorship, or reads a mentee's
data bundle, requires require_mentor_capability() -- matching exactly
what the RLS policies in 040 independently enforce.

Do NOT add a directory/browse endpoint here (e.g. "list students I could
mentor") -- explicitly out of scope (no broad Faculty student directory).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_faculty, require_mentor_capability
from app.core.security import build_user_client
from app.schemas.faculty_student_mentorship import (
    CreateMentorshipRequest,
    FacultyStudentMentorshipListResponse,
    FacultyStudentMentorshipResponse,
    MenteeProfileBundleResponse,
    MentorshipNoteResponse,
    UpdateMentorshipStatusRequest,
    UpsertMentorshipNoteRequest,
)
from app.services import faculty_student_mentorship_service as service

router = APIRouter(prefix="/faculty/mentorships", tags=["faculty-mentorships"])


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=FacultyStudentMentorshipListResponse)
def list_my_mentorships(
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyStudentMentorshipListResponse:
    """The caller's own mentorships, at any status."""
    try:
        client = build_user_client(current_user.access_token)
        rows = service.list_for_faculty(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your mentorships") from exc
    return FacultyStudentMentorshipListResponse(mentorships=[FacultyStudentMentorshipResponse(**r) for r in rows])


@router.post("", response_model=FacultyStudentMentorshipResponse, status_code=status.HTTP_201_CREATED)
def request_mentorship(
    body: CreateMentorshipRequest,
    current_user: CurrentUser = Depends(require_mentor_capability),
) -> FacultyStudentMentorshipResponse:
    """Request mentoring a specific student. `target_id` must be a real
    STUDENT account -- re-verified independently by RLS."""
    try:
        client = build_user_client(current_user.access_token)
        row = service.create_faculty_request(client, current_user.id, body.target_id, body.focus_area)
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
    current_user: CurrentUser = Depends(require_faculty),
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
    current_user: CurrentUser = Depends(require_mentor_capability),
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


@router.get("/{mentorship_id}/student", response_model=MenteeProfileBundleResponse)
def get_mentee_profile(
    mentorship_id: str,
    current_user: CurrentUser = Depends(require_mentor_capability),
) -> MenteeProfileBundleResponse:
    """The authorized subset of the mentee's data -- 404 if the
    mentorship doesn't exist or isn't the caller's own, 409 if it exists
    but isn't ACTIVE yet."""
    try:
        client = build_user_client(current_user.access_token)
        bundle = service.get_mentee_bundle(client, current_user.id, mentorship_id)
    except service.MentorshipNotActiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mentorship is not yet ACTIVE -- no student data is available.",
        ) from exc
    except Exception as exc:
        raise _server_error("load this mentee's information") from exc
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentorship not found.")
    return MenteeProfileBundleResponse(**bundle)


@router.get("/{mentorship_id}/notes", response_model=MentorshipNoteResponse | None)
def get_mentorship_note(
    mentorship_id: str,
    current_user: CurrentUser = Depends(require_mentor_capability),
) -> MentorshipNoteResponse | None:
    """The caller's own private note for this mentorship, if any. RLS
    ("Faculty can view their own mentorship notes") makes this
    impossible to use to read another Faculty member's note even if the
    id is guessed."""
    try:
        client = build_user_client(current_user.access_token)
        row = service.get_note(client, current_user.id, mentorship_id)
    except Exception as exc:
        raise _server_error("load this mentorship's note") from exc
    return MentorshipNoteResponse(**row) if row is not None else None


@router.put("/{mentorship_id}/notes", response_model=MentorshipNoteResponse)
def upsert_mentorship_note(
    mentorship_id: str,
    body: UpsertMentorshipNoteRequest,
    current_user: CurrentUser = Depends(require_mentor_capability),
) -> MentorshipNoteResponse:
    """Create or replace the caller's own private note for this
    mentorship. RLS's own INSERT policy independently re-verifies the
    caller actually owns the referenced mentorship, so a mentorship_id
    the caller doesn't own is rejected at the database layer even if
    this route's own checks were ever removed."""
    try:
        client = build_user_client(current_user.access_token)
        row = service.upsert_note(client, current_user.id, mentorship_id, body.note)
    except Exception as exc:
        raise _server_error("save this note") from exc
    return MentorshipNoteResponse(**row)
