"""API routes for the STUDENT view of their own Internship Workspaces
(database/migrations/038_internship_workspace.sql).

PHASE 3: list, detail (with the PUBLISHED program preview), accept,
decline, optional-skill selection.
PHASE 5: the workspace's published assignments, one assignment's detail
with full attempt history, and creating an append-only submission
attempt.
PHASE 7: the student's read-only completion + certificate summary.
PHASE 8: the student's read-only stipend summary. This module NEVER
writes submission_reviews, internship_completions,
internship_certificates or stipend_disbursements -- verification and
stipend management are industry-only actions.

Guarded by require_student(); every read/write goes through
build_user_client(current_user.access_token) -- so Supabase RLS
("Students can view their own internship workspace", the
enforce_workspace_status_transitions and enforce_workspace_skill_selectable
triggers) stays the real access-control boundary. `student_id` is always
current_user.id, never read from the request. A workspace the student
does not own is a clean 404, indistinguishable from one that does not
exist.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.internship_completion import CompletionSummary
from app.schemas.internship_stipend import StipendSummary
from app.schemas.internship_workspace import (
    CreateSubmissionRequest,
    DeclineWorkspaceRequest,
    InternshipWorkspaceDetail,
    InternshipWorkspaceListResponse,
    InternshipWorkspaceSummary,
    SkillSelectionRequest,
    WorkspaceAssignmentDetail,
    WorkspaceAssignmentListResponse,
    WorkspaceAssignmentSummary,
)
from app.services import internship_workspace_service as workspace_service

router = APIRouter(
    prefix="/student/internship-workspaces", tags=["student-internship-workspaces"]
)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Internship workspace not found."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=InternshipWorkspaceListResponse)
def list_my_internship_workspaces(
    current_user: CurrentUser = Depends(require_student),
) -> InternshipWorkspaceListResponse:
    """Every internship workspace belonging to the authenticated student,
    newest first -- across all statuses. A workspace stays listed even
    after its internship posting is CLOSED / ARCHIVED."""
    client = build_user_client(current_user.access_token)
    try:
        rows = workspace_service.list_student_workspaces(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your internship workspaces") from exc
    return InternshipWorkspaceListResponse(
        workspaces=[InternshipWorkspaceSummary(**row) for row in rows]
    )


@router.get("/{workspace_id}", response_model=InternshipWorkspaceDetail)
def get_my_internship_workspace(
    workspace_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> InternshipWorkspaceDetail:
    """One workspace the student owns, with the PUBLISHED program preview
    (modules / items / skills) and the student's current optional-skill
    selections. Readable regardless of the internship posting's status."""
    client = build_user_client(current_user.access_token)
    try:
        row = workspace_service.get_student_workspace(client, current_user.id, workspace_id)
    except Exception as exc:
        raise _server_error("load this internship workspace") from exc
    if row is None:
        raise _not_found()
    return InternshipWorkspaceDetail(**row)


@router.post("/{workspace_id}/accept", response_model=InternshipWorkspaceDetail)
def accept_my_internship_workspace(
    workspace_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> InternshipWorkspaceDetail:
    """Accept a still-pending internship offer: PENDING_ACCEPTANCE ->
    ACCEPTED. Only the owner, only from PENDING_ACCEPTANCE (the DB trigger
    enforce_workspace_status_transitions is the final authority). Does not
    touch the application or internship."""
    client = build_user_client(current_user.access_token)
    try:
        row = workspace_service.accept_workspace(client, current_user.id, workspace_id)
    except workspace_service.WorkspaceNotFoundError as exc:
        raise _not_found() from exc
    except workspace_service.InvalidWorkspaceTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This internship workspace can't be accepted from '{exc.current}'.",
        ) from exc
    except Exception as exc:
        raise _server_error("accept this internship workspace") from exc
    return InternshipWorkspaceDetail(**row)


@router.post("/{workspace_id}/decline", response_model=InternshipWorkspaceDetail)
def decline_my_internship_workspace(
    workspace_id: str,
    body: DeclineWorkspaceRequest,
    current_user: CurrentUser = Depends(require_student),
) -> InternshipWorkspaceDetail:
    """Decline a still-pending internship offer: PENDING_ACCEPTANCE ->
    DECLINED. Only the owner, only from PENDING_ACCEPTANCE. Does not touch
    the application or internship."""
    client = build_user_client(current_user.access_token)
    try:
        row = workspace_service.decline_workspace(
            client, current_user.id, workspace_id, body.reason
        )
    except workspace_service.WorkspaceNotFoundError as exc:
        raise _not_found() from exc
    except workspace_service.InvalidWorkspaceTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This internship workspace can't be declined from '{exc.current}'.",
        ) from exc
    except Exception as exc:
        raise _server_error("decline this internship workspace") from exc
    return InternshipWorkspaceDetail(**row)


