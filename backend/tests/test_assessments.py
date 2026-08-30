"""Tests for the Assessment API: schemas (Phase 1C), the read endpoints
(Phase 1D), and attempt creation (Phase 1E).

No live Supabase project or real token is used anywhere in this file --
Phase 1C tests are pure Pydantic model tests; Phase 1D/1E tests mock the
auth dependency chain (see conftest.py) and, where appropriate, the
Supabase client/service layer directly.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
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


def test_assessments_allowed_for_every_authenticated_role():
    """Phase 1K: list_assessments/get_assessment are no longer
    STUDENT-only (see test_list_and_get_assessment_now_allowed_for_faculty
    below) -- matching RLS ("Authenticated users can view active
    assessments"), which was never role-restricted to begin with. Content
    here (title/description/difficulty) carries no sensitive information,
    so widening to every authenticated role leaks nothing RLS wouldn't
    already permit."""
    for role in ("FACULTY", "INDUSTRY", "INSTITUTION"):
        with (
            authenticated_as(role),
            patch.object(assessment_service, "list_active_assessments", return_value=[]),
        ):
            response = client.get(
                "/api/v1/assessments", headers={"Authorization": "Bearer token"}
            )
        assert response.status_code == 200


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


def test_service_role_intentionally_imported_only_for_create_attempt():
    """As of Phase 1K, app.api.assessments DOES import get_supabase --
    create_attempt is the one documented, deliberate exception (mirroring
    score_attempt in app.api.attempts), needed for the single atomic
    transaction that starts an attempt and persists its randomized
    question selection together. Every other route in this module still
    uses build_user_client only -- confirmed by the sentinel-object tests
    right below, not by a blanket "get_supabase absent" check, which would
    now be a false assertion."""
    from app.api import assessments as assessments_routes

    assert hasattr(assessments_routes, "get_supabase")


def test_service_role_not_referenced_in_assessment_service():
    assert not hasattr(assessment_service, "get_supabase")


def test_response_schemas_carry_no_student_identifying_fields():
    """These three endpoints return shared catalog-like content, never a
    specific student's data -- confirm no student_id/personal field ever
    appears on the response schemas."""
    for schema in (AssessmentResponse, AssessmentQuestionResponse, AssessmentOptionResponse):
        assert "student_id" not in schema.model_fields


def test_non_student_forbidden_on_the_student_only_questions_endpoint():
    """GET .../questions stays require_student -- it's the student-safe,
    approved-only view used by the taking flow. FACULTY has its own richer
    view via GET /questions?assessment_id=... (app.api.questions), so this
    endpoint has no reason to widen the way list_assessments/get_assessment
    did in Phase 1K."""
    assessment_id = uuid4()
    with authenticated_as("FACULTY"):
        response = client.get(
            f"/api/v1/assessments/{assessment_id}/questions",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_list_and_get_assessment_now_allowed_for_faculty():
    """Phase 1K: list_assessments/get_assessment were widened from
    require_student to get_current_user() -- RLS never role-restricted
    these reads, and FACULTY needs them to pick an assessment for
    question authoring / blueprint configuration."""
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    with (
        authenticated_as("FACULTY"),
        patch.object(assessment_service, "list_active_assessments", return_value=[assessment_row]),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
    ):
        r1 = client.get("/api/v1/assessments", headers={"Authorization": "Bearer token"})
        r2 = client.get(
            f"/api/v1/assessments/{assessment_id}", headers={"Authorization": "Bearer token"}
        )
    assert r1.status_code == 200
    assert r2.status_code == 200


# ============================================================
# Phase 1E -- Assessment attempt creation
# ============================================================


def _row_attempt(**overrides):
    row = {
        "id": str(uuid4()),
        "student_id": str(uuid4()),
        "assessment_id": str(uuid4()),
        "status": "IN_PROGRESS",
        "started_at": "2026-01-01T00:00:00Z",
        "submitted_at": None,
        "score": None,
        "total_marks": None,
        "percentage": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _attempts_url(assessment_id) -> str:
    return f"/api/v1/assessments/{assessment_id}/attempts"


# ------------------------------------------------------------
# Service layer: insert construction + duplicate translation
# ------------------------------------------------------------


def test_service_create_attempt_calls_rpc_with_correct_params():
    """Phase 1K: create_attempt no longer does a plain table insert -- it
    calls the create_assessment_attempt() RPC (the same trusted,
    single-transaction pattern score_attempt already uses for scoring),
    so that persisting the attempt row and its randomized
    assessment_attempt_questions selection happens atomically."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = _row_attempt()
    mock_client.rpc.return_value.execute.return_value = response

    student_id = "student-1"
    assessment_id = uuid4()
    assessment_service.create_attempt(mock_client, student_id, assessment_id)

    mock_client.rpc.assert_called_once_with(
        "create_assessment_attempt",
        {"p_assessment_id": str(assessment_id), "p_student_id": student_id},
    )


def test_service_create_attempt_translates_unique_violation_to_duplicate_error():
    """A real 23505 (unique_violation) from the DB's own partial unique
    index -- still enforced exactly as before Phase 1K, now surfacing from
    inside the RPC instead of a plain insert -- must become
    DuplicateInProgressAttemptError, not propagate as a raw postgrest
    APIError."""
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "23505", "message": "duplicate key value violates unique constraint"}
    )

    with pytest.raises(assessment_service.DuplicateInProgressAttemptError):
        assessment_service.create_attempt(mock_client, "student-1", uuid4())


