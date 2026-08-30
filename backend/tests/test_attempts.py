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


# ============================================================
# Phase 1G -- Assessment submission
# ============================================================
#
# Reminder of the schema-derived design (see the Phase 1G report):
# submission sets ONLY submitted_at, leaving status IN_PROGRESS and every
# score field untouched -- the DB's own assessment_attempts_completed_has_score
# constraint and prevent_self_attempt_scoring trigger make any other
# behavior structurally impossible for a non-service_role caller. Phase 1H
# owns the eventual COMPLETED transition.


def _submit_url(attempt_id) -> str:
    return f"/api/v1/attempts/{attempt_id}/submit"


def _eligible_question(**overrides):
    row = {"id": str(uuid4())}
    row.update(overrides)
    return row


# ------------------------------------------------------------
# Service layer: query construction
# ------------------------------------------------------------


def test_service_get_answered_question_ids_filters_by_attempt_id():
    """Answers from a DIFFERENT attempt (e.g. a previous retake by the
    same student) must never count -- the query itself is scoped to one
    attempt_id, not the student in general."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [{"question_id": "q1"}, {"question_id": "q2"}]
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        response
    )

    attempt_id = uuid4()
    result = assessment_service.get_answered_question_ids(mock_client, attempt_id)

    mock_client.table.assert_called_once_with("assessment_answers")
    mock_client.table.return_value.select.return_value.eq.assert_called_once_with(
        "attempt_id", str(attempt_id)
    )
    assert result == {"q1", "q2"}


def test_service_mark_attempt_submitted_only_sets_submitted_at():
    """The UPDATE payload contains exactly one key -- submitted_at.
    Structurally proves status/score/total_marks/percentage/awarded_marks/
    is_correct can never be part of this write, satisfying the scoring
    boundary at the query-construction level, not just by convention."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [_row_attempt()]
    mock_client.table.return_value.update.return_value.eq.return_value.is_.return_value.execute.return_value = response

    attempt_id = uuid4()
    assessment_service.mark_attempt_submitted(mock_client, attempt_id)

    mock_client.table.assert_called_once_with("assessment_attempts")
    sent_payload = mock_client.table.return_value.update.call_args[0][0]
    assert set(sent_payload.keys()) == {"submitted_at"}
    for forbidden in (
        "status",
        "score",
        "total_marks",
        "percentage",
        "awarded_marks",
        "is_correct",
        "student_id",
    ):
        assert forbidden not in sent_payload


def test_service_mark_attempt_submitted_guards_with_is_null():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [_row_attempt()]
    mock_client.table.return_value.update.return_value.eq.return_value.is_.return_value.execute.return_value = response

    attempt_id = uuid4()
    assessment_service.mark_attempt_submitted(mock_client, attempt_id)

    mock_client.table.return_value.update.return_value.eq.assert_called_once_with(
        "id", str(attempt_id)
    )
    mock_client.table.return_value.update.return_value.eq.return_value.is_.assert_called_once_with(
        "submitted_at", None
    )


