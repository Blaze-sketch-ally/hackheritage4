"""API routes for the STUDENT view of their own Job Training
(database/migrations/052_job_training.sql).

PHASE J3: list the student's job training enrollments, and read the
PUBLISHED program behind one enrollment (job info + program metadata +
published modules / items / assignments + skills). No acceptance step
(J1 has no student opt-in).

PHASE J4 adds two READ-ONLY endpoints: the completion summary and the
certificate for one of the student's own enrollments. Students NEVER
verify a completion or issue a certificate -- that is industry-only
(app.api.industry_job_training). No submission / progress surface.

Guarded by require_student(); every read goes through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so Supabase RLS
("Students can view their own job training enrollment",
 "Students can view published job programs for their enrollment" via
 public.student_can_access_job_program) stays the real access-control
boundary. `student_id` is always current_user.id, never read from the
request. An enrollment the student does not own, a REVOKED enrollment,
and a program that is not PUBLISHED are all a clean, indistinguishable
404.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.job_training import (
    JobTrainingEnrollmentSummary,
    JobTrainingListResponse,
    StudentJobTrainingDetail,
)
from app.schemas.job_training_completion import (
    JobTrainingCertificateInfo,
    JobTrainingCompletionSummary,
)
from app.services import job_training_service

router = APIRouter(prefix="/student/job-training", tags=["student-job-training"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Job training program not found."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=JobTrainingListResponse)
def list_my_job_training(
    current_user: CurrentUser = Depends(require_student),
) -> JobTrainingListResponse:
    """Every non-REVOKED job training enrollment belonging to the
    authenticated student, newest first. A SELECTED job with no program
    yet has no enrollment and therefore never appears here."""
    client = build_user_client(current_user.access_token)
    try:
        rows = job_training_service.list_student_enrollments(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your job training") from exc
    return JobTrainingListResponse(
        enrollments=[JobTrainingEnrollmentSummary(**row) for row in rows]
    )


@router.get("/{enrollment_id}", response_model=StudentJobTrainingDetail)
def get_my_job_training(
    enrollment_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> StudentJobTrainingDetail:
    """The PUBLISHED job training program behind one of the student's own
    enrollments. Readable regardless of the job posting's status (a CLOSED
    / ARCHIVED job does not revoke a selected candidate's training)."""
    client = build_user_client(current_user.access_token)
    try:
        row = job_training_service.get_student_program(
            client, current_user.id, enrollment_id
        )
    except Exception as exc:
        raise _server_error("load this job training program") from exc
    if row is None:
        raise _not_found()
    return StudentJobTrainingDetail(**row)


# ============================================================
# Phase J4 -- completion + certificate (READ-ONLY for the student)
# ============================================================


@router.get("/{enrollment_id}/completion", response_model=JobTrainingCompletionSummary)
def get_my_job_training_completion(
    enrollment_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> JobTrainingCompletionSummary:
    """Whether the company has verified this training and its outcome.
    Read-only -- students never verify their own completion. 404 for an
    enrollment that is not the student's or is REVOKED."""
    client = build_user_client(current_user.access_token)
    try:
        row = job_training_service.get_student_completion(
            client, current_user.id, enrollment_id
        )
    except Exception as exc:
        raise _server_error("load your completion status") from exc
    if row is None:
        raise _not_found()
    return JobTrainingCompletionSummary(**row)


@router.get("/{enrollment_id}/certificate", response_model=JobTrainingCertificateInfo)
def get_my_job_training_certificate(
    enrollment_id: str,
    current_user: CurrentUser = Depends(require_student),
) -> JobTrainingCertificateInfo:
    """The student's own job training certificate for one enrollment.
    404 until the company has verified the training as PASSED and the
    certificate has been issued."""
    client = build_user_client(current_user.access_token)
    try:
        row = job_training_service.get_student_certificate(
            client, current_user.id, enrollment_id
        )
    except Exception as exc:
        raise _server_error("load your certificate") from exc
    if row is None:
        raise _not_found()
    return JobTrainingCertificateInfo(**row)
