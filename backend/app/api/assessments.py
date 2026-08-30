"""API routes for assessments. Endpoints implemented feature-by-feature.

Phase 1D: read-only endpoints. Phase 1E: attempt creation. Every route
requires require_student() (which itself requires get_current_user()) and
reads/writes through build_user_client(access_token) -- never
get_supabase() -- so RLS stays the real access-control boundary. See
app.services.assessment_service for the actual queries.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.assessment import (
    AssessmentAttemptResponse,
    AssessmentListResponse,
    AssessmentQuestionResponse,
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


@router.get("/{assessment_id}/questions", response_model=list[AssessmentQuestionResponse])
def get_assessment_questions(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> list[AssessmentQuestionResponse]:
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

    try:
        questions = assessment_service.list_visible_questions(client, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the assessment's questions.",
        ) from exc

    return [AssessmentQuestionResponse(**question) for question in questions]


@router.post(
    "/{assessment_id}/attempts",
    response_model=AssessmentAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attempt(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> AssessmentAttemptResponse:
    """Start a new attempt for the calling student.

    No request body is accepted at all -- assessment_id comes from the
    URL, student_id from current_user.id, and every other column
    (status/score/total_marks/percentage/submitted_at) is either a fixed
    server-controlled value or left for the DB's own defaults. There is no
    field a client could inject here even by mistake.
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

    try:
        row = assessment_service.create_attempt(client, current_user.id, assessment_id)
    except assessment_service.DuplicateInProgressAttemptError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an in-progress attempt for this assessment.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start the attempt.",
        ) from exc

    return AssessmentAttemptResponse(**row)
