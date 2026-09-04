"""Pydantic schemas for INDUSTRY internship-program authoring
(database/migrations/037_internship_program.sql).

Phase 4 scope: an industry account authors exactly one internship_program
per internship posting -- program metadata, ordered modules, module
items, and required/optional program skills -- and publishes it. The
student-facing preview (Phase 3) consumes the PUBLISHED result unchanged.

Phase 5 adds authoring for program_assignments (one normalized table for
ASSIGNMENT / QUIZ / PROJECT -- migration 037) and a READ-ONLY industry
view of workspace_submissions (migration 039).

Phase 6 adds industry review of those submissions: the industry can move
an attempt SUBMITTED -> UNDER_REVIEW and record a terminal verdict
(ACCEPTED / REVISION_REQUESTED / REJECTED) with optional feedback + score.
The decision is stored in submission_reviews (the source of truth);
workspace_submissions.submission_status is only its denormalized cache.
internship_completions, internship_certificates and stipend_disbursements
still have no schema here and are never written.

Ownership is never accepted in a request: every endpoint derives the
industry from the token (require_industry -> current_user.id) and RLS
(037_internship_program.sql, via public.owns_internship_program) is the
real access-control boundary.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# database/migrations/037_internship_program.sql -- CHECK value lists
ProgramStatus = Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
SkillRequirement = Literal["REQUIRED", "OPTIONAL"]
ModuleItemType = Literal["VIDEO", "PDF", "LINK", "TEXT"]
AssignmentType = Literal["ASSIGNMENT", "QUIZ", "PROJECT"]
SubmissionKind = Literal["LINK", "REPO", "FILE", "TEXT", "MIXED"]
# database/migrations/039_workspace_submissions_completion.sql
SubmissionStatus = Literal[
    "SUBMITTED", "UNDER_REVIEW", "REVISION_REQUESTED", "ACCEPTED", "REJECTED"
]
# submission_reviews.verdict CHECK -- a review is a terminal decision;
# UNDER_REVIEW is a submission_status only, never a verdict.
ReviewVerdict = Literal["ACCEPTED", "REVISION_REQUESTED", "REJECTED"]


# ============================================================
# responses
# ============================================================


class ProgramInternshipRef(BaseModel):
    id: str
    title: str
    status: str


class ProgramMeta(BaseModel):
    id: str
    internship_id: str
    title: str
    summary: str | None = None
    estimated_weeks: int | None = None
    status: str
    published_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ProgramModuleItemResponse(BaseModel):
    id: str
    module_id: str
    title: str
    item_type: str
    content_url: str | None = None
    content_text: str | None = None
    order_index: int
    is_published: bool


class ProgramAssignmentResponse(BaseModel):
    id: str
    module_id: str
    program_id: str
    title: str
    description: str | None = None
    instructions: str | None = None
    assignment_type: str
    is_required: bool
    is_published: bool
    order_index: int
    due_offset_days: int | None = None
    submission_kind: str
    repo_required: bool
    live_url_expected: bool
    max_score: float | None = None
    linked_skill_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ProgramModuleResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    order_index: int
    is_published: bool
    items: list[ProgramModuleItemResponse] = []
    assignments: list[ProgramAssignmentResponse] = []


class ProgramSkillResponse(BaseModel):
    skill_id: str
    skill_name: str
    requirement: str  # REQUIRED | OPTIONAL


class AvailableSkill(BaseModel):
    """One of the internship's recruitment skills (internship_skills,
    018) -- the only skills a program is allowed to train."""

    skill_id: str
    skill_name: str
    required_level: str | None = None
    importance: str | None = None


class InternshipProgramBundle(BaseModel):
    """Everything the authoring UI needs in one payload. `program` is null
    when the industry hasn't created one yet (the internship is still
    resolvable and `available_skills` is still populated)."""

    internship: ProgramInternshipRef
    program: ProgramMeta | None = None
    modules: list[ProgramModuleResponse] = []
    skills: list[ProgramSkillResponse] = []
    available_skills: list[AvailableSkill] = []


# ============================================================
# request bodies (all extra="forbid")
# ============================================================


class ProgramCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    estimated_weeks: int | None = Field(default=None, ge=1, le=52)


class ProgramUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    estimated_weeks: int | None = Field(default=None, ge=1, le=52)


class ProgramModuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    is_published: bool = True


class ProgramModuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    is_published: bool | None = None


class ModuleItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    item_type: ModuleItemType
    content_url: str | None = Field(default=None, max_length=2000)
    content_text: str | None = Field(default=None, max_length=20000)
    is_published: bool = True


class ModuleItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    item_type: ModuleItemType | None = None
    content_url: str | None = Field(default=None, max_length=2000)
    content_text: str | None = Field(default=None, max_length=20000)
    is_published: bool | None = None


class ReorderRequest(BaseModel):
    """The full set of child ids in the desired order. Must contain
    exactly the current children -- no additions or omissions."""

    model_config = ConfigDict(extra="forbid")

    ordered_ids: list[UUID] = Field(min_length=1, max_length=200)


class ProgramSkillInput(BaseModel):
    skill_id: UUID
    requirement: SkillRequirement = "REQUIRED"


class ProgramSkillsUpdate(BaseModel):
    """Replace-set the program's skills. Every skill_id must be one of the
    internship's own recruitment skills (internship_skills)."""

    model_config = ConfigDict(extra="forbid")

    skills: list[ProgramSkillInput] = Field(default_factory=list, max_length=50)


