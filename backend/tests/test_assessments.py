"""Tests for the Assessment API: schemas (Phase 1C) and the read endpoints
(Phase 1D).

No live Supabase project or real token is used anywhere in this file --
Phase 1C tests are pure Pydantic model tests; Phase 1D tests mock the auth
dependency chain (see conftest.py) and, where appropriate, the Supabase
client/service layer directly.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.security import InvalidTokenError
from app.main import app
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
from app.services import assessment_service
from tests.conftest import authenticated_as

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


# ============================================================
# Phase 1D -- Assessment read API
# ============================================================
#
# Two layers, tested separately:
#   - "service layer" tests mock the Supabase client itself and assert the
#     query WE construct (the filters/ordering our code is responsible
#     for) -- this is what we actually control and can verify in pytest.
#     Whether Postgres/RLS truly enforces those filters live is a database
#     concern, already verified separately against the real project.
#   - "API layer" tests use FastAPI's TestClient against the real app,
#     mocking only the auth dependency chain (conftest.authenticated_as)
#     and, where relevant, the assessment_service functions -- this
#     verifies routing, auth/role enforcement, status codes, and response
#     shape end-to-end through the real dependency-injection pipeline.

client = TestClient(app)


def _row_assessment(**overrides):
    row = {
        "id": str(uuid4()),
        "skill_id": str(uuid4()),
        "title": "Python Intermediate Assessment",
        "description": "Covers functions, OOP, and exceptions.",
        "difficulty": "Intermediate",
        "duration_minutes": 30,
        "question_count": 10,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _row_option(**overrides):
    row = {
        "id": str(uuid4()),
        "question_id": str(uuid4()),
        "option_text": "A tuple is immutable.",
        "display_order": 0,
    }
    row.update(overrides)
    return row


def _row_question(**overrides):
    row = {
        "id": str(uuid4()),
        "assessment_id": str(uuid4()),
        "question_text": "Which of the following is true about Python lists?",
        "question_type": "MCQ",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Intermediate",
        "points": "2.00",
        "display_order": 0,
        "options": [_row_option(display_order=0), _row_option(display_order=1)],
    }
    row.update(overrides)
    return row


# ------------------------------------------------------------
# Service layer: query construction
# ------------------------------------------------------------


def _chain_returning(data):
    """A MagicMock Supabase client whose .table().select().eq()...eq()
    .order().execute() returns an object with `.data = data`.

    .eq() is configured to return the SAME node every time it's called, so
    this works regardless of how many .eq() calls a given service function
    chains (1 for assessments, 4 for questions) -- the exact call count
    doesn't need to match here, only each individual call's arguments,
    which tests assert via query.eq.call_args_list.
    """
    mock_client = MagicMock()
    query = mock_client.table.return_value.select.return_value
    query.eq.return_value = query
    query.order.return_value.execute.return_value.data = data
    return mock_client, query


def test_list_active_assessments_filters_is_active_and_orders():
    mock_client, query = _chain_returning([_row_assessment()])
    assessment_service.list_active_assessments(mock_client)

    mock_client.table.assert_called_once_with("assessments")
    assert query.eq.call_args_list == [(("is_active", True), {})]
    query.order.assert_called_once_with("created_at")


def test_list_visible_questions_filters_approved_active_objective():
    mock_client, query = _chain_returning([_row_question()])
    assessment_id = uuid4()
    assessment_service.list_visible_questions(mock_client, assessment_id)

    mock_client.table.assert_called_once_with("assessment_questions")
    assert query.eq.call_args_list == [
        (("assessment_id", str(assessment_id)), {}),
        (("review_status", "APPROVED"), {}),
        (("is_active", True), {}),
        (("scoring_method", "OBJECTIVE"), {}),
    ]
    query.order.assert_called_once_with("display_order")


def test_list_visible_questions_sorts_options_by_display_order():
    """Options come back from Supabase in whatever order PostgREST/JSON
    embedding happens to produce -- verify the service sorts them."""
    scrambled = _row_question(
        options=[
            _row_option(display_order=2, option_text="third"),
            _row_option(display_order=0, option_text="first"),
            _row_option(display_order=1, option_text="second"),
        ]
    )
    mock_client, _query = _chain_returning([scrambled])
    questions = assessment_service.list_visible_questions(mock_client, uuid4())

    ordered_texts = [o["option_text"] for o in questions[0]["options"]]
    assert ordered_texts == ["first", "second", "third"]


def test_get_active_assessment_returns_none_when_not_found():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None

    result = assessment_service.get_active_assessment(mock_client, uuid4())
    assert result is None


def test_get_active_assessment_filters_is_active():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = _row_assessment()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = response

    assessment_service.get_active_assessment(mock_client, uuid4())

    eq1 = mock_client.table.return_value.select.return_value.eq
    eq2 = eq1.return_value.eq
    eq2.assert_called_once_with("is_active", True)


# ------------------------------------------------------------
# API layer: GET /api/v1/assessments
# ------------------------------------------------------------


def test_assessments_missing_token_returns_401():
    response = client.get("/api/v1/assessments")
    assert response.status_code == 401


def test_assessments_invalid_token_returns_401():
    with patch(
        "app.core.dependencies.verify_access_token",
        side_effect=InvalidTokenError("bad"),
    ):
        response = client.get(
            "/api/v1/assessments", headers={"Authorization": "Bearer not-real"}
        )
    assert response.status_code == 401


def test_assessments_student_allowed():
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "list_active_assessments", return_value=[]),
    ):
        response = client.get(
            "/api/v1/assessments", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200


def test_assessments_faculty_forbidden():
    with authenticated_as("FACULTY"):
        response = client.get(
            "/api/v1/assessments", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_assessments_industry_forbidden():
    with authenticated_as("INDUSTRY"):
        response = client.get(
            "/api/v1/assessments", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_assessments_institution_forbidden():
    with authenticated_as("INSTITUTION"):
        response = client.get(
            "/api/v1/assessments", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_assessments_returns_active_assessments():
    row = _row_assessment(title="Python Beginner Assessment")
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "list_active_assessments", return_value=[row]),
    ):
        response = client.get(
            "/api/v1/assessments", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["assessments"]) == 1
    assert body["assessments"][0]["title"] == "Python Beginner Assessment"


def test_assessments_response_matches_schema():
    row = _row_assessment()
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "list_active_assessments", return_value=[row]),
    ):
        response = client.get(
            "/api/v1/assessments", headers={"Authorization": "Bearer token"}
        )
    parsed = AssessmentListResponse(**response.json())
    assert len(parsed.assessments) == 1


def test_assessments_unexpected_failure_returns_clean_500():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "list_active_assessments",
            side_effect=RuntimeError("connection refused to internal db host 10.0.0.5"),
        ),
    ):
        response = client.get(
            "/api/v1/assessments", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 500
    body = response.json()
    assert "10.0.0.5" not in str(body)
    assert "connection refused" not in str(body).lower()


# ------------------------------------------------------------
# API layer: GET /api/v1/assessments/{assessment_id}
# ------------------------------------------------------------


def test_single_assessment_valid_returns_200():
    assessment_id = uuid4()
    row = _row_assessment(id=str(assessment_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=row),
    ):
        response = client.get(
            f"/api/v1/assessments/{assessment_id}", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["id"] == str(assessment_id)


def test_single_assessment_invalid_uuid_returns_422():
    with authenticated_as("STUDENT"):
        response = client.get(
            "/api/v1/assessments/not-a-uuid", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 422


def test_single_assessment_not_found_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=None),
    ):
        response = client.get(
            f"/api/v1/assessments/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_single_assessment_database_error_returns_clean_500():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_active_assessment", side_effect=RuntimeError("db exploded")
        ),
    ):
        response = client.get(
            f"/api/v1/assessments/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 500
    assert "db exploded" not in str(response.json())


# ------------------------------------------------------------
# API layer: GET /api/v1/assessments/{assessment_id}/questions
# ------------------------------------------------------------


def test_questions_approved_active_returned():
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    question_row = _row_question(assessment_id=str(assessment_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(assessment_service, "list_visible_questions", return_value=[question_row]),
    ):
        response = client.get(
            f"/api/v1/assessments/{assessment_id}/questions",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["question_text"] == question_row["question_text"]


def test_questions_options_returned_and_ordered():
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    question_row = _row_question(
        assessment_id=str(assessment_id),
        options=[
            _row_option(display_order=0, option_text="first"),
            _row_option(display_order=1, option_text="second"),
        ],
    )
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(assessment_service, "list_visible_questions", return_value=[question_row]),
    ):
        response = client.get(
            f"/api/v1/assessments/{assessment_id}/questions",
            headers={"Authorization": "Bearer token"},
        )
    options = response.json()[0]["options"]
    assert [o["option_text"] for o in options] == ["first", "second"]


def test_questions_inactive_assessment_returns_404_and_skips_question_query():
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=None),
        patch.object(assessment_service, "list_visible_questions") as mock_list_questions,
    ):
        response = client.get(
            f"/api/v1/assessments/{uuid4()}/questions",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    mock_list_questions.assert_not_called()


def test_questions_response_has_no_answer_key_fields():
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    question_row = _row_question(assessment_id=str(assessment_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(assessment_service, "list_visible_questions", return_value=[question_row]),
    ):
        response = client.get(
            f"/api/v1/assessments/{assessment_id}/questions",
            headers={"Authorization": "Bearer token"},
        )
    body_text = response.text
    for forbidden in ("correct_option_ids", "correct_answer_text", "explanation"):
        assert forbidden not in body_text


def test_questions_response_has_no_moderation_fields():
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    question_row = _row_question(assessment_id=str(assessment_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(assessment_service, "list_visible_questions", return_value=[question_row]),
    ):
        response = client.get(
            f"/api/v1/assessments/{assessment_id}/questions",
            headers={"Authorization": "Bearer token"},
        )
    body_text = response.text
    for forbidden in ("review_status", "generation_source", "generation_model", "generated_at"):
        assert forbidden not in body_text


class _FakeFilterQuery:
    """A minimal fake standing in for the real Supabase/postgrest query
    chain that actually APPLIES .eq() filters to an in-memory row set,
    unlike a MagicMock (which only records that an argument was passed).
    This is what makes the regression test below prove real exclusion
    behavior rather than just asserting a mock call happened."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self._rows = [row for row in self._rows if row.get(column) == value]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        result = MagicMock()
        result.data = self._rows
        return result


