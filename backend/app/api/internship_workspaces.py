"""API routes for the INDUSTRY view of Internship Workspaces belonging to
its own internship postings (database/migrations/038_internship_workspace.sql).

PHASE 2 SCOPE: a single read endpoint, to verify provisioning. Program
authoring and submission review are later phases and are NOT in this
module. (Workspace provisioning itself is triggered by the SELECTED
transition in app.services.application_service, and can be re-run via
POST /api/v1/applications/{id}/provision-workspace in app.api.applications.)

PHASE 7 adds completion + certificate: a read-only summary and the
explicit verification action.
PHASE 8 adds stipend record-keeping: a read-only summary, configuring the
one stipend record, and the approve/release/cancel transitions.
RECORD-KEEPING ONLY -- no payment gateway, no bank/UPI integration, no
real money movement.

Guarded by require_industry(); every read/write goes through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so Supabase RLS ("Industry can view internship workspaces
for their own internships", auth.uid() = industry_id) stays the real
access-control boundary. The owning industry account is always
current_user.id, never read from the request.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.internship_completion import CompletionSummary, VerifyCompletionRequest
from app.schemas.internship_stipend import (
    CreateStipendRequest,
    StipendSummary,
    UpdateStipendRequest,
)
from app.schemas.internship_workspace import (
    InternshipWorkspaceListResponse,
    InternshipWorkspaceSummary,
    WorkspaceStatus,
)
from app.services import internship_workspace_service, notification_producer

router = APIRouter(prefix="/internship-workspaces", tags=["internship-workspaces"])


@router.get("", response_model=InternshipWorkspaceListResponse)
def list_internship_workspaces(
    internship_id: UUID | None = Query(default=None),
    workspace_status: WorkspaceStatus | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_industry),
) -> InternshipWorkspaceListResponse:
    """Internship workspaces for the authenticated industry account's own
    postings, newest first. Optional `internship_id` and `status` filters
    are additive."""
    client = build_user_client(current_user.access_token)
    try:
        rows = internship_workspace_service.list_industry_workspaces(
            client,
            current_user.id,
            internship_id=str(internship_id) if internship_id else None,
            workspace_status=workspace_status,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load internship workspaces. Please try again.",
        ) from exc
    return InternshipWorkspaceListResponse(
        workspaces=[InternshipWorkspaceSummary(**row) for row in rows]
    )


def _workspace_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Internship workspace not found."
    )


@router.get("/{workspace_id}/completion", response_model=CompletionSummary)
def get_workspace_completion(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> CompletionSummary:
    """The completion summary for one of the industry's own workspaces:
    required/completed counts, outstanding requirements, verification
    state, and the certificate once issued. Always computed live from
    program_assignments + workspace_submissions -- never a stored
    percentage."""
    client = build_user_client(current_user.access_token)
    try:
        row = internship_workspace_service.get_industry_completion(
            client, current_user.id, str(workspace_id)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the completion summary. Please try again.",
        ) from exc
    if row is None:
        raise _workspace_not_found()
    return CompletionSummary(**row)


@router.post("/{workspace_id}/completion/verify", response_model=CompletionSummary)
def verify_workspace_completion(
    workspace_id: UUID,
    body: VerifyCompletionRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> CompletionSummary:
    """Explicitly verify that this workspace's REQUIRED, published
    assignments are all ACCEPTED, then record the completion (PASS) and
    issue the certificate. Idempotent: repeat calls return the SAME
    completion + certificate, never a duplicate. Never accepts
    student_id / industry_id / outcome / certificate_number from the
    client -- every one is server-derived."""
    client = build_user_client(current_user.access_token)
    try:
        row = internship_workspace_service.verify_workspace_completion(
            client, current_user.id, str(workspace_id), body.summary
        )
    except internship_workspace_service.WorkspaceNotFoundError as exc:
        raise _workspace_not_found() from exc
    except internship_workspace_service.InvalidWorkspaceStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An internship workspace at '{exc.current}' cannot be completed.",
        ) from exc
    except internship_workspace_service.RequirementsNotMetError as exc:
        titles = ", ".join(r["title"] for r in exc.outstanding)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot complete this internship yet. Outstanding: {titles}.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify completion. Please try again.",
        ) from exc

    # Best-effort, exactly once: notify the student only the first time
    # this workspace becomes verified. row["_newly_verified"] is False on
    # a repeat/idempotent call (the same already-issued certificate is
    # returned), so a repeated verify never re-notifies.
    if row.get("_newly_verified") and row.get("_student_id"):
        certificate = row.get("certificate") or {}
        notification_producer.emit_internship_completed(
            student_id=row["_student_id"],
            workspace_id=str(workspace_id),
            internship_title=certificate.get("internship_title"),
            certificate_number=certificate.get("certificate_number"),
        )
    return CompletionSummary(**row)


# ============================================================
# Phase 8 -- stipend record-keeping (RECORD-KEEPING ONLY)
# ============================================================


def _handle_stipend_error(exc: Exception) -> HTTPException:
    if isinstance(exc, internship_workspace_service.WorkspaceNotFoundError):
        return _workspace_not_found()
    if isinstance(exc, internship_workspace_service.StipendNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No stipend record exists for this workspace yet.",
        )
    if isinstance(exc, internship_workspace_service.StipendExistsError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A stipend record already exists for this workspace.",
        )
    if isinstance(exc, internship_workspace_service.StipendImmutableError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, internship_workspace_service.InvalidStipendTransitionError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, internship_workspace_service.StipendRejectedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not complete that stipend action. Please try again.",
    )


def _notify_stipend_change(row: dict, new_status: str) -> None:
    if row.get("_student_id"):
        notification_producer.emit_stipend_status_change(
            student_id=row["_student_id"], workspace_id=row["workspace_id"], new_status=new_status
        )


@router.get("/{workspace_id}/stipend", response_model=StipendSummary)
def get_workspace_stipend(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> StipendSummary:
    """The stipend summary for one of the industry's own workspaces.
    `stipend: null` means none has been configured yet -- that is a
    normal 200, not a 404."""
    client = build_user_client(current_user.access_token)
    try:
        row = internship_workspace_service.get_industry_stipend(
            client, current_user.id, str(workspace_id)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the stipend summary. Please try again.",
        ) from exc
    if row is None:
        raise _workspace_not_found()
    return StipendSummary(**row)


@router.post(
    "/{workspace_id}/stipend", response_model=StipendSummary, status_code=status.HTTP_201_CREATED
)
def create_workspace_stipend(
    workspace_id: UUID,
    body: CreateStipendRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> StipendSummary:
    """Configure the ONE stipend record for this workspace -- starts
    PENDING. 409 if one already exists. `disbursement_status` /
    `released_by` are never accepted -- always server-derived."""
    client = build_user_client(current_user.access_token)
    try:
        row = internship_workspace_service.create_stipend(
            client, current_user.id, str(workspace_id), body.model_dump()
        )
    except Exception as exc:
        raise _handle_stipend_error(exc) from exc
    return StipendSummary(**row)


@router.put("/{workspace_id}/stipend", response_model=StipendSummary)
def update_workspace_stipend(
    workspace_id: UUID,
    body: UpdateStipendRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> StipendSummary:
    """Edit amount / currency / reference / notes -- only while PENDING.
    409 once APPROVED / RELEASED / CANCELLED."""
    client = build_user_client(current_user.access_token)
    try:
        row = internship_workspace_service.update_stipend_details(
            client, current_user.id, str(workspace_id), body.model_dump(exclude_unset=True)
        )
    except Exception as exc:
        raise _handle_stipend_error(exc) from exc
    return StipendSummary(**row)


@router.post("/{workspace_id}/stipend/approve", response_model=StipendSummary)
def approve_workspace_stipend(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> StipendSummary:
    """PENDING -> APPROVED. 409 for any other current status, including an
    already-APPROVED record -- a repeat request is rejected, never a
    silent no-op."""
    client = build_user_client(current_user.access_token)
    try:
        row = internship_workspace_service.approve_stipend(
            client, current_user.id, str(workspace_id)
        )
    except Exception as exc:
        raise _handle_stipend_error(exc) from exc
    _notify_stipend_change(row, "APPROVED")
    return StipendSummary(**row)


@router.post("/{workspace_id}/stipend/release", response_model=StipendSummary)
def release_workspace_stipend(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> StipendSummary:
    """APPROVED -> RELEASED. RECORD-KEEPING ONLY -- this records that a
    disbursement happened; it never moves money. `released_by` /
    `released_at` are DB-forced to the caller and now()."""
    client = build_user_client(current_user.access_token)
    try:
        row = internship_workspace_service.release_stipend(
            client, current_user.id, str(workspace_id)
        )
    except Exception as exc:
        raise _handle_stipend_error(exc) from exc
    _notify_stipend_change(row, "RELEASED")
    return StipendSummary(**row)


@router.post("/{workspace_id}/stipend/cancel", response_model=StipendSummary)
def cancel_workspace_stipend(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> StipendSummary:
    """PENDING -> CANCELLED. Terminal."""
    client = build_user_client(current_user.access_token)
    try:
        row = internship_workspace_service.cancel_stipend(
            client, current_user.id, str(workspace_id)
        )
    except Exception as exc:
        raise _handle_stipend_error(exc) from exc
    _notify_stipend_change(row, "CANCELLED")
    return StipendSummary(**row)
