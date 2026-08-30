"""Pydantic schemas for the Assessment API.

Mirrors database/migrations/004_assessments.sql exactly -- no invented
columns, no invented enum values. Field-by-field mapping:

  assessments                  -> AssessmentResponse
  assessment_questions         -> AssessmentQuestionResponse (options embedded)
  assessment_question_options  -> AssessmentOptionResponse
  assessment_question_answers  -> AssessmentAnswerKeyResponse (POST-COMPLETION ONLY)
  assessment_attempts          -> AssessmentAttemptResponse / SubmitAttemptResponse
  assessment_answers           -> AssessmentAnswerRequest / AssessmentAnswerResponse

Security invariant (see the migration's own header comment on why this is
structural, not just an application convention): AssessmentQuestionResponse
and AssessmentOptionResponse can NEVER carry a correct_option_ids /
correct_answer_text / explanation field, because assessment_questions and
assessment_question_options physically have no such column. The only place
those three fields may appear anywhere in this module is
AssessmentAnswerKeyResponse, which every doctring below marks as
post-completion-only -- callers must not construct it for an IN_PROGRESS
attempt (RLS already refuses to return that data for one; this is the
schema-layer half of the same rule).

No endpoint, service, or scoring logic lives here -- schemas only.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

# ============================================================
# Enums -- exact mirrors of the CHECK constraints in 004_assessments.sql
# ============================================================


class Difficulty(str, Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXPERT = "Expert"


class QuestionType(str, Enum):
    MCQ = "MCQ"
    MULTIPLE_SELECT = "MULTIPLE_SELECT"
    SHORT_ANSWER = "SHORT_ANSWER"
    CODE = "CODE"
    SUBJECTIVE = "SUBJECTIVE"


class ScoringMethod(str, Enum):
    OBJECTIVE = "OBJECTIVE"
    AI_EVALUATED = "AI_EVALUATED"


class AttemptStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


# ============================================================
# assessments
# ============================================================


class AssessmentResponse(BaseModel):
    """Mirrors `assessments`. Only ever populated from rows RLS already
    filtered to is_active = true, but the field is still included as a
    plain mirror of the row -- not sensitive, no reason to hide it."""

    id: UUID
    skill_id: UUID
    title: str
    description: str | None
    difficulty: Difficulty
    duration_minutes: int | None
    question_count: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssessmentListResponse(BaseModel):
    assessments: list[AssessmentResponse]


# ============================================================
# assessment_question_options
# ============================================================


class AssessmentOptionResponse(BaseModel):
    """Mirrors `assessment_question_options`. This table has no
    correctness column at all -- there is structurally nothing here to
    leak, pre- or post-completion."""

    id: UUID
    question_id: UUID
    option_text: str
    display_order: int


# ============================================================
# assessment_questions
# ============================================================


class AssessmentQuestionResponse(BaseModel):
    """Mirrors `assessment_questions`, with its options embedded (the one
    thing a student always needs alongside a question). Deliberately
    excludes generation_source/generation_model/generated_at/review_status:
    real columns, but internal provenance/moderation metadata with no
    student-facing purpose -- see the Phase 1C report for this as a
    documented decision, not an oversight.

    NEVER add a correct_option_ids/correct_answer_text/explanation field to
    this model. That data belongs only on AssessmentAnswerKeyResponse.
    """

    id: UUID
    assessment_id: UUID
    question_text: str
    question_type: QuestionType
    scoring_method: ScoringMethod
    difficulty: Difficulty
    points: Decimal
    display_order: int
    options: list[AssessmentOptionResponse]


# ============================================================
# assessment_question_answers -- THE PROTECTED ANSWER KEY.
# ============================================================


class AssessmentAnswerKeyResponse(BaseModel):
    """Mirrors `assessment_question_answers`.

    POST-COMPLETION ONLY. RLS itself already refuses to return this data
    for anything but the student's own COMPLETED attempt (see the
    "Students can view answer keys for their own completed attempts"
    policy) -- this model must never be constructed or returned outside
    that same condition at the application layer either. Never embed this
    in AssessmentQuestionResponse or any other pre-completion schema.
    """

    question_id: UUID
    correct_option_ids: list[UUID] | None
    correct_answer_text: str | None
    explanation: str | None


# ============================================================
# assessment_attempts
# ============================================================


class AssessmentAttemptResponse(BaseModel):
    """Mirrors `assessment_attempts`. score/total_marks/percentage/
    submitted_at are all null until the attempt is scored -- this one
    model naturally represents both an IN_PROGRESS and a COMPLETED attempt,
    matching the table's own nullable semantics rather than inventing a
    separate pre/post type."""

    id: UUID
    student_id: UUID
    assessment_id: UUID
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime | None
    score: Decimal | None
    total_marks: Decimal | None
    percentage: Decimal | None
    created_at: datetime
    updated_at: datetime


# ============================================================
# assessment_answers
# ============================================================


class AssessmentAnswerRequest(BaseModel):
    """What a student may submit to answer/revise a question.

    extra="forbid" is the actual enforcement mechanism for "students must
    never submit awarded_marks/is_correct": those fields simply don't
    exist on this model, and any request body containing them (or any
    other unrecognized field) is rejected with a 422 before any handler
    code runs -- not a manual field-by-field denylist.
    """

    model_config = ConfigDict(extra="forbid")

    question_id: UUID
    answer_text: str | None = None
    selected_option_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def _at_least_one_answer_field(self) -> "AssessmentAnswerRequest":
        # Mirrors the DB's own assessment_answers_has_content check exactly
        # -- not a stricter, invented rule.
        if self.answer_text is None and self.selected_option_ids is None:
            raise ValueError("Provide answer_text and/or selected_option_ids.")
        if self.selected_option_ids is not None and len(self.selected_option_ids) == 0:
            raise ValueError("selected_option_ids must not be empty when provided.")
        return self


class AssessmentAnswerResponse(BaseModel):
    """Mirrors `assessment_answers`. awarded_marks/is_correct are null
    until the attempt is submitted -- exposing them here isn't an answer-key
    leak (the correct answer itself is never on this table), only ever
    "was *your* answer right," and only once it's actually been computed."""

    id: UUID
    attempt_id: UUID
    question_id: UUID
    answer_text: str | None
    selected_option_ids: list[UUID] | None
    awarded_marks: Decimal | None
    is_correct: bool | None
    created_at: datetime
    updated_at: datetime


