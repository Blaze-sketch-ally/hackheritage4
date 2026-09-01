"""API routes for Industry interview scheduling -- the concrete
date/time/mode/location/notes layer on top of the recruitment pipeline's
"interview stage" (applications.status = 'INTERVIEW_SCHEDULED', 020).

Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. The owning Industry account is always
current_user.id; industry_id / student_id are never read from the
request (a database trigger derives them from the referenced application).

Lifecycle: SCHEDULED -> COMPLETED / CANCELLED, plus reschedule (an edit of
a still-SCHEDULED interview). There is deliberately NO DELETE endpoint --
an interview is recruitment history; cancellation is a status, matching
applications / collaborations / postings (020 / 026 / 027 / 028).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.interview import (
    InterviewCreate,
    InterviewListResponse,
    InterviewResponse,
    InterviewStatus,
    InterviewUpdate,
)
from app.services import interview_service

router = APIRouter(prefix="/interviews", tags=["interviews"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=InterviewListResponse)
def list_interviews(
    status_filter: InterviewStatus | None = Query(default=None, alias="status"),
    application_id: UUID | None = Query(default=None),
    upcoming: bool | None = Query(default=None),
    current_user: CurrentUser = Depends(require_industry),
) -> InterviewListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = interview_service.list_interviews(
            client,
            current_user.id,
            status=status_filter,
            application_id=str(application_id) if application_id else None,
            upcoming=upcoming,
        )
    except Exception as exc:
        raise _server_error("load interviews") from exc
    return InterviewListResponse(interviews=rows)


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def create_interview(
    body: InterviewCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> InterviewResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json")
    try:
        row = interview_service.create_interview(client, current_user.id, payload)
    except interview_service.IneligibleApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except interview_service.InvalidInterviewTimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except interview_service.SchedulingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("schedule the interview") from exc
    return InterviewResponse(**row)


@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> InterviewResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = interview_service.get_interview(client, current_user.id, str(interview_id))
    except Exception as exc:
        raise _server_error("load the interview") from exc
    if row is None:
        raise _not_found()
    return InterviewResponse(**row)


@router.patch("/{interview_id}", response_model=InterviewResponse)
def reschedule_interview(
    interview_id: UUID,
    body: InterviewUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> InterviewResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json", exclude_unset=True)
    try:
        row = interview_service.reschedule_interview(
            client, current_user.id, str(interview_id), payload
        )
    except interview_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a scheduled interview can be changed.",
        ) from exc
    except interview_service.InvalidInterviewTimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except interview_service.SchedulingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("update the interview") from exc
    if row is None:
        raise _not_found()
    return InterviewResponse(**row)


@router.post("/{interview_id}/complete", response_model=InterviewResponse)
def complete_interview(
    interview_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> InterviewResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = interview_service.complete_interview(client, current_user.id, str(interview_id))
    except interview_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a scheduled interview can be marked completed.",
        ) from exc
    except Exception as exc:
        raise _server_error("complete the interview") from exc
    if row is None:
        raise _not_found()
    return InterviewResponse(**row)


@router.post("/{interview_id}/cancel", response_model=InterviewResponse)
def cancel_interview(
    interview_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> InterviewResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = interview_service.cancel_interview(client, current_user.id, str(interview_id))
    except interview_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This interview can no longer be cancelled.",
        ) from exc
    except Exception as exc:
        raise _server_error("cancel the interview") from exc
    if row is None:
        raise _not_found()
    return InterviewResponse(**row)
