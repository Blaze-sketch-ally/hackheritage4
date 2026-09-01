"""API routes for Industry mentorship opportunity management.

Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. The mentorship opportunity owner is always
current_user.id; `industry_id` is never read from the request. Lifecycle
changes go through the dedicated publish/close/archive endpoints, not PUT.

This is the Industry-side mentorship *opportunity* resource only (Model
C, approved product decision): Student-facing mentorship
request/enrollment/pairing is NOT part of this module -- see
database/migrations/025_industry_mentorship.sql.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.industry_mentorship import (
    IndustryMentorship,
    MentorshipCreate,
    MentorshipListResponse,
    MentorshipStatus,
    MentorshipUpdate,
)
from app.services import industry_mentorship_service

router = APIRouter(prefix="/mentorship-opportunities", tags=["industry-mentorship"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Mentorship opportunity not found."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=MentorshipListResponse)
def list_mentorship_opportunities(
    status_filter: MentorshipStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_industry),
) -> MentorshipListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_mentorship_service.list_mentorships(
            client, current_user.id, status=status_filter, search=search
        )
    except Exception as exc:
        raise _server_error("load your mentorship opportunities") from exc
    return MentorshipListResponse(mentorship_opportunities=rows)


@router.post("", response_model=IndustryMentorship, status_code=status.HTTP_201_CREATED)
def create_mentorship_opportunity(
    body: MentorshipCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryMentorship:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json")
    try:
        row = industry_mentorship_service.create_mentorship(client, current_user.id, payload)
    except Exception as exc:
        raise _server_error("create the mentorship opportunity") from exc
    return IndustryMentorship(**row)


@router.get("/{mentorship_id}", response_model=IndustryMentorship)
def get_mentorship_opportunity(
    mentorship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryMentorship:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_mentorship_service.get_mentorship(
            client, current_user.id, str(mentorship_id)
        )
    except Exception as exc:
        raise _server_error("load the mentorship opportunity") from exc
    if row is None:
        raise _not_found()
    return IndustryMentorship(**row)


@router.put("/{mentorship_id}", response_model=IndustryMentorship)
def update_mentorship_opportunity(
    mentorship_id: UUID,
    body: MentorshipUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryMentorship:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json", exclude_unset=True)
    try:
        row = industry_mentorship_service.update_mentorship(
            client, current_user.id, str(mentorship_id), payload
        )
    except Exception as exc:
        raise _server_error("save the mentorship opportunity") from exc
    if row is None:
        raise _not_found()
    return IndustryMentorship(**row)


@router.post("/{mentorship_id}/publish", response_model=IndustryMentorship)
def publish_mentorship_opportunity(
    mentorship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryMentorship:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_mentorship_service.publish_mentorship(
            client, current_user.id, str(mentorship_id)
        )
    except industry_mentorship_service.PublishValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This mentorship opportunity isn't ready to publish. Add: "
            + ", ".join(exc.missing)
            + ".",
        ) from exc
    except industry_mentorship_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft or closed mentorship opportunity can be published.",
        ) from exc
    except Exception as exc:
        raise _server_error("publish the mentorship opportunity") from exc
    if row is None:
        raise _not_found()
    return IndustryMentorship(**row)


@router.post("/{mentorship_id}/close", response_model=IndustryMentorship)
def close_mentorship_opportunity(
    mentorship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryMentorship:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_mentorship_service.close_mentorship(
            client, current_user.id, str(mentorship_id)
        )
    except industry_mentorship_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a published mentorship opportunity can be closed.",
        ) from exc
    except Exception as exc:
        raise _server_error("close the mentorship opportunity") from exc
    if row is None:
        raise _not_found()
    return IndustryMentorship(**row)


@router.post("/{mentorship_id}/archive", response_model=IndustryMentorship)
def archive_mentorship_opportunity(
    mentorship_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryMentorship:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_mentorship_service.archive_mentorship(
            client, current_user.id, str(mentorship_id)
        )
    except industry_mentorship_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mentorship opportunity is already archived.",
        ) from exc
    except Exception as exc:
        raise _server_error("archive the mentorship opportunity") from exc
    if row is None:
        raise _not_found()
    return IndustryMentorship(**row)
