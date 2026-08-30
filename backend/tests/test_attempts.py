"""Tests for the attempt-scoped API: answer saving (Phase 1F).

No live Supabase project or real token is used anywhere in this file --
service-layer tests mock the Supabase client itself and assert the query
WE construct; API-layer tests use FastAPI's TestClient against the real
app, mocking only the auth dependency chain (conftest.authenticated_as)
and, where relevant, the assessment_service functions.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import InvalidTokenError
from app.main import app
from app.schemas.assessment import AssessmentAnswerRequest
from app.services import assessment_service
from tests.conftest import authenticated_as

client = TestClient(app)


def _row_attempt(**overrides):
    row = {
        "id": str(uuid4()),
        "student_id": "student-1",
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


def _row_answer(**overrides):
    row = {
        "id": str(uuid4()),
        "attempt_id": str(uuid4()),
        "question_id": str(uuid4()),
        "answer_text": None,
        "selected_option_ids": [str(uuid4())],
        "awarded_marks": None,
        "is_correct": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _answers_url(attempt_id) -> str:
    return f"/api/v1/attempts/{attempt_id}/answers"


def _valid_body(question_id) -> dict:
    return {"question_id": str(question_id), "selected_option_ids": [str(uuid4())]}


# ============================================================
# Service layer: query construction
# ============================================================


def test_service_get_own_attempt_filters_id_and_student_id():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = _row_attempt()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = response

    attempt_id = uuid4()
    assessment_service.get_own_attempt(mock_client, "student-1", attempt_id)

    mock_client.table.assert_called_once_with("assessment_attempts")
    eq1 = mock_client.table.return_value.select.return_value.eq
    eq1.assert_called_once_with("id", str(attempt_id))
    eq1.return_value.eq.assert_called_once_with("student_id", "student-1")


def test_service_get_visible_question_filters_all_eligibility_conditions():
    mock_client = MagicMock()
    query = mock_client.table.return_value.select.return_value
    query.eq.return_value = query
    response = MagicMock()
    response.data = {"id": "q1"}
    query.maybe_single.return_value.execute.return_value = response

    question_id = uuid4()
    assessment_id = uuid4()
    assessment_service.get_visible_question(mock_client, assessment_id, question_id)

    mock_client.table.assert_called_once_with("assessment_questions")
    assert query.eq.call_args_list == [
        (("id", str(question_id)), {}),
        (("assessment_id", str(assessment_id)), {}),
        (("review_status", "APPROVED"), {}),
        (("is_active", True), {}),
        (("scoring_method", "OBJECTIVE"), {}),
    ]


def test_service_save_answer_inserts_when_no_existing_answer():
    mock_client = MagicMock()
    # get_existing_answer -> None (maybe_single().execute() returns None on 0 rows)
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None
    insert_response = MagicMock()
    insert_response.data = [_row_answer()]
    mock_client.table.return_value.insert.return_value.execute.return_value = insert_response

    attempt_id = uuid4()
    question_id = uuid4()
    option_id = uuid4()
    assessment_service.save_answer(mock_client, attempt_id, question_id, None, [option_id])

    mock_client.table.return_value.insert.assert_called_once_with(
        {
            "answer_text": None,
            "selected_option_ids": [str(option_id)],
            "attempt_id": str(attempt_id),
            "question_id": str(question_id),
        }
    )
    mock_client.table.return_value.update.assert_not_called()


def test_service_save_answer_updates_when_answer_already_exists():
    mock_client = MagicMock()
    existing = _row_answer()
    existing_response = MagicMock()
    existing_response.data = existing
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = existing_response
    update_response = MagicMock()
    update_response.data = [existing]
    mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = (
        update_response
    )

    attempt_id = uuid4()
    question_id = uuid4()
    assessment_service.save_answer(mock_client, attempt_id, question_id, "my answer", None)

    mock_client.table.return_value.update.assert_called_once_with(
        {"answer_text": "my answer", "selected_option_ids": None}
    )
    mock_client.table.return_value.update.return_value.eq.assert_called_once_with(
        "id", existing["id"]
    )
    mock_client.table.return_value.insert.assert_not_called()


def test_service_save_answer_never_includes_scoring_fields_in_payload():
    """Structural guarantee: no code path in save_answer can ever place
    awarded_marks/is_correct into a payload sent to Supabase -- those
    keys simply never appear in the dict literals this function builds."""
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None
    insert_response = MagicMock()
    insert_response.data = [_row_answer()]
    mock_client.table.return_value.insert.return_value.execute.return_value = insert_response

    assessment_service.save_answer(mock_client, uuid4(), uuid4(), "text", None)

    sent_payload = mock_client.table.return_value.insert.call_args[0][0]
    assert "awarded_marks" not in sent_payload
    assert "is_correct" not in sent_payload


# ============================================================
# API layer: AUTH
# ============================================================


def test_save_answer_missing_token_returns_401():
    response = client.post(_answers_url(uuid4()), json=_valid_body(uuid4()))
    assert response.status_code == 401


def test_save_answer_invalid_token_returns_401():
    with patch(
        "app.core.dependencies.verify_access_token",
        side_effect=InvalidTokenError("bad"),
    ):
        response = client.post(
            _answers_url(uuid4()),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer not-real"},
        )
    assert response.status_code == 401


def test_save_answer_faculty_forbidden():
    with authenticated_as("FACULTY"):
        response = client.post(
            _answers_url(uuid4()),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_save_answer_industry_forbidden():
    with authenticated_as("INDUSTRY"):
        response = client.post(
            _answers_url(uuid4()),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_save_answer_institution_forbidden():
    with authenticated_as("INSTITUTION"):
        response = client.post(
            _answers_url(uuid4()),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


# ============================================================
# API layer: attempt validation
# ============================================================


def test_save_answer_nonexistent_attempt_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=None),
    ):
        response = client.post(
            _answers_url(uuid4()),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_save_answer_another_students_attempt_returns_404():
    # get_own_attempt is scoped by student_id -- another student's attempt
    # is indistinguishable from a nonexistent one at this layer, by design
    # (never reveal which).
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=None) as mock_get,
    ):
        response = client.post(
            _answers_url(uuid4()),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    mock_get.assert_called_once()


def test_save_answer_completed_attempt_returns_409():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(status="COMPLETED")
        ),
    ):
        response = client.post(
            _answers_url(uuid4()),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_save_answer_in_progress_own_attempt_allowed():
    attempt_id = uuid4()
    question_id = uuid4()
    attempt_row = _row_attempt(id=str(attempt_id))
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=attempt_row),
        patch.object(assessment_service, "get_visible_question", return_value={"id": str(question_id)}),
        patch.object(
            assessment_service,
            "save_answer",
            return_value=_row_answer(attempt_id=str(attempt_id), question_id=str(question_id)),
        ),
    ):
        response = client.post(
            _answers_url(attempt_id),
            json=_valid_body(question_id),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200


# ============================================================
# API layer: question validation
# ============================================================


def test_save_answer_nonexistent_question_returns_404():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "get_visible_question", return_value=None),
    ):
        response = client.post(
            _answers_url(attempt_id),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_save_answer_question_from_another_assessment_returns_404():
    # get_visible_question filters by the attempt's OWN assessment_id -- a
    # question belonging to a different assessment is indistinguishable
    # from a nonexistent one, by design.
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "get_visible_question", return_value=None) as mock_get_q,
    ):
        response = client.post(
            _answers_url(attempt_id),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    mock_get_q.assert_called_once()


def test_save_answer_ai_evaluated_question_returns_404():
    """get_visible_question filters scoring_method = OBJECTIVE, so an
    AI_EVALUATED question -- Phase 1 has no scoring path for it -- is
    unreachable through this endpoint, same as a nonexistent question."""
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "get_visible_question", return_value=None),
    ):
        response = client.post(
            _answers_url(attempt_id),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


# ============================================================
# API layer: answer validation
# ============================================================


def test_save_answer_missing_content_returns_422():
    """Neither answer_text nor selected_option_ids provided -- rejected by
    AssessmentAnswerRequest's own validator before the handler runs."""
    with authenticated_as("STUDENT"):
        response = client.post(
            _answers_url(uuid4()),
            json={"question_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_save_answer_rejects_scoring_and_answer_key_fields_in_body():
    """A maximally hostile body -- scoring fields AND answer-key fields
    AND ownership fields AND a nonsense extra field -- is rejected
    entirely by AssessmentAnswerRequest's extra="forbid", before any
    handler code runs."""
    hostile_body = {
        "question_id": str(uuid4()),
        "selected_option_ids": [str(uuid4())],
        "awarded_marks": 5,
        "is_correct": True,
        "correct_option_ids": [str(uuid4())],
        "correct_answer_text": "the real answer",
        "explanation": "why it's correct",
        "attempt_id": str(uuid4()),
        "student_id": "someone-elses-id",
        "not_even_a_real_field": "whatever",
    }
    with authenticated_as("STUDENT"):
        response = client.post(
            _answers_url(uuid4()),
            json=hostile_body,
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


# ============================================================
# Create vs. update (API-level; service-level covered above)
# ============================================================


def test_save_answer_updated_answer_preserves_attempt_and_question():
    attempt_id = uuid4()
    question_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "get_visible_question", return_value={"id": str(question_id)}),
        patch.object(
            assessment_service,
            "save_answer",
            return_value=_row_answer(attempt_id=str(attempt_id), question_id=str(question_id)),
        ),
    ):
        response = client.post(
            _answers_url(attempt_id),
            json=_valid_body(question_id),
            headers={"Authorization": "Bearer token"},
        )
    body = response.json()
    assert body["attempt_id"] == str(attempt_id)
    assert body["question_id"] == str(question_id)


def test_save_answer_another_students_attempt_never_reaches_save():
    """Confirms the short-circuit: when get_own_attempt returns None
    (another student's attempt, or nonexistent), save_answer is never
    called at all."""
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=None),
        patch.object(assessment_service, "save_answer") as mock_save,
    ):
        client.post(
            _answers_url(uuid4()),
            json=_valid_body(uuid4()),
            headers={"Authorization": "Bearer token"},
        )
    mock_save.assert_not_called()


