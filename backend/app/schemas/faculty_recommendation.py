"""Pydantic schemas for the deterministic Faculty task/recommendation
surface (Faculty Module audit).

Mirrors app.schemas.student_recommendation's own posture exactly: a thin
ADAPTER/COMPOSER response over canonical, UNCHANGED-here services
(question_bank_service, evaluation_service, faculty_student_mentorship_service).
No new score, probability, or LLM-derived value is invented anywhere --
every field here is a real, already-authorized fact (a question's own
created_at, an evaluation's own assigned_at, a mentorship's own status)
that the caller could already see via the existing question bank /
evaluation / mentorship endpoints. This only aggregates and ranks by a
real lifecycle signal (age, or a documented status), never a fabricated
relevance score.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.faculty_student_mentorship import MentorshipStatus


class PendingReviewItem(BaseModel):
    """One PENDING question authored by a DIFFERENT faculty member, only
    ever populated for a caller who currently holds assessment_reviewer
    (see faculty_recommendation_service.list_pending_reviews)."""

    question_id: str
    assessment_id: str
    question_text: str
    created_at: datetime


class PendingEvaluationItem(BaseModel):
    """One of the caller's own ASSIGNED/IN_PROGRESS evaluations, only
    ever populated for a caller who currently holds assessment_evaluator."""

    evaluation_id: str
    attempt_id: str | None = None
    assessment_title: str | None = None
    status: Literal["ASSIGNED", "IN_PROGRESS"]
    assigned_at: datetime | None = None


class MentorshipAttentionItem(BaseModel):
    """One of the caller's own mentorships sitting at a documented
    lifecycle checkpoint that needs THEIR action next: REQUESTED (a
    student is awaiting the caller's accept/decline) or ACCEPTED (both
    sides consented, but the mentorship has not yet been activated --
    see 040_faculty_student_mentorships.sql's own status comment)."""

    mentorship_id: str
    student_id: str
    student_name: str
    status: MentorshipStatus
    reason: str
    updated_at: datetime


class PendingReconciliationItem(BaseModel):
    """One (attempt, question) currently in a genuine, unresolved
    evaluator conflict, only ever populated for a caller who currently
    holds assessment_moderator (Faculty Assessment Governance audit).
    Read-only -- there is no resolution action behind this item in this
    phase; see 067_assessment_reconciliation_visibility.sql's own header
    for why."""

    attempt_id: str
    assessment_id: str
    assessment_title: str
    student_label: str
    question_id: str
    question_text: str
    points: Decimal


class FacultyTasksResponse(BaseModel):
    pending_reviews: list[PendingReviewItem] = []
    pending_evaluations: list[PendingEvaluationItem] = []
    mentorship_attention: list[MentorshipAttentionItem] = []
    pending_reconciliations: list[PendingReconciliationItem] = []
