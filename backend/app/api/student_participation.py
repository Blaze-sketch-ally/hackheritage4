"""API routes for the STUDENT side of the shared Participation Workspace
domain (Project / Training / Workshop), database/migrations/062-065.

Every route is guarded by require_student() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role. `student_id` is always current_user.id.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.participation import (
    AssignmentListResponse,
    CompletionResponse,
    CriterionListResponse,
    EvaluationResponse,
    FeedbackListResponse,
    ModuleListResponse,
    ParticipationKind,
    ResourceListResponse,
    SkillRecommendationListResponse,
    SubmissionCreate,
    SubmissionListResponse,
    SubmissionResponse,
    WorkspaceListResponse,
    WorkspaceResponse,
)
from app.services import (
    notification_producer,
)
from app.services import (
    participation_evaluation_service as eval_service,
)
from app.services import (
    participation_feedback_service as feedback_service,
)
from app.services import (
    participation_student_service as student_content_service,
)
from app.services import (
    participation_submission_service as submission_service,
)
from app.services import (
    participation_workspace_service as workspace_service,
)

router = APIRouter(prefix="/student/participation", tags=["student-participation"])


def _not_found(what: str = "Not found.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=what)


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


def _own_workspace(client, student_id: str, workspace_id: str) -> dict | None:
    return workspace_service.get_workspace(client, student_id, workspace_id, as_industry=False)


@router.get("/workspaces", response_model=WorkspaceListResponse)
def list_my_workspaces(
    kind: ParticipationKind | None = Query(default=None),
    current_user: CurrentUser = Depends(require_student),
) -> WorkspaceListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = workspace_service.list_my_workspaces(client, current_user.id, kind=kind)
    except Exception as exc:
        raise _server_error("load your workspaces") from exc
    return WorkspaceListResponse(workspaces=rows)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> WorkspaceResponse:
    client = build_user_client(current_user.access_token)
    row = _own_workspace(client, current_user.id, str(workspace_id))
    if row is None:
        raise _not_found("Workspace not found.")
    row["progress"] = workspace_service.get_progress(client, str(workspace_id))
    return WorkspaceResponse(**row)


@router.get("/workspaces/{workspace_id}/modules", response_model=ModuleListResponse)
def list_modules(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> ModuleListResponse:
    client = build_user_client(current_user.access_token)
    ws = _own_workspace(client, current_user.id, str(workspace_id))
    if ws is None or not ws.get("program_id"):
        return ModuleListResponse(modules=[])
    rows = student_content_service.list_modules(client, ws["program_id"])
    return ModuleListResponse(modules=rows)


@router.get("/workspaces/{workspace_id}/resources", response_model=ResourceListResponse)
def list_resources(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> ResourceListResponse:
    client = build_user_client(current_user.access_token)
    ws = _own_workspace(client, current_user.id, str(workspace_id))
    if ws is None or not ws.get("program_id"):
        return ResourceListResponse(resources=[])
    rows = student_content_service.list_resources(client, ws["program_id"])
    return ResourceListResponse(resources=rows)


@router.get("/workspaces/{workspace_id}/assignments", response_model=AssignmentListResponse)
def list_assignments(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> AssignmentListResponse:
    client = build_user_client(current_user.access_token)
    ws = _own_workspace(client, current_user.id, str(workspace_id))
    if ws is None or not ws.get("program_id"):
        return AssignmentListResponse(assignments=[])
    rows = student_content_service.list_assignments(client, ws["program_id"])
    return AssignmentListResponse(assignments=rows)


@router.get("/workspaces/{workspace_id}/criteria", response_model=CriterionListResponse)
def list_criteria(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> CriterionListResponse:
    client = build_user_client(current_user.access_token)
    ws = _own_workspace(client, current_user.id, str(workspace_id))
    if ws is None or not ws.get("program_id"):
        return CriterionListResponse(criteria=[])
    rows = student_content_service.list_criteria(client, ws["program_id"])
    return CriterionListResponse(criteria=rows)


@router.get("/workspaces/{workspace_id}/submissions", response_model=SubmissionListResponse)
def list_submissions(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> SubmissionListResponse:
    client = build_user_client(current_user.access_token)
    if _own_workspace(client, current_user.id, str(workspace_id)) is None:
        raise _not_found("Workspace not found.")
    rows = submission_service.list_submissions(client, str(workspace_id))
    return SubmissionListResponse(submissions=rows)


@router.post(
    "/workspaces/{workspace_id}/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED
)
def create_submission(
    workspace_id: UUID, body: SubmissionCreate, current_user: CurrentUser = Depends(require_student)
) -> SubmissionResponse:
    client = build_user_client(current_user.access_token)
    workspace = _own_workspace(client, current_user.id, str(workspace_id))
    if workspace is None:
        raise _not_found("Workspace not found.")
    try:
        row = submission_service.create_submission(client, str(workspace_id), body.model_dump(mode="json"))
    except Exception as exc:
        raise _server_error("submit your work") from exc

    try:
        own_name = (
            client.table("profiles").select("full_name").eq("id", current_user.id).maybe_single().execute().data
            or {}
        ).get("full_name")
    except Exception:  # noqa: BLE001 -- notification enrichment only
        own_name = None
    notification_producer.emit_participation_submission(
        industry_id=workspace["industry_id"],
        workspace_id=str(workspace_id),
        student_name=own_name,
        assignment_title=row.get("assignment_title") or "an assignment",
        is_resubmission=row["attempt_number"] > 1,
    )

    return SubmissionResponse(**row)


@router.get("/workspaces/{workspace_id}/feedback", response_model=FeedbackListResponse)
def list_feedback(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> FeedbackListResponse:
    client = build_user_client(current_user.access_token)
    if _own_workspace(client, current_user.id, str(workspace_id)) is None:
        raise _not_found("Workspace not found.")
    rows = feedback_service.list_feedback(client, str(workspace_id))
    return FeedbackListResponse(feedback=rows)


@router.get("/workspaces/{workspace_id}/recommendations", response_model=SkillRecommendationListResponse)
def list_recommendations(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> SkillRecommendationListResponse:
    client = build_user_client(current_user.access_token)
    if _own_workspace(client, current_user.id, str(workspace_id)) is None:
        raise _not_found("Workspace not found.")
    rows = feedback_service.list_recommendations(client, str(workspace_id))
    return SkillRecommendationListResponse(recommendations=rows)


@router.get("/workspaces/{workspace_id}/evaluation", response_model=EvaluationResponse)
def get_evaluation(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> EvaluationResponse:
    client = build_user_client(current_user.access_token)
    if _own_workspace(client, current_user.id, str(workspace_id)) is None:
        raise _not_found("Workspace not found.")
    row = eval_service.get_evaluation(client, str(workspace_id))
    if row is None or row["status"] != "FINALIZED":
        raise _not_found("No final evaluation is available yet.")
    return EvaluationResponse(**row)


@router.get("/workspaces/{workspace_id}/completion", response_model=CompletionResponse)
def get_completion(workspace_id: UUID, current_user: CurrentUser = Depends(require_student)) -> CompletionResponse:
    client = build_user_client(current_user.access_token)
    if _own_workspace(client, current_user.id, str(workspace_id)) is None:
        raise _not_found("Workspace not found.")
    row = eval_service.get_completion(client, str(workspace_id))
    if row is None:
        raise _not_found("This workspace has not been completed yet.")
    return CompletionResponse(**row)
