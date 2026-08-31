"""API routes for opportunities (Phase 1M) -- the unified JOB/INTERNSHIP
domain, its skill requirements, and the Phase 1L-alignment-engine-backed
student match endpoint.

RLS (024_opportunities_and_applications.sql) plus the
prevent_invalid_opportunity_transition trigger are the real enforcement
for ownership and lifecycle legality; this router's own checks are
defense in depth, matching every other router in this codebase. Every
route reads/writes through build_user_client(access_token) -- never
get_supabase() -- except the applicant-list route, which additionally
needs the service-role client for the narrow, documented reason explained
in app.services.application_service.list_opportunity_applicants.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError

from app.core.dependencies import CurrentUser, get_current_user, require_industry, require_student
from app.core.security import build_user_client
from app.database.supabase import get_supabase
from app.schemas.application import (
    ApplicantDetailResponse,
    ApplicantListResponse,
    ApplicantResponse,
    ApplicationCreateRequest,
    ApplicationResponse,
)
from app.schemas.opportunity import (
    OpportunityCreateRequest,
    OpportunityListResponse,
    OpportunityMatchResponse,
    OpportunityMatchSkillResponse,
    OpportunityRequirementResponse,
    OpportunityRequirementsReplaceRequest,
    OpportunityRequirementsResponse,
    OpportunityResponse,
    OpportunityUpdateRequest,
)
from app.services import application_service, opportunity_service

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found.")


@router.get("", response_model=OpportunityListResponse)
def list_opportunities(
    opportunity_type: str | None = Query(default=None),
    mine: bool = Query(default=False),
    current_user: CurrentUser = Depends(get_current_user),
) -> OpportunityListResponse:
    """Any authenticated caller sees PUBLISHED opportunities by default.
    `mine=true` additionally requires INDUSTRY and returns the caller's
    own opportunities at any status (RLS's "Industry can view their own
    opportunities" policy is what actually permits this -- a STUDENT
    passing mine=true simply gets an empty list, RLS never returns
    anyone else's DRAFT/CLOSED postings)."""
    if mine and current_user.role != "INDUSTRY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only INDUSTRY accounts can list their own opportunities.",
        )
    client = build_user_client(current_user.access_token)
    try:
        rows = opportunity_service.list_opportunities(client, opportunity_type, mine_only=mine)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load opportunities.",
        ) from exc
    return OpportunityListResponse(opportunities=rows)


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: UUID, current_user: CurrentUser = Depends(get_current_user)
) -> OpportunityResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = opportunity_service.get_opportunity(client, opportunity_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this opportunity.",
        ) from exc
    if row is None:
        raise _not_found()
    return OpportunityResponse(**row)


@router.post("", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreateRequest, current_user: CurrentUser = Depends(require_industry)
) -> OpportunityResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = opportunity_service.create_opportunity(
            client, current_user.id, payload.model_dump(mode="json")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create this opportunity.",
        ) from exc
    return OpportunityResponse(**row)


@router.patch("/{opportunity_id}", response_model=OpportunityResponse)
def update_opportunity(
    opportunity_id: UUID,
    payload: OpportunityUpdateRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> OpportunityResponse:
    client = build_user_client(current_user.access_token)
    update_data = payload.model_dump(mode="json", exclude_unset=True)
    try:
        row = opportunity_service.update_opportunity(client, opportunity_id, update_data)
    except APIError as exc:
        if exc.code == "42501":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This opportunity cannot be edited in its current state.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update this opportunity.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update this opportunity.",
        ) from exc
    if row is None:
        raise _not_found()
    return OpportunityResponse(**row)


@router.post("/{opportunity_id}/publish", response_model=OpportunityResponse)
def publish_opportunity(
    opportunity_id: UUID, current_user: CurrentUser = Depends(require_industry)
) -> OpportunityResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = opportunity_service.publish_opportunity(client, opportunity_id)
    except APIError as exc:
        if exc.code == "42501":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This opportunity cannot be published from its current state.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not publish this opportunity."
        ) from exc
    if row is None:
        raise _not_found()
    return OpportunityResponse(**row)


@router.post("/{opportunity_id}/close", response_model=OpportunityResponse)
def close_opportunity(
    opportunity_id: UUID, current_user: CurrentUser = Depends(require_industry)
) -> OpportunityResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = opportunity_service.close_opportunity(client, opportunity_id)
    except APIError as exc:
        if exc.code == "42501":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This opportunity cannot be closed from its current state.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not close this opportunity."
        ) from exc
    if row is None:
        raise _not_found()
    return OpportunityResponse(**row)


# ------------------------------------------------------------
# opportunity_skill_requirements
# ------------------------------------------------------------


@router.get("/{opportunity_id}/requirements", response_model=OpportunityRequirementsResponse)
def get_requirements(
    opportunity_id: UUID, current_user: CurrentUser = Depends(get_current_user)
) -> OpportunityRequirementsResponse:
    client = build_user_client(current_user.access_token)
    try:
        requirements = opportunity_service.get_requirements(client, opportunity_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load requirements."
        ) from exc
    return OpportunityRequirementsResponse(
        opportunity_id=opportunity_id,
        requirements=[
            OpportunityRequirementResponse(
                skill_id=r.skill_id, skill_name=r.skill_name, required_level=r.required_level, weight=r.weight
            )
            for r in requirements
        ],
    )


