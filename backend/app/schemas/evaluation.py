"""Pydantic schemas for the F8.3 evaluator workflow. Mirrors
`evaluations`/`evaluator_assignments`/`rubrics`/`rubric_criteria`
(045_evaluation_foundation.sql, 046_evaluator_answer_access.sql).

Every response here is built from data already scoped by RLS through the
caller's own client (app.core.security.build_user_client) -- these models
describe shape, not access control. Nothing here ever includes an answer
key (AssessmentAnswerKeyResponse) or another evaluator's data -- see
app.services.evaluation_service for the actual queries.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import AssessmentAnswerResponse, AssessmentQuestionResponse


class EvaluationStatus(str, Enum):
    """Mirrors evaluations.status (045). ASSIGNED is the initial,
    system-created state -- never a client-requested target, see
    UpdateEvaluationStatusRequest below, which deliberately excludes it."""

    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    FINALIZED = "FINALIZED"


# ============================================================
# rubrics / rubric_criteria -- read-only in F8.3. Who may author a rubric
# remains an F8.1-deferred decision; these models exist only to describe
# the rubric a caller's own evaluation happens to reference (046's own
# narrow SELECT policy is what actually scopes visibility).
# ============================================================


class RubricCriterionResponse(BaseModel):
    id: UUID
    rubric_id: UUID
    criterion: str
    description: str | None
    max_marks: Decimal
    display_order: int


class RubricResponse(BaseModel):
    id: UUID
    question_id: UUID
    name: str
    description: str | None
    max_marks: Decimal
    status: str
    criteria: list[RubricCriterionResponse]


# ============================================================
# evaluations
# ============================================================


class EvaluationSummaryResponse(BaseModel):
    """One row of GET /faculty/evaluations -- the caller's own work
    queue. Deliberately thin: no question/answer/rubric content (kept for
    the detail endpoint), no co-evaluator information (F8.2 never exposed
    this and F8.3 does not introduce it -- see the F8.3 audit's own
    co-evaluation section).

    Phase 2 (Evaluation Workspace): assessment_title/assigned_at added --
    both already stored (assessments.title, evaluator_assignments.
    created_at), joined once per list call (batched exactly like
    student_id already is, never one query per row) -- needed so the
    workspace's own assignment list is usable without a separate
    per-row fetch."""

    evaluation_id: UUID
    assignment_id: UUID
    status: EvaluationStatus
    awarded_marks: Decimal | None
    attempt_id: UUID
    question_id: UUID
    student_id: UUID
    assessment_title: str
    assigned_at: datetime


class EvaluationDetailResponse(BaseModel):
    """GET /faculty/evaluations/{id} -- everything needed to actually
    evaluate one assigned answer. question is the student-facing shape
    (AssessmentQuestionResponse) -- it has no answer-key fields by
    construction (see that model's own docstring); this endpoint never
    constructs or returns an AssessmentAnswerKeyResponse, matching the
    F8.2 audit's explicit decision C."""

    evaluation_id: UUID
    assignment_id: UUID
    status: EvaluationStatus
    awarded_marks: Decimal | None
    feedback: str | None
    rubric_id: UUID | None
    submitted_at: datetime | None
    finalized_at: datetime | None
    finalized_by: UUID | None
    attempt_id: UUID
    question_id: UUID
    student_id: UUID
    assessment_title: str
    assigned_at: datetime
    question: AssessmentQuestionResponse
    student_answer: AssessmentAnswerResponse | None
    rubric: RubricResponse | None


class SaveEvaluationRequest(BaseModel):
    """PATCH /faculty/evaluations/{id} body -- content only, never
    status. Every field is optional and exclude_unset-driven at the route
    layer: an omitted field leaves the column unchanged, an explicit null
    clears it where the database allows that (rubric_id/feedback; the
    database's own CHECK constraints are the authority on which nulls are
    actually legal, not this schema). extra="forbid" is what makes it
    impossible for a client to submit status/submitted_at/finalized_at/
    finalized_by here -- those fields simply don't exist on this model.
    """

    model_config = ConfigDict(extra="forbid")

    rubric_id: UUID | None = None
    awarded_marks: Decimal | None = Field(default=None, ge=0)
    feedback: str | None = Field(default=None, max_length=5_000)


class UpdateEvaluationStatusRequest(BaseModel):
    """PATCH /faculty/evaluations/{id}/status body -- lifecycle only. A
    Literal of the three client-reachable targets, not the full
    EvaluationStatus enum -- ASSIGNED is the system-created initial
    state, never something a client transitions INTO, so it is excluded
    at the type level (matching QuestionUpdateInput.review_status's own
    Literal["PENDING"] precedent) rather than rejected by a runtime
    check. submitted_at/finalized_at/finalized_by are never accepted here
    at all -- the F8.1 trigger server-forces them unconditionally
    regardless of what reaches this schema, so it does not even offer
    the fields to reject.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal[EvaluationStatus.IN_PROGRESS, EvaluationStatus.SUBMITTED, EvaluationStatus.FINALIZED]


# ============================================================
# Phase 2 -- ADMIN-facing evaluator assignment management.
#
# These carry more than the evaluator-facing models above ever do
# (evaluator identity, student attempt/question browsing across every
# student) -- exactly the audience require_admin() exists for. Never
# reuse these on a Faculty-facing route. Assignment CREATION/REVOCATION
# itself still goes entirely through create_evaluator_assignment()/
# revoke_evaluator_assignment() (045_evaluation_foundation.sql,
# service_role-only, unmodified) -- these models only describe the
# request/response shape around those existing, reused RPCs.
# ============================================================


class EligibleEvaluatorResponse(BaseModel):
    """One Faculty member currently eligible to be assigned as an
    evaluator (holds an active, unexpired assessment_evaluator
    capability) -- see faculty_permission_service.
    admin_list_eligible_evaluators."""

    faculty_id: UUID
    email: str
    full_name: str | None = None


class ExistingAssignmentResponse(BaseModel):
    """One evaluator_assignments row already made against a given
    attempt/question, shown to an ADMIN deciding whether/who else to
    assign (e.g. for co-evaluation) -- never shown to another evaluator."""

    assignment_id: UUID
    evaluator_id: UUID
    evaluator_email: str
    evaluator_full_name: str | None = None
    assignment_status: Literal["ACTIVE", "REVOKED"]
    evaluation_status: EvaluationStatus


class AttemptQuestionForAssignmentResponse(BaseModel):
    """One AI_EVALUATED question within one attempt, for the admin
    assignment picker -- only AI_EVALUATED questions are ever eligible
    for a human evaluator assignment (scoring_method alone is the only
    signal this schema persists, per fold_in_attempt_evaluation()'s own
    established "what counts as required" rule, 049)."""

    question_id: UUID
    question_text: str
    points: Decimal
    existing_assignments: list[ExistingAssignmentResponse]


class AttemptForAssignmentResponse(BaseModel):
    """One COMPLETED attempt for a chosen assessment, with its
    AI_EVALUATED questions and any assignments already made against
    them. student_label is a privacy-safe, truncated identifier (never
    email/name) -- matching this project's own established convention
    for showing a caller an identity they should not see the full
    profile of (question_detail_view.tsx's own reviewerLabel design,
    reused here for the same reason)."""

    attempt_id: UUID
    student_label: str
    status: str
    questions: list[AttemptQuestionForAssignmentResponse]


class CreateEvaluatorAssignmentRequest(BaseModel):
    """POST /admin/evaluator-assignments body. extra=\"forbid\" so
    created_by can never be smuggled in from the client -- it is always
    the authenticated admin, passed server-side to
    create_evaluator_assignment()."""

    model_config = ConfigDict(extra="forbid")

    evaluator_id: UUID
    attempt_id: UUID
    question_id: UUID


class EvaluatorAssignmentResponse(BaseModel):
    """The evaluator_assignments row created/revoked, as seen by an
    ADMIN."""

    assignment_id: UUID
    evaluator_id: UUID
    attempt_id: UUID
    question_id: UUID
    status: Literal["ACTIVE", "REVOKED"]
    created_at: datetime
    revoked_at: datetime | None