# ============================================================
# Phase 5 -- assignments (industry authoring)
# ============================================================


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    instructions: str | None = Field(default=None, max_length=20000)
    assignment_type: AssignmentType = "ASSIGNMENT"
    is_required: bool = True
    is_published: bool = True
    due_offset_days: int | None = Field(default=None, ge=0, le=3650)
    submission_kind: SubmissionKind = "LINK"
    repo_required: bool = False
    live_url_expected: bool = False
    max_score: float | None = Field(default=None, gt=0, le=10000)
    linked_skill_id: UUID | None = None


class AssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    instructions: str | None = Field(default=None, max_length=20000)
    assignment_type: AssignmentType | None = None
    is_required: bool | None = None
    is_published: bool | None = None
    due_offset_days: int | None = Field(default=None, ge=0, le=3650)
    submission_kind: SubmissionKind | None = None
    repo_required: bool | None = None
    live_url_expected: bool | None = None
    max_score: float | None = Field(default=None, gt=0, le=10000)
    linked_skill_id: UUID | None = None


# ============================================================
# Phase 5 / 6 -- submission viewing + review (industry)
# ============================================================
# Phase 5 gave the industry a read-only view of workspace_submissions.
# Phase 6 adds the review: submission_reviews rows are the source of truth;
# every response carries the review history for the attempt it describes.


class SubmissionReviewResponse(BaseModel):
    """One submission_reviews row (migration 039). Append-only -- a
    correction is a new row, so responses carry the whole list newest
    first. `reviewer_id` is exposed only on the INDUSTRY side (the
    reviewer's own account); the student never sees it."""

    id: str
    verdict: str
    feedback: str | None = None
    score: float | None = None
    reviewer_id: str | None = None
    created_at: str | None = None


class IndustrySubmissionResponse(BaseModel):
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
    # Phase 6: the industry's review of THIS attempt (append-only history).
    reviews: list[SubmissionReviewResponse] = []
    latest_review: SubmissionReviewResponse | None = None


class IndustrySubmissionListItem(IndustrySubmissionResponse):
    """A submission row plus the light context the list view needs."""

    student_name: str | None = None
    assignment_title: str | None = None
    module_title: str | None = None
    attempt_count: int = 1


class IndustrySubmissionListResponse(BaseModel):
    submissions: list[IndustrySubmissionListItem]


class IndustrySubmissionDetailResponse(BaseModel):
    submission: IndustrySubmissionResponse
    student_name: str | None = None
    assignment_title: str | None = None
    module_title: str | None = None
    assignment_max_score: float | None = None
    # every attempt for the same (workspace, assignment), newest first
    attempts: list[IndustrySubmissionResponse] = []


class StartReviewRequest(BaseModel):
    """POST .../review/start carries no body -- the path + token identify
    everything. Present only so the route can `extra="forbid"` a stray
    payload."""

    model_config = ConfigDict(extra="forbid")


class ReviewSubmissionRequest(BaseModel):
    """Record a terminal review decision. `reviewer_id` is ALWAYS the
    authenticated industry account (the DB trigger
    set_submission_review_reviewer forces it) -- never accepted here."""

    model_config = ConfigDict(extra="forbid")

    verdict: ReviewVerdict
    feedback: str | None = Field(default=None, max_length=8000)
    score: float | None = Field(default=None, ge=0, le=100000)
