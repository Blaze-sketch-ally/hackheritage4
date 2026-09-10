"""Pydantic schemas for the assessment reconciliation surface (Faculty
Assessment Reconciliation -- Option C).

Mirrors app.schemas.evaluation's own conventions exactly (UUID-typed ids,
Decimal marks, the existing `student_label` privacy convention from
AttemptForAssignmentResponse -- never email/name/profile).

Visibility (ReconciliationCaseSummary/Detail) is read-only, backed by the
067_assessment_reconciliation_visibility.sql RPCs. Decision creation/
supersession (CreateReconciliationDecisionRequest,
SupersedeReconciliationDecisionRequest, ReconciliationDecisionResponse)
is backed by the 068_assessment_reconciliation_decisions.sql RPCs --
`moderator_id` is NEVER accepted from the client anywhere in this module
(extra="forbid" on every request schema); the database exclusively
derives it from auth.uid() inside the RPC, matching this project's
existing precedent for the identical concern (ReviewDecisionRequest,
CreateEvaluatorAssignmentRequest).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReconciliationCaseSummary(BaseModel):
    """One (attempt, question) pair currently in genuine, unresolved
    disagreement -- one row per still-conflicting question, so a single
    attempt with two conflicting questions appears as two rows (mirrors
    fold_in_attempt_evaluation()'s own per-question conflict detection,
    not invented at this layer)."""

    attempt_id: UUID
    assessment_id: UUID
    assessment_title: str
    student_label: str
    question_id: UUID
    question_text: str
    points: Decimal


class ReconciliationCaseListResponse(BaseModel):
    cases: list[ReconciliationCaseSummary]


class ReconciliationEvaluatorMark(BaseModel):
    """One evaluator's FINALIZED, eligible (rubric.max_marks = question.
    points) mark on one conflicting question -- exactly the same set of
    rows fold_in_attempt_evaluation() itself reads to detect the
    conflict, never a second, independently-computed view of it."""

    question_id: UUID
    question_text: str
    points: Decimal
    evaluator_id: UUID
    awarded_marks: Decimal
    feedback: str | None = None
    rubric_id: UUID
    rubric_name: str
    finalized_at: datetime | None = None


class ReconciliationCaseDetailResponse(BaseModel):
    attempt_id: UUID
    marks: list[ReconciliationEvaluatorMark]


def _reject_blank(value: str, field_name: str) -> str:
    if value.strip() == "":
        raise ValueError(f"{field_name} must not be blank.")
    return value


class CreateReconciliationDecisionRequest(BaseModel):
    """POST .../cases/{attempt_id}/questions/{question_id}/decisions body.
    `final_awarded_marks` may equal either conflicting evaluator's own
    mark or a custom value -- the RPC itself, not this schema, enforces
    the actual [0, question.points] bound (the schema only rejects an
    obviously-invalid negative value early, matching the >= 0 CHECK
    already on the column). `rationale` is mandatory and non-blank,
    matching the approved decision -- max_length reuses
    ReviewDecisionRequest's own existing 5,000-character bound rather
    than inventing a new one; the database enforces no upper bound
    (mirrors the fact that no existing text column in this schema has
    one), so this is a request-size sanity cap, not a business rule.
    Never accepts moderator_id -- see module docstring."""

    model_config = ConfigDict(extra="forbid")

    final_awarded_marks: Decimal = Field(ge=0)
    rationale: str = Field(min_length=1, max_length=5_000)

    @model_validator(mode="after")
    def _rationale_not_blank(self) -> "CreateReconciliationDecisionRequest":
        _reject_blank(self.rationale, "rationale")
        return self


class SupersedeReconciliationDecisionRequest(BaseModel):
    """POST .../decisions/{decision_id}/supersede body. Same score/
    rationale contract as creation; never accepts moderator_id."""

    model_config = ConfigDict(extra="forbid")

    final_awarded_marks: Decimal = Field(ge=0)
    rationale: str = Field(min_length=1, max_length=5_000)

    @model_validator(mode="after")
    def _rationale_not_blank(self) -> "SupersedeReconciliationDecisionRequest":
        _reject_blank(self.rationale, "rationale")
        return self


class ReconciliationDecisionResponse(BaseModel):
    """The result of creating or superseding a decision: the new
    decision's own fields, plus the freshly-refolded attempt's own
    evaluation_status/final_percentage (never computed or set by this
    schema/service/route -- fold_in_attempt_evaluation() remains the one
    place those are derived)."""

    decision_id: UUID
    attempt_id: UUID
    question_id: UUID
    moderator_id: UUID
    final_awarded_marks: Decimal
    rationale: str
    status: str
    created_at: datetime
    evaluation_status: str
    final_percentage: Decimal | None = None


class ReconciliationDecisionHistoryItem(BaseModel):
    """One entry in a question's full decision chain (ACTIVE + every
    SUPERSEDED ancestor) -- moderator-only visibility (Stage 8)."""

    decision_id: UUID
    moderator_id: UUID
    final_awarded_marks: Decimal
    rationale: str
    status: str
    created_at: datetime
    superseded_by: UUID | None = None


class ReconciliationDecisionHistoryResponse(BaseModel):
    question_id: UUID
    decisions: list[ReconciliationDecisionHistoryItem]