def test_service_mark_attempt_submitted_returns_none_when_race_loses():
    """Zero rows matched (submitted_at was no longer null by the time the
    guarded UPDATE ran) -- the DB-level guard caught a race the
    application-level pre-check missed."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = []
    mock_client.table.return_value.update.return_value.eq.return_value.is_.return_value.execute.return_value = response

    result = assessment_service.mark_attempt_submitted(mock_client, uuid4())
    assert result is None


# ------------------------------------------------------------
# API layer: AUTH
# ------------------------------------------------------------


def test_submit_missing_token_returns_401():
    response = client.post(_submit_url(uuid4()))
    assert response.status_code == 401


def test_submit_invalid_token_returns_401():
    with patch(
        "app.core.dependencies.verify_access_token",
        side_effect=InvalidTokenError("bad"),
    ):
        response = client.post(_submit_url(uuid4()), headers={"Authorization": "Bearer not-real"})
    assert response.status_code == 401


def test_submit_faculty_forbidden():
    with authenticated_as("FACULTY"):
        response = client.post(_submit_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_submit_industry_forbidden():
    with authenticated_as("INDUSTRY"):
        response = client.post(_submit_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_submit_institution_forbidden():
    with authenticated_as("INSTITUTION"):
        response = client.post(_submit_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


# ------------------------------------------------------------
# API layer: ownership
# ------------------------------------------------------------


def test_submit_nonexistent_attempt_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=None),
    ):
        response = client.post(_submit_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 404


def test_submit_another_students_attempt_returns_404():
    # get_own_attempt is scoped by student_id -- another student's attempt
    # is indistinguishable from a nonexistent one, by design.
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=None) as mock_get,
    ):
        response = client.post(_submit_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 404
    mock_get.assert_called_once()


# ------------------------------------------------------------
# API layer: state
# ------------------------------------------------------------


def test_submit_already_submitted_returns_409():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:00:00Z"),
        ),
        patch.object(assessment_service, "mark_attempt_submitted") as mock_mark,
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 409
    mock_mark.assert_not_called()


def test_submit_abandoned_attempt_returns_409():
    """ABANDONED is a real status value in the schema -- not submittable,
    same as any non-IN_PROGRESS state."""
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="ABANDONED"),
        ),
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 409


# ------------------------------------------------------------
# API layer: completeness
# ------------------------------------------------------------


def test_submit_all_eligible_answered_succeeds():
    attempt_id = uuid4()
    q1, q2 = _eligible_question(), _eligible_question()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1, q2]),
        patch.object(
            assessment_service,
            "get_answered_question_ids",
            return_value={q1["id"], q2["id"]},
        ),
        patch.object(
            assessment_service,
            "mark_attempt_submitted",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:00:00Z"),
        ),
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


def test_submit_one_unanswered_eligible_question_returns_400():
    attempt_id = uuid4()
    q1, q2 = _eligible_question(), _eligible_question()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1, q2]),
        patch.object(
            assessment_service, "get_answered_question_ids", return_value={q1["id"]}
        ),
        patch.object(assessment_service, "mark_attempt_submitted") as mock_mark,
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 400
    mock_mark.assert_not_called()


def test_submit_multiple_unanswered_eligible_questions_returns_400():
    attempt_id = uuid4()
    q1, q2, q3 = _eligible_question(), _eligible_question(), _eligible_question()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1, q2, q3]),
        patch.object(assessment_service, "get_answered_question_ids", return_value=set()),
        patch.object(assessment_service, "mark_attempt_submitted") as mock_mark,
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 400
    mock_mark.assert_not_called()


def test_submit_answers_from_another_assessment_do_not_satisfy_completeness():
    """A stray answered question_id that isn't in this assessment's
    eligible set must not help satisfy completeness for a DIFFERENT
    eligible question that's still unanswered."""
    attempt_id = uuid4()
    q1 = _eligible_question()
    foreign_question_id = str(uuid4())
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1]),
        patch.object(
            assessment_service,
            "get_answered_question_ids",
            return_value={foreign_question_id},
        ),
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 400


def test_submit_ineligible_extra_answers_do_not_block_submission():
    """An answered question_id that ISN'T currently eligible (e.g. for a
    deactivated question) must not incorrectly block submission when every
    actually-eligible question IS answered."""
    attempt_id = uuid4()
    q1 = _eligible_question()
    ineligible_question_id = str(uuid4())
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1]),
        patch.object(
            assessment_service,
            "get_answered_question_ids",
            return_value={q1["id"], ineligible_question_id},
        ),
        patch.object(
            assessment_service,
            "mark_attempt_submitted",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:00:00Z"),
        ),
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


def test_submit_zero_eligible_questions_succeeds_vacuously():
    """No currently-eligible questions -- nothing to require an answer
    for, so completeness is trivially satisfied. Matches how Phase 1D
    already treats a zero-question assessment as a normal state, not an
    error."""
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[]),
        patch.object(assessment_service, "get_answered_question_ids", return_value=set()),
        patch.object(
            assessment_service,
            "mark_attempt_submitted",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:00:00Z"),
        ),
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


