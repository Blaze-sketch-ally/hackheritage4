"""API routes for the INDUSTRY side of the shared Participation Workspace
domain (Project / Training / Workshop), database/migrations/062-065.

Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. Generic by `kind`: one route set for all three
opportunity types, never three.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.participation import (
    AssignmentCreate,
    AssignmentListResponse,
    AssignmentResponse,
    AssignmentUpdate,
    CompletionResponse,
    CriterionCreate,
    CriterionListResponse,
    CriterionResponse,
    CriterionUpdate,
    EnsureWorkspaceRequest,
    EvaluationResponse,
    EvaluationSaveRequest,
    FeedbackCreate,
    FeedbackListResponse,
    FeedbackResponse,
    ModuleCreate,
    ModuleListResponse,
    ModuleResponse,
    ModuleUpdate,
    ParticipationKind,
    ProgramCreate,
    ProgramResponse,
    ProgramUpdate,
    ResourceCreate,
    ResourceListResponse,
    ResourceResponse,
    ResourceUpdate,
    ReviewCreate,
    ReviewResponse,
    SkillRecommendationCreate,
    SkillRecommendationListResponse,
    SkillRecommendationResponse,
    SubmissionListResponse,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceStatus,
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
    participation_program_service as program_service,
)
from app.services import (
    participation_submission_service as submission_service,
)
from app.services import (
    participation_workspace_service as workspace_service,
)

router = APIRouter(prefix="/participation", tags=["industry-participation"])


def _not_found(what: str = "Not found.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=what)


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


# ============================================================
# Programs
# ============================================================


@router.get("/programs/by-opportunity", response_model=ProgramResponse)
def get_program_for_opportunity(
    kind: ParticipationKind = Query(...),
    opportunity_id: UUID = Query(...),
    current_user: CurrentUser = Depends(require_industry),
) -> ProgramResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.get_program_for_opportunity(client, current_user.id, kind, str(opportunity_id))
    except Exception as exc:
        raise _server_error("load the participation program") from exc
    if row is None:
        raise _not_found("No participation program exists for this opportunity yet.")
    return ProgramResponse(**row)


@router.post("/programs", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
def create_program(
    body: ProgramCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> ProgramResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.create_program(client, current_user.id, body.model_dump(mode="json"))
    except program_service.OpportunityNotOwnedError as exc:
        raise _not_found("That opportunity was not found.") from exc
    except program_service.ProgramAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This opportunity already has a participation program."
        ) from exc
    except Exception as exc:
        raise _server_error("create the participation program") from exc
    return ProgramResponse(**row)


@router.get("/programs/{program_id}", response_model=ProgramResponse)
def get_program(
    program_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ProgramResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.get_program(client, current_user.id, str(program_id))
    except Exception as exc:
        raise _server_error("load the participation program") from exc
    if row is None:
        raise _not_found("Participation program not found.")
    return ProgramResponse(**row)


@router.put("/programs/{program_id}", response_model=ProgramResponse)
def update_program(
    program_id: UUID,
    body: ProgramUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> ProgramResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.update_program(client, current_user.id, str(program_id), body.model_dump(mode="json", exclude_unset=True))
    except Exception as exc:
        raise _server_error("save the participation program") from exc
    if row is None:
        raise _not_found("Participation program not found.")
    return ProgramResponse(**row)


@router.post("/programs/{program_id}/publish", response_model=ProgramResponse)
def publish_program(
    program_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ProgramResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.publish_program(client, current_user.id, str(program_id))
    except Exception as exc:
        raise _server_error("publish the participation program") from exc
    if row is None:
        raise _not_found("Participation program not found.")
    return ProgramResponse(**row)


@router.post("/programs/{program_id}/archive", response_model=ProgramResponse)
def archive_program(
    program_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ProgramResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.archive_program(client, current_user.id, str(program_id))
    except Exception as exc:
        raise _server_error("archive the participation program") from exc
    if row is None:
        raise _not_found("Participation program not found.")
    return ProgramResponse(**row)


# ---- modules ----


@router.get("/programs/{program_id}/modules", response_model=ModuleListResponse)
def list_modules(program_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> ModuleListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = program_service.list_modules(client, current_user.id, str(program_id))
    except Exception as exc:
        raise _server_error("load modules") from exc
    if rows is None:
        raise _not_found("Participation program not found.")
    return ModuleListResponse(modules=rows)


@router.post("/programs/{program_id}/modules", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED)
def create_module(program_id: UUID, body: ModuleCreate, current_user: CurrentUser = Depends(require_industry)) -> ModuleResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.create_module(client, current_user.id, str(program_id), body.model_dump(mode="json"))
    except Exception as exc:
        raise _server_error("create the module") from exc
    if row is None:
        raise _not_found("Participation program not found.")
    return ModuleResponse(**row)


@router.put("/programs/{program_id}/modules/{module_id}", response_model=ModuleResponse)
def update_module(
    program_id: UUID, module_id: UUID, body: ModuleUpdate, current_user: CurrentUser = Depends(require_industry)
) -> ModuleResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.update_module(client, current_user.id, str(program_id), str(module_id), body.model_dump(mode="json", exclude_unset=True))
    except Exception as exc:
        raise _server_error("save the module") from exc
    if row is None:
        raise _not_found("Module not found.")
    return ModuleResponse(**row)


@router.post("/programs/{program_id}/modules/{module_id}/publish", response_model=ModuleResponse)
def publish_module(program_id: UUID, module_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> ModuleResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.set_module_published(client, current_user.id, str(program_id), str(module_id), True)
    if row is None:
        raise _not_found("Module not found.")
    return ModuleResponse(**row)


@router.post("/programs/{program_id}/modules/{module_id}/unpublish", response_model=ModuleResponse)
def unpublish_module(program_id: UUID, module_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> ModuleResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.set_module_published(client, current_user.id, str(program_id), str(module_id), False)
    if row is None:
        raise _not_found("Module not found.")
    return ModuleResponse(**row)


# ---- resources ----


@router.get("/programs/{program_id}/resources", response_model=ResourceListResponse)
def list_resources(program_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> ResourceListResponse:
    client = build_user_client(current_user.access_token)
    rows = program_service.list_resources(client, current_user.id, str(program_id))
    if rows is None:
        raise _not_found("Participation program not found.")
    return ResourceListResponse(resources=rows)


@router.post("/programs/{program_id}/resources", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
def create_resource(program_id: UUID, body: ResourceCreate, current_user: CurrentUser = Depends(require_industry)) -> ResourceResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.create_resource(client, current_user.id, str(program_id), body.model_dump(mode="json"))
    if row is None:
        raise _not_found("Participation program not found.")
    return ResourceResponse(**row)


@router.put("/programs/{program_id}/resources/{resource_id}", response_model=ResourceResponse)
def update_resource(
    program_id: UUID, resource_id: UUID, body: ResourceUpdate, current_user: CurrentUser = Depends(require_industry)
) -> ResourceResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.update_resource(client, current_user.id, str(program_id), str(resource_id), body.model_dump(mode="json", exclude_unset=True))
    if row is None:
        raise _not_found("Resource not found.")
    return ResourceResponse(**row)


@router.post("/programs/{program_id}/resources/{resource_id}/publish", response_model=ResourceResponse)
def publish_resource(program_id: UUID, resource_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> ResourceResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.set_resource_published(client, current_user.id, str(program_id), str(resource_id), True)
    if row is None:
        raise _not_found("Resource not found.")
    return ResourceResponse(**row)


@router.post("/programs/{program_id}/resources/{resource_id}/unpublish", response_model=ResourceResponse)
def unpublish_resource(program_id: UUID, resource_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> ResourceResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.set_resource_published(client, current_user.id, str(program_id), str(resource_id), False)
    if row is None:
        raise _not_found("Resource not found.")
    return ResourceResponse(**row)


# ---- assignments ----


@router.get("/programs/{program_id}/assignments", response_model=AssignmentListResponse)
def list_assignments(program_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> AssignmentListResponse:
    client = build_user_client(current_user.access_token)
    rows = program_service.list_assignments(client, current_user.id, str(program_id))
    if rows is None:
        raise _not_found("Participation program not found.")
    return AssignmentListResponse(assignments=rows)


@router.post("/programs/{program_id}/assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
def create_assignment(program_id: UUID, body: AssignmentCreate, current_user: CurrentUser = Depends(require_industry)) -> AssignmentResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.create_assignment(client, current_user.id, str(program_id), body.model_dump(mode="json"))
    if row is None:
        raise _not_found("Participation program not found.")
    return AssignmentResponse(**row)


@router.put("/programs/{program_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
def update_assignment(
    program_id: UUID, assignment_id: UUID, body: AssignmentUpdate, current_user: CurrentUser = Depends(require_industry)
) -> AssignmentResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.update_assignment(client, current_user.id, str(program_id), str(assignment_id), body.model_dump(mode="json", exclude_unset=True))
    if row is None:
        raise _not_found("Assignment not found.")
    return AssignmentResponse(**row)


@router.post("/programs/{program_id}/assignments/{assignment_id}/publish", response_model=AssignmentResponse)
def publish_assignment(program_id: UUID, assignment_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> AssignmentResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.set_assignment_published(client, current_user.id, str(program_id), str(assignment_id), True)
    if row is None:
        raise _not_found("Assignment not found.")

    # Best-effort: tell every current participant a new assignment is
    # available. Never turns a successful publish into an error.
    program = program_service.get_program(client, current_user.id, str(program_id))
    if program:
        fk = {"PROJECT": "project_id", "TRAINING": "training_id", "WORKSHOP": "workshop_id"}[program["kind"]]
        opportunity_id = program.get(fk)
        for ws in workspace_service.list_workspaces_for_opportunity(client, program["kind"], opportunity_id):
            notification_producer.emit_participation_new_assignment(
                student_id=ws["student_id"], workspace_id=ws["id"], assignment_title=row["title"]
            )

    return AssignmentResponse(**row)


@router.post("/programs/{program_id}/assignments/{assignment_id}/unpublish", response_model=AssignmentResponse)
def unpublish_assignment(program_id: UUID, assignment_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> AssignmentResponse:
    client = build_user_client(current_user.access_token)
    row = program_service.set_assignment_published(client, current_user.id, str(program_id), str(assignment_id), False)
    if row is None:
        raise _not_found("Assignment not found.")
    return AssignmentResponse(**row)


# ---- evaluation criteria ----


@router.get("/programs/{program_id}/criteria", response_model=CriterionListResponse)
def list_criteria(program_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> CriterionListResponse:
    client = build_user_client(current_user.access_token)
    if program_service.get_program(client, current_user.id, str(program_id)) is None:
        raise _not_found("Participation program not found.")
    rows = eval_service.list_criteria(client, str(program_id))
    return CriterionListResponse(criteria=rows)


@router.post("/programs/{program_id}/criteria", response_model=CriterionResponse, status_code=status.HTTP_201_CREATED)
def create_criterion(program_id: UUID, body: CriterionCreate, current_user: CurrentUser = Depends(require_industry)) -> CriterionResponse:
    client = build_user_client(current_user.access_token)
    if program_service.get_program(client, current_user.id, str(program_id)) is None:
        raise _not_found("Participation program not found.")
    row = eval_service.create_criterion(client, str(program_id), body.model_dump(mode="json"))
    return CriterionResponse(**row)


@router.put("/programs/{program_id}/criteria/{criterion_id}", response_model=CriterionResponse)
def update_criterion(
    program_id: UUID, criterion_id: UUID, body: CriterionUpdate, current_user: CurrentUser = Depends(require_industry)
) -> CriterionResponse:
    client = build_user_client(current_user.access_token)
    if program_service.get_program(client, current_user.id, str(program_id)) is None:
        raise _not_found("Participation program not found.")
    row = eval_service.update_criterion(client, str(program_id), str(criterion_id), body.model_dump(mode="json", exclude_unset=True))
    if row is None:
        raise _not_found("Criterion not found.")
    return CriterionResponse(**row)


@router.delete("/programs/{program_id}/criteria/{criterion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_criterion(program_id: UUID, criterion_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> None:
    client = build_user_client(current_user.access_token)
    if program_service.get_program(client, current_user.id, str(program_id)) is None:
        raise _not_found("Participation program not found.")
    try:
        eval_service.delete_criterion(client, str(program_id), str(criterion_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This criterion has already been used in an evaluation and cannot be removed.",
        ) from exc


# ============================================================
# Workspaces
# ============================================================


@router.post("/workspaces/ensure", response_model=WorkspaceResponse, status_code=status.HTTP_200_OK)
def ensure_workspace(body: EnsureWorkspaceRequest, current_user: CurrentUser = Depends(require_industry)) -> WorkspaceResponse:
    client = build_user_client(current_user.access_token)
    application_id = {
        "PROJECT": body.project_application_id,
        "TRAINING": body.training_application_id,
        "WORKSHOP": body.workshop_application_id,
    }[body.kind]
    try:
        row = workspace_service.ensure_workspace(client, current_user.id, body.kind, str(application_id))
    except LookupError as exc:
        raise _not_found("That application was not found among your own postings.") from exc
    except workspace_service.ApplicationNotEligibleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("provision the participation workspace") from exc
    return WorkspaceResponse(**row)


@router.get("/workspaces", response_model=WorkspaceListResponse)
def list_workspaces(
    kind: ParticipationKind | None = Query(default=None),
    workspace_status: WorkspaceStatus | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_industry),
) -> WorkspaceListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = workspace_service.list_workspaces(client, current_user.id, kind=kind, status=workspace_status)
    except Exception as exc:
        raise _server_error("load participation workspaces") from exc
    return WorkspaceListResponse(workspaces=rows)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> WorkspaceResponse:
    client = build_user_client(current_user.access_token)
    row = workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True)
    if row is None:
        raise _not_found("Participation workspace not found.")
    row["progress"] = workspace_service.get_progress(client, str(workspace_id))
    return WorkspaceResponse(**row)


# ---- submissions / reviews ----


@router.get("/workspaces/{workspace_id}/submissions", response_model=SubmissionListResponse)
def list_submissions(workspace_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> SubmissionListResponse:
    client = build_user_client(current_user.access_token)
    if workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True) is None:
        raise _not_found("Participation workspace not found.")
    rows = submission_service.list_submissions(client, str(workspace_id))
    return SubmissionListResponse(submissions=rows)


@router.post("/submissions/{submission_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(submission_id: UUID, body: ReviewCreate, current_user: CurrentUser = Depends(require_industry)) -> ReviewResponse:
    client = build_user_client(current_user.access_token)
    # Ownership check first: only Industry-owned submissions are readable
    # through this user-scoped client at all (RLS), so a lookup miss here
    # is indistinguishable from "not yours" -- same 404 contract as
    # everywhere else in this module.
    submission_row = client.table("participation_submissions").select("workspace_id, assignment_id").eq("id", str(submission_id)).maybe_single().execute()
    submission = submission_row.data if submission_row is not None else None
    if submission is None:
        raise _not_found("Submission not found.")

    try:
        row = submission_service.create_review(client, str(submission_id), body.model_dump(mode="json"))
    except Exception as exc:
        raise _server_error("record the review") from exc

    workspace = client.table("participation_workspaces").select("student_id").eq("id", submission["workspace_id"]).maybe_single().execute()
    assignment = client.table("participation_assignments").select("title").eq("id", submission["assignment_id"]).maybe_single().execute()
    if workspace is not None and workspace.data:
        notification_producer.emit_participation_submission_reviewed(
            student_id=workspace.data["student_id"],
            workspace_id=submission["workspace_id"],
            verdict=body.status,
            assignment_title=(assignment.data or {}).get("title", "an assignment") if assignment is not None else "an assignment",
        )

    return ReviewResponse(**row)


# ---- feedback ----


@router.get("/workspaces/{workspace_id}/feedback", response_model=FeedbackListResponse)
def list_feedback(workspace_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> FeedbackListResponse:
    client = build_user_client(current_user.access_token)
    if workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True) is None:
        raise _not_found("Participation workspace not found.")
    rows = feedback_service.list_feedback(client, str(workspace_id))
    return FeedbackListResponse(feedback=rows)


@router.post("/workspaces/{workspace_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def create_feedback(workspace_id: UUID, body: FeedbackCreate, current_user: CurrentUser = Depends(require_industry)) -> FeedbackResponse:
    client = build_user_client(current_user.access_token)
    workspace = workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True)
    if workspace is None:
        raise _not_found("Participation workspace not found.")
    row = feedback_service.create_feedback(client, str(workspace_id), body.model_dump(mode="json"))
    notification_producer.emit_participation_new_feedback(student_id=workspace["student_id"], workspace_id=str(workspace_id))
    return FeedbackResponse(**row)


# ---- skill recommendations ----


@router.get("/workspaces/{workspace_id}/recommendations", response_model=SkillRecommendationListResponse)
def list_recommendations(workspace_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> SkillRecommendationListResponse:
    client = build_user_client(current_user.access_token)
    if workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True) is None:
        raise _not_found("Participation workspace not found.")
    rows = feedback_service.list_recommendations(client, str(workspace_id))
    return SkillRecommendationListResponse(recommendations=rows)


@router.post("/workspaces/{workspace_id}/recommendations", response_model=SkillRecommendationResponse, status_code=status.HTTP_201_CREATED)
def create_recommendation(workspace_id: UUID, body: SkillRecommendationCreate, current_user: CurrentUser = Depends(require_industry)) -> SkillRecommendationResponse:
    client = build_user_client(current_user.access_token)
    workspace = workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True)
    if workspace is None:
        raise _not_found("Participation workspace not found.")
    row = feedback_service.create_recommendation(client, str(workspace_id), body.model_dump(mode="json"))
    notification_producer.emit_participation_new_recommendation(
        student_id=workspace["student_id"], workspace_id=str(workspace_id), skill_name=row.get("skill_name") or "a skill"
    )
    return SkillRecommendationResponse(**row)


# ---- evaluation ----


@router.get("/workspaces/{workspace_id}/evaluation", response_model=EvaluationResponse)
def get_evaluation(workspace_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> EvaluationResponse:
    client = build_user_client(current_user.access_token)
    if workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True) is None:
        raise _not_found("Participation workspace not found.")
    row = eval_service.ensure_evaluation(client, str(workspace_id))
    return EvaluationResponse(**row)


@router.put("/workspaces/{workspace_id}/evaluation", response_model=EvaluationResponse)
def save_evaluation(workspace_id: UUID, body: EvaluationSaveRequest, current_user: CurrentUser = Depends(require_industry)) -> EvaluationResponse:
    client = build_user_client(current_user.access_token)
    if workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True) is None:
        raise _not_found("Participation workspace not found.")
    try:
        row = eval_service.save_evaluation(client, str(workspace_id), body.model_dump(mode="json"))
    except eval_service.EvaluationFinalizedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This evaluation has already been finalized.") from exc
    except Exception as exc:
        raise _server_error("save the evaluation") from exc
    return EvaluationResponse(**row)


@router.post("/workspaces/{workspace_id}/evaluation/finalize", response_model=EvaluationResponse)
def finalize_evaluation(workspace_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> EvaluationResponse:
    client = build_user_client(current_user.access_token)
    workspace = workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True)
    if workspace is None:
        raise _not_found("Participation workspace not found.")
    program_id = workspace.get("program_id")
    try:
        row = eval_service.finalize_evaluation(client, program_id, str(workspace_id))
    except eval_service.EvaluationFinalizedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This evaluation has already been finalized.") from exc
    except eval_service.IncompleteRubricError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Score every criterion before finalizing: " + ", ".join(exc.missing),
        ) from exc
    except Exception as exc:
        raise _server_error("finalize the evaluation") from exc
    notification_producer.emit_participation_evaluation_finalized(student_id=workspace["student_id"], workspace_id=str(workspace_id))
    return EvaluationResponse(**row)


# ---- completion ----


@router.get("/workspaces/{workspace_id}/completion", response_model=CompletionResponse)
def get_completion(workspace_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> CompletionResponse:
    client = build_user_client(current_user.access_token)
    if workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True) is None:
        raise _not_found("Participation workspace not found.")
    row = eval_service.get_completion(client, str(workspace_id))
    if row is None:
        raise _not_found("This workspace has not been completed yet.")
    return CompletionResponse(**row)


@router.post("/workspaces/{workspace_id}/complete", response_model=CompletionResponse, status_code=status.HTTP_201_CREATED)
def complete_workspace(workspace_id: UUID, current_user: CurrentUser = Depends(require_industry)) -> CompletionResponse:
    client = build_user_client(current_user.access_token)
    workspace = workspace_service.get_workspace(client, current_user.id, str(workspace_id), as_industry=True)
    if workspace is None:
        raise _not_found("Participation workspace not found.")
    try:
        row = eval_service.create_completion(client, workspace.get("program_id"), str(workspace_id))
    except eval_service.CompletionNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("complete this participation") from exc
    notification_producer.emit_participation_completed(student_id=workspace["student_id"], workspace_id=str(workspace_id))
    return CompletionResponse(**row)
