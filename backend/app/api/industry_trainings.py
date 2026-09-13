"""API routes for Industry training management.

Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. The training owner is always current_user.id;
`industry_id` is never read from the request. Lifecycle changes go
through the dedicated publish/close/archive endpoints, not PUT.

Student-facing training discovery/enrollment is NOT part of this module
(Phase 10B scope -- see database/migrations/023_industry_training.sql).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.industry_training import (
    TrainingCreate,
    TrainingListResponse,
    TrainingResponse,
    TrainingStatus,
    TrainingUpdate,
)
from app.schemas.training_application import (
    TrainingApplicationListResponse,
    TrainingApplicationResponse,
    TrainingApplicationStatus,
    TrainingApplicationStatusUpdate,
)
from app.services import (
    industry_training_application_service,
    industry_training_service,
    notification_producer,
)

router = APIRouter(prefix="/trainings", tags=["industry-training"])


def _application_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Training application not found."
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=TrainingListResponse)
def list_trainings(
    status_filter: TrainingStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_industry),
) -> TrainingListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_training_service.list_trainings(
            client, current_user.id, status=status_filter, search=search
        )
    except Exception as exc:
        raise _server_error("load your training records") from exc
    return TrainingListResponse(trainings=rows)


@router.post("", response_model=TrainingResponse, status_code=status.HTTP_201_CREATED)
def create_training(
    body: TrainingCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> TrainingResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json")
    try:
        row = industry_training_service.create_training(client, current_user.id, payload)
    except Exception as exc:
        raise _server_error("create the training record") from exc
    return TrainingResponse(**row)


@router.get("/{training_id}", response_model=TrainingResponse)
def get_training(
    training_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> TrainingResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_training_service.get_training(client, current_user.id, str(training_id))
    except Exception as exc:
        raise _server_error("load the training record") from exc
    if row is None:
        raise _not_found()
    return TrainingResponse(**row)


@router.put("/{training_id}", response_model=TrainingResponse)
def update_training(
    training_id: UUID,
    body: TrainingUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> TrainingResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json", exclude_unset=True)
    try:
        row = industry_training_service.update_training(
            client, current_user.id, str(training_id), payload
        )
    except Exception as exc:
        raise _server_error("save the training record") from exc
    if row is None:
        raise _not_found()
    return TrainingResponse(**row)


@router.post("/{training_id}/publish", response_model=TrainingResponse)
def publish_training(
    training_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> TrainingResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_training_service.publish_training(client, current_user.id, str(training_id))
    except industry_training_service.PublishValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This training record isn't ready to publish. Add: " + ", ".join(exc.missing) + ".",
        ) from exc
    except industry_training_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft or closed training record can be published.",
        ) from exc
    except Exception as exc:
        raise _server_error("publish the training record") from exc
    if row is None:
        raise _not_found()
    return TrainingResponse(**row)


@router.post("/{training_id}/close", response_model=TrainingResponse)
def close_training(
    training_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> TrainingResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_training_service.close_training(client, current_user.id, str(training_id))
    except industry_training_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a published training record can be closed.",
        ) from exc
    except Exception as exc:
        raise _server_error("close the training record") from exc
    if row is None:
        raise _not_found()
    return TrainingResponse(**row)


@router.post("/{training_id}/archive", response_model=TrainingResponse)
def archive_training(
    training_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> TrainingResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_training_service.archive_training(client, current_user.id, str(training_id))
    except industry_training_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This training record is already archived.",
        ) from exc
    except Exception as exc:
        raise _server_error("archive the training record") from exc
    if row is None:
        raise _not_found()
    return TrainingResponse(**row)


# ============================================================
# Applicants (industry_training_applications, 059_training_applications.sql)
# ============================================================


@router.get("/{training_id}/applications", response_model=TrainingApplicationListResponse)
def list_training_applications(
    training_id: UUID,
    status_filter: TrainingApplicationStatus | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_industry),
) -> TrainingApplicationListResponse:
    """Students who applied to one of the caller's own training records.
    Human-readable applicant info is attached server-side -- never a raw
    student_id."""
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_training_application_service.list_applications(
            client, current_user.id, status=status_filter, training_id=str(training_id)
        )
    except Exception as exc:
        raise _server_error("load applicants") from exc
    return TrainingApplicationListResponse(applications=rows)


@router.patch(
    "/applications/{application_id}/status", response_model=TrainingApplicationResponse
)
def update_training_application_status(
    application_id: UUID,
    body: TrainingApplicationStatusUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> TrainingApplicationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_training_application_service.update_status(
            client, current_user.id, str(application_id), body.status
        )
    except industry_training_application_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An application at '{exc.current}' can't be moved to '{exc.target}'.",
        ) from exc
    except Exception as exc:
        raise _server_error("update the application") from exc
    if row is None:
        raise _application_not_found()

    notification_producer.emit_training_status_change(
        student_id=row["student_id"],
        training_id=row["training_id"],
        new_status=row["status"],
        training_title=(row.get("training") or {}).get("title"),
    )

    return TrainingApplicationResponse(**row)
