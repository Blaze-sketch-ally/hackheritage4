"""Faculty-side evaluator workflow routes (Phase F8.3). Reads/writes the
`evaluations`/`evaluator_assignments`/`rubrics`/`rubric_criteria`
foundation from 045_evaluation_foundation.sql, through the RLS boundary
046_evaluator_answer_access.sql already established.

Every route goes through build_user_client(current_user.access_token) --
never get_supabase()/service_role -- so RLS stays the real access-control
boundary; require_assessment_evaluator() is the app-layer complement, not
a replacement, matching every other Faculty router in this codebase
(faculty_mentorships.py's own module docstring states the identical
principle). No new RLS, no new RPC, no new migration -- F8.3 is
backend-only, wiring the F8.1/F8.2 database work up to an API for the
first time.

Deliberately two separate PATCH endpoints, not one combined one: content
(rubric_id/awarded_marks/feedback) vs lifecycle (status) -- mirrors this
codebase's own existing split (attempts.py's save_answer vs
submit_attempt; faculty_mentorships.py's status-PATCH vs notes-PUT), not
an invented convention.

Phase F8.4.2 adds exactly one thing to update_evaluation_status below: a
service-role-only trigger of the trusted F8.4.1 fold-in RPC
(fold_in_attempt_evaluation, 049_evaluation_status_and_final_score.sql)
whenever an evaluation reaches FINALIZED, mirroring
app.api.attempts.score_attempt's own established "ownership verified via
the user client first, service-role step only afterward" pattern. See
that function's own docstring for the full failure/retry contract.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_assessment_evaluator
from app.core.security import build_user_client
from app.database.supabase import get_supabase
from app.schemas.evaluation import (
    EvaluationDetailResponse,
    EvaluationStatus,
    EvaluationSummaryResponse,
    RubricResponse,
    SaveEvaluationRequest,
    UpdateEvaluationStatusRequest,
)
from app.services import evaluation_service

router = APIRouter(prefix="/faculty/evaluations", tags=["faculty-evaluations"])

logger = logging.getLogger(__name__)


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=list[EvaluationSummaryResponse])
def list_my_evaluations(
    status_filter: EvaluationStatus | None = None,
    current_user: CurrentUser = Depends(require_assessment_evaluator),
) -> list[EvaluationSummaryResponse]:
    """The caller's own evaluator work queue, optionally filtered by
    status. Never a general Faculty-wide listing -- evaluation_service.
    list_my_evaluations() scopes to the caller's own evaluator_id, and
    evaluations' own SELECT policy (045) makes this the only possible
    result regardless."""
    try:
        client = build_user_client(current_user.access_token)
        rows = evaluation_service.list_my_evaluations(
            client, current_user.id, status_filter.value if status_filter else None
        )
    except Exception as exc:
        raise _server_error("load your assigned evaluations") from exc
    return [EvaluationSummaryResponse(**row) for row in rows]


@router.get("/{evaluation_id}", response_model=EvaluationDetailResponse)
def get_evaluation(
    evaluation_id: UUID,
    current_user: CurrentUser = Depends(require_assessment_evaluator),
) -> EvaluationDetailResponse:
    """One assigned evaluation's full detail: question content, the
    student's submitted answer, and the attached rubric if any. 404
    whether the evaluation doesn't exist, isn't the caller's own, or the
    caller's assignment/capability is no longer ACTIVE/valid -- never
    distinguished, matching this codebase's own repeated convention."""
    try:
        client = build_user_client(current_user.access_token)
        row = evaluation_service.get_evaluation_detail(client, current_user.id, evaluation_id)
    except Exception as exc:
        raise _server_error("load this evaluation") from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")
    return EvaluationDetailResponse(**row)


@router.get("/{evaluation_id}/rubrics", response_model=list[RubricResponse])
def list_candidate_rubrics(
    evaluation_id: UUID,
    current_user: CurrentUser = Depends(require_assessment_evaluator),
) -> list[RubricResponse]:
    """Phase 2: ACTIVE rubrics that exist for the question this
    evaluation is assigned against -- what PATCH .../{id}'s own
    rubric_id can legitimately be set to. Fixes a real, pre-existing gap
    this phase's own audit found: without this, an evaluator had no way
    to discover ANY rubric before picking one (046's own rubric SELECT
    policy only ever matched AFTER a rubric was already saved onto the
    evaluation) -- see 051_evaluator_candidate_rubric_visibility.sql for
    the new, narrow, evaluator-assignment-scoped policy this relies on.
    404 under the identical conditions as GET /faculty/evaluations/{id}
    -- evaluation doesn't exist, isn't the caller's own, or the caller's
    assignment is no longer ACTIVE."""
    try:
        client = build_user_client(current_user.access_token)
        rows = evaluation_service.list_candidate_rubrics(client, current_user.id, evaluation_id)
    except Exception as exc:
        raise _server_error("load candidate rubrics for this evaluation") from exc
    if rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")
    return [RubricResponse(**row) for row in rows]


@router.patch("/{evaluation_id}", response_model=EvaluationSummaryResponse)
def save_evaluation(
    evaluation_id: UUID,
    body: SaveEvaluationRequest,
    current_user: CurrentUser = Depends(require_assessment_evaluator),
) -> EvaluationSummaryResponse:
    """Save rubric selection / marks / feedback -- never status (see
    update_evaluation_status below). exclude_unset means an omitted
    field is left unchanged; an explicit null clears it where the
    database allows that. The database remains authoritative for
    rubric/question compatibility, the max-marks ceiling, and
    finalized-immutability regardless of what this route checks."""
    payload = body.model_dump(mode="json", exclude_unset=True)
    try:
        client = build_user_client(current_user.access_token)
        row = evaluation_service.save_evaluation(client, current_user.id, evaluation_id, payload)
    except evaluation_service.EvaluationFinalizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This evaluation has already been finalized and can no longer be changed.",
        ) from exc
    except evaluation_service.EvaluationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("save this evaluation") from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")
    return EvaluationSummaryResponse(**row)


