"""ADMIN-only read-only oversight of Faculty <-> Student mentorships
(Phase F4.2, admin_list_faculty_student_mentorships() RPC in
040_faculty_student_mentorships.sql).

Kept as its own small router, separate from admin_faculty.py -- mentor
CAPABILITY management (who may participate) and mentorship RELATIONSHIP
oversight (who is currently mentoring whom) are different admin concerns,
mirroring how faculty_engagements.py is kept separate from
faculty_opportunities.py.

This is READ-ONLY and deliberately narrow: it returns exactly the fields
the approved scope named (id, faculty_id, student_id, status,
requested_by, dates, timestamps) and NEVER focus_area or
faculty_mentorship_notes. Admin gains oversight of the relationship, not
the mentor-only student-data visibility that relationship would
otherwise grant to Faculty -- there is no Admin policy anywhere in this
project on student_profiles/student_skills/portfolio_projects/
portfolio_certifications/assessment_attempts, and this router never
reads any of them.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_admin
from app.core.security import build_user_client
from app.schemas.faculty_student_mentorship import (
    AdminMentorshipListResponse,
    AdminMentorshipResponse,
)
from app.services import faculty_student_mentorship_service as service

router = APIRouter(prefix="/admin/mentorships", tags=["admin-mentorships"])


@router.get("", response_model=AdminMentorshipListResponse)
def list_all_mentorships(
    current_user: CurrentUser = Depends(require_admin),
) -> AdminMentorshipListResponse:
    try:
        client = build_user_client(current_user.access_token)
        rows = service.admin_list_mentorships(client)
    except service.AdminAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load mentorships. Please try again.",
        ) from exc
    return AdminMentorshipListResponse(mentorships=[AdminMentorshipResponse(**r) for r in rows])
