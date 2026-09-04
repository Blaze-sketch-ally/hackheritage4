"""Pydantic schemas for the Internship Workspace read / provisioning /
acceptance surface (database/migrations/038_internship_workspace.sql).

Phases 2-3 expose: a workspace summary + list, a detail view with the
PUBLISHED program preview, the provisioning-result body, and the
accept / decline / skill-selection request bodies.

Phase 5 adds the student assignment + submission surface: a list of the
workspace's published assignments with the student's latest attempt, an
assignment detail with full attempt history, and the create-submission
body. A submission is append-only (a resubmission is a new attempt).

Phase 6 adds the student's view of the industry's review of each of their
own attempts: verdict, feedback and score (NO reviewer identity -- the
student never sees who reviewed). Completion / certificate / stipend
schemas stay later phases.

`student_id` / `industry_id` are never accepted in a request -- every
endpoint derives identity from the authenticated token (require_student /
require_industry -> current_user.id) and RLS
(038_internship_workspace.sql) is the real access-control boundary.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

# database/migrations/038_internship_workspace.sql -- CHECK value lists
WorkspaceStatus = Literal[
    "PENDING_ACCEPTANCE",
    "ACCEPTED",
    "IN_PROGRESS",
    "COMPLETED",
    "DECLINED",
    "RESCINDED",
]
WorkMode = Literal["REMOTE", "HYBRID"]
SkillRequirement = Literal["REQUIRED", "OPTIONAL"]
# database/migrations/037_internship_program.sql -- module_items.item_type
ModuleItemType = Literal["VIDEO", "PDF", "LINK", "TEXT"]
AssignmentType = Literal["ASSIGNMENT", "QUIZ", "PROJECT"]
SubmissionKind = Literal["LINK", "REPO", "FILE", "TEXT", "MIXED"]
SubmissionStatus = Literal[
    "SUBMITTED", "UNDER_REVIEW", "REVISION_REQUESTED", "ACCEPTED", "REJECTED"
]

# Mirrors app.services.internship_workspace_service.ProvisionResult.outcome
ProvisionOutcome = Literal[
    "CREATED",
    "ALREADY_EXISTS",
    "SKIPPED_WORK_MODE",
    "SKIPPED_NO_PROGRAM",
    "SKIPPED_NOT_SELECTED",
    "SKIPPED_NOT_INTERNSHIP",
]


class WorkspaceInternshipRef(BaseModel):
    """The internship posting behind a workspace. `status` is the
    posting's own lifecycle (DRAFT / PUBLISHED / CLOSED / ARCHIVED) --
    shown for context only, it is NOT an access gate.

    For the STUDENT endpoints this is resolved server-side (see
    internship_workspace_service) so the title/description stay available
    even after the posting is CLOSED / ARCHIVED, when student RLS on
    `internships` would otherwise hide the row. It exposes ONLY these
    fields -- never industry contact info or other posting columns."""

    id: str
    title: str | None = None
    description: str | None = None
    work_mode: str | None = None
    status: str | None = None


class InternshipWorkspaceSummary(BaseModel):
    id: str
    application_id: str
    internship_id: str
    student_id: str
    industry_id: str
    work_mode: str
    workspace_status: str
    accepted_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    declined_at: str | None = None
    decline_reason: str | None = None
    rescinded_at: str | None = None
    rescind_reason: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    internship: WorkspaceInternshipRef | None = None


class InternshipWorkspaceListResponse(BaseModel):
    workspaces: list[InternshipWorkspaceSummary]


# ---- program preview (read-only; students never author) ----


class WorkspaceProgramModuleItem(BaseModel):
    id: str
    title: str
    item_type: str
    content_url: str | None = None
    content_text: str | None = None
    order_index: int = 0


class WorkspaceProgramModule(BaseModel):
    id: str
    title: str
    description: str | None = None
    order_index: int = 0
    items: list[WorkspaceProgramModuleItem] = []


class WorkspaceProgramSkill(BaseModel):
    skill_id: str
    skill_name: str
    requirement: str  # REQUIRED | OPTIONAL


class WorkspaceProgramPreview(BaseModel):
    """The PUBLISHED internship_program for the workspace's internship,
    with its published modules / items / skills. Null when the industry
    has not published a program yet (the offer can still be accepted)."""

    id: str
    title: str
    summary: str | None = None
    status: str
    modules: list[WorkspaceProgramModule] = []
    skills: list[WorkspaceProgramSkill] = []


class InternshipWorkspaceDetail(InternshipWorkspaceSummary):
    program: WorkspaceProgramPreview | None = None
    # skill_ids the student has currently selected (all OPTIONAL program
    # skills; REQUIRED skills are always in scope and are not stored here).
    selected_skill_ids: list[str] = []


# ---- request bodies ----


class DeclineWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


class SkillSelectionRequest(BaseModel):
    """The full desired set of OPTIONAL program skills (replace-set). An
    empty list clears the student's selections. Duplicates are normalised
    server-side."""

    model_config = ConfigDict(extra="forbid")

    skill_ids: list[str] = []


# ---- Phase 5: assignments + submissions / Phase 6: review outcome ----


class StudentSubmissionReview(BaseModel):
    """The industry's review of ONE of the student's own attempts, as the
    student sees it: the decision, the feedback and the score only. There
    is deliberately NO reviewer_id -- the student never sees who reviewed
    (submission_reviews' reviewer_id stays industry-side)."""

    verdict: str
    feedback: str | None = None
    score: float | None = None
    reviewed_at: str | None = None


class WorkspaceSubmissionResponse(BaseModel):
    """One of the student's OWN submission attempts, plus the industry's
    review of it (append-only history, newest first). The submission's own
    content is immutable once written -- a review never rewrites it."""

    id: str
    workspace_id: str
    assignment_id: str
    attempt_number: int
    submission_status: str
    repo_url: str | None = None
    live_url: str | None = None
    attachment_url: str | None = None
    notes: str | None = None
    submitted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    reviews: list[StudentSubmissionReview] = []
    latest_review: StudentSubmissionReview | None = None


class WorkspaceAssignmentBase(BaseModel):
    id: str
    module_id: str
    program_id: str
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


class WorkspaceAssignmentSummary(WorkspaceAssignmentBase):
    module_title: str | None = None
    module_order_index: int = 0
    attempt_count: int = 0
    latest_submission: WorkspaceSubmissionResponse | None = None
    can_submit: bool = False
    submit_blocked_reason: str | None = None


class WorkspaceAssignmentListResponse(BaseModel):
    assignments: list[WorkspaceAssignmentSummary]


class WorkspaceAssignmentModuleRef(BaseModel):
    id: str
    title: str | None = None


class WorkspaceAssignmentDetail(BaseModel):
    assignment: WorkspaceAssignmentBase
    module: WorkspaceAssignmentModuleRef
    submissions: list[WorkspaceSubmissionResponse] = []
    attempt_count: int = 0
    can_submit: bool = False
    submit_blocked_reason: str | None = None


class CreateSubmissionRequest(BaseModel):
    """The student's work for one assignment. Only the fields
    workspace_submissions supports (migration 039); which are required
    depends on the assignment's submission_kind / repo_required /
    live_url_expected. `attempt_number` / `submission_status` are always
    server-set."""

    model_config = ConfigDict(extra="forbid")

    repo_url: str | None = None
    live_url: str | None = None
    attachment_url: str | None = None
    notes: str | None = None


# ---- provisioning ----


class ProvisionWorkspaceResponse(BaseModel):
    """Result of POST /api/v1/applications/{id}/provision-workspace.
    `workspace` is populated for CREATED / ALREADY_EXISTS, null for every
    no-op outcome."""

    outcome: ProvisionOutcome
    detail: str
    work_mode: str | None = None
    workspace: InternshipWorkspaceSummary | None = None