# ============================================================
# Security
# ============================================================


def test_answer_request_schema_has_no_ownership_fields():
    assert "student_id" not in AssessmentAnswerRequest.model_fields
    assert "attempt_id" not in AssessmentAnswerRequest.model_fields


def test_save_answer_response_has_no_answer_key_fields():
    attempt_id = uuid4()
    question_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "get_visible_question", return_value={"id": str(question_id)}),
        patch.object(
            assessment_service,
            "save_answer",
            return_value=_row_answer(attempt_id=str(attempt_id), question_id=str(question_id)),
        ),
    ):
        response = client.post(
            _answers_url(attempt_id),
            json=_valid_body(question_id),
            headers={"Authorization": "Bearer token"},
        )
    body_text = response.text
    for forbidden in ("correct_option_ids", "correct_answer_text", "explanation"):
        assert forbidden not in body_text


def test_service_role_not_referenced_in_attempts_routes():
    from app.api import attempts as attempts_routes

    assert not hasattr(attempts_routes, "get_supabase")


def test_save_answer_uses_user_scoped_client_not_service_role():
    attempt_id = uuid4()
    question_id = uuid4()
    sentinel_client = object()
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.build_user_client", return_value=sentinel_client),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ) as mock_get_attempt,
        patch.object(
            assessment_service, "get_visible_question", return_value={"id": str(question_id)}
        ) as mock_get_question,
        patch.object(
            assessment_service,
            "save_answer",
            return_value=_row_answer(attempt_id=str(attempt_id), question_id=str(question_id)),
        ) as mock_save,
    ):
        client.post(
            _answers_url(attempt_id),
            json=_valid_body(question_id),
            headers={"Authorization": "Bearer token"},
        )

    assert mock_get_attempt.call_args[0][0] is sentinel_client
    assert mock_get_question.call_args[0][0] is sentinel_client
    assert mock_save.call_args[0][0] is sentinel_client


# ============================================================
# Errors
# ============================================================


def test_save_answer_unexpected_failure_returns_clean_500():
    attempt_id = uuid4()
    question_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "get_visible_question", return_value={"id": str(question_id)}),
        patch.object(
            assessment_service,
            "save_answer",
            side_effect=RuntimeError("connection refused to internal db host 10.0.0.5"),
        ),
    ):
        response = client.post(
            _answers_url(attempt_id),
            json=_valid_body(question_id),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 500
    body_text = str(response.json())
    assert "10.0.0.5" not in body_text
    assert "connection refused" not in body_text.lower()
