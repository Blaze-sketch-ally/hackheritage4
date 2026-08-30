"""API routes for assessments. Endpoints implemented feature-by-feature.

Phase 1D: read-only endpoints. Phase 1E: attempt creation. Phase 1K:
assessment blueprints (how questions get selected). Every route requires
require_student() or require_faculty() (each of which itself requires
get_current_user()) and reads/writes through build_user_client
(access_token) for everything except create_attempt, which switched in
Phase 1K to the service-role client -- see that route's own docstring and
app.services.assessment_service.create_attempt for why. See
app.services.assessment_service / app.services.question_bank_service for
the actual queries.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, get_current_user, require_faculty, require_student
from app.core.security import build_user_client
from app.database.supabase import get_supabase
from app.schemas.assessment import (
    AssessmentAttemptResponse,
    AssessmentListResponse,
    AssessmentQuestionResponse,
    AssessmentResponse,
)
from app.schemas.question_bank import (
    BlueprintResponse,
    BlueprintRuleResponse,
    BlueprintUpsertRequest,
)
from app.services import assessment_service, question_bank_service

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.get("", response_model=AssessmentListResponse)
def list_assessments(
    current_user: CurrentUser = Depends(get_current_user),
) -> AssessmentListResponse:
    """Phase 1K: widened from require_student to get_current_user() --
    RLS ("Authenticated users can view active assessments") was never
    role-restricted in the first place, and FACULTY now legitimately needs
    this to pick an assessment for question authoring / blueprint
    configuration. No new data becomes reachable that RLS didn't already
    permit; this only removes an app-layer restriction that had no
    matching RLS reason to exist."""
    client = build_user_client(current_user.access_token)
    try:
        rows = assessment_service.list_active_assessments(client)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load assessments.",
        ) from exc
    return AssessmentListResponse(assessments=rows)


@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> AssessmentResponse:
    """Phase 1K: widened from require_student to get_current_user() -- see
    list_assessments above for why."""
    client = build_user_client(current_user.access_token)
    try:
        row = assessment_service.get_active_assessment(client, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the assessment.",
        ) from exc

    if row is None:
        # Same response whether the assessment never existed or exists but
        # is inactive -- never reveal which.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")

    return AssessmentResponse(**row)


@router.get("/{assessment_id}/questions", response_model=list[AssessmentQuestionResponse])
def get_assessment_questions(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> list[AssessmentQuestionResponse]:
    client = build_user_client(current_user.access_token)

    try:
        assessment = assessment_service.get_active_assessment(client, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the assessment.",
        ) from exc

    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")

    try:
        questions = assessment_service.list_visible_questions(client, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the assessment's questions.",
        ) from exc

    return [AssessmentQuestionResponse(**question) for question in questions]


@router.post(
    "/{assessment_id}/attempts",
    response_model=AssessmentAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attempt(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> AssessmentAttemptResponse:
    """Start a new attempt for the calling student, with a randomized
    question set (Phase 1K) selected and persisted for it atomically.

    No request body is accepted at all -- assessment_id comes from the
    URL, student_id from current_user.id, and every other column
    (status/score/total_marks/percentage/submitted_at) is either a fixed
    server-controlled value or left for the DB's own defaults. There is no
    field a client could inject here even by mistake.

    Ownership/existence is still verified first via the user-scoped
    client, exactly as before Phase 1K -- only once that passes does this
    route reach for get_supabase(), for the one operation
    (create_assessment_attempt) that needs a single atomic transaction
    RLS cannot give an ordinary REST call. Same two-step pattern
    score_attempt already uses.
    """
    client = build_user_client(current_user.access_token)

    try:
        assessment = assessment_service.get_active_assessment(client, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the assessment.",
        ) from exc

    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")

    service_client = get_supabase()
    try:
        row = assessment_service.create_attempt(service_client, current_user.id, assessment_id)
    except assessment_service.DuplicateInProgressAttemptError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an in-progress attempt for this assessment.",
        ) from exc
    except assessment_service.InsufficientQuestionPoolError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This assessment does not currently have enough approved questions to start.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start the attempt.",
        ) from exc

    return AssessmentAttemptResponse(**row)


@router.get("/{assessment_id}/blueprint", response_model=BlueprintResponse)
def get_blueprint(
    assessment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> BlueprintResponse:
    """The assessment's current blueprint (Phase 1K) -- readable by any
    authenticated user, matching 015's own SELECT policy ("Authenticated
    users can view blueprint rules for active assessments"); a difficulty/
    count breakdown carries no sensitive information. Uses
    get_current_user() rather than require_student/require_faculty since
    both roles legitimately read this -- students to see what an
    assessment will look like, faculty to see the current configuration
    before editing it via PUT below."""
    client = build_user_client(current_user.access_token)
    try:
        rows = question_bank_service.get_blueprint(client, assessment_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the blueprint.",
        ) from exc
    return BlueprintResponse(
        assessment_id=assessment_id,
        rules=[BlueprintRuleResponse(**row) for row in rows],
    )


@router.put("/{assessment_id}/blueprint", response_model=BlueprintResponse)
def replace_blueprint(
    assessment_id: UUID,
    body: BlueprintUpsertRequest,
    current_user: CurrentUser = Depends(require_faculty),
) -> BlueprintResponse:
    """Replace an assessment's entire blueprint. RLS ("Faculty can
    create/update/delete blueprint rules") is the real enforcement that
    only FACULTY may write here -- assessments have no owner/creator
    column in this schema, so blueprint configuration is a shared FACULTY
    capability, not scoped to an individual setter, matching how
    assessments themselves have always been managed."""
    client = build_user_client(current_user.access_token)
    try:
        rows = question_bank_service.replace_blueprint(
            client,
            assessment_id,
            [rule.model_dump(mode="json") for rule in body.rules],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save the blueprint.",
        ) from exc
    return BlueprintResponse(
        assessment_id=assessment_id,
        rules=[BlueprintRuleResponse(**row) for row in rows],
    )
