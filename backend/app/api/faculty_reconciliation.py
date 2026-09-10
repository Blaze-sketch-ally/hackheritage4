"""Faculty assessment reconciliation API (Faculty Assessment
Reconciliation -- Option C).

Every route is require_assessment_moderator-gated and reads/writes
through build_user_client(current_user.access_token) -- never
service_role -- so the underlying SECURITY DEFINER RPCs
(067_assessment_reconciliation_visibility.sql read-only;
068_assessment_reconciliation_decisions.sql for decision creation/
supersession) remain the actual capability-enforcing boundary; this
dependency is defense-in-depth, matching the existing pattern throughout
app.api.questions/app.api.admin_evaluator_assignments.

The two write routes (create/supersede a decision) never accept a
moderator identity from the request body -- it is exclusively derived
from auth.uid() inside the RPC (schema-layer extra="forbid" makes this
structural, not just a convention). Neither route ever writes
evaluation_status/final_* directly; fold_in_attempt_evaluation() (049,
extended by 068) remains the one place those are computed -- this file
only ever calls the two new RPCs and, best-effort, the existing
Faculty Notification producer (066/068) to inform affected evaluators.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_assessment_moderator
from app.core.security import build_user_client
from app.schemas.reconciliation import (
    CreateReconciliationDecisionRequest,
    ReconciliationCaseDetailResponse,
    ReconciliationCaseListResponse,
    ReconciliationCaseSummary,
    ReconciliationDecisionHistoryItem,
    ReconciliationDecisionHistoryResponse,
    ReconciliationDecisionResponse,
    ReconciliationEvaluatorMark,
    SupersedeReconciliationDecisionRequest,
)
from app.services import faculty_notification_producer, reconciliation_service

router = APIRouter(prefix="/faculty/reconciliation", tags=["faculty-reconciliation"])


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


def _map_reconciliation_errors(exc: Exception, action: str) -> HTTPException:
    if isinstance(exc, reconciliation_service.NotModeratorError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc) or "Forbidden.")
    if isinstance(exc, reconciliation_service.ReconciliationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc) or "Not found.")
    if isinstance(exc, reconciliation_service.ReconciliationStateError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc) or "Conflict.")
    if isinstance(exc, reconciliation_service.DuplicateActiveDecisionError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active reconciliation decision already exists for this question.",
        )
    if isinstance(exc, reconciliation_service.InvalidReconciliationRequestError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc) or "Invalid request.")
    return _server_error(action)


def _notify_affected_evaluators(row: dict, decision_id: str) -> None:
    """Best-effort: informs every evaluator whose FINALIZED mark applied
    to the resolved question -- never blocks the response if it fails
    (matching faculty_notification_producer's own contract)."""
    evaluator_ids = row.get("affected_evaluator_ids") or []
    evaluation_ids = row.get("affected_evaluation_ids") or []
    for evaluator_id, evaluation_id in zip(evaluator_ids, evaluation_ids, strict=False):
        faculty_notification_producer.emit_reconciliation_resolved(
            evaluator_id=str(evaluator_id), evaluation_id=str(evaluation_id), decision_id=decision_id
        )


@router.get("/cases", response_model=ReconciliationCaseListResponse)
def list_reconciliation_cases(
    current_user: CurrentUser = Depends(require_assessment_moderator),
) -> ReconciliationCaseListResponse:
    try:
        client = build_user_client(current_user.access_token)
        rows = reconciliation_service.list_cases(client)
    except reconciliation_service.NotModeratorError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc) or "Forbidden.") from exc
    except Exception as exc:
        raise _server_error("load reconciliation cases") from exc
    return ReconciliationCaseListResponse(cases=[ReconciliationCaseSummary(**row) for row in rows])


@router.get("/cases/{attempt_id}", response_model=ReconciliationCaseDetailResponse)
def get_reconciliation_case(
    attempt_id: UUID,
    current_user: CurrentUser = Depends(require_assessment_moderator),
) -> ReconciliationCaseDetailResponse:
    try:
        client = build_user_client(current_user.access_token)
        rows = reconciliation_service.get_case(client, attempt_id)
    except reconciliation_service.NotModeratorError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc) or "Forbidden.") from exc
    except Exception as exc:
        raise _server_error("load this reconciliation case") from exc
    if rows is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This is not a current reconciliation case.",
        )
    return ReconciliationCaseDetailResponse(
        attempt_id=attempt_id, marks=[ReconciliationEvaluatorMark(**row) for row in rows]
    )


@router.post(
    "/cases/{attempt_id}/questions/{question_id}/decisions",
    response_model=ReconciliationDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reconciliation_decision(
    attempt_id: UUID,
    question_id: UUID,
    body: CreateReconciliationDecisionRequest,
    current_user: CurrentUser = Depends(require_assessment_moderator),
) -> ReconciliationDecisionResponse:
    """Create the first reconciliation decision for a genuinely
    conflicting question. moderator_id is always current_user.id, via
    auth.uid() inside the RPC -- CreateReconciliationDecisionRequest has
    no such field at all (extra="forbid")."""
    client = build_user_client(current_user.access_token)
    try:
        row = reconciliation_service.create_decision(
            client, attempt_id, question_id, body.final_awarded_marks, body.rationale
        )
    except Exception as exc:
        raise _map_reconciliation_errors(exc, "create this reconciliation decision") from exc
    _notify_affected_evaluators(row, str(row["decision_id"]))
    return ReconciliationDecisionResponse(**row)


@router.post(
    "/decisions/{decision_id}/supersede",
    response_model=ReconciliationDecisionResponse,
)
def supersede_reconciliation_decision(
    decision_id: UUID,
    body: SupersedeReconciliationDecisionRequest,
    current_user: CurrentUser = Depends(require_assessment_moderator),
) -> ReconciliationDecisionResponse:
    """Correct an existing ACTIVE decision: the prior row is marked
    SUPERSEDED (never edited in place -- its own final_awarded_marks/
    rationale/moderator_id remain exactly as originally recorded), a new
    ACTIVE row is inserted, and fold-in re-runs. Allowed even if the
    attempt has already reached COMPLETE -- see 068's own "Stage 7 edge
    case" comment."""
    client = build_user_client(current_user.access_token)
    try:
        row = reconciliation_service.supersede_decision(
            client, decision_id, body.final_awarded_marks, body.rationale
        )
    except Exception as exc:
        raise _map_reconciliation_errors(exc, "supersede this reconciliation decision") from exc
    _notify_affected_evaluators(row, str(row["decision_id"]))
    return ReconciliationDecisionResponse(**row)


@router.get(
    "/cases/{attempt_id}/questions/{question_id}/decisions",
    response_model=ReconciliationDecisionHistoryResponse,
)
def list_reconciliation_decisions(
    attempt_id: UUID,
    question_id: UUID,
    current_user: CurrentUser = Depends(require_assessment_moderator),
) -> ReconciliationDecisionHistoryResponse:
    """The full ACTIVE + SUPERSEDED decision chain for one question --
    moderator-only visibility (Stage 8); never exposed to an evaluator or
    ordinary Faculty caller."""
    client = build_user_client(current_user.access_token)
    try:
        rows = reconciliation_service.list_decision_history(client, attempt_id, question_id)
    except reconciliation_service.NotModeratorError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc) or "Forbidden.") from exc
    except Exception as exc:
        raise _server_error("load this reconciliation decision history") from exc
    return ReconciliationDecisionHistoryResponse(
        question_id=question_id,
        decisions=[ReconciliationDecisionHistoryItem(**row) for row in rows],
    )
