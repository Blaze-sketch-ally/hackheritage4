"""ADMIN-only evaluator-assignment management (Phase 2: Evaluator
Assignment + Real Evaluation Workspace).

Resolves the governance question 045_evaluation_foundation.sql's own
migration header explicitly left open ("The real governance-actor
question (Admin? a new capability? something else?) is left open for
F8.2/F8.3 to decide explicitly, not resolved here") -- this phase
decides it as: the existing ADMIN role (require_admin(), is_admin(),
035_admin_faculty_permission_management.sql), the same authority that
already governs the "exactly analogous" action of granting Faculty
their assessment capabilities in the first place. assessment_moderator/
assessment_lead remain completely dormant, exactly as every prior F8
phase left them -- this phase does not activate them, and ordinary
Faculty/evaluators are never given assignment authority (an evaluator
can never assign themselves).

create_evaluator_assignment()/revoke_evaluator_assignment() (045) are
reused completely unmodified, service_role-only. Every route here:
require_admin() (app-layer -- the REAL authorization boundary for these
two RPCs, since they are unreachable by any authenticated non-service-
role caller regardless of role, matching assessment_service.
score_attempt's identical "ownership verified in Python, then
service-role" reasoning) -> build_user_client() only for the read-only,
self-contained eligible-evaluator re-check -> get_supabase() only for
the actual privileged read/write, never constructed before require_admin()
(and, for creation, the eligibility check) has already passed.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_admin
from app.core.security import build_user_client
from app.database.supabase import get_supabase
from app.schemas.evaluation import (
    AttemptForAssignmentResponse,
    CreateEvaluatorAssignmentRequest,
    EligibleEvaluatorResponse,
    EvaluatorAssignmentResponse,
)
from app.services import evaluation_service, faculty_permission_service

router = APIRouter(prefix="/admin/evaluator-assignments", tags=["admin-evaluator-assignments"])


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


def _to_assignment_response(row: dict) -> EvaluatorAssignmentResponse:
    return EvaluatorAssignmentResponse(
        assignment_id=row["id"],
        evaluator_id=row["evaluator_id"],
        attempt_id=row["attempt_id"],
        question_id=row["question_id"],
        status=row["status"],
        created_at=row["created_at"],
        revoked_at=row["revoked_at"],
    )


@router.get("/eligible-evaluators", response_model=list[EligibleEvaluatorResponse])
def list_eligible_evaluators(
    current_user: CurrentUser = Depends(require_admin),
) -> list[EligibleEvaluatorResponse]:
    """Faculty currently holding an active, unexpired assessment_evaluator
    capability -- the picker for "who can I assign". Reuses
    admin_list_faculty_assessment_permissions() (035) via
    faculty_permission_service.admin_list_eligible_evaluators, filtered
    server-side to only the eligible subset -- never the whole Faculty
    population sent to the browser for client-side filtering."""
    try:
        client = build_user_client(current_user.access_token)
        rows = faculty_permission_service.admin_list_eligible_evaluators(client)
    except faculty_permission_service.AdminAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("load eligible evaluators") from exc
    return [EligibleEvaluatorResponse(**row) for row in rows]


@router.get("/attempts", response_model=list[AttemptForAssignmentResponse])
def list_attempts_for_assignment(
    assessment_id: UUID = Query(...),
    current_user: CurrentUser = Depends(require_admin),
) -> list[AttemptForAssignmentResponse]:
    """COMPLETED attempts for one assessment, with their AI_EVALUATED
    questions and any evaluator_assignments already made against them --
    the "select an attempt/question" step of assignment creation. No
    student email/name/profile is ever read -- student_label is a
    short, truncated identifier only."""
    try:
        service_client = get_supabase()
        rows = evaluation_service.admin_list_attempts_for_assignment(service_client, assessment_id)
    except Exception as exc:
        raise _server_error("load attempts for assignment") from exc
    return [AttemptForAssignmentResponse(**row) for row in rows]


@router.post("", response_model=EvaluatorAssignmentResponse, status_code=status.HTTP_201_CREATED)
def create_assignment(
    body: CreateEvaluatorAssignmentRequest,
    current_user: CurrentUser = Depends(require_admin),
) -> EvaluatorAssignmentResponse:
    """Assign one evaluator to one (attempt, question). Multiple
    evaluators may be assigned to the same question (co-evaluation,
    unchanged from F8.1/F8.4.1's own design) -- this only rejects a
    genuine duplicate: the same evaluator, the same question, while
    already ACTIVE."""
    try:
        user_client = build_user_client(current_user.access_token)
        service_client = get_supabase()
        row = evaluation_service.admin_create_assignment(
            user_client,
            service_client,
            str(body.evaluator_id),
            body.attempt_id,
            body.question_id,
            current_user.id,
        )
    except evaluation_service.EvaluatorIneligibleError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except evaluation_service.EvaluatorAssignmentDuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except evaluation_service.InvalidAssignmentTargetError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("create this evaluator assignment") from exc
    return _to_assignment_response(row)


@router.post("/{assignment_id}/revoke", response_model=EvaluatorAssignmentResponse)
def revoke_assignment(
    assignment_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
) -> EvaluatorAssignmentResponse:
    """Revoke one evaluator assignment. The evaluator immediately loses
    access to the assigned answer/question/rubric (RLS: 046/047/051,
    all ACTIVE-assignment-gated); any FINALIZED evaluation and its
    append-only history remain completely untouched and immutable --
    this call only ever updates the evaluator_assignments row itself."""
    try:
        service_client = get_supabase()
        row = evaluation_service.admin_revoke_assignment(service_client, assignment_id, current_user.id)
    except evaluation_service.EvaluatorAssignmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except evaluation_service.EvaluatorAssignmentAlreadyRevokedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("revoke this evaluator assignment") from exc
    return _to_assignment_response(row)