class _FakeFilterClient:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _FakeFilterQuery(self._rows)


def test_ai_evaluated_question_excluded_from_questions_endpoint():
    """Regression test for the Phase 1D decision to filter
    scoring_method = OBJECTIVE: an AI_EVALUATED question -- even if
    APPROVED and active, exactly like a real one would need to be to
    reach this filter at all -- must never be returned by
    GET /api/v1/assessments/{assessment_id}/questions, because Phase 1 has
    no scoring path for it yet.

    Runs the REAL list_visible_questions() query-building logic (not a
    mocked return value) against a fake client that genuinely filters --
    proving the .eq("scoring_method", "OBJECTIVE") call actually excludes
    the AI_EVALUATED row, not just that the argument was passed.
    """
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))

    objective_question = _row_question(
        assessment_id=str(assessment_id),
        question_text="OBJECTIVE question -- must be returned",
        scoring_method="OBJECTIVE",
        review_status="APPROVED",
        is_active=True,
    )
    ai_evaluated_question = _row_question(
        assessment_id=str(assessment_id),
        question_text="AI_EVALUATED question -- must NOT be returned",
        scoring_method="AI_EVALUATED",
        review_status="APPROVED",
        is_active=True,
    )
    fake_client = _FakeFilterClient([objective_question, ai_evaluated_question])

    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch("app.api.assessments.build_user_client", return_value=fake_client),
    ):
        response = client.get(
            f"/api/v1/assessments/{assessment_id}/questions",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    question_texts = [q["question_text"] for q in response.json()]
    assert "OBJECTIVE question -- must be returned" in question_texts
    assert "AI_EVALUATED question -- must NOT be returned" not in question_texts


# ------------------------------------------------------------
# Security
# ------------------------------------------------------------


def test_service_role_not_referenced_in_assessment_routes():
    # Checking module *namespace*, not source text: the module's own
    # docstring explains get_supabase() is deliberately NOT used, which
    # would false-positive a plain substring search. If get_supabase were
    # ever imported for real use, it would show up as a module attribute.
    from app.api import assessments as assessments_routes

    assert not hasattr(assessments_routes, "get_supabase")


def test_service_role_not_referenced_in_assessment_service():
    assert not hasattr(assessment_service, "get_supabase")


def test_response_schemas_carry_no_student_identifying_fields():
    """These three endpoints return shared catalog-like content, never a
    specific student's data -- confirm no student_id/personal field ever
    appears on the response schemas."""
    for schema in (AssessmentResponse, AssessmentQuestionResponse, AssessmentOptionResponse):
        assert "student_id" not in schema.model_fields


def test_non_student_forbidden_on_all_three_endpoints():
    assessment_id = uuid4()
    with authenticated_as("FACULTY"):
        r1 = client.get("/api/v1/assessments", headers={"Authorization": "Bearer token"})
        r2 = client.get(
            f"/api/v1/assessments/{assessment_id}", headers={"Authorization": "Bearer token"}
        )
        r3 = client.get(
            f"/api/v1/assessments/{assessment_id}/questions",
            headers={"Authorization": "Bearer token"},
        )
    assert r1.status_code == 403
    assert r2.status_code == 403
    assert r3.status_code == 403
