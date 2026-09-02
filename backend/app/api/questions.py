"""API routes for the Question Bank + review workflow (Phase 1K,
capability-gated since Phase F5A).

GET routes require only require_faculty() -- RLS (041_assessment_
capability_authorization.sql) does the real visibility filtering (own
questions, or any question if the caller holds assessment_reviewer), so
there is nothing additional for the route layer to gate on a plain read.
create_question/update_question require require_assessment_author();
approve_question/reject_question require require_assessment_reviewer().
Every route reads/writes exclusively through build_user_client
(access_token) -- never get_supabase(). RLS plus the
prevent_unauthorized_question_review trigger (015) remain the entire
enforcement mechanism for WHICH mutation is legal once a caller is in
the door; this router's own checks (role + capability) are defense in
depth, not the real boundary, matching every other router in this
codebase.

Approved product decisions this router implements (see the Phase 1K
report and the Phase F5A readiness audit, not re-derived here):
  - Peer faculty review: any FACULTY account holding assessment_reviewer,
    other than a question's own setter, may approve/reject it. No
    dedicated "submit for review" route exists -- a question is PENDING
    (and thus reviewable) from the moment it's created; review_status has
    no DRAFT state.
  - Approved questions are content-immutable (is_active remains
    togglable). A REJECTED question's own setter may keep revising it and
    it becomes reviewable again the moment they set review_status back to
    PENDING via PATCH.
  - assessment_author/assessment_reviewer are two of F2's five dormant
    capabilities, activated here for the first time; assessment_evaluator/
    moderator/lead remain completely unreferenced -- they belong to F8/F10.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError

from app.core.dependencies import (
    CurrentUser,
    require_assessment_author,
    require_assessment_reviewer,
    require_faculty,
)
from app.core.security import build_user_client
from app.schemas.question_bank import (
    QuestionBankResponse,
    QuestionCreateRequest,
    QuestionUpdateRequest,
)
from app.services import question_bank_service

router = APIRouter(prefix="/questions", tags=["questions"])


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not allowed to make this change.",
    )


@router.get("", response_model=list[QuestionBankResponse])
def list_questions(
    assessment_id: UUID | None = None,
    current_user: CurrentUser = Depends(require_faculty),
) -> list[QuestionBankResponse]:
    """The shared question bank, as filtered by RLS (041): the caller's
    own questions always, plus every question if the caller holds
    assessment_reviewer. A plain FACULTY account with neither capability
    sees nothing here. Optionally scoped to one assessment via a query
    parameter."""
    client = build_user_client(current_user.access_token)
    try:
        rows = question_bank_service.list_my_questions(client, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load questions.",
        ) from exc
    return [QuestionBankResponse(**row) for row in rows]


@router.get("/{question_id}", response_model=QuestionBankResponse)
def get_question(
    question_id: UUID,
    current_user: CurrentUser = Depends(require_faculty),
) -> QuestionBankResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = question_bank_service.get_my_question(client, question_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the question.",
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    return QuestionBankResponse(**row)


@router.post("", response_model=QuestionBankResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    body: QuestionCreateRequest,
    current_user: CurrentUser = Depends(require_assessment_author),
) -> QuestionBankResponse:
    """Create a new question, its options, and (optionally) its answer
    key -- three RLS-scoped inserts, not one atomic transaction. If a
    later step fails, the question row itself still exists as a PENDING
    draft the caller can keep editing via PATCH, never a
    scoring-correctness concern (unlike attempt creation, nothing here is
    time-sensitive or student-facing yet, so this does not need the
    RPC/service-role treatment score_assessment_attempt and
    create_assessment_attempt get)."""
    client = build_user_client(current_user.access_token)

    question_payload = body.model_dump(mode="json", exclude={"options", "answer_key"})

    try:
        question = question_bank_service.create_question(client, current_user.id, question_payload)
    except APIError as exc:
        raise _forbidden() from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create the question.",
        ) from exc

    question_id = UUID(question["id"])

    try:
        if body.options:
            # exclude_none on each option so an option with no client-
            # generated id omits "id" entirely from the insert payload,
            # letting the column's own `default gen_random_uuid()` apply
            # -- sending an explicit "id": null would instead try to
            # insert NULL into a NOT NULL primary key and fail outright.
            question_bank_service.replace_options(
                client,
                question_id,
                [option.model_dump(mode="json", exclude_none=True) for option in body.options],
            )
        if body.answer_key is not None:
            question_bank_service.upsert_answer_key(
                client, question_id, body.answer_key.model_dump(mode="json")
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Question created, but its options/answer key could not be saved.",
        ) from exc

    row = question_bank_service.get_my_question(client, question_id)
    return QuestionBankResponse(**row)


@router.patch("/{question_id}", response_model=QuestionBankResponse)
def update_question(
    question_id: UUID,
    body: QuestionUpdateRequest,
    current_user: CurrentUser = Depends(require_assessment_author),
) -> QuestionBankResponse:
    """Edit a question's own content, and optionally replace its options/
    answer key. Only ever succeeds while the caller is the question's own
    creator and it is not yet APPROVED -- enforced by RLS +
    prevent_unauthorized_question_review, not by this route.

    options/answer_key are handled separately from the rest of the
    payload -- they aren't columns on assessment_questions, so they never
    reach question_bank_service.update_question. exclude_unset (not
    exclude_none) is used for the top-level dump so "field omitted
    entirely" (leave untouched) is distinguishable from "field explicitly
    set to null" (only meaningful for answer_key: clears it)."""
    client = build_user_client(current_user.access_token)
    fields_set = body.model_fields_set
    payload = body.model_dump(mode="json", exclude_unset=True, exclude={"options", "answer_key"})

    try:
        if "options" in fields_set and body.options is not None:
            question_bank_service.replace_options(
                client,
                question_id,
                [option.model_dump(mode="json", exclude_none=True) for option in body.options],
            )
        if "answer_key" in fields_set:
            if body.answer_key is not None:
                question_bank_service.upsert_answer_key(
                    client, question_id, body.answer_key.model_dump(mode="json")
                )
            else:
                question_bank_service.clear_answer_key(client, question_id)
    except APIError as exc:
        if exc.code == "42501":
            raise _forbidden() from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the question's options/answer key.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the question's options/answer key.",
        ) from exc

    if payload:
        try:
            updated = question_bank_service.update_question(client, question_id, payload)
        except APIError as exc:
            if exc.code == "42501":
                raise _forbidden() from exc
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not update the question.",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not update the question.",
            ) from exc
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")

    row = question_bank_service.get_my_question(client, question_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    return QuestionBankResponse(**row)


def _review(question_id: UUID, decision: str, current_user: CurrentUser) -> QuestionBankResponse:
    """Shared by approve_question/reject_question -- both call the same
    review_question() RPC (016_review_question_rpc.sql) with a different
    decision literal, and map its typed exceptions to HTTP responses
    identically."""
    client = build_user_client(current_user.access_token)
    try:
        updated = question_bank_service.set_review_status(client, question_id, decision)
    except question_bank_service.OwnQuestionReviewError as exc:
        raise _forbidden() from exc
    except question_bank_service.QuestionNotPendingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This question is no longer pending review.",
        ) from exc
    except question_bank_service.QuestionNotApprovableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This question cannot be approved yet: it is not a complete, "
                "scoreable question (missing or invalid answer key, an "
                "unsupported question type/scoring combination, or too few "
                "options)."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the question's review status.",
        ) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    row = question_bank_service.get_my_question(client, question_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    return QuestionBankResponse(**row)


@router.post("/{question_id}/approve", response_model=QuestionBankResponse)
def approve_question(
    question_id: UUID,
    current_user: CurrentUser = Depends(require_assessment_reviewer),
) -> QuestionBankResponse:
    """Approve a PENDING question submitted by a DIFFERENT faculty member.
    review_question() rejects this outright (403) if the caller is the
    question's own creator, and (409) if it's no longer PENDING (e.g. a
    concurrent review already resolved it)."""
    return _review(question_id, "APPROVED", current_user)


@router.post("/{question_id}/reject", response_model=QuestionBankResponse)
def reject_question(
    question_id: UUID,
    current_user: CurrentUser = Depends(require_assessment_reviewer),
) -> QuestionBankResponse:
    """Reject a PENDING question submitted by a DIFFERENT faculty member.
    Its own setter may revise it and set review_status back to PENDING
    via PATCH -- Phase 1K's entire "resubmit after rejection" path."""
    return _review(question_id, "REJECTED", current_user)
