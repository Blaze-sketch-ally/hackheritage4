"""Pydantic schemas for the STUDENT side of Job Training
(database/migrations/052_job_training.sql).

PHASE J3 scope: a SELECTED job candidate whose industry has authored a
job training program can list their enrollment(s) and read the PUBLISHED
program (job info + program metadata + published modules / items /
assignments + skills). No completion, certificate, progress, submission,
or notification surface -- those are later phases.

There are NO request bodies here: both student endpoints are GETs whose
identity comes entirely from the token. The one non-GET surface (the
industry self-heal endpoint) carries no body either. `ProvisionJobTrainingResponse`
is the shape returned by that industry-side heal endpoint.
"""

from pydantic import BaseModel


class JobTrainingEnrollmentSummary(BaseModel):
    """One row of the student's job training list. `program_*` are null
    while the program is still DRAFT (the student cannot read an
    unpublished program); `job_title` is best-effort (a CLOSED / ARCHIVED
    job is not student-readable, which never affects access)."""

    enrollment_id: str
    application_id: str
    job_id: str
    job_title: str | None = None
    program_id: str | None = None
    program_title: str | None = None
    program_status: str | None = None
    enrollment_status: str  # ACTIVE | COMPLETED  (REVOKED is never listed)
    created_at: str | None = None
    completed_at: str | None = None


class JobTrainingListResponse(BaseModel):
    enrollments: list[JobTrainingEnrollmentSummary]


class StudentJobProgramItem(BaseModel):
    id: str
    title: str
    item_type: str
    content_url: str | None = None
    content_text: str | None = None
    order_index: int


class StudentJobProgramAssignment(BaseModel):
    id: str
    title: str
    description: str | None = None
    instructions: str | None = None
    assignment_type: str
    is_required: bool
    order_index: int
    due_offset_days: int | None = None
    submission_kind: str
    repo_required: bool
    live_url_expected: bool
    max_score: float | None = None
    linked_skill_id: str | None = None


class StudentJobProgramModule(BaseModel):
    id: str
    title: str
    description: str | None = None
    order_index: int
    items: list[StudentJobProgramItem] = []
    assignments: list[StudentJobProgramAssignment] = []


class StudentJobProgramSkill(BaseModel):
    skill_id: str
    skill_name: str
    requirement: str  # REQUIRED | OPTIONAL


class StudentJobProgramMeta(BaseModel):
    id: str
    job_id: str
    title: str
    summary: str | None = None
    estimated_weeks: int | None = None
    status: str  # always PUBLISHED in a successful detail response
    published_at: str | None = None


class StudentJobTrainingDetail(BaseModel):
    enrollment: JobTrainingEnrollmentSummary
    program: StudentJobProgramMeta
    modules: list[StudentJobProgramModule] = []
    skills: list[StudentJobProgramSkill] = []


# ============================================================
# industry self-heal endpoint response
# ============================================================


class JobTrainingEnrollmentRef(BaseModel):
    """The raw enrollment row, as returned to the OWNING INDUSTRY from the
    self-heal endpoint (they own the posting and legitimately see the
    applicant). Never returned to a student."""

    id: str
    application_id: str
    job_id: str
    student_id: str
    industry_id: str
    enrollment_status: str
    created_at: str | None = None
    completed_at: str | None = None
    revoked_at: str | None = None


class ProvisionJobTrainingResponse(BaseModel):
    outcome: str  # CREATED | ALREADY_EXISTS | SKIPPED_NO_PROGRAM |
    #               SKIPPED_NOT_SELECTED | SKIPPED_NOT_JOB | REVOKED_BLOCKED
    detail: str
    enrollment: JobTrainingEnrollmentRef | None = None
