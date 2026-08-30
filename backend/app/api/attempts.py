"""API routes for assessment attempts. Phase 1F: answer saving.
Phase 1G: submission.

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
from app.schemas.assessment import (
    AssessmentAnswerRequest,
    AssessmentAnswerResponse,
    AssessmentAttemptResponse,
)
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


@router.post("/{attempt_id}/submit", response_model=AssessmentAttemptResponse)
def submit_attempt(
    attempt_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> AssessmentAttemptResponse:
    """Mark the calling student's own IN_PROGRESS attempt as submitted.

    This does NOT complete or score the attempt -- see the module
    docstring and app.services.assessment_service.mark_attempt_submitted.
    status stays IN_PROGRESS; only submitted_at is set. Phase 1H owns the
    later COMPLETED transition, which the database itself only allows a
    trusted service_role write to perform (see
    assessment_attempts_completed_has_score and
    prevent_self_attempt_scoring in 004_assessments.sql) -- this endpoint
    never attempts it and never reads answer keys or computes a score.

    No request body is accepted at all -- there is nothing for a client
    to legitimately supply here, so there is no field to forbid.
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

    if attempt["submitted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This attempt has already been submitted.",
        )

    try:
        assessment_id = UUID(attempt["assessment_id"])
        eligible_question_ids = {
            question["id"]
            for question in assessment_service.list_visible_questions(client, assessment_id)
        }
        answered_question_ids = assessment_service.get_answered_question_ids(client, attempt_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify submission eligibility.",
        ) from exc

    # Vacuously satisfied when eligible_question_ids is empty -- an
    # assessment with zero currently-eligible questions has nothing to
    # require an answer for, matching how Phase 1D already treats a
    # zero-question assessment as a normal (not exceptional) state.
    if not eligible_question_ids.issubset(answered_question_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All assessment questions must be answered before submission.",
        )

    try:
        row = assessment_service.mark_attempt_submitted(client, attempt_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not submit the attempt.",
        ) from exc

    if row is None:
        # Raced with another submission of the same attempt between our
        # check above and the guarded UPDATE -- same conflict either way.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This attempt has already been submitted.",
        )

    return AssessmentAttemptResponse(**row)