@router.put("/{workspace_id}/skills", response_model=InternshipWorkspaceDetail)
def set_my_internship_workspace_skills(
    workspace_id: str,
    body: SkillSelectionRequest,
    current_user: CurrentUser = Depends(require_student),
) -> InternshipWorkspaceDetail:
    """Replace-set the student's OPTIONAL training-skill selections.
    REQUIRED program skills are always in scope and cannot be removed
    (they are never stored here). A skill that is not an OPTIONAL skill of
    this workspace's program is rejected."""
    client = build_user_client(current_user.access_token)
    try:
        row = workspace_service.set_skill_selections(
            client, current_user.id, workspace_id, body.skill_ids
        )
    except workspace_service.WorkspaceNotFoundError as exc:
        raise _not_found() from exc
    except workspace_service.WorkspaceNotAcceptedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except workspace_service.InvalidSkillSelectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise _server_error("save your training skills") from exc
    return InternshipWorkspaceDetail(**row)


# ============================================================
# Phase 5 -- assignments + submissions
# ============================================================


def _assignment_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")


@router.get("/{workspace_id}/assignments", response_model=WorkspaceAssignmentListResponse)
def list_my_workspace_assignments(
    workspace_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> WorkspaceAssignmentListResponse:
    """Every published assignment in the student's own workspace's
    program, ordered by module then assignment, each with the student's
    latest attempt and whether a new submission is currently allowed."""
    client = build_user_client(current_user.access_token)
    try:
        rows = workspace_service.list_workspace_assignments(
            client, current_user.id, workspace_id
        )
    except workspace_service.WorkspaceNotFoundError as exc:
        raise _not_found() from exc
    except Exception as exc:
        raise _server_error("load your assignments") from exc
    return WorkspaceAssignmentListResponse(
        assignments=[WorkspaceAssignmentSummary(**row) for row in rows]
    )


@router.get(
    "/{workspace_id}/assignments/{assignment_id}", response_model=WorkspaceAssignmentDetail
)
def get_my_workspace_assignment(
    workspace_id: str,
    assignment_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> WorkspaceAssignmentDetail:
    """One visible assignment plus every attempt the student has made
    against it (newest first). 404 if the workspace isn't the student's or
    the assignment isn't visible in its program."""
    client = build_user_client(current_user.access_token)
    try:
        row = workspace_service.get_workspace_assignment(
            client, current_user.id, workspace_id, assignment_id
        )
    except Exception as exc:
        raise _server_error("load this assignment") from exc
    if row is None:
        raise _assignment_not_found()
    return WorkspaceAssignmentDetail(**row)


@router.post(
    "/{workspace_id}/assignments/{assignment_id}/submissions",
    response_model=WorkspaceAssignmentDetail,
    status_code=status.HTTP_201_CREATED,
)
def submit_my_workspace_assignment(
    workspace_id: str,
    assignment_id: str,
    body: CreateSubmissionRequest,
    current_user: CurrentUser = Depends(require_student),
) -> WorkspaceAssignmentDetail:
    """Create the next append-only submission attempt. `attempt_number`
    and `submission_status` (SUBMITTED) are always server-set. A
    resubmission is a NEW attempt -- the previous one is never modified."""
    client = build_user_client(current_user.access_token)
    try:
        row = workspace_service.create_submission(
            client,
            current_user.id,
            workspace_id,
            assignment_id,
            body.model_dump(exclude_unset=True),
        )
    except workspace_service.WorkspaceNotFoundError as exc:
        raise _not_found() from exc
    except workspace_service.AssignmentNotFoundError as exc:
        raise _assignment_not_found() from exc
    except workspace_service.WorkspaceNotAcceptedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except workspace_service.SubmissionRejectedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except workspace_service.InvalidSubmissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise _server_error("submit your work") from exc
    return WorkspaceAssignmentDetail(**row)


# ============================================================
# Phase 7 -- completion + certificate (read-only)
# ============================================================


@router.get("/{workspace_id}/completion", response_model=CompletionSummary)
def get_my_workspace_completion(
    workspace_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> CompletionSummary:
    """The completion summary for the student's own workspace: how many
    REQUIRED assignments are done, what's outstanding, whether industry
    has verified, and the certificate once issued. Read-only -- students
    never verify their own completion."""
    client = build_user_client(current_user.access_token)
    try:
        row = workspace_service.get_student_completion(client, current_user.id, workspace_id)
    except Exception as exc:
        raise _server_error("load your completion status") from exc
    if row is None:
        raise _not_found()
    return CompletionSummary(**row)


# ============================================================
# Phase 8 -- stipend (read-only; RECORD-KEEPING ONLY, no payment gateway)
# ============================================================


@router.get("/{workspace_id}/stipend", response_model=StipendSummary)
def get_my_workspace_stipend(
    workspace_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> StipendSummary:
    """The stipend summary for the student's own workspace. Read-only --
    students never create, edit, approve, release, or cancel a stipend
    record. `stipend: null` means none has been configured yet, a normal
    200, never a 404."""
    client = build_user_client(current_user.access_token)
    try:
        row = workspace_service.get_student_stipend(client, current_user.id, workspace_id)
    except Exception as exc:
        raise _server_error("load your stipend status") from exc
    if row is None:
        raise _not_found()
    return StipendSummary(**row)
