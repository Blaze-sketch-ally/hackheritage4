"""API routes for the INDUSTRY side of Job Training completion
(database/migrations/053_job_training_completion.sql).

PHASE J4: read the completion state of one of the industry's own job
training enrollments, and perform the explicit verification (PASS / FAIL)
that records the completion and -- on PASS -- issues the certificate and
moves the enrollment ACTIVE -> COMPLETED.

Guarded by require_industry(); every read/write goes through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so Supabase RLS (public.industry_owns_job_training_enrollment
+ the job_training_completions / job_training_certificates policies + the
DB derivation/verifier triggers) stays the real access-control boundary.
`industry_id` is always current_user.id, never read from the request. An
enrollment that is not one of the caller's own is a clean 404. Students
can never reach this router (require_industry).

The J2 industry *authoring* API is nested under a job
(/api/v1/jobs/{job_id}/training-program); this completion API is keyed on
the ENROLLMENT, so it lives under its own /industry/job-training prefix.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.job_training_completion import (
    JobTrainingCompletionSummary,
    VerifyJobTrainingCompletionRequest,
)
from app.services import job_training_service, notification_producer

router = APIRouter(prefix="/industry/job-training", tags=["industry-job-training"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Job training enrollment not found."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/{enrollment_id}/completion", response_model=JobTrainingCompletionSummary)
def get_job_training_completion(
    enrollment_id: str,
    current_user: CurrentUser = Depends(require_industry),
) -> JobTrainingCompletionSummary:
    """The completion state for one of the industry's own job training
    enrollments: whether it has been verified, the outcome, and the
    certificate once issued. Read-only."""
    client = build_user_client(current_user.access_token)
    try:
        row = job_training_service.get_industry_completion(
            client, current_user.id, enrollment_id
        )
    except Exception as exc:
        raise _server_error("load the completion status") from exc
    if row is None:
        raise _not_found()
    return JobTrainingCompletionSummary(**row)


@router.post(
    "/{enrollment_id}/completion/verify", response_model=JobTrainingCompletionSummary
)
def verify_job_training_completion(
    enrollment_id: str,
    body: VerifyJobTrainingCompletionRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> JobTrainingCompletionSummary:
    """Explicitly verify the student's job training with a PASS or FAIL
    decision. On PASS: records the completion and issues the certificate
    (one per enrollment / completion, ever, with a server-generated
    AIC-JOB number). On any decided outcome: moves the enrollment
    ACTIVE -> COMPLETED. IDEMPOTENT -- a repeat call returns the SAME
    completion + certificate, never a duplicate and never a flipped
    outcome. Never accepts student_id / industry_id / job_id / program_id
    / certificate_number from the client."""
    client = build_user_client(current_user.access_token)
    try:
        row = job_training_service.verify_completion(
            client, current_user.id, enrollment_id, body.outcome, body.notes
        )
    except job_training_service.EnrollmentNotFoundError as exc:
        raise _not_found() from exc
    except job_training_service.EnrollmentRevokedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job training enrollment was revoked and can't be completed.",
        ) from exc
    except job_training_service.ProgramMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job has no training program, so there's nothing to complete.",
        ) from exc
    except job_training_service.CompletionRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise _server_error("verify this job training") from exc

    # Best-effort, exactly once: notify the student. `_newly_verified` is
    # False on a repeated/idempotent verify, so this never re-notifies.
    if row.get("_newly_verified") and row.get("_student_id"):
        certificate = row.get("certificate") or {}
        notification_producer.emit_job_training_completed(
            student_id=row["_student_id"],
            enrollment_id=enrollment_id,
            job_title=certificate.get("job_title"),
            program_title=certificate.get("program_title"),
            outcome=row.get("_outcome") or row["completion_status"],
            certificate_number=certificate.get("certificate_number"),
        )

    return JobTrainingCompletionSummary(**row)