@router.put("/{opportunity_id}/requirements", response_model=OpportunityRequirementsResponse)
def replace_requirements(
    opportunity_id: UUID,
    payload: OpportunityRequirementsReplaceRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> OpportunityRequirementsResponse:
    client = build_user_client(current_user.access_token)

    opportunity = opportunity_service.get_opportunity(client, opportunity_id)
    if opportunity is None:
        raise _not_found()
    # Checked explicitly here, not left to RLS alone: an empty
    # `requirements` list against a non-DRAFT opportunity would otherwise
    # silently no-op (the DELETE half of replace_requirements matches
    # zero rows under RLS, no error raised, nothing to catch) and this
    # route would wrongly report success without actually clearing
    # anything. RLS remains the real, structural boundary either way --
    # this is purely about giving a clear, deterministic error instead of
    # relying on that edge case.
    if opportunity["status"] != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requirements can only be edited while the opportunity is a draft.",
        )

    seen_skill_ids = set()
    for req in payload.requirements:
        if req.skill_id in seen_skill_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Duplicate skill in requirements.",
            )
        seen_skill_ids.add(req.skill_id)

    try:
        opportunity_service.replace_requirements(
            client, opportunity_id, [r.model_dump(mode="json") for r in payload.requirements]
        )
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requirements can only be edited while the opportunity is a draft.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not save requirements."
        ) from exc

    requirements = opportunity_service.get_requirements(client, opportunity_id)
    return OpportunityRequirementsResponse(
        opportunity_id=opportunity_id,
        requirements=[
            OpportunityRequirementResponse(
                skill_id=r.skill_id, skill_name=r.skill_name, required_level=r.required_level, weight=r.weight
            )
            for r in requirements
        ],
    )


# ------------------------------------------------------------
# Matching (Phase 1L alignment engine, reused unchanged)
# ------------------------------------------------------------


@router.get("/{opportunity_id}/match", response_model=OpportunityMatchResponse)
def get_match(
    opportunity_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> OpportunityMatchResponse:
    """The authenticated student's own derived match -- identity always
    comes from the token (current_user.id), never a client-supplied
    student_id, matching Phase 1L's GET /career-roles/{id}/skill-gap
    exactly. Computed with app.services.skill_alignment_service.
    compute_alignment() -- the same, unmodified Phase 1L engine, not a
    second implementation."""
    client = build_user_client(current_user.access_token)

    opportunity = opportunity_service.get_opportunity(client, opportunity_id)
    if opportunity is None:
        raise _not_found()

    try:
        overall_score, results = application_service.get_student_match(
            client, current_user.id, opportunity_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not compute your match."
        ) from exc

    return OpportunityMatchResponse(
        opportunity=OpportunityResponse(**opportunity),
        overall_score=overall_score,
        skills=[
            OpportunityMatchSkillResponse(
                skill_id=r.skill_id,
                skill_name=r.skill_name,
                required_level=r.required_level,
                student_score=r.student_score,
                gap=r.gap,
                weight=r.weight,
                status=r.status.value,
            )
            for r in results
        ],
    )


# ------------------------------------------------------------
# Applications (opportunity-scoped sub-routes)
# ------------------------------------------------------------


@router.post(
    "/{opportunity_id}/applications",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_opportunity(
    opportunity_id: UUID,
    payload: ApplicationCreateRequest,
    current_user: CurrentUser = Depends(require_student),
) -> ApplicationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = application_service.create_application(
            client, current_user.id, opportunity_id, payload.cover_note
        )
    except application_service.DuplicateApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You have already applied to this opportunity."
        ) from exc
    except application_service.OpportunityNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This opportunity is not currently accepting applications.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not submit your application."
        ) from exc
    return ApplicationResponse(**row)


@router.get("/{opportunity_id}/applicants", response_model=ApplicantListResponse)
def list_applicants(
    opportunity_id: UUID, current_user: CurrentUser = Depends(require_industry)
) -> ApplicantListResponse:
    """Never exposes answer keys, raw assessment answers, or any other
    opportunity's applicants -- each applicant row carries only a
    freshly-computed match score. See
    app.services.application_service.list_opportunity_applicants for the
    ownership-then-service-role read pattern this depends on."""
    client = build_user_client(current_user.access_token)
    service_client = get_supabase()
    try:
        rows = application_service.list_opportunity_applicants(client, service_client, opportunity_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load applicants."
        ) from exc
    return ApplicantListResponse(
        opportunity_id=opportunity_id,
        applicants=[ApplicantResponse(**row) for row in rows],
    )


@router.get(
    "/{opportunity_id}/applicants/{application_id}", response_model=ApplicantDetailResponse
)
def get_applicant_detail(
    opportunity_id: UUID,
    application_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ApplicantDetailResponse:
    """Phase 1N: the "Applicant" step of Industry -> My Opportunities ->
    Applicants -> Applicant -> Portfolio -- candidate overview plus the
    full skill-alignment breakdown (list_applicants above only returns
    the aggregate score, to stay lean). See
    app.services.application_service.get_applicant_detail for the
    ownership-then-service-role read pattern this depends on; portfolio
    itself is fetched separately by the frontend, via
    GET /applications/{id}/portfolio (app/api/applications.py) -- kept
    out of this response so opportunities.py never needs to import the
    portfolio domain."""
    client = build_user_client(current_user.access_token)
    service_client = get_supabase()
    try:
        detail = application_service.get_applicant_detail(
            client, service_client, opportunity_id, application_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load this applicant."
        ) from exc
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant not found.")
    return ApplicantDetailResponse(
        id=detail["id"],
        student_id=detail["student_id"],
        student_name=detail["student_name"],
        status=detail["status"],
        cover_note=detail["cover_note"],
        overall_match_score=detail["overall_match_score"],
        created_at=detail["created_at"],
        updated_at=detail["updated_at"],
        skills=[
            OpportunityMatchSkillResponse(
                skill_id=r.skill_id,
                skill_name=r.skill_name,
                required_level=r.required_level,
                student_score=r.student_score,
                gap=r.gap,
                weight=r.weight,
                status=r.status.value,
            )
            for r in detail["skills"]
        ],
    )
