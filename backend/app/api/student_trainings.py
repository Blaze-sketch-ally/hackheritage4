"""API routes for the STUDENT side of Training discovery and applying.

Exact mirror of app.api.student_workshops, over the standalone
`industry_training` / `industry_training_applications` tables
(023_industry_training.sql / 059_training_applications.sql).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_training import StudentTraining, StudentTrainingListResponse
from app.schemas.training_application import (
    TrainingApplicationListResponse,
    TrainingApplicationResponse,
    TrainingApplyRequest,
)
from app.services import notification_producer, student_training_service

router = APIRouter(prefix="/student", tags=["student-training"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="This training is not available."
    )


def _application_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="We couldn't find that application."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


def _own_name(client: Client, student_id: str) -> str | None:
    try:
        response = (
            client.table("profiles")
            .select("full_name")
            .eq("id", student_id)
            .maybe_single()
            .execute()
        )
        row = response.data if response is not None else None
        return row.get("full_name") if row else None
    except Exception:  # noqa: BLE001 -- notification enrichment only
        return None


@router.get("/trainings", response_model=StudentTrainingListResponse)
def list_trainings(
    search: str | None = Query(default=None, max_length=200),
    current_user: CurrentUser = Depends(require_student),
) -> StudentTrainingListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_training_service.list_trainings(client, current_user.id, search=search)
    except Exception as exc:
        raise _server_error("load training programs") from exc
    return StudentTrainingListResponse(trainings=[StudentTraining(**row) for row in rows])


@router.get("/trainings/{training_id}", response_model=StudentTraining)
def get_training(
    training_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> StudentTraining:
    client = build_user_client(current_user.access_token)
    try:
        row = student_training_service.get_training(client, current_user.id, str(training_id))
    except Exception as exc:
        raise _server_error("load this training program") from exc
    if row is None:
        raise _not_found()
    return StudentTraining(**row)


@router.post(
    "/trainings/{training_id}/applications",
    response_model=TrainingApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_training(
    training_id: UUID,
    _body: TrainingApplyRequest,
    current_user: CurrentUser = Depends(require_student),
) -> TrainingApplicationResponse:
    client = build_user_client(current_user.access_token)

    try:
        training = student_training_service.get_training(
            client, current_user.id, str(training_id)
        )
    except Exception as exc:
        raise _server_error("load this training program") from exc
    if training is None:
        raise _not_found()

    try:
        row = student_training_service.apply_to_training(
            client, current_user.id, str(training_id)
        )
    except student_training_service.DuplicateApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this training program.",
        ) from exc
    except student_training_service.TrainingNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This training program is no longer accepting applications.",
        ) from exc
    except Exception as exc:
        raise _server_error("submit your application") from exc

    notification_producer.emit_new_application(
        industry_id=row["industry_id"],
        kind="TRAINING",
        related_entity_id=row["training_id"],
        opportunity_title=training.get("title"),
        student_name=_own_name(client, current_user.id),
    )

    return TrainingApplicationResponse(**row)


@router.get("/training-applications", response_model=TrainingApplicationListResponse)
def list_my_applications(
    current_user: CurrentUser = Depends(require_student),
) -> TrainingApplicationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_training_service.list_my_applications(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your applications") from exc
    return TrainingApplicationListResponse(
        applications=[TrainingApplicationResponse(**row) for row in rows]
    )


@router.post(
    "/training-applications/{application_id}/withdraw",
    response_model=TrainingApplicationResponse,
)
def withdraw_application(
    application_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> TrainingApplicationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_training_service.withdraw_application(
            client, current_user.id, str(application_id)
        )
    except student_training_service.ApplicationNotWithdrawableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("withdraw this application") from exc
    if row is None:
        raise _application_not_found()

    notification_producer.emit_application_withdrawn(
        industry_id=row["industry_id"],
        kind="TRAINING",
        related_entity_id=row["training_id"],
        opportunity_title=(row.get("training") or {}).get("title"),
        student_name=_own_name(client, current_user.id),
    )

    return TrainingApplicationResponse(**row)