# ------------------------------------------------------------
# API layer: successful submission -- resulting attempt shape
# ------------------------------------------------------------


def test_submit_success_response_has_correct_fields():
    attempt_id = uuid4()
    q1 = _eligible_question()
    submitted_row = _row_attempt(
        id=str(attempt_id),
        status="IN_PROGRESS",
        submitted_at="2026-01-01T12:00:00Z",
        score=None,
        total_marks=None,
        percentage=None,
    )
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1]),
        patch.object(
            assessment_service, "get_answered_question_ids", return_value={q1["id"]}
        ),
        patch.object(assessment_service, "mark_attempt_submitted", return_value=submitted_row),
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    body = response.json()
    assert body["submitted_at"] is not None
    assert body["status"] == "IN_PROGRESS"
    assert body["score"] is None
    assert body["total_marks"] is None
    assert body["percentage"] is None


# ------------------------------------------------------------
# Security
# ------------------------------------------------------------


def test_submit_ignores_client_supplied_body_entirely():
    """No request body parameter exists on this route at all -- a client
    sending student_id/submitted_at/status/score/total_marks/percentage/
    awarded_marks/is_correct/answer-key fields has zero effect. Same
    proof pattern as Phase 1E's create_attempt hostile-body test."""
    attempt_id = uuid4()
    q1 = _eligible_question()
    hostile_body = {
        "student_id": "someone-elses-id",
        "submitted_at": "2020-01-01T00:00:00Z",
        "status": "COMPLETED",
        "score": 100,
        "total_marks": 100,
        "percentage": 100,
        "awarded_marks": 100,
        "is_correct": True,
        "correct_option_ids": [str(uuid4())],
        "correct_answer_text": "the real answer",
        "explanation": "why",
        "not_even_a_real_field": "whatever",
    }
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1]),
        patch.object(
            assessment_service, "get_answered_question_ids", return_value={q1["id"]}
        ),
        patch.object(
            assessment_service,
            "mark_attempt_submitted",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:00:00Z"),
        ) as mock_mark,
    ):
        response = client.post(
            _submit_url(attempt_id),
            json=hostile_body,
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    # mark_attempt_submitted(client, attempt_id) -- exactly 2 positional
    # args, neither sourced from hostile_body.
    mock_mark.assert_called_once_with(mock_mark.call_args[0][0], attempt_id)


def test_submit_response_has_no_answer_key_fields():
    attempt_id = uuid4()
    q1 = _eligible_question()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1]),
        patch.object(
            assessment_service, "get_answered_question_ids", return_value={q1["id"]}
        ),
        patch.object(
            assessment_service,
            "mark_attempt_submitted",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:00:00Z"),
        ),
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    body_text = response.text
    for forbidden in ("correct_option_ids", "correct_answer_text", "explanation"):
        assert forbidden not in body_text


def test_submit_service_role_not_referenced_in_attempts_routes():
    from app.api import attempts as attempts_routes

    assert not hasattr(attempts_routes, "get_supabase")


def test_submit_uses_user_scoped_client_not_service_role():
    attempt_id = uuid4()
    q1 = _eligible_question()
    sentinel_client = object()
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.build_user_client", return_value=sentinel_client),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ) as mock_get_attempt,
        patch.object(
            assessment_service, "list_visible_questions", return_value=[q1]
        ) as mock_list_questions,
        patch.object(
            assessment_service, "get_answered_question_ids", return_value={q1["id"]}
        ) as mock_answered,
        patch.object(
            assessment_service,
            "mark_attempt_submitted",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:00:00Z"),
        ) as mock_mark,
    ):
        client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert mock_get_attempt.call_args[0][0] is sentinel_client
    assert mock_list_questions.call_args[0][0] is sentinel_client
    assert mock_answered.call_args[0][0] is sentinel_client
    assert mock_mark.call_args[0][0] is sentinel_client


