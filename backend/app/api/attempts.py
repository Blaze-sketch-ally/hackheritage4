"""API routes for assessment attempts. Phase 1F: answer saving.

Deliberately a separate router from app.api.assessments, not nested under
/assessments: an answer is identified by (attempt_id, question_id) per
assessment_answers' own schema, not by assessment_id -- and
AssessmentAnswerRequest (Phase 1C) already carries question_id in the
body, which only makes sense if attempt_id is the URL's resource. Every
route requires require_student() (which itself requires
get_current_user()) and reads/writes through build_user_client
(access_token) -- never get_supabase() -- so RLS stays the real
access-control boundary. See app.services.assessment_service for the
actual queries.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.assessment import AssessmentAnswerRequest, AssessmentAnswerResponse
from app.services import assessment_service

router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.post("/{attempt_id}/answers", response_model=AssessmentAnswerResponse)
def save_answer(
    attempt_id: UUID,
    body: AssessmentAnswerRequest,
    current_user: CurrentUser = Depends(require_student),
) -> AssessmentAnswerResponse:
    """Save or revise the calling student's answer to one question in
    their own IN_PROGRESS attempt.

    Validation order matches ownership/state before content: the attempt
    must exist and belong to the caller, then be IN_PROGRESS, then the
    question must exist, belong to the attempt's own assessment, and be
    eligible (approved/active/OBJECTIVE) -- only then is the answer
    itself written. AssessmentAnswerRequest's own extra="forbid" already
    makes awarded_marks/is_correct/attempt ownership impossible for a
    client to submit; this function never reads a student_id from the
    request at all, only current_user.id.
    """
    client = build_user_client(current_user.access_token)

    try:
        attempt = assessment_service.get_own_attempt(client, current_user.id, attempt_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the attempt.",
        ) from exc

    if attempt is None:
        # Same response whether the attempt never existed or belongs to
        # someone else -- never reveal which.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    if attempt["status"] != "IN_PROGRESS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This attempt is no longer in progress.",
        )

    try:
        question = assessment_service.get_visible_question(
            client, UUID(attempt["assessment_id"]), body.question_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the question.",
        ) from exc

    if question is None:
        # Same response whether the question doesn't exist, belongs to a
        # different assessment, or isn't currently eligible -- never
        # reveal which.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")

    try:
        row = assessment_service.save_answer(
            client,
            attempt_id,
            body.question_id,
            body.answer_text,
            body.selected_option_ids,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save the answer.",
        ) from exc

    return AssessmentAnswerResponse(**row)