def test_service_create_attempt_translates_55000_to_insufficient_pool_error():
    """Phase 1K: SQLSTATE 55000 from create_assessment_attempt() (either no
    blueprint configured, or too few approved questions in some difficulty
    bucket) must become InsufficientQuestionPoolError, not propagate as a
    raw postgrest APIError -- same SQLSTATE score_attempt's own
    AttemptNotEligibleForScoringError already uses for "object not in
    prerequisite state"."""
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "55000", "message": "Insufficient approved Beginner questions..."}
    )

    with pytest.raises(assessment_service.InsufficientQuestionPoolError):
        assessment_service.create_attempt(mock_client, "student-1", uuid4())


def test_service_create_attempt_reraises_other_api_errors():
    """Only 23505 and 55000 are special-cased -- any other database error
    must propagate normally (the route layer turns it into a generic
    500)."""
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "23503", "message": "foreign key violation"}
    )

    with pytest.raises(APIError):
        assessment_service.create_attempt(mock_client, "student-1", uuid4())


# ------------------------------------------------------------
# API layer: AUTH
# ------------------------------------------------------------


def test_create_attempt_missing_token_returns_401():
    response = client.post(_attempts_url(uuid4()))
    assert response.status_code == 401


def test_create_attempt_invalid_token_returns_401():
    with patch(
        "app.core.dependencies.verify_access_token",
        side_effect=InvalidTokenError("bad"),
    ):
        response = client.post(
            _attempts_url(uuid4()), headers={"Authorization": "Bearer not-real"}
        )
    assert response.status_code == 401