# ============================================================
# Submit attempt
# ============================================================


class SubmitAttemptRequest(BaseModel):
    """Deliberately empty. The attempt to submit is identified by the URL
    path (attempt_id), never the body. extra="forbid" means any body
    content at all -- score, total_marks, percentage, is_correct,
    awarded_marks, submitted_at, or anything else -- is rejected outright.
    """

    model_config = ConfigDict(extra="forbid")


class SubmitAttemptResponse(BaseModel):
    """The completed attempt. Unlike AssessmentAttemptResponse, the score
    fields are required (not Optional) here: a successful submission is the
    one moment those values are guaranteed non-null, mirroring the DB's own
    assessment_attempts_completed_has_score constraint at the type level."""

    id: UUID
    student_id: UUID
    assessment_id: UUID
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime
    score: Decimal
    total_marks: Decimal
    percentage: Decimal


# ============================================================
# Assessment result (post-completion only)
# ============================================================


class AssessmentResultQuestionResponse(BaseModel):
    """One question's full post-completion breakdown. Safe to expose the
    answer key here only because this type is never constructed for
    anything but a COMPLETED attempt -- see AssessmentAnswerKeyResponse."""

    question: AssessmentQuestionResponse
    student_answer: AssessmentAnswerResponse | None
    answer_key: AssessmentAnswerKeyResponse


class AssessmentResultResponse(BaseModel):
    """POST-COMPLETION ONLY -- the full result view for one attempt:
    the attempt summary plus, per question, the question/options, the
    student's own answer, and (only because the attempt is COMPLETED) the
    answer key. Never construct this for an IN_PROGRESS attempt."""

    attempt: AssessmentAttemptResponse
    questions: list[AssessmentResultQuestionResponse]
