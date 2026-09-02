"""Self-service Faculty API: assessment capabilities (Phase F2) and the
academic profile (Phase F3 subphase 1). Kept as one focused router for
Faculty's own self-scoped resources -- everything here is `require_faculty`
+ the caller's own row, never another Faculty member's data and never an
Admin-management concern (that lives in app.api.admin_faculty)."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_faculty
from app.core.security import build_user_client
from app.schemas.faculty_mentor_permission import MyMentorCapabilityResponse
from app.schemas.faculty_permissions import MyFacultyCapabilitiesResponse
from app.schemas.faculty_profile import (
    FacultyProfileResponse,
    FacultyProfileUpdate,
    compute_completeness,
)
from app.services import (
    faculty_mentor_permission_service,
    faculty_permission_service,
    faculty_profile_service,
)

router = APIRouter(prefix="/faculty", tags=["faculty"])


@router.get("/me/assessment-capabilities", response_model=MyFacultyCapabilitiesResponse)
def get_my_assessment_capabilities(
    current_user: CurrentUser = Depends(require_faculty),
) -> MyFacultyCapabilitiesResponse:
    """Return only the caller's effective assessment capabilities."""
    try:
        client = build_user_client(current_user.access_token)
        capabilities = faculty_permission_service.get_effective_capabilities(client)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load Faculty assessment capabilities.",
        ) from exc
    return MyFacultyCapabilitiesResponse(role="FACULTY", capabilities=sorted(capabilities, key=lambda item: item.value))


@router.get("/me/mentor-capability", response_model=MyMentorCapabilityResponse)
def get_my_mentor_capability(
    current_user: CurrentUser = Depends(require_faculty),
) -> MyMentorCapabilityResponse:
    """Return only whether the caller currently holds faculty_mentor
    (Phase F4.2) -- independent of assessment capabilities."""
    try:
        client = build_user_client(current_user.access_token)
        can_mentor = faculty_mentor_permission_service.get_my_mentor_capability(client)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the Faculty mentor capability.",
        ) from exc
    return MyMentorCapabilityResponse(role="FACULTY", can_mentor=can_mentor)


@router.get("/profile", response_model=FacultyProfileResponse)
def get_faculty_profile(
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyProfileResponse:
    """The caller's own academic profile.

    `faculty_profiles` is a lazy 1:1 row -- a brand-new FACULTY account
    has none yet. That is not a 404: this returns 200 with `id` set and
    every other field null/empty, so the frontend can render a clean
    "complete your profile" state.
    """
    try:
        client = build_user_client(current_user.access_token)
        row = faculty_profile_service.get_profile(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your profile.",
        ) from exc

    if row is None:
        return FacultyProfileResponse(id=current_user.id, completeness=0.0)
    return FacultyProfileResponse(**row, completeness=compute_completeness(row))


@router.put("/profile", response_model=FacultyProfileResponse)
def update_faculty_profile(
    body: FacultyProfileUpdate,
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyProfileResponse:
    """Create (first save) or replace the caller's own academic profile.

    The row id is forced to current_user.id inside the service; nothing
    from `body` can change which row is written. RLS re-checks ownership
    and the FACULTY role on both the INSERT and UPDATE paths.
    """
    try:
        client = build_user_client(current_user.access_token)
        row = faculty_profile_service.upsert_profile(client, current_user.id, body.model_dump())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save your profile.",
        ) from exc

    return FacultyProfileResponse(**row, completeness=compute_completeness(row))
