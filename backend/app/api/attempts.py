"""API routes for assessment attempts. Phase 1F: answer saving.
Phase 1G: submission. Phase 1H: scoring. Phase 1I: results.

Deliberately a separate router from app.api.assessments, not nested under
/assessments: an answer is identified by (attempt_id, question_id) per
assessment_answers' own schema, not by assessment_id -- and
AssessmentAnswerRequest (Phase 1C) already carries question_id in the
body, which only makes sense if attempt_id is the URL's resource. Every
route requires require_student() (which itself requires
get_current_user()).

Every route except one reads/writes through build_user_client
(access_token) only, never get_supabase(), so RLS stays the real
access-control boundary. The one exception is score_attempt (Phase 1H):
it still verifies ownership via build_user_client() first -- exactly like
every other route -- and only reaches for get_supabase() afterward, for
the one operation RLS structurally forbids everyone else from performing.
get_attempt_result (Phase 1I) is NOT an exception: answer-key data for a
COMPLETED, owned attempt is readable through RLS alone (see "Students can
view answer keys for their own completed attempts" in 004_assessments.sql),
so it uses build_user_client() throughout, like every other route besides
score_attempt. See app.services.assessment_service for the actual queries.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.database.supabase import get_supabase
from app.schemas.assessment import (
    AssessmentAnswerKeyResponse,
    AssessmentAnswerRequest,
    AssessmentAnswerResponse,
    AssessmentAttemptResponse,
    AssessmentQuestionResponse,
    AssessmentResultQuestionResponse,
    AssessmentResultResponse,
    SubmitAttemptResponse,
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


@router.post("/{attempt_id}/score", response_model=SubmitAttemptResponse)
def score_attempt(
    attempt_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> SubmitAttemptResponse:
    """Trigger trusted backend scoring for the calling student's own
    submitted attempt, completing it.

    Ownership/eligibility is verified TWICE, deliberately, in two
    different trust domains:
      1. Here, via build_user_client() + get_own_attempt() -- the exact
         same RLS-respecting path every other route in this file uses.
         Only after this passes does get_supabase() ever get constructed.
      2. Again, inside score_assessment_attempt() itself (the Postgres
         function), via its own `select ... for update ... where id = ...
         and student_id = ...` -- defense in depth against this Python
         code ever calling the RPC with the wrong ids, and the mechanism
         that makes concurrent scoring attempts on the same attempt safe
         (the second one blocks on the row lock, then sees the first
         one's COMPLETED status and is rejected as 409, not raced).

    All scoring math (which questions count, how each type is compared,
    total_marks/score/percentage) happens entirely inside that Postgres
    function, as one atomic transaction -- this route never reads answer
    keys, never computes a score, and never calls an AI/LLM anywhere.

    No request body is accepted at all -- there is nothing for a client
    to legitimately supply here.
    """
    user_client = build_user_client(current_user.access_token)

    try:
        attempt = assessment_service.get_own_attempt(user_client, current_user.id, attempt_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the attempt.",
        ) from exc

    if attempt is None:
        # Same response whether the attempt never existed or belongs to
        # someone else -- never reveal which.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    if attempt["status"] != "IN_PROGRESS" or attempt["submitted_at"] is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This attempt is not eligible for scoring.",
        )

    service_client = get_supabase()
    try:
        row = assessment_service.score_attempt(service_client, attempt_id, current_user.id)
    except assessment_service.AttemptNotEligibleForScoringError:
        # Lost a race against a concurrent scoring call for the same
        # attempt -- the RPC's own row lock caught what our check above,
        # taken slightly earlier, could not.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This attempt is not eligible for scoring.",
        ) from None
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not score the attempt.",
        ) from exc

    return SubmitAttemptResponse(**row)


@router.get("/{attempt_id}/result", response_model=AssessmentResultResponse)
def get_attempt_result(
    attempt_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> AssessmentResultResponse:
    """The calling student's own full post-completion result: the attempt
    summary plus, per historically-scored question, the question/options,
    the student's own answer, and the answer key.

    Ownership and completion are both re-checked here, independently of
    RLS: get_own_attempt() already scopes to the caller via
    build_user_client(), and RLS itself would refuse an answer-key read
    for anything but a COMPLETED attempt -- but this route still checks
    attempt["status"] explicitly (defense in depth, same pattern as every
    other route in this file) so an IN_PROGRESS/ABANDONED attempt gets a
    clean 409 rather than a confusing empty/partial result.

    The question population is NOT re-derived from current eligibility
    (list_visible_questions() is never called here) -- see
    assessment_service.get_attempt_result_rows for why that would silently
    diverge from what was actually scored. score/total_marks/percentage
    are read as-is from the attempt row; awarded_marks/is_correct are read
    as-is from each answer row. Nothing here recalculates anything, and
    this route never invokes score_attempt() or the scoring RPC.

    A successful response must contain the COMPLETE historically-scored
    question population represented by assessment_answers for this
    attempt -- never a silently partial one. If any row's "question" or
    "answer_key" embed came back None (RLS-invisible because the
    question/assessment was deactivated after this attempt completed --
    see get_attempt_result_rows), that is treated as a hard failure: a
    generic 500, not a result quietly missing that question. This is a
    deliberate approved choice over dropping the affected question, since
    a student silently seeing fewer questions than were actually scored
    would be worse than an explicit error.
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

    if attempt["status"] != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This attempt has not been completed yet.",
        )

    try:
        rows = assessment_service.get_attempt_result_rows(client, attempt_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the result.",
        ) from exc

    try:
        questions = []
        for row in rows:
            if row.get("question") is None or row.get("answer_key") is None:
                # A historically-scored question (it has an
                # assessment_answers row) whose question or answer-key
                # content is no longer RLS-visible -- see the module/route
                # docstrings for why this is a hard failure rather than a
                # silently incomplete result. Never construct a partial
                # AssessmentResultResponse.
                raise RuntimeError(
                    "Historical question/answer-key data unavailable for "
                    f"question {row['question_id']} in attempt {attempt_id}."
                )
            questions.append(
                AssessmentResultQuestionResponse(
                    question=AssessmentQuestionResponse(**row["question"]),
                    student_answer=AssessmentAnswerResponse(
                        id=row["id"],
                        attempt_id=row["attempt_id"],
                        question_id=row["question_id"],
                        answer_text=row["answer_text"],
                        selected_option_ids=row["selected_option_ids"],
                        awarded_marks=row["awarded_marks"],
                        is_correct=row["is_correct"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    ),
                    answer_key=AssessmentAnswerKeyResponse(**row["answer_key"]),
                )
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not construct the result.",
        ) from exc

    return AssessmentResultResponse(
        attempt=AssessmentAttemptResponse(**attempt),
        questions=questions,
    )
