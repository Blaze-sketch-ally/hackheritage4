"""Pydantic schemas for assessment endpoints."""

from pydantic import BaseModel


class SubmitAssessmentResult(BaseModel):
    """Safe result information returned to the frontend after scoring.

    Deliberately excludes anything answer-key-related (which option was
    correct, per-question correctness of other students, etc.) — only
    this attempt's own aggregate outcome.
    """

    attempt_id: str
    status: str
    score: float
    total_marks: float
    percentage: float
    correct_count: int
    incorrect_count: int
    submitted_at: str | None
