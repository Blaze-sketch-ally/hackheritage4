"""Pydantic schemas for the shared Participation Workspace domain (Project /
Training / Workshop), database/migrations/062-065_participation_*.sql.

ONE reusable domain, not three duplicated ones -- every model here is
discriminated by `kind` ('PROJECT' | 'TRAINING' | 'WORKSHOP') rather than
having a separate schema module per opportunity type, mirroring how
`applications.opportunity_type` already discriminates INTERNSHIP/JOB rows
in one table (app.schemas.application).

Field names mirror the migrations exactly. `industry_id` is never accepted
from a client anywhere in this module -- ownership is always derived
server-side (from the opportunity for programs, from the application for
workspaces), matching every other opportunity-owned table in this schema.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ParticipationKind = Literal["PROJECT", "TRAINING", "WORKSHOP"]
ProgramStatus = Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
ResourceType = Literal["VIDEO", "DOCUMENT", "LINK", "REFERENCE", "OTHER"]
WorkspaceStatus = Literal["ACTIVE", "COMPLETED"]
SubmissionStatus = Literal["SUBMITTED", "UNDER_REVIEW", "REVIEWED"]
ReviewStatus = Literal["REVIEWED", "NEEDS_REVISION", "ACCEPTED"]
FeedbackType = Literal["GENERAL", "PROGRESS", "STRENGTH", "IMPROVEMENT", "FINAL_NOTE"]
RecommendedLevel = Literal["Beginner", "Intermediate", "Advanced", "Expert"]
RecommendationPriority = Literal["LOW", "MEDIUM", "HIGH"]
EvaluationStatus = Literal["DRAFT", "FINALIZED"]
CompletionStatus = Literal["COMPLETED"]


def _blank_to_none(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    return cleaned


# ---- programs ----


class ProgramCreate(BaseModel):
    """POST body. Exactly one of project_id/training_id/workshop_id must be
    supplied, matching `kind` -- the route re-validates ownership of that
    opportunity before the insert; `industry_id` is never part of this
    model."""

    model_config = ConfigDict(extra="forbid")

    kind: ParticipationKind
    project_id: str | None = None
    training_id: str | None = None
    workshop_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)

    @model_validator(mode="after")
    def _one_opportunity(self) -> "ProgramCreate":
        picked = {"PROJECT": self.project_id, "TRAINING": self.training_id, "WORKSHOP": self.workshop_id}
        if not picked[self.kind]:
            raise ValueError(f"{self.kind.lower()}_id is required for kind={self.kind}.")
        others = [v for k, v in picked.items() if k != self.kind]
        if any(others):
            raise ValueError("Only the opportunity id matching `kind` may be set.")
        return self


class ProgramUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class ProgramOpportunityRef(BaseModel):
    id: str
    title: str
    status: str


class ProgramResponse(BaseModel):
    id: str
    kind: ParticipationKind
    project_id: str | None = None
    training_id: str | None = None
    workshop_id: str | None = None
    title: str
    description: str | None = None
    status: ProgramStatus
    published_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    opportunity: ProgramOpportunityRef | None = None


class ProgramListResponse(BaseModel):
    programs: list[ProgramResponse]


# ---- modules ----


class ModuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    sequence_order: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class ModuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    sequence_order: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class ModuleResponse(BaseModel):
    id: str
    program_id: str
    title: str
    description: str | None = None
    sequence_order: int
    is_published: bool
    created_at: str | None = None
    updated_at: str | None = None


class ModuleListResponse(BaseModel):
    modules: list[ModuleResponse]


# ---- resources ----


class ResourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    resource_type: ResourceType
    resource_url: str | None = Field(default=None, max_length=2_000)
    sequence_order: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class ResourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    resource_url: str | None = Field(default=None, max_length=2_000)
    sequence_order: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class ResourceResponse(BaseModel):
    id: str
    program_id: str
    module_id: str | None = None
    title: str
    description: str | None = None
    resource_type: ResourceType
    resource_url: str | None = None
    sequence_order: int
    is_published: bool
    created_at: str | None = None


class ResourceListResponse(BaseModel):
    resources: list[ResourceResponse]


# ---- assignments ----


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    instructions: str | None = Field(default=None, max_length=10_000)
    due_at: str | None = None
    max_score: float | None = Field(default=None, gt=0)
    is_required: bool = True

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class AssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5_000)
    instructions: str | None = Field(default=None, max_length=10_000)
    due_at: str | None = None
    max_score: float | None = Field(default=None, gt=0)
    is_required: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class AssignmentResponse(BaseModel):
    id: str
    program_id: str
    module_id: str | None = None
    title: str
    description: str | None = None
    instructions: str | None = None
    due_at: str | None = None
    max_score: float | None = None
    is_required: bool
    is_published: bool
    sequence_order: int
    created_at: str | None = None
    updated_at: str | None = None


class AssignmentListResponse(BaseModel):
    assignments: list[AssignmentResponse]


# ---- workspaces ----


class WorkspaceOpportunityRef(BaseModel):
    id: str
    title: str
    status: str


class WorkspaceResponse(BaseModel):
    id: str
    kind: ParticipationKind
    student_id: str
    student_name: str | None = None
    industry_id: str
    project_id: str | None = None
    training_id: str | None = None
    workshop_id: str | None = None
    project_application_id: str | None = None
    training_application_id: str | None = None
    workshop_application_id: str | None = None
    workspace_status: WorkspaceStatus
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    opportunity: WorkspaceOpportunityRef | None = None
    program_id: str | None = None
    progress: "ProgressSummary | None" = None


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceResponse]


class EnsureWorkspaceRequest(BaseModel):
    """POST body for the idempotent ensure-or-create operation. Exactly one
    of the three application ids must be supplied, matching `kind`."""

    model_config = ConfigDict(extra="forbid")

    kind: ParticipationKind
    project_application_id: str | None = None
    training_application_id: str | None = None
    workshop_application_id: str | None = None

    @model_validator(mode="after")
    def _one_application(self) -> "EnsureWorkspaceRequest":
        picked = {
            "PROJECT": self.project_application_id,
            "TRAINING": self.training_application_id,
            "WORKSHOP": self.workshop_application_id,
        }
        if not picked[self.kind]:
            raise ValueError(f"{self.kind.lower()}_application_id is required for kind={self.kind}.")
        others = [v for k, v in picked.items() if k != self.kind]
        if any(others):
            raise ValueError("Only the application id matching `kind` may be set.")
        return self


class ProgressSummary(BaseModel):
    completed_required: int
    published_required: int
    percent: int  # 0-100, 0 when published_required == 0


# ---- submissions ----


class SubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: str
    submission_text: str | None = Field(default=None, max_length=20_000)
    submission_url: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)

    @model_validator(mode="after")
    def _has_content(self) -> "SubmissionCreate":
        if not self.submission_text and not self.submission_url:
            raise ValueError("Provide submission_text and/or submission_url.")
        return self


class SubmissionResponse(BaseModel):
    id: str
    workspace_id: str
    assignment_id: str
    assignment_title: str | None = None
    attempt_number: int
    submission_text: str | None = None
    submission_url: str | None = None
    submitted_at: str | None = None
    status: SubmissionStatus
    created_at: str | None = None
    latest_review: "ReviewResponse | None" = None


class SubmissionListResponse(BaseModel):
    submissions: list[SubmissionResponse]


# ---- reviews ----


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float | None = Field(default=None, ge=0)
    feedback: str | None = Field(default=None, max_length=10_000)
    status: ReviewStatus

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class ReviewResponse(BaseModel):
    id: str
    submission_id: str
    reviewer_id: str
    score: float | None = None
    feedback: str | None = None
    status: ReviewStatus
    reviewed_at: str | None = None
    created_at: str | None = None


class ReviewListResponse(BaseModel):
    reviews: list[ReviewResponse]


# ---- feedback ----


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_type: FeedbackType
    title: str | None = Field(default=None, max_length=200)
    feedback: str = Field(min_length=1, max_length=10_000)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class FeedbackResponse(BaseModel):
    id: str
    workspace_id: str
    industry_id: str
    feedback_type: FeedbackType
    title: str | None = None
    feedback: str
    created_at: str | None = None


class FeedbackListResponse(BaseModel):
    feedback: list[FeedbackResponse]


# ---- skill recommendations ----


class SkillRecommendationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str
    recommended_level: RecommendedLevel | None = None
    reason: str = Field(min_length=1, max_length=2_000)
    priority: RecommendationPriority = "MEDIUM"

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class SkillRecommendationResponse(BaseModel):
    id: str
    workspace_id: str
    skill_id: str
    skill_name: str | None = None
    recommended_level: RecommendedLevel | None = None
    reason: str
    priority: RecommendationPriority
    created_by: str
    created_at: str | None = None


class SkillRecommendationListResponse(BaseModel):
    recommendations: list[SkillRecommendationResponse]


# ---- evaluation criteria ----


class CriterionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    max_score: float = Field(gt=0)
    weight: float = Field(gt=0, le=100)
    sequence_order: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class CriterionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    max_score: float | None = Field(default=None, gt=0)
    weight: float | None = Field(default=None, gt=0, le=100)
    sequence_order: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class CriterionResponse(BaseModel):
    id: str
    program_id: str
    name: str
    description: str | None = None
    max_score: float
    weight: float
    sequence_order: int
    created_at: str | None = None
    updated_at: str | None = None


class CriterionListResponse(BaseModel):
    criteria: list[CriterionResponse]


# ---- evaluations ----


class EvaluationScoreInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: str
    score: float = Field(ge=0)
    feedback: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class EvaluationScoreResponse(BaseModel):
    id: str
    evaluation_id: str
    criterion_id: str
    criterion_name: str | None = None
    max_score: float | None = None
    score: float
    feedback: str | None = None


class EvaluationSaveRequest(BaseModel):
    """PUT body for saving a DRAFT evaluation's scores/feedback. Rejected
    once the evaluation is FINALIZED (409, not a validation error --
    the route checks current status first)."""

    model_config = ConfigDict(extra="forbid")

    overall_feedback: str | None = Field(default=None, max_length=10_000)
    scores: list[EvaluationScoreInput] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        return _blank_to_none(data)


class EvaluationResponse(BaseModel):
    id: str
    workspace_id: str
    evaluator_id: str
    status: EvaluationStatus
    overall_score: float | None = None
    overall_feedback: str | None = None
    evaluated_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    scores: list[EvaluationScoreResponse] = Field(default_factory=list)


# ---- completion ----


class CompletionResponse(BaseModel):
    id: str
    workspace_id: str
    final_evaluation_id: str | None = None
    completed_at: str | None = None
    completion_status: CompletionStatus
    final_score: float | None = None
    created_at: str | None = None
