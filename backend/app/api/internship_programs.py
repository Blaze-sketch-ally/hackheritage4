"""API routes for INDUSTRY internship-program authoring
(database/migrations/037_internship_program.sql).

Nested under an internship: /api/v1/internships/{internship_id}/program.
Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS
(public.owns_internship_program + the internship-ownership predicate)
stays the real access-control boundary. The owning industry is always
current_user.id; it is never read from the request. An internship /
program / module / item the caller does not own is a clean 404.

PHASE 4: program metadata, modules, module items, required/optional
program skills, publish.
PHASE 5: assignment authoring within a module (create / update / reorder;
no delete -- hide via is_published) and a READ-ONLY submission view (list
+ detail + attempt history).
PHASE 6: reviewing a submission attempt -- start_review (SUBMITTED ->
UNDER_REVIEW) and a terminal verdict (ACCEPTED / REVISION_REQUESTED /
REJECTED) recorded in submission_reviews. Completion / certificates /
stipends stay later phases -- this module never writes
internship_completions, internship_certificates or stipend_disbursements,
and never touches an application or a program's publication state.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.internship_program import (
    AssignmentCreate,
    AssignmentUpdate,
    IndustrySubmissionDetailResponse,
    IndustrySubmissionListResponse,
    InternshipProgramBundle,
    ModuleItemCreate,
    ModuleItemUpdate,
    ProgramCreate,
    ProgramModuleCreate,
    ProgramModuleUpdate,
    ProgramSkillsUpdate,
    ProgramUpdate,
    ReorderRequest,
    ReviewSubmissionRequest,
    StartReviewRequest,
)
from app.services import internship_program_service as program_service
from app.services import notification_producer

router = APIRouter(
    prefix="/internships/{internship_id}/program", tags=["industry-internship-program"]
)


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


_INTERNSHIP_404 = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found."
)
_PROGRAM_404 = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="No program has been created for this internship yet.",
)
_MODULE_404 = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")
_ITEM_404 = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module item not found.")
_ASSIGNMENT_404 = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found."
)
_SUBMISSION_404 = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found."
)


def _handle(exc: Exception) -> HTTPException:
    """Map a service error to an HTTPException (unknown errors -> 500)."""
    if isinstance(exc, program_service.InternshipNotFoundError):
        return _INTERNSHIP_404
    if isinstance(exc, program_service.ProgramNotFoundError):
        return _PROGRAM_404
    if isinstance(exc, program_service.ModuleNotFoundError):
        return _MODULE_404
    if isinstance(exc, program_service.ItemNotFoundError):
        return _ITEM_404
    if isinstance(exc, program_service.AssignmentNotFoundError):
        return _ASSIGNMENT_404
    if isinstance(exc, program_service.SubmissionNotFoundError):
        return _SUBMISSION_404
    if isinstance(exc, program_service.ProgramExistsError):
        return _conflict("This internship already has a program.")
    if isinstance(exc, program_service.InvalidStatusTransitionError):
        return _conflict("Only a draft program can be published.")
    if isinstance(exc, program_service.InvalidReviewTransitionError):
        return _conflict(str(exc))
    if isinstance(exc, program_service.ReviewRejectedError):
        return _conflict(str(exc))
    if isinstance(exc, program_service.PublishValidationError):
        return _unprocessable(
            "This program isn't ready to publish. Add: " + ", ".join(exc.missing) + "."
        )
    if isinstance(
        exc,
        program_service.InvalidItemError
        | program_service.InvalidReorderError
        | program_service.InvalidProgramSkillError
        | program_service.InvalidAssignmentError
        | program_service.InvalidReviewError,
    ):
        return _unprocessable(str(exc))
    return _server_error("complete that action")


def _run(fn, *args) -> InternshipProgramBundle:
    try:
        bundle = fn(*args)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle(exc) from exc
    return InternshipProgramBundle(**bundle)


@router.get("", response_model=InternshipProgramBundle)
def get_program(
    internship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(program_service.get_program_bundle, client, current_user.id, str(internship_id))


@router.post("", response_model=InternshipProgramBundle, status_code=status.HTTP_201_CREATED)
def create_program(
    internship_id: UUID,
    body: ProgramCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.create_program,
        client,
        current_user.id,
        str(internship_id),
        body.model_dump(),
    )


@router.put("", response_model=InternshipProgramBundle)
def update_program(
    internship_id: UUID,
    body: ProgramUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.update_program,
        client,
        current_user.id,
        str(internship_id),
        body.model_dump(exclude_unset=True),
    )


@router.post("/publish", response_model=InternshipProgramBundle)
def publish_program(
    internship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(program_service.publish_program, client, current_user.id, str(internship_id))


@router.put("/skills", response_model=InternshipProgramBundle)
def set_program_skills(
    internship_id: UUID,
    body: ProgramSkillsUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.set_program_skills,
        client,
        current_user.id,
        str(internship_id),
        [s.model_dump(mode="json") for s in body.skills],
    )


@router.post("/modules/reorder", response_model=InternshipProgramBundle)
def reorder_modules(
    internship_id: UUID,
    body: ReorderRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.reorder_modules,
        client,
        current_user.id,
        str(internship_id),
        [str(x) for x in body.ordered_ids],
    )


@router.post(
    "/modules", response_model=InternshipProgramBundle, status_code=status.HTTP_201_CREATED
)
def create_module(
    internship_id: UUID,
    body: ProgramModuleCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.create_module,
        client,
        current_user.id,
        str(internship_id),
        body.model_dump(),
    )


@router.put("/modules/{module_id}", response_model=InternshipProgramBundle)
def update_module(
    internship_id: UUID,
    module_id: UUID,
    body: ProgramModuleUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.update_module,
        client,
        current_user.id,
        str(internship_id),
        str(module_id),
        body.model_dump(exclude_unset=True),
    )


@router.post("/modules/{module_id}/items/reorder", response_model=InternshipProgramBundle)
def reorder_items(
    internship_id: UUID,
    module_id: UUID,
    body: ReorderRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.reorder_items,
        client,
        current_user.id,
        str(internship_id),
        str(module_id),
        [str(x) for x in body.ordered_ids],
    )


@router.post(
    "/modules/{module_id}/items",
    response_model=InternshipProgramBundle,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    internship_id: UUID,
    module_id: UUID,
    body: ModuleItemCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.create_item,
        client,
        current_user.id,
        str(internship_id),
        str(module_id),
        body.model_dump(),
    )


@router.put("/modules/{module_id}/items/{item_id}", response_model=InternshipProgramBundle)
def update_item(
    internship_id: UUID,
    module_id: UUID,
    item_id: UUID,
    body: ModuleItemUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.update_item,
        client,
        current_user.id,
        str(internship_id),
        str(module_id),
        str(item_id),
        body.model_dump(exclude_unset=True),
    )


# ============================================================
# Phase 5 -- assignments (within a module)
# ============================================================


@router.post(
    "/modules/{module_id}/assignments/reorder", response_model=InternshipProgramBundle
)
def reorder_assignments(
    internship_id: UUID,
    module_id: UUID,
    body: ReorderRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.reorder_assignments,
        client,
        current_user.id,
        str(internship_id),
        str(module_id),
        [str(x) for x in body.ordered_ids],
    )


@router.post(
    "/modules/{module_id}/assignments",
    response_model=InternshipProgramBundle,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    internship_id: UUID,
    module_id: UUID,
    body: AssignmentCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.create_assignment,
        client,
        current_user.id,
        str(internship_id),
        str(module_id),
        body.model_dump(mode="json"),
    )


@router.put(
    "/modules/{module_id}/assignments/{assignment_id}",
    response_model=InternshipProgramBundle,
)
def update_assignment(
    internship_id: UUID,
    module_id: UUID,
    assignment_id: UUID,
    body: AssignmentUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.update_assignment,
        client,
        current_user.id,
        str(internship_id),
        str(module_id),
        str(assignment_id),
        body.model_dump(mode="json", exclude_unset=True),
    )


# ============================================================
# Phase 5 -- READ-ONLY industry submission view
# ============================================================


@router.get("/submissions", response_model=IndustrySubmissionListResponse)
def list_submissions(
    internship_id: UUID,
    assignment_id: UUID | None = None,
    workspace_id: UUID | None = None,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustrySubmissionListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = program_service.list_submissions(
            client,
            current_user.id,
            str(internship_id),
            assignment_id=str(assignment_id) if assignment_id else None,
            workspace_id=str(workspace_id) if workspace_id else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle(exc) from exc
    return IndustrySubmissionListResponse(submissions=rows)


@router.get("/submissions/{submission_id}", response_model=IndustrySubmissionDetailResponse)
def get_submission(
    internship_id: UUID,
    submission_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustrySubmissionDetailResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.get_submission_detail(
            client, current_user.id, str(internship_id), str(submission_id)
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle(exc) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found."
        )
    return IndustrySubmissionDetailResponse(**row)


# ============================================================
# Phase 6 -- review a submission attempt
# ============================================================


@router.post(
    "/submissions/{submission_id}/review/start",
    response_model=IndustrySubmissionDetailResponse,
)
def start_submission_review(
    internship_id: UUID,
    submission_id: UUID,
    _body: StartReviewRequest | None = None,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustrySubmissionDetailResponse:
    """Move a SUBMITTED attempt to UNDER_REVIEW. The reviewer is always the
    authenticated industry account. 404 if the submission is not for one
    of the caller's internships; 409 if it is not SUBMITTED."""
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.start_review(
            client, current_user.id, str(internship_id), str(submission_id)
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle(exc) from exc
    return IndustrySubmissionDetailResponse(**row)


@router.post(
    "/submissions/{submission_id}/review",
    response_model=IndustrySubmissionDetailResponse,
)
def review_submission(
    internship_id: UUID,
    submission_id: UUID,
    body: ReviewSubmissionRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustrySubmissionDetailResponse:
    """Record a terminal verdict (ACCEPTED / REVISION_REQUESTED /
    REJECTED) with optional feedback + score. Appends a submission_reviews
    row (reviewer_id is DB-forced to the caller) and updates the
    submission_status cache. 404 for a foreign / missing submission; 409
    if the attempt is not SUBMITTED / UNDER_REVIEW; 422 for an invalid
    score."""
    client = build_user_client(current_user.access_token)
    try:
        row = program_service.review_submission(
            client,
            current_user.id,
            str(internship_id),
            str(submission_id),
            body.model_dump(mode="json"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle(exc) from exc

    # Best-effort, exactly once: let the student know the outcome. The
    # producer writes with the service role and swallows its own errors --
    # a failed notification never turns a successful review into an error.
    notification_producer.emit_submission_review_decision(
        student_id=row.get("student_id"),
        workspace_id=row.get("workspace_id"),
        verdict=body.verdict,
        assignment_title=row.get("assignment_title"),
    )
    return IndustrySubmissionDetailResponse(**row)
