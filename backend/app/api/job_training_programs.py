"""API routes for INDUSTRY Job Training program authoring
(database/migrations/052_job_training.sql).

Nested under a job: /api/v1/jobs/{job_id}/training-program. Mirrors
app.api.internship_programs (the internship-program authoring analog).
Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS
(public.owns_job_program + the job-ownership predicate) stays the real
access-control boundary. The owning industry is always current_user.id;
it is never read from the request. A job / program / module / item /
assignment the caller does not own is a clean 404.

PHASE J2: program metadata, ordered modules, learning items,
required/optional program skills, gradable assignments, and
publish / unpublish. This module NEVER touches job_training_enrollments
and has no student-facing surface, no provisioning, no completion /
certificate / progress / notification code -- those are later phases.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.job_training_program import (
    JobAssignmentCreate,
    JobAssignmentUpdate,
    JobProgramBundle,
    JobProgramCreate,
    JobProgramItemCreate,
    JobProgramItemUpdate,
    JobProgramModuleCreate,
    JobProgramModuleUpdate,
    JobProgramSkillsUpdate,
    JobProgramUpdate,
    ReorderRequest,
)
from app.services import job_training_program_service as program_service

router = APIRouter(
    prefix="/jobs/{job_id}/training-program", tags=["industry-job-training-program"]
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


_JOB_404 = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
_PROGRAM_404 = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="No training program has been created for this job yet.",
)
_MODULE_404 = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")
_ITEM_404 = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module item not found.")
_ASSIGNMENT_404 = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found."
)


def _handle(exc: Exception) -> HTTPException:
    """Map a service error to an HTTPException (unknown errors -> 500)."""
    if isinstance(exc, program_service.JobNotFoundError):
        return _JOB_404
    if isinstance(exc, program_service.ProgramNotFoundError):
        return _PROGRAM_404
    if isinstance(exc, program_service.ModuleNotFoundError):
        return _MODULE_404
    if isinstance(exc, program_service.ItemNotFoundError):
        return _ITEM_404
    if isinstance(exc, program_service.AssignmentNotFoundError):
        return _ASSIGNMENT_404
    if isinstance(exc, program_service.ProgramExistsError):
        return _conflict("This job already has a training program.")
    if isinstance(exc, program_service.InvalidStatusTransitionError):
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
        | program_service.InvalidAssignmentError,
    ):
        return _unprocessable(str(exc))
    return _server_error("complete that action")


def _run(fn, *args) -> JobProgramBundle:
    try:
        bundle = fn(*args)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle(exc) from exc
    return JobProgramBundle(**bundle)


# ============================================================
# program metadata + lifecycle
# ============================================================


@router.get("", response_model=JobProgramBundle)
def get_program(
    job_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(program_service.get_program_bundle, client, current_user.id, str(job_id))


@router.post("", response_model=JobProgramBundle, status_code=status.HTTP_201_CREATED)
def create_program(
    job_id: UUID,
    body: JobProgramCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.create_program,
        client,
        current_user.id,
        str(job_id),
        body.model_dump(),
    )


@router.put("", response_model=JobProgramBundle)
def update_program(
    job_id: UUID,
    body: JobProgramUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.update_program,
        client,
        current_user.id,
        str(job_id),
        body.model_dump(exclude_unset=True),
    )


@router.post("/publish", response_model=JobProgramBundle)
def publish_program(
    job_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(program_service.publish_program, client, current_user.id, str(job_id))


@router.post("/unpublish", response_model=JobProgramBundle)
def unpublish_program(
    job_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(program_service.unpublish_program, client, current_user.id, str(job_id))


@router.put("/skills", response_model=JobProgramBundle)
def set_program_skills(
    job_id: UUID,
    body: JobProgramSkillsUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.set_program_skills,
        client,
        current_user.id,
        str(job_id),
        [s.model_dump(mode="json") for s in body.skills],
    )


# ============================================================
# modules
# ============================================================


@router.post("/modules/reorder", response_model=JobProgramBundle)
def reorder_modules(
    job_id: UUID,
    body: ReorderRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.reorder_modules,
        client,
        current_user.id,
        str(job_id),
        [str(x) for x in body.ordered_ids],
    )


@router.post(
    "/modules", response_model=JobProgramBundle, status_code=status.HTTP_201_CREATED
)
def create_module(
    job_id: UUID,
    body: JobProgramModuleCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.create_module,
        client,
        current_user.id,
        str(job_id),
        body.model_dump(),
    )


@router.put("/modules/{module_id}", response_model=JobProgramBundle)
def update_module(
    job_id: UUID,
    module_id: UUID,
    body: JobProgramModuleUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.update_module,
        client,
        current_user.id,
        str(job_id),
        str(module_id),
        body.model_dump(exclude_unset=True),
    )


# ============================================================
# module items
# ============================================================


@router.post("/modules/{module_id}/items/reorder", response_model=JobProgramBundle)
def reorder_items(
    job_id: UUID,
    module_id: UUID,
    body: ReorderRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.reorder_items,
        client,
        current_user.id,
        str(job_id),
        str(module_id),
        [str(x) for x in body.ordered_ids],
    )


@router.post(
    "/modules/{module_id}/items",
    response_model=JobProgramBundle,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    job_id: UUID,
    module_id: UUID,
    body: JobProgramItemCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.create_item,
        client,
        current_user.id,
        str(job_id),
        str(module_id),
        body.model_dump(),
    )


@router.put("/modules/{module_id}/items/{item_id}", response_model=JobProgramBundle)
def update_item(
    job_id: UUID,
    module_id: UUID,
    item_id: UUID,
    body: JobProgramItemUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.update_item,
        client,
        current_user.id,
        str(job_id),
        str(module_id),
        str(item_id),
        body.model_dump(exclude_unset=True),
    )


# ============================================================
# assignments (within a module)
# ============================================================


@router.post("/modules/{module_id}/assignments/reorder", response_model=JobProgramBundle)
def reorder_assignments(
    job_id: UUID,
    module_id: UUID,
    body: ReorderRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.reorder_assignments,
        client,
        current_user.id,
        str(job_id),
        str(module_id),
        [str(x) for x in body.ordered_ids],
    )


@router.post(
    "/modules/{module_id}/assignments",
    response_model=JobProgramBundle,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    job_id: UUID,
    module_id: UUID,
    body: JobAssignmentCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.create_assignment,
        client,
        current_user.id,
        str(job_id),
        str(module_id),
        body.model_dump(mode="json"),
    )


@router.put(
    "/modules/{module_id}/assignments/{assignment_id}",
    response_model=JobProgramBundle,
)
def update_assignment(
    job_id: UUID,
    module_id: UUID,
    assignment_id: UUID,
    body: JobAssignmentUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobProgramBundle:
    client = build_user_client(current_user.access_token)
    return _run(
        program_service.update_assignment,
        client,
        current_user.id,
        str(job_id),
        str(module_id),
        str(assignment_id),
        body.model_dump(mode="json", exclude_unset=True),
    )
