"""API routes for assessments."""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_student_id
from app.database.supabase import get_supabase
from app.schemas.assessment import SubmitAssessmentResult
from app.services.assessment_service import submit_and_score_attempt

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("/{attempt_id}/submit", response_model=SubmitAssessmentResult)
def submit_assessment(
    attempt_id: str,
    student_id: str = Depends(get_current_student_id),
) -> SubmitAssessmentResult:
    """Authoritatively scores and completes the caller's own attempt.

    attempt_id comes from the URL path only to identify *which* attempt;
    ownership is verified against the authenticated student_id (resolved
    from the bearer token, never trusted from the request) inside
    submit_and_score_attempt.

    get_supabase() is called directly here (not as a second, sibling
    Depends()) rather than in the function signature: by the time this
    body runs, get_current_student_id has already proven a working
    Supabase client is reachable, and get_supabase() is @lru_cache'd, so
    this is a free cache hit, not a new construction attempt. Declaring
    it as a sibling Depends() previously masked the auth check entirely
    when Supabase was unconfigured — see the comment on
    app.core.dependencies._resolve_supabase for the full explanation.
    """
    supabase = get_supabase()
    return submit_and_score_attempt(supabase, attempt_id, student_id)
