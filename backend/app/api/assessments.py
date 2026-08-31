"""API routes for assessments. Endpoints implemented feature-by-feature.

Phase 1D: read-only endpoints. Phase 1E/1K: attempt creation, now backed
by the server-side random-question-selection RPC
(015_assessment_verification.sql). Every route requires require_student()
(which itself requires get_current_user()).

Most routes read/write through build_user_client(access_token) -- never
get_supabase() -- so RLS stays the real access-control boundary. The one
exception is create_attempt, which -- exactly like attempts.score_attempt
-- verifies the assessment via the user-scoped client FIRST, and only
reaches for get_supabase() afterward, for the one operation
(create_assessment_attempt(), service_role-only) that RLS structurally
forbids everyone else from performing. See
app.services.assessment_service for the actual queries.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.database.supabase import get_supabase
from app.schemas.assessment import (
    AssessmentAttemptResponse,
    AssessmentListResponse,
    AssessmentResponse,
)
from app.services import assessment_service

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.get("", response_model=AssessmentListResponse)
def list_assessments(
    current_user: CurrentUser = Depends(require_student),
) -> AssessmentListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = assessment_service.list_active_assessments(client)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load assessments.",
        ) from exc
    return AssessmentListResponse(assessments=rows)


@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> AssessmentResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = assessment_service.get_active_assessment(client, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the assessment.",
        ) from exc

    if row is None:
        # Same response whether the assessment never existed or exists but
        # is inactive -- never reveal which.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")

    return AssessmentResponse(**row)


@router.get("/{assessment_id}/attempts/current", response_model=AssessmentAttemptResponse)
def get_current_attempt(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> AssessmentAttemptResponse:
    """The calling student's own IN_PROGRESS attempt at this assessment, if
    any -- 404 otherwise. Lets the frontend resume a genuinely in-progress
    attempt (fetching its frozen questions via GET /attempts/{id}/questions)
    instead of only discovering one exists via a 409 from POST .../attempts.
    """
    client = build_user_client(current_user.access_token)

    try:
        row = assessment_service.get_in_progress_attempt(client, current_user.id, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the attempt.",
        ) from exc

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No in-progress attempt.")

    return AssessmentAttemptResponse(**row)


@router.post(
    "/{assessment_id}/attempts",
    response_model=AssessmentAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attempt(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> AssessmentAttemptResponse:
    """Start a new attempt for the calling student, with its question
    selection randomly drawn from the approved question bank and
    permanently frozen in the same atomic operation
    (create_assessment_attempt(), 015_assessment_verification.sql).

    No request body is accepted at all -- assessment_id comes from the
    URL, student_id from current_user.id, and every other column
    (status/score/total_marks/percentage/submitted_at) is either a fixed
    server-controlled value or left for the DB's own defaults. There is no
    field a client could inject here even by mistake, and the client never
    chooses -- or even sees -- which questions get selected.
    """
    client = build_user_client(current_user.access_token)

    try:
        assessment = assessment_service.get_active_assessment(client, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the assessment.",
        ) from exc

    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")

    service_client = get_supabase()
    try:
        row = assessment_service.create_attempt(service_client, current_user.id, assessment_id)
    except assessment_service.DuplicateInProgressAttemptError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an in-progress attempt for this assessment.",
        ) from exc
    except assessment_service.AssessmentNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This assessment isn't ready to take yet. Please try again later.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start the attempt.",
        ) from exc

    return AssessmentAttemptResponse(**row)