# ------------------------------------------------------------
# Scoring boundary
# ------------------------------------------------------------


def test_submit_never_queries_answer_key_table():
    """assessment_question_answers (the protected answer key) must never
    be queried anywhere in the submit flow -- verified against a mock
    client's actual .table() call history, not just by inspection."""
    attempt_id = uuid4()
    q1 = _eligible_question()
    mock_client = MagicMock()
    # get_own_attempt
    attempt_response = MagicMock()
    attempt_response.data = _row_attempt(id=str(attempt_id))
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = attempt_response

    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.build_user_client", return_value=mock_client),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1]),
        patch.object(
            assessment_service, "get_answered_question_ids", return_value={q1["id"]}
        ),
        patch.object(
            assessment_service,
            "mark_attempt_submitted",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:00:00Z"),
        ),
    ):
        client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})

    tables_touched = {call.args[0] for call in mock_client.table.call_args_list}
    assert "assessment_question_answers" not in tables_touched


def test_submit_module_has_no_ai_imports():
    """No AI/scoring-service call exists anywhere in this phase -- trivially
    true since nothing in app.ai is imported here, but asserted explicitly
    as a regression guard."""
    from app.api import attempts as attempts_routes

    module_globals = vars(attempts_routes)
    ai_related = [name for name in module_globals if "ai" in name.lower() and name != "main"]
    assert ai_related == []


def test_submit_status_never_appears_in_update_payload():
    """A more direct restatement of test_service_mark_attempt_submitted_
    only_sets_submitted_at, at the API-request level: confirm the actual
    payload sent to Supabase during a real submit flow has no status key,
    proving the COMPLETED transition is structurally unreachable through
    this endpoint."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [_row_attempt()]
    mock_client.table.return_value.update.return_value.eq.return_value.is_.return_value.execute.return_value = response

    assessment_service.mark_attempt_submitted(mock_client, uuid4())

    sent_payload = mock_client.table.return_value.update.call_args[0][0]
    assert "status" not in sent_payload


# ------------------------------------------------------------
# Atomicity / failure behavior
# ------------------------------------------------------------


def test_submit_incomplete_does_not_call_mark_submitted():
    attempt_id = uuid4()
    q1, q2 = _eligible_question(), _eligible_question()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1, q2]),
        patch.object(
            assessment_service, "get_answered_question_ids", return_value={q1["id"]}
        ),
        patch.object(assessment_service, "mark_attempt_submitted") as mock_mark,
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 400
    mock_mark.assert_not_called()


def test_submit_database_update_failure_returns_clean_500():
    attempt_id = uuid4()
    q1 = _eligible_question()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1]),
        patch.object(
            assessment_service, "get_answered_question_ids", return_value={q1["id"]}
        ),
        patch.object(
            assessment_service,
            "mark_attempt_submitted",
            side_effect=RuntimeError("connection refused to internal db host 10.0.0.5"),
        ),
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 500
    body_text = str(response.json())
    assert "10.0.0.5" not in body_text
    assert "connection refused" not in body_text.lower()


def test_submit_race_loss_returns_409_not_fabricated_success():
    """The pre-check saw submitted_at = None (so it passed), but by the
    time the guarded UPDATE ran, another request had already submitted --
    mark_attempt_submitted correctly returns None, and the route must
    surface a real 409, never a fabricated success with a made-up
    timestamp."""
    attempt_id = uuid4()
    q1 = _eligible_question()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service, "get_own_attempt", return_value=_row_attempt(id=str(attempt_id))
        ),
        patch.object(assessment_service, "list_visible_questions", return_value=[q1]),
        patch.object(
            assessment_service, "get_answered_question_ids", return_value={q1["id"]}
        ),
        patch.object(assessment_service, "mark_attempt_submitted", return_value=None),
    ):
        response = client.post(_submit_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 409
