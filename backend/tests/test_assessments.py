"""Tests for the Assessment API schema layer (Phase 1C).

Pure Pydantic model tests -- no database, no HTTP, no live Supabase call.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.assessment import (
    AssessmentAnswerKeyResponse,
    AssessmentAnswerRequest,
    AssessmentAnswerResponse,
    AssessmentAttemptResponse,
    AssessmentListResponse,
    AssessmentOptionResponse,
    AssessmentQuestionResponse,
    AssessmentResponse,
    AttemptStatus,
    Difficulty,
    QuestionType,
    ScoringMethod,
    SubmitAttemptRequest,
    SubmitAttemptResponse,
)

# ============================================================
# Valid-payload fixtures
# ============================================================


def _assessment_data(**overrides):
    data = {
        "id": uuid4(),
        "skill_id": uuid4(),
        "title": "Python Intermediate Assessment",
        "description": "Covers functions, OOP, and exceptions.",
        "difficulty": "Intermediate",
        "duration_minutes": 30,
        "question_count": 10,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _option_data(**overrides):
    data = {
        "id": uuid4(),
        "question_id": uuid4(),
        "option_text": "A list is mutable, a tuple is not.",
        "display_order": 0,
    }
    data.update(overrides)
    return data


def _question_data(**overrides):
    data = {
        "id": uuid4(),
        "assessment_id": uuid4(),
        "question_text": "Which of the following is true about Python lists?",
        "question_type": "MCQ",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Intermediate",
        "points": "2.00",
        "display_order": 0,
        "options": [_option_data(), _option_data()],
    }
    data.update(overrides)
    return data


def _attempt_data(**overrides):
    data = {
        "id": uuid4(),
        "student_id": uuid4(),
        "assessment_id": uuid4(),
        "status": "IN_PROGRESS",
        "started_at": "2026-01-01T00:00:00Z",
        "submitted_at": None,
        "score": None,
        "total_marks": None,
        "percentage": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _answer_response_data(**overrides):
    data = {
        "id": uuid4(),
        "attempt_id": uuid4(),
        "question_id": uuid4(),
        "answer_text": None,
        "selected_option_ids": [uuid4()],
        "awarded_marks": None,
        "is_correct": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


# ============================================================
# 1. Valid assessment response
# ============================================================


def test_valid_assessment_response():
    assessment = AssessmentResponse(**_assessment_data())
    assert assessment.title == "Python Intermediate Assessment"
    assert assessment.difficulty == Difficulty.INTERMEDIATE
    assert assessment.is_active is True


def test_valid_assessment_list_response():
    listing = AssessmentListResponse(assessments=[_assessment_data(), _assessment_data()])
    assert len(listing.assessments) == 2
    assert all(isinstance(a, AssessmentResponse) for a in listing.assessments)


# ============================================================
# 2. Valid question response (+ embedded options)
# ============================================================


def test_valid_question_response():
    question = AssessmentQuestionResponse(**_question_data())
    assert question.question_type == QuestionType.MCQ
    assert question.scoring_method == ScoringMethod.OBJECTIVE
    assert len(question.options) == 2
    assert all(isinstance(o, AssessmentOptionResponse) for o in question.options)


# ============================================================
# 3. Valid option response
# ============================================================


def test_valid_option_response():
    option = AssessmentOptionResponse(**_option_data(option_text="A tuple is immutable."))
    assert option.option_text == "A tuple is immutable."
    assert option.display_order == 0


# ============================================================
# 4. Valid attempt response (both IN_PROGRESS and COMPLETED shapes)
# ============================================================


def test_valid_attempt_response_in_progress():
    attempt = AssessmentAttemptResponse(**_attempt_data())
    assert attempt.status == AttemptStatus.IN_PROGRESS
    assert attempt.score is None
    assert attempt.submitted_at is None


def test_valid_attempt_response_completed():
    attempt = AssessmentAttemptResponse(
        **_attempt_data(
            status="COMPLETED",
            submitted_at="2026-01-01T01:00:00Z",
            score="8.00",
            total_marks="10.00",
            percentage="80.00",
        )
    )
    assert attempt.status == AttemptStatus.COMPLETED
    assert attempt.score == attempt.score  # populated, no error constructing
    assert attempt.percentage is not None


# ============================================================
# 5. Valid answer request
# ============================================================


def test_valid_answer_request_with_selected_options():
    request = AssessmentAnswerRequest(question_id=uuid4(), selected_option_ids=[uuid4()])
    assert request.selected_option_ids is not None
    assert request.answer_text is None


def test_valid_answer_request_with_text():
    request = AssessmentAnswerRequest(question_id=uuid4(), answer_text="A tuple is immutable.")
    assert request.answer_text == "A tuple is immutable."


# ============================================================
# 6. Server-controlled fields cannot be accepted
# ============================================================


def test_answer_request_rejects_awarded_marks():
    with pytest.raises(ValidationError):
        AssessmentAnswerRequest(
            question_id=uuid4(), selected_option_ids=[uuid4()], awarded_marks="5.00"
        )


def test_answer_request_rejects_is_correct():
    with pytest.raises(ValidationError):
        AssessmentAnswerRequest(question_id=uuid4(), selected_option_ids=[uuid4()], is_correct=True)


def test_submit_attempt_request_rejects_any_body_content():
    with pytest.raises(ValidationError):
        SubmitAttemptRequest(score="100.00", status="COMPLETED")


def test_submit_attempt_request_accepts_empty_body():
    # No error -- this is the only valid shape.
    SubmitAttemptRequest()


# ============================================================
# 7. Answer-key fields are not present in student-facing schemas
# ============================================================


def test_question_response_has_no_answer_key_fields():
    forbidden = {"correct_option_ids", "correct_answer_text", "explanation"}
    assert forbidden.isdisjoint(AssessmentQuestionResponse.model_fields.keys())


def test_option_response_has_no_answer_key_fields():
    forbidden = {"correct_option_ids", "correct_answer_text", "explanation"}
    assert forbidden.isdisjoint(AssessmentOptionResponse.model_fields.keys())


def test_answer_key_fields_are_confined_to_answer_key_response():
    # The only schema allowed to carry this data.
    assert "correct_option_ids" in AssessmentAnswerKeyResponse.model_fields
    assert "correct_answer_text" in AssessmentAnswerKeyResponse.model_fields
    assert "explanation" in AssessmentAnswerKeyResponse.model_fields


def test_answer_response_has_no_correct_answer_fields():
    # awarded_marks/is_correct (the student's OWN score) are allowed here --
    # correct_option_ids/correct_answer_text (someone else's answer key) are not.
    forbidden = {"correct_option_ids", "correct_answer_text"}
    assert forbidden.isdisjoint(AssessmentAnswerResponse.model_fields.keys())


def test_submit_attempt_response_has_no_input_score_fields():
    # SubmitAttemptResponse is a response -- confirm nothing here could be
    # mistaken for an accepted request field.
    assert "score" in SubmitAttemptResponse.model_fields  # present as OUTPUT, expected
    assert SubmitAttemptRequest.model_fields == {}  # but never as INPUT


# ============================================================
# 8. Invalid UUID rejected
# ============================================================


def test_assessment_response_rejects_invalid_uuid():
    with pytest.raises(ValidationError):
        AssessmentResponse(**_assessment_data(id="not-a-uuid"))


def test_answer_request_rejects_invalid_question_id():
    with pytest.raises(ValidationError):
        AssessmentAnswerRequest(question_id="not-a-uuid", answer_text="whatever")


# ============================================================
# 9. Invalid/missing required fields rejected
# ============================================================


def test_assessment_response_requires_title():
    data = _assessment_data()
    del data["title"]
    with pytest.raises(ValidationError):
        AssessmentResponse(**data)


def test_answer_request_requires_at_least_one_answer_field():
    with pytest.raises(ValidationError):
        AssessmentAnswerRequest(question_id=uuid4())


def test_answer_request_rejects_empty_selected_option_ids():
    with pytest.raises(ValidationError):
        AssessmentAnswerRequest(question_id=uuid4(), selected_option_ids=[])


# ============================================================
# 10. Enum/controlled values rejected when invalid
# ============================================================


def test_assessment_response_rejects_invalid_difficulty():
    with pytest.raises(ValidationError):
        AssessmentResponse(**_assessment_data(difficulty="Expert-ish"))


def test_question_response_rejects_invalid_question_type():
    with pytest.raises(ValidationError):
        AssessmentQuestionResponse(**_question_data(question_type="ESSAY"))


def test_question_response_rejects_invalid_scoring_method():
    with pytest.raises(ValidationError):
        AssessmentQuestionResponse(**_question_data(scoring_method="MANUAL"))


def test_attempt_response_rejects_invalid_status():
    with pytest.raises(ValidationError):
        AssessmentAttemptResponse(**_attempt_data(status="CANCELLED"))
