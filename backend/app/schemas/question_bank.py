"""Pydantic schemas for the Question Bank + Assessment Blueprint API
(Phase 1K) -- database/migrations/015_question_bank_random_assessment.sql.

  assessment_questions (extended: created_by)  -> QuestionBankResponse /
                                                    QuestionCreateRequest /
                                                    QuestionUpdateRequest
  assessment_question_options                  -> reuses AssessmentOptionResponse
                                                    (app.schemas.assessment)
  assessment_question_answers                   -> QuestionAnswerKeyInput
  assessment_blueprint_rules                     -> BlueprintRuleRequest /
                                                    BlueprintRuleResponse

Security invariant: QuestionBankResponse is a FACULTY-facing view --
distinct from AssessmentQuestionResponse (app.schemas.assessment), which
stays the student-facing view and must never gain review_status/
created_by/answer_key fields. Every route returning QuestionBankResponse
requires require_faculty and is further scoped by RLS (015's "Faculty can
view their own or pending questions" policy) -- a faculty member can never
see another setter's still-non-approved private draft through this schema
either; RLS enforces that regardless of what this module declares.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.assessment import AssessmentOptionResponse, Difficulty, QuestionType, ScoringMethod


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ============================================================
# Question bank -- create/update/read
# ============================================================


class QuestionOptionInput(BaseModel):
    """One option supplied when creating/replacing a question's options.
    display_order is caller-supplied (not auto-assigned) so MCQ/
    MULTIPLE_SELECT ordering is explicit and stable, matching
    assessment_question_options' unique(question_id, display_order)
    constraint.

    id is optional and CLIENT-GENERATED (never server-assigned before the
    row exists): an option's real id doesn't exist until it's inserted,
    but QuestionAnswerKeyInput.correct_option_ids must reference real
    option ids in the SAME request that creates them. The frontend
    generates a UUID per option up front (crypto.randomUUID()) and reuses
    it as both this id and the matching correct_option_ids entry -- a
    standard client-generated-id pattern, not a security-relevant choice
    (assessment_question_options.id has no FK depending on insertion
    order, so an explicit id in the INSERT payload is exactly as valid as
    the column's own `default gen_random_uuid()`)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    option_text: str
    display_order: int


class QuestionAnswerKeyInput(BaseModel):
    """The answer key supplied alongside a question. Mirrors
    assessment_question_answers exactly -- no question_id field; the
    parent question's id always comes from the URL, never the body."""

    model_config = ConfigDict(extra="forbid")

    correct_option_ids: list[UUID] | None = None
    correct_answer_text: str | None = None
    explanation: str | None = None


class QuestionCreateRequest(BaseModel):
    """What a faculty setter submits to add a new question to the shared
    bank. review_status is never accepted here -- every question starts
    PENDING (015's own INSERT policy independently enforces this), and
    created_by is always the caller's own id, never taken from the body."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: UUID
    question_text: str
    question_type: QuestionType
    scoring_method: ScoringMethod
    difficulty: Difficulty
    points: Decimal
    display_order: int = 0
    options: list[QuestionOptionInput] = []
    answer_key: QuestionAnswerKeyInput | None = None


class QuestionUpdateRequest(BaseModel):
    """Partial update to a question's own content fields, and (optionally)
    a full replacement of its options/answer key. Only meaningful while
    review_status is not APPROVED -- 015's own trigger
    (prevent_unauthorized_question_review) rejects any content-field
    change to an approved question regardless of what this schema allows
    through, and separately rejects a non-owner changing anything but
    review_status; options/answer_key writes are independently scoped by
    RLS to the same "own, non-approved question" condition. Never accepts
    created_by -- that never changes after creation.

    review_status accepts ONLY 'PENDING' here (rejected/validated below,
    not left to the trigger alone, for a clearer 422 over a generic 403)
    -- this is Phase 1K's entire "resubmit after rejection" path: a
    question's own creator revises its content, then sets review_status
    back to PENDING in the same or a follow-up PATCH. Approving/rejecting
    someone else's question goes through the dedicated /approve and
    /reject routes only, never through this field.

    options/answer_key, when present, REPLACE the question's entire
    current set (same delete-then-insert semantics as
    question_bank_service.replace_options/upsert_answer_key used by
    create_question) -- not a per-option patch. Omit them entirely to
    leave options/the answer key untouched while editing only the
    question's own fields."""

    model_config = ConfigDict(extra="forbid")

    question_text: str | None = None
    question_type: QuestionType | None = None
    scoring_method: ScoringMethod | None = None
    difficulty: Difficulty | None = None
    points: Decimal | None = None
    display_order: int | None = None
    is_active: bool | None = None
    review_status: ReviewStatus | None = None
    options: list[QuestionOptionInput] | None = None
    answer_key: QuestionAnswerKeyInput | None = None

    @model_validator(mode="after")
    def _review_status_only_pending(self) -> "QuestionUpdateRequest":
        if self.review_status is not None and self.review_status != ReviewStatus.PENDING:
            raise ValueError(
                "review_status may only be set to PENDING here (a resubmission) -- "
                "approve/reject a question via POST .../approve or .../reject."
            )
        return self


class QuestionBankResponse(BaseModel):
    """The FACULTY-facing view of one question -- unlike
    AssessmentQuestionResponse (student-facing), this includes
    review_status/created_by/is_active/the answer key. Every route
    producing this requires require_faculty."""

    id: UUID
    assessment_id: UUID
    question_text: str
    question_type: QuestionType
    scoring_method: ScoringMethod
    difficulty: Difficulty
    points: Decimal
    display_order: int
    review_status: ReviewStatus
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    options: list[AssessmentOptionResponse]
    answer_key: QuestionAnswerKeyInput | None


# ============================================================
# Assessment blueprint
# ============================================================


class BlueprintRuleRequest(BaseModel):
    """One difficulty bucket's required question count."""

    model_config = ConfigDict(extra="forbid")

    difficulty: Difficulty
    question_count: int

    @model_validator(mode="after")
    def _positive_count(self) -> "BlueprintRuleRequest":
        if self.question_count <= 0:
            raise ValueError("question_count must be greater than 0.")
        return self


class BlueprintUpsertRequest(BaseModel):
    """Replaces an assessment's ENTIRE blueprint (delete-then-insert), not
    a per-difficulty PATCH -- matches how a blueprint is actually
    authored in one sitting, and avoids needing a separate delete route
    for a bucket that's no longer wanted."""

    model_config = ConfigDict(extra="forbid")

    rules: list[BlueprintRuleRequest]

    @model_validator(mode="after")
    def _unique_difficulties(self) -> "BlueprintUpsertRequest":
        difficulties = [rule.difficulty for rule in self.rules]
        if len(difficulties) != len(set(difficulties)):
            raise ValueError("Each difficulty may appear at most once in a blueprint.")
        return self


class BlueprintRuleResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    difficulty: Difficulty
    question_count: int
    created_at: datetime
    updated_at: datetime


class BlueprintResponse(BaseModel):
    assessment_id: UUID
    rules: list[BlueprintRuleResponse]