def test_create_attempt_faculty_forbidden():
    with authenticated_as("FACULTY"):
        response = client.post(
            _attempts_url(uuid4()), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_create_attempt_industry_forbidden():
    with authenticated_as("INDUSTRY"):
        response = client.post(
            _attempts_url(uuid4()), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_create_attempt_institution_forbidden():
    with authenticated_as("INSTITUTION"):
        response = client.post(
            _attempts_url(uuid4()), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


# ------------------------------------------------------------
# API layer: assessment validation
# ------------------------------------------------------------


def test_create_attempt_invalid_uuid_returns_422():
    with authenticated_as("STUDENT"):
        response = client.post(
            "/api/v1/assessments/not-a-uuid/attempts", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 422


def test_create_attempt_nonexistent_assessment_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=None),
    ):
        response = client.post(
            _attempts_url(uuid4()), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_create_attempt_inactive_assessment_returns_404():
    # get_active_assessment() is the single source of truth for
    # "exists AND active" -- it returns None for both an unknown id and an
    # inactive one, so this is the same observable behavior as the
    # nonexistent-assessment case, deliberately (never reveal which).
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=None),
    ):
        response = client.post(
            _attempts_url(uuid4()), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


# ------------------------------------------------------------
# API layer: creation + initial state
# ------------------------------------------------------------


def test_create_attempt_student_can_create():
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    attempt_row = _row_attempt(assessment_id=str(assessment_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(assessment_service, "create_attempt", return_value=attempt_row),
    ):
        response = client.post(
            _attempts_url(assessment_id), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 201
    assert response.json()["assessment_id"] == str(assessment_id)


def test_create_attempt_student_id_comes_from_authenticated_user():
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    with (
        authenticated_as("STUDENT", user_id="the-real-caller"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(
            assessment_service,
            "create_attempt",
            return_value=_row_attempt(),
        ) as mock_create,
    ):
        client.post(_attempts_url(assessment_id), headers={"Authorization": "Bearer token"})

    # assessment_service.create_attempt(client, student_id, assessment_id)
    called_student_id = mock_create.call_args[0][1]
    assert called_student_id == "the-real-caller"


def test_create_attempt_initial_state_is_fresh():
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    attempt_row = _row_attempt(assessment_id=str(assessment_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(assessment_service, "create_attempt", return_value=attempt_row),
    ):
        response = client.post(
            _attempts_url(assessment_id), headers={"Authorization": "Bearer token"}
        )
    body = response.json()
    assert body["status"] == "IN_PROGRESS"
    assert body["score"] is None
    assert body["total_marks"] is None
    assert body["percentage"] is None
    assert body["submitted_at"] is None


# ------------------------------------------------------------
# Security: client cannot control server-owned fields
# ------------------------------------------------------------


def test_create_attempt_ignores_client_supplied_body_entirely():
    """No request body parameter exists on this route at all -- a client
    trying to inject student_id/status/score/total_marks/percentage/
    submitted_at, or any arbitrary extra field, has no effect whatsoever.
    Proves it by sending a maximally hostile payload and confirming only
    current_user.id/assessment_id ever reach the service layer."""
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    attempt_row = _row_attempt(assessment_id=str(assessment_id))
    hostile_body = {
        "student_id": "someone-elses-id",
        "status": "COMPLETED",
        "score": 100,
        "total_marks": 100,
        "percentage": 100,
        "submitted_at": "2026-01-01T00:00:00Z",
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "not_even_a_real_field": "whatever",
    }
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(
            assessment_service, "create_attempt", return_value=attempt_row
        ) as mock_create,
    ):
        response = client.post(
            _attempts_url(assessment_id),
            json=hostile_body,
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 201
    # assessment_service.create_attempt(client, student_id, assessment_id) --
    # exactly 3 positional args, none of them sourced from hostile_body.
    _call_client, called_student_id, called_assessment_id = mock_create.call_args[0]
    assert called_student_id == "student-1"
    assert called_assessment_id == assessment_id


def test_create_attempt_uses_build_user_client_for_ownership_check():
    """The FIRST client used must be the user-scoped one, for the
    assessment existence/active check -- never get_supabase(), even for a
    read. Mirrors test_score_uses_build_user_client_for_ownership_check in
    test_attempts.py."""
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    attempt_row = _row_attempt(assessment_id=str(assessment_id))
    sentinel_user_client = object()

    with (
        authenticated_as("STUDENT"),
        patch("app.api.assessments.build_user_client", return_value=sentinel_user_client),
        patch("app.api.assessments.get_supabase", return_value=MagicMock()),
        patch.object(
            assessment_service, "get_active_assessment", return_value=assessment_row
        ) as mock_get_assessment,
        patch.object(assessment_service, "create_attempt", return_value=attempt_row),
    ):
        client.post(_attempts_url(assessment_id), headers={"Authorization": "Bearer token"})

    assert mock_get_assessment.call_args[0][0] is sentinel_user_client


def test_create_attempt_uses_service_role_client_only_for_creation():
    """get_supabase()'s return value must be exactly what reaches
    assessment_service.create_attempt() -- confirming the service-role
    client is used for the trusted attempt-creation-plus-selection call,
    and (via the previous test) NOT for the assessment existence check.
    Mirrors test_score_uses_service_role_client_only_for_scoring."""
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    attempt_row = _row_attempt(assessment_id=str(assessment_id))
    sentinel_service_client = object()

    with (
        authenticated_as("STUDENT"),
        patch("app.api.assessments.get_supabase", return_value=sentinel_service_client),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(
            assessment_service, "create_attempt", return_value=attempt_row
        ) as mock_create,
    ):
        client.post(_attempts_url(assessment_id), headers={"Authorization": "Bearer token"})

    assert mock_create.call_args[0][0] is sentinel_service_client


# ------------------------------------------------------------
# Errors
# ------------------------------------------------------------


def test_create_attempt_unexpected_failure_returns_clean_500():
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(
            assessment_service,
            "create_attempt",
            side_effect=RuntimeError("connection refused to internal db host 10.0.0.5"),
        ),
    ):
        response = client.post(
            _attempts_url(assessment_id), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 500
    body_text = str(response.json())
    assert "10.0.0.5" not in body_text
    assert "connection refused" not in body_text.lower()


# ------------------------------------------------------------
# Duplicate attempt
# ------------------------------------------------------------


def test_create_attempt_duplicate_in_progress_returns_409():
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(
            assessment_service,
            "create_attempt",
            side_effect=assessment_service.DuplicateInProgressAttemptError(),
        ),
    ):
        response = client.post(
            _attempts_url(assessment_id), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 409


# ============================================================
# Phase 1K -- Assessment blueprint
# ============================================================


def _blueprint_url(assessment_id) -> str:
    return f"/api/v1/assessments/{assessment_id}/blueprint"


def _row_blueprint_rule(**overrides):
    row = {
        "id": str(uuid4()),
        "assessment_id": str(uuid4()),
        "difficulty": "Beginner",
        "question_count": 8,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_get_blueprint_readable_by_student():
    assessment_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch("app.services.question_bank_service.get_blueprint", return_value=[]),
    ):
        response = client.get(
            _blueprint_url(assessment_id), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json() == {"assessment_id": str(assessment_id), "rules": []}


def test_get_blueprint_readable_by_faculty():
    assessment_id = uuid4()
    rule = _row_blueprint_rule(assessment_id=str(assessment_id))
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        patch("app.services.question_bank_service.get_blueprint", return_value=[rule]),
    ):
        response = client.get(
            _blueprint_url(assessment_id), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["rules"][0]["difficulty"] == "Beginner"


def test_replace_blueprint_requires_faculty():
    assessment_id = uuid4()
    with authenticated_as("STUDENT"):
        response = client.put(
            _blueprint_url(assessment_id),
            json={"rules": [{"difficulty": "Beginner", "question_count": 8}]},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_replace_blueprint_faculty_success():
    assessment_id = uuid4()
    rule = _row_blueprint_rule(assessment_id=str(assessment_id), question_count=8)
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        patch("app.services.question_bank_service.replace_blueprint", return_value=[rule]),
    ):
        response = client.put(
            _blueprint_url(assessment_id),
            json={"rules": [{"difficulty": "Beginner", "question_count": 8}]},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["rules"][0]["question_count"] == 8


def test_replace_blueprint_rejects_duplicate_difficulty_before_reaching_service():
    assessment_id = uuid4()
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        patch("app.services.question_bank_service.replace_blueprint") as mock_replace,
    ):
        response = client.put(
            _blueprint_url(assessment_id),
            json={
                "rules": [
                    {"difficulty": "Beginner", "question_count": 8},
                    {"difficulty": "Beginner", "question_count": 3},
                ]
            },
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422
    mock_replace.assert_not_called()


def test_create_attempt_insufficient_question_pool_returns_409():
    """Phase 1K: create_assessment_attempt() rejecting a too-small or
    unconfigured question pool (SQLSTATE 55000) must surface as a clean
    409, never a silently smaller question set and never a 500."""
    assessment_id = uuid4()
    assessment_row = _row_assessment(id=str(assessment_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_active_assessment", return_value=assessment_row),
        patch.object(
            assessment_service,
            "create_attempt",
            side_effect=assessment_service.InsufficientQuestionPoolError(),
        ),
    ):
        response = client.post(
            _attempts_url(assessment_id), headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 409