@router.patch("/{evaluation_id}/status", response_model=EvaluationSummaryResponse)
def update_evaluation_status(
    evaluation_id: UUID,
    body: UpdateEvaluationStatusRequest,
    current_user: CurrentUser = Depends(require_assessment_evaluator),
) -> EvaluationSummaryResponse:
    """Lifecycle transition only: IN_PROGRESS, SUBMITTED, or FINALIZED
    (ASSIGNED is rejected at the schema layer -- see
    UpdateEvaluationStatusRequest). A re-send of the current status
    succeeds idempotently rather than erroring -- see evaluation_service.
    update_evaluation_status's own docstring.

    Phase F8.4.2: whenever the evaluation ends up FINALIZED -- whether by
    an actual transition just now, or by an idempotent re-send of an
    already-FINALIZED status -- this triggers the trusted F8.4.1 fold-in
    RPC (evaluation_service.fold_in_attempt) for the evaluation's attempt,
    via the service-role client, ONLY after the transition has already
    committed through the caller's own RLS-scoped client above. An
    evaluator can never reach fold_in_attempt_evaluation() directly: it
    is not exposed by any route, and this trigger only runs after the
    user-scoped call already proved the caller owns an ACTIVE assignment
    for a legally-reachable FINALIZED state (a failed/invalid/
    unauthorized/revoked-assignment transition raises or returns None
    above and never reaches this point).

    Ownership/eligibility is verified via the user-scoped client exactly
    as with app.api.attempts.score_attempt; only afterward does
    get_supabase() ever get constructed -- same "ownership verified,
    THEN service-role" ordering, never the reverse.

    NOT-YET-ELIGIBLE (benign, NOT a failure): create_evaluator_assignment
    (045_evaluation_foundation.sql) has no attempt-status precondition,
    so F8.3's own established workflow has always allowed an evaluator to
    be assigned to, and finalize, an evaluation before the student's
    attempt has been submitted/scored to COMPLETED -- fold_in_attempt_
    evaluation() itself requires status = 'COMPLETED' (049). When that
    precondition isn't met yet, evaluation_service.fold_in_attempt raises
    EvaluationFoldInNotEligibleError, which this route treats as an
    ordinary 200: the evaluation genuinely finalized, there is simply
    nothing yet to fold in, and no error is raised or logged as one.

    KNOWN GAP (documented, intentionally not addressed here -- would
    require touching score_assessment_attempt(), explicitly out of
    F8.4.2's scope): nothing currently re-triggers fold-in automatically
    when the attempt LATER becomes COMPLETED after being deferred this
    way -- only a SUBSEQUENT FINALIZED event on the same attempt (this
    same evaluation's own idempotent re-send, or a co-required
    evaluation's own finalize) re-attempts it. See the F8.4.2
    implementation report's own Risks/blockers section.

    FAILURE/RETRY CONTRACT for every OTHER (genuinely unexpected) fold-in
    failure: fold_in_attempt_evaluation() is fully idempotent and
    attempt-row-locked (049) -- it always recomputes the attempt's
    evaluation_status/final_* from scratch from the FINALIZED evaluations
    that currently exist, so calling it again is always safe and never
    compounds a partial/corrupted result. If it fails here, the
    evaluation's own FINALIZED transition is deliberately NOT rolled back
    -- it already committed in its own request/transaction, this
    endpoint's primary contract (this evaluation is now finalized)
    genuinely succeeded, and the existing architecture provides no
    cross-request transaction spanning both the PostgREST update above
    and this RPC call. The failure is logged (never swallowed) and
    surfaced as a 500 whose detail explicitly tells the caller the
    evaluation itself is safe and that resending the identical PATCH is
    the correct recovery: a duplicate FINALIZED request takes the
    idempotent short-circuit path in evaluation_service.
    update_evaluation_status (no second database write to the
    evaluation) and reaches this same trigger again, safely retrying the
    fold-in with no separate retry endpoint or job needed.
    """
    try:
        client = build_user_client(current_user.access_token)
        row = evaluation_service.update_evaluation_status(
            client, current_user.id, evaluation_id, body.status.value
        )
    except evaluation_service.EvaluationInvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except evaluation_service.EvaluationFinalizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This evaluation has already been finalized and can no longer be changed.",
        ) from exc
    except evaluation_service.EvaluationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("update this evaluation") from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")

    if row["status"] == EvaluationStatus.FINALIZED.value and row.get("attempt_id") is not None:
        try:
            evaluation_service.fold_in_attempt(get_supabase(), row["attempt_id"])
        except evaluation_service.EvaluationFoldInNotEligibleError:
            # Benign, expected, not logged as an error -- see this
            # function's own "NOT-YET-ELIGIBLE" docstring section.
            pass
        except Exception:
            logger.exception(
                "fold_in_attempt_evaluation failed for attempt_id=%s after evaluation_id=%s "
                "was finalized; the evaluation remains finalized and this is safely retryable "
                "by resending the same PATCH request.",
                row["attempt_id"],
                evaluation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Your evaluation was finalized successfully, but the attempt's overall "
                    "result could not be recalculated. Please try again -- resending this "
                    "same request is safe."
                ),
            ) from None

    return EvaluationSummaryResponse(**row)
