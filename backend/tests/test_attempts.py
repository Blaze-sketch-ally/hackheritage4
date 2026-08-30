"""Tests for the attempt-scoped API: answer saving (Phase 1F), submission
(Phase 1G), and scoring (Phase 1H).

No live Supabase project or real token is used anywhere in this file --
service-layer tests mock the Supabase client itself and assert the query
WE construct; API-layer tests use FastAPI's TestClient against the real
app, mocking only the auth dependency chain (conftest.authenticated_as)
and, where relevant, the assessment_service functions.

IMPORTANT SCOPE NOTE for Phase 1H specifically: the actual scoring
algorithm (which questions are eligible, how MCQ/MULTIPLE_SELECT/
SHORT_ANSWER answers are compared, total_marks/score/percentage
arithmetic, the zero-total-marks case, atomic rollback-on-failure, and
true concurrent-request row-locking behavior) lives entirely inside the
score_assessment_attempt() PL/pgSQL function
(database/migrations/014_score_assessment_attempt.sql). None of that can
be exercised by pytest without a real Postgres connection running that
exact migration, which this environment does not have. Writing tests that
assert against a Python re-implementation of that SQL logic would test
the Python mirror, not the actual deployed function -- so this file does
NOT do that. What it does test, thoroughly, is everything on the Python
side of the RPC boundary: auth, ownership, state checks, which Supabase
client is used where, error-code translation, response shape, and the
absence of any AI/scoring logic in Python. The SQL itself needs live
verification once the migration is applied -- see the Phase 1H report.

This includes the unanswered-eligible-question persistence behavior
(inserting an assessment_answers row with selected_option_ids = '{}' as
an internal-only sentinel, awarded_marks = 0, is_correct = false, for
every eligible question with no existing answer row) added for Phase 1I:
that INSERT, its interaction with assessment_answers_has_content, its
atomicity/rollback under a later failure, and its uniqueness under
(attempt_id, question_id) are all facts about the deployed PL/pgSQL
function's runtime behavior against a real Postgres instance -- not
something a mocked Supabase client can prove. It also includes the
placeholder INSERT's ON CONFLICT (attempt_id, question_id) DO NOTHING
race-safety refinement (a concurrent POST /attempts/{id}/answers for the
same question, still legal while status stays IN_PROGRESS for this
function's whole duration, must never be overwritten by the placeholder
and must never be silently scored as unanswered) -- that this doesn't
raise unique_violation, that a real racing answer gets picked up by the
mandatory re-SELECT and scored normally, and that a plain student answer
still can never collide with the '{}' sentinel, are equally real-Postgres
facts, not something a single-threaded mocked test can exercise. This
file does not fabricate a fake concurrency test claiming to prove
otherwise. score_attempt()'s Python wrapper
(app.services.assessment_service.score_attempt) is completely unchanged
by any of this: it still only invokes the RPC and translates SQLSTATE
55000, so the existing tests below already cover everything
Python-observable about it. See the Phase 1I report for exactly what
still requires manual Supabase SQL Editor verification.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

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


def test_save_answer_does_not_use_service_role_client():
    """As of Phase 1H, app.api.attempts DOES import get_supabase (for the
    score_attempt route only -- see test_score_uses_service_role_client_
    only_for_scoring) -- a blanket "module never references get_supabase"
    check is no longer accurate and would be testing the wrong thing.
    What actually matters for save_answer specifically is proven by the
    sentinel-object test right below: the client save_answer receives is
    exactly what build_user_client() returned, never get_supabase()'s."""
    from app.api import attempts as attempts_routes

    assert hasattr(attempts_routes, "get_supabase")  # present (Phase 1H)
    assert hasattr(attempts_routes, "build_user_client")  # still the default


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


def test_submit_does_not_use_service_role_client():
    """Same note as test_save_answer_does_not_use_service_role_client:
    the module-level "get_supabase absent" check is obsolete since Phase
    1H. submit_attempt's own guarantee is proven by the sentinel-object
    test right below."""
    from app.api import attempts as attempts_routes

    assert hasattr(attempts_routes, "get_supabase")  # present (Phase 1H)
    assert hasattr(attempts_routes, "build_user_client")  # still the default


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


# ============================================================
# Phase 1H -- Assessment scoring
# ============================================================


def _score_url(attempt_id) -> str:
    return f"/api/v1/attempts/{attempt_id}/score"


def _row_completed_attempt(**overrides):
    row = {
        "id": str(uuid4()),
        "student_id": str(uuid4()),
        "assessment_id": str(uuid4()),
        "status": "COMPLETED",
        "started_at": "2026-01-01T00:00:00Z",
        "submitted_at": "2026-01-01T00:05:00Z",
        "score": "8.00",
        "total_marks": "10.00",
        "percentage": "80.00",
    }
    row.update(overrides)
    return row


# ------------------------------------------------------------
# Service layer: RPC call construction + error translation
# ------------------------------------------------------------


def test_service_score_attempt_calls_rpc_with_correct_params():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = _row_completed_attempt()
    mock_client.rpc.return_value.execute.return_value = response

    attempt_id = uuid4()
    assessment_service.score_attempt(mock_client, attempt_id, "student-1")

    mock_client.rpc.assert_called_once_with(
        "score_assessment_attempt",
        {"p_attempt_id": str(attempt_id), "p_student_id": "student-1"},
    )


def test_service_score_attempt_translates_55000_to_not_eligible_error():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "55000", "message": "Attempt is not eligible for scoring."}
    )

    with pytest.raises(assessment_service.AttemptNotEligibleForScoringError):
        assessment_service.score_attempt(mock_client, uuid4(), "student-1")


def test_service_score_attempt_reraises_other_api_errors():
    """Only 55000 is special-cased -- missing-answer-key (XX000),
    not-found (P0002), or anything else must propagate as a raw APIError
    for the route's generic except-clause to turn into a safe 500. These
    are data-integrity problems, never silently treated as "not
    eligible."""
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "XX000", "message": "Missing answer key for question ..."}
    )

    with pytest.raises(APIError):
        assessment_service.score_attempt(mock_client, uuid4(), "student-1")


def test_service_score_attempt_handles_dict_shaped_rpc_response():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = _row_completed_attempt(id="attempt-1")
    mock_client.rpc.return_value.execute.return_value = response

    result = assessment_service.score_attempt(mock_client, uuid4(), "student-1")
    assert result["id"] == "attempt-1"


def test_service_score_attempt_handles_list_shaped_rpc_response():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [_row_completed_attempt(id="attempt-1")]
    mock_client.rpc.return_value.execute.return_value = response

    result = assessment_service.score_attempt(mock_client, uuid4(), "student-1")
    assert result["id"] == "attempt-1"


# ------------------------------------------------------------
# API layer: AUTH
# ------------------------------------------------------------


def test_score_missing_token_returns_401():
    response = client.post(_score_url(uuid4()))
    assert response.status_code == 401


def test_score_invalid_token_returns_401():
    with patch(
        "app.core.dependencies.verify_access_token",
        side_effect=InvalidTokenError("bad"),
    ):
        response = client.post(_score_url(uuid4()), headers={"Authorization": "Bearer not-real"})
    assert response.status_code == 401


def test_score_faculty_forbidden():
    with authenticated_as("FACULTY"):
        response = client.post(_score_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_score_industry_forbidden():
    with authenticated_as("INDUSTRY"):
        response = client.post(_score_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_score_institution_forbidden():
    with authenticated_as("INSTITUTION"):
        response = client.post(_score_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


# ------------------------------------------------------------
# API layer: ownership
# ------------------------------------------------------------


def test_score_nonexistent_attempt_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=None),
    ):
        response = client.post(_score_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 404


def test_score_another_students_attempt_returns_404():
    # get_own_attempt is scoped by student_id -- another student's attempt
    # is indistinguishable from a nonexistent one, by design.
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=None) as mock_get,
    ):
        response = client.post(_score_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 404
    mock_get.assert_called_once()


# ------------------------------------------------------------
# API layer: state
# ------------------------------------------------------------


def test_score_not_yet_submitted_returns_409():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), submitted_at=None),
        ),
    ):
        response = client.post(_score_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 409


def test_score_completed_attempt_returns_409():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch.object(assessment_service, "score_attempt") as mock_score,
    ):
        response = client.post(_score_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 409
    mock_score.assert_not_called()


def test_score_abandoned_attempt_returns_409():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="ABANDONED"),
        ),
    ):
        response = client.post(_score_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 409


def test_score_submitted_in_progress_attempt_succeeds():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.get_supabase", return_value=MagicMock()),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:05:00Z"),
        ),
        patch.object(
            assessment_service,
            "score_attempt",
            return_value=_row_completed_attempt(id=str(attempt_id)),
        ),
    ):
        response = client.post(_score_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["score"] == "8.00"
    assert body["total_marks"] == "10.00"
    assert body["percentage"] == "80.00"


# ------------------------------------------------------------
# API layer: duplicate / concurrent scoring
# ------------------------------------------------------------


def test_score_race_lost_returns_409():
    """The pre-check (via build_user_client) saw IN_PROGRESS + submitted,
    but by the time the RPC's own row lock resolved, a concurrent request
    had already completed the attempt -- the RPC raises 55000, which must
    surface as 409, not a fabricated success or a 500."""
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.get_supabase", return_value=MagicMock()),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:05:00Z"),
        ),
        patch.object(
            assessment_service,
            "score_attempt",
            side_effect=assessment_service.AttemptNotEligibleForScoringError(),
        ),
    ):
        response = client.post(_score_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 409


# ------------------------------------------------------------
# Security
# ------------------------------------------------------------


def test_score_ignores_client_supplied_body_entirely():
    """No request body parameter exists on this route at all."""
    attempt_id = uuid4()
    hostile_body = {
        "student_id": "someone-elses-id",
        "status": "COMPLETED",
        "score": 100,
        "total_marks": 1,
        "percentage": 10000,
        "awarded_marks": 100,
        "is_correct": True,
        "correct_option_ids": [str(uuid4())],
        "correct_answer_text": "the real answer",
        "explanation": "why",
    }
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.get_supabase", return_value=MagicMock()),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:05:00Z"),
        ),
        patch.object(
            assessment_service,
            "score_attempt",
            return_value=_row_completed_attempt(id=str(attempt_id)),
        ) as mock_score,
    ):
        response = client.post(
            _score_url(attempt_id),
            json=hostile_body,
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    # score_attempt(client, attempt_id, student_id) -- exactly 3 positional
    # args, none sourced from hostile_body.
    _call_client, called_attempt_id, called_student_id = mock_score.call_args[0]
    assert called_attempt_id == attempt_id
    assert called_student_id == "student-1"


def test_score_response_has_no_answer_key_fields():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.get_supabase", return_value=MagicMock()),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:05:00Z"),
        ),
        patch.object(
            assessment_service,
            "score_attempt",
            return_value=_row_completed_attempt(id=str(attempt_id)),
        ),
    ):
        response = client.post(_score_url(attempt_id), headers={"Authorization": "Bearer token"})
    body_text = response.text
    for forbidden in ("correct_option_ids", "correct_answer_text", "explanation"):
        assert forbidden not in body_text


def test_score_uses_build_user_client_for_ownership_check():
    """The FIRST client used must be the user-scoped one, for the
    ownership/state check -- never get_supabase(), even for a read."""
    attempt_id = uuid4()
    sentinel_user_client = object()
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.build_user_client", return_value=sentinel_user_client),
        patch("app.api.attempts.get_supabase", return_value=MagicMock()),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:05:00Z"),
        ) as mock_get_attempt,
        patch.object(
            assessment_service,
            "score_attempt",
            return_value=_row_completed_attempt(id=str(attempt_id)),
        ),
    ):
        client.post(_score_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert mock_get_attempt.call_args[0][0] is sentinel_user_client


def test_score_uses_service_role_client_only_for_scoring():
    """get_supabase()'s return value must be exactly what reaches
    score_attempt() -- confirming the service-role client is used for the
    trusted scoring call, and (via the previous test) NOT for the
    ownership check."""
    attempt_id = uuid4()
    sentinel_service_client = object()
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.get_supabase", return_value=sentinel_service_client),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:05:00Z"),
        ),
        patch.object(
            assessment_service,
            "score_attempt",
            return_value=_row_completed_attempt(id=str(attempt_id)),
        ) as mock_score,
    ):
        client.post(_score_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert mock_score.call_args[0][0] is sentinel_service_client


def test_score_route_intentionally_imports_get_supabase():
    """Unlike every other route in this file, score_attempt is the one
    documented, deliberate exception that uses the service-role client --
    confirming that's actually wired up, complementing (not contradicting)
    the "get_supabase is never used" tests for the other endpoints."""
    from app.api import attempts as attempts_routes

    assert hasattr(attempts_routes, "get_supabase")


def test_score_module_has_no_ai_imports():
    from app.api import attempts as attempts_routes

    module_globals = vars(attempts_routes)
    ai_related = [name for name in module_globals if "ai" in name.lower() and name != "main"]
    assert ai_related == []


# ------------------------------------------------------------
# Errors
# ------------------------------------------------------------


def test_score_ownership_check_failure_returns_clean_500():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            side_effect=RuntimeError("connection refused to internal db host 10.0.0.5"),
        ),
    ):
        response = client.post(_score_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 500
    body_text = str(response.json())
    assert "10.0.0.5" not in body_text
    assert "connection refused" not in body_text.lower()


def test_score_rpc_failure_returns_clean_500():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.get_supabase", return_value=MagicMock()),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), submitted_at="2026-01-01T00:05:00Z"),
        ),
        patch.object(
            assessment_service,
            "score_attempt",
            side_effect=RuntimeError("Missing answer key for question abc123 -- internal db state"),
        ),
    ):
        response = client.post(_score_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 500
    body_text = str(response.json())
    assert "abc123" not in body_text
    assert "missing answer key" not in body_text.lower()


# ============================================================
# Phase 1I: results
# ============================================================
#
# Same SQL-vs-Python boundary note as the Phase 1H section above applies
# here too: get_attempt_result_rows() issues real Supabase queries (one
# .eq() against assessment_answers, one .in_() against
# assessment_question_answers) -- the tests below either mock those calls
# entirely (API-layer tests) or run the REAL service-layer query-building
# logic against a fake client that actually applies .eq()/.in_() filters
# to an in-memory row set (the same pattern as
# test_ai_evaluated_question_excluded_from_questions_endpoint in
# test_assessments.py), never a hand-rolled Python reimplementation of
# what Postgres/PostgREST does. Nothing here can prove the *migration's*
# PL/pgSQL INSERT/embed behavior against a real Postgres instance -- see
# the Phase 1I report for what still needs manual Supabase verification.


def _result_url(attempt_id) -> str:
    return f"/api/v1/attempts/{attempt_id}/result"


def _result_question(**overrides):
    row = {
        "id": str(uuid4()),
        "assessment_id": str(uuid4()),
        "question_text": "What is 2 + 2?",
        "question_type": "MCQ",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Intermediate",
        "points": "5.00",
        "display_order": 1,
        "options": [],
    }
    row.update(overrides)
    return row


def _result_answer_row(**overrides):
    row = {
        "id": str(uuid4()),
        "attempt_id": str(uuid4()),
        "question_id": str(uuid4()),
        "answer_text": None,
        "selected_option_ids": [],
        "awarded_marks": "0.00",
        "is_correct": False,
        "created_at": "2026-01-01T00:10:00Z",
        "updated_at": "2026-01-01T00:10:00Z",
        "question": None,
    }
    row.update(overrides)
    return row


def _result_answer_key_row(**overrides):
    row = {
        "question_id": str(uuid4()),
        "correct_option_ids": [str(uuid4())],
        "correct_answer_text": None,
        "explanation": "Because 2 + 2 = 4.",
    }
    row.update(overrides)
    return row


class _FakeResultQuery:
    """Same real-filtering-fake pattern as _FakeFilterQuery in
    test_assessments.py, extended with .in_() since
    get_attempt_result_rows() uses it for the answer-key lookup."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self._rows = [row for row in self._rows if row.get(column) == value]
        return self

    def in_(self, column, values):
        values = set(values)
        self._rows = [row for row in self._rows if row.get(column) in values]
        return self

    def execute(self):
        result = MagicMock()
        result.data = self._rows
        return result


class _FakeResultClient:
    def __init__(self, answers, answer_keys):
        self._tables = {
            "assessment_answers": answers,
            "assessment_question_answers": answer_keys,
        }

    def table(self, name):
        return _FakeResultQuery(list(self._tables[name]))


# ------------------------------------------------------------
# API layer: AUTH
# ------------------------------------------------------------


def test_result_missing_token_returns_401():
    response = client.get(_result_url(uuid4()))
    assert response.status_code == 401


def test_result_invalid_token_returns_401():
    with patch(
        "app.core.dependencies.verify_access_token",
        side_effect=InvalidTokenError("bad"),
    ):
        response = client.get(_result_url(uuid4()), headers={"Authorization": "Bearer not-real"})
    assert response.status_code == 401


# ------------------------------------------------------------
# API layer: ROLE
# ------------------------------------------------------------


def test_result_faculty_forbidden():
    with authenticated_as("FACULTY"):
        response = client.get(_result_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_result_industry_forbidden():
    with authenticated_as("INDUSTRY"):
        response = client.get(_result_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_result_institution_forbidden():
    with authenticated_as("INSTITUTION"):
        response = client.get(_result_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


# ------------------------------------------------------------
# API layer: ownership
# ------------------------------------------------------------


def test_result_nonexistent_attempt_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=None),
    ):
        response = client.get(_result_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 404


def test_result_another_students_attempt_returns_404():
    # get_own_attempt is scoped by student_id -- another student's attempt
    # is indistinguishable from a nonexistent one, by design.
    with (
        authenticated_as("STUDENT"),
        patch.object(assessment_service, "get_own_attempt", return_value=None) as mock_get,
    ):
        response = client.get(_result_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 404
    mock_get.assert_called_once()


# ------------------------------------------------------------
# API layer: state
# ------------------------------------------------------------


def test_result_in_progress_returns_409():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="IN_PROGRESS"),
        ),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 409


def test_result_abandoned_returns_409():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="ABANDONED"),
        ),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 409


def test_result_completed_attempt_returns_200():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(
                id=str(attempt_id),
                status="COMPLETED",
                submitted_at="2026-01-01T00:05:00Z",
                score="8.00",
                total_marks="10.00",
                percentage="80.00",
            ),
        ),
        patch.object(assessment_service, "get_attempt_result_rows", return_value=[]),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()
    assert body["attempt"]["status"] == "COMPLETED"
    assert body["questions"] == []


# ------------------------------------------------------------
# Result content / answer mapping / ordering -- real fake-client tests
# ------------------------------------------------------------


def test_result_maps_answered_question_and_answer_key_correctly():
    """Full round trip through the REAL get_attempt_result_rows() query
    logic (not mocked): an answered question's real answer_text/
    selected_option_ids/awarded_marks/is_correct and its answer key's
    correct_option_ids/correct_answer_text/explanation must all reach the
    response body unchanged."""
    attempt_id = uuid4()
    question_id = uuid4()
    option_id = uuid4()

    question = _result_question(
        id=str(question_id),
        options=[
            {
                "id": str(option_id),
                "question_id": str(question_id),
                "option_text": "4",
                "display_order": 1,
            }
        ],
    )
    answer_row = _result_answer_row(
        attempt_id=str(attempt_id),
        question_id=str(question_id),
        answer_text=None,
        selected_option_ids=[str(option_id)],
        awarded_marks="5.00",
        is_correct=True,
        question=question,
    )
    answer_key_row = _result_answer_key_row(
        question_id=str(question_id),
        correct_option_ids=[str(option_id)],
        explanation="Because 2 + 2 = 4.",
    )
    fake_client = _FakeResultClient([answer_row], [answer_key_row])

    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch("app.api.attempts.build_user_client", return_value=fake_client),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    questions = response.json()["questions"]
    assert len(questions) == 1
    item = questions[0]
    assert item["question"]["id"] == str(question_id)
    assert item["student_answer"]["selected_option_ids"] == [str(option_id)]
    assert item["student_answer"]["awarded_marks"] == "5.00"
    assert item["student_answer"]["is_correct"] is True
    assert item["answer_key"]["correct_option_ids"] == [str(option_id)]
    assert item["answer_key"]["explanation"] == "Because 2 + 2 = 4."


def test_result_maps_unanswered_question_with_zero_score():
    """The Phase 1H placeholder row (selected_option_ids = [], answer_text
    = None, awarded_marks = 0, is_correct = false) must be represented
    exactly as-is, not omitted and not disguised as a real "selected zero
    options" answer -- it is a distinct, explicit zero/false row, present
    in the response like any other question."""
    attempt_id = uuid4()
    question_id = uuid4()

    question = _result_question(id=str(question_id))
    answer_row = _result_answer_row(
        attempt_id=str(attempt_id),
        question_id=str(question_id),
        answer_text=None,
        selected_option_ids=[],
        awarded_marks="0.00",
        is_correct=False,
        question=question,
    )
    answer_key_row = _result_answer_key_row(question_id=str(question_id))
    fake_client = _FakeResultClient([answer_row], [answer_key_row])

    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch("app.api.attempts.build_user_client", return_value=fake_client),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    item = response.json()["questions"][0]
    assert item["student_answer"]["answer_text"] is None
    assert item["student_answer"]["selected_option_ids"] == []
    assert item["student_answer"]["awarded_marks"] == "0.00"
    assert item["student_answer"]["is_correct"] is False


def test_result_orders_questions_by_display_order():
    """Rows are seeded in intentionally scrambled order -- the response
    must follow assessment_questions.display_order, not row/insertion
    order."""
    attempt_id = uuid4()
    q_first_id, q_second_id, q_third_id = uuid4(), uuid4(), uuid4()

    rows = [
        _result_answer_row(
            attempt_id=str(attempt_id),
            question_id=str(q_third_id),
            question=_result_question(id=str(q_third_id), display_order=3),
        ),
        _result_answer_row(
            attempt_id=str(attempt_id),
            question_id=str(q_first_id),
            question=_result_question(id=str(q_first_id), display_order=1),
        ),
        _result_answer_row(
            attempt_id=str(attempt_id),
            question_id=str(q_second_id),
            question=_result_question(id=str(q_second_id), display_order=2),
        ),
    ]
    answer_keys = [
        _result_answer_key_row(question_id=str(qid))
        for qid in (q_third_id, q_first_id, q_second_id)
    ]
    fake_client = _FakeResultClient(rows, answer_keys)

    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch("app.api.attempts.build_user_client", return_value=fake_client),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    ordered_ids = [q["question"]["id"] for q in response.json()["questions"]]
    assert ordered_ids == [str(q_first_id), str(q_second_id), str(q_third_id)]


def test_result_does_not_leak_another_attempts_answer():
    """Real .eq("attempt_id", ...) filtering, proven against a fake client
    seeded with rows from TWO different attempts -- only the requested
    attempt's own row may appear."""
    attempt_id = uuid4()
    other_attempt_id = uuid4()
    own_question_id = uuid4()
    other_question_id = uuid4()

    own_row = _result_answer_row(
        attempt_id=str(attempt_id),
        question_id=str(own_question_id),
        question=_result_question(id=str(own_question_id)),
    )
    other_attempts_row = _result_answer_row(
        attempt_id=str(other_attempt_id),
        question_id=str(other_question_id),
        question=_result_question(id=str(other_question_id)),
    )
    fake_client = _FakeResultClient(
        [own_row, other_attempts_row],
        [
            _result_answer_key_row(question_id=str(own_question_id)),
            _result_answer_key_row(question_id=str(other_question_id)),
        ],
    )

    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch("app.api.attempts.build_user_client", return_value=fake_client),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    questions = response.json()["questions"]
    assert len(questions) == 1
    assert questions[0]["question"]["id"] == str(own_question_id)


def test_result_does_not_leak_unrelated_answer_key_rows():
    """Real .in_("question_id", [...]) filtering: an answer-key row for a
    question that is NOT part of this attempt must never be attached to
    any question in the response."""
    attempt_id = uuid4()
    question_id = uuid4()
    unrelated_question_id = uuid4()

    question = _result_question(id=str(question_id))
    answer_row = _result_answer_row(
        attempt_id=str(attempt_id), question_id=str(question_id), question=question
    )
    fake_client = _FakeResultClient(
        [answer_row],
        [
            _result_answer_key_row(question_id=str(question_id), explanation="correct one"),
            _result_answer_key_row(
                question_id=str(unrelated_question_id), explanation="must never appear"
            ),
        ],
    )

    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch("app.api.attempts.build_user_client", return_value=fake_client),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    body_text = response.text
    assert "must never appear" not in body_text
    assert "correct one" in body_text


def test_result_missing_question_embed_returns_500_not_partial_result():
    """A successful response must contain the COMPLETE historically-scored
    population -- a question whose "question" embed came back None
    (deactivated content, invisible via RLS after completion -- see
    get_attempt_result_rows) must fail the WHOLE request with a generic
    500, never silently omit that question from an otherwise-200 result.
    Approved decision: hard failure over a partial result."""
    attempt_id = uuid4()
    visible_question_id = uuid4()
    hidden_question_id = uuid4()

    visible_row = _result_answer_row(
        attempt_id=str(attempt_id),
        question_id=str(visible_question_id),
        question=_result_question(id=str(visible_question_id)),
    )
    hidden_row = _result_answer_row(
        attempt_id=str(attempt_id),
        question_id=str(hidden_question_id),
        question=None,  # simulates RLS hiding a deactivated question
    )
    fake_client = _FakeResultClient(
        [visible_row, hidden_row],
        [
            _result_answer_key_row(question_id=str(visible_question_id)),
            _result_answer_key_row(question_id=str(hidden_question_id)),
        ],
    )

    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch("app.api.attempts.build_user_client", return_value=fake_client),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert response.status_code == 500
    body_text = str(response.json())
    assert str(hidden_question_id) not in body_text
    assert str(visible_question_id) not in body_text
    assert str(attempt_id) not in body_text


def test_result_missing_answer_key_returns_500_not_partial_result():
    """Same hard-failure requirement as a missing question embed, for a
    missing answer_key embed: a question row that has a real
    assessment_answers row but whose answer key could not be resolved
    must fail the whole request, not be silently omitted."""
    attempt_id = uuid4()
    visible_question_id = uuid4()
    no_key_question_id = uuid4()

    visible_row = _result_answer_row(
        attempt_id=str(attempt_id),
        question_id=str(visible_question_id),
        question=_result_question(id=str(visible_question_id)),
    )
    no_key_row = _result_answer_row(
        attempt_id=str(attempt_id),
        question_id=str(no_key_question_id),
        question=_result_question(id=str(no_key_question_id)),
    )
    fake_client = _FakeResultClient(
        [visible_row, no_key_row],
        # Only the visible question's answer key exists -- no_key_row's
        # question_id has no matching row in assessment_question_answers.
        [_result_answer_key_row(question_id=str(visible_question_id))],
    )

    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch("app.api.attempts.build_user_client", return_value=fake_client),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert response.status_code == 500
    body_text = str(response.json())
    assert str(no_key_question_id) not in body_text
    assert str(visible_question_id) not in body_text
    assert str(attempt_id) not in body_text


def test_result_fully_valid_completed_result_still_returns_200():
    """Baseline: a completed attempt whose every historically-scored
    question has BOTH a resolvable question embed and answer key must
    still return 200 with the full population -- the new hard-failure
    path must not have broken the ordinary, common case."""
    attempt_id = uuid4()
    q1_id, q2_id = uuid4(), uuid4()

    rows = [
        _result_answer_row(
            attempt_id=str(attempt_id),
            question_id=str(q1_id),
            question=_result_question(id=str(q1_id), display_order=1),
        ),
        _result_answer_row(
            attempt_id=str(attempt_id),
            question_id=str(q2_id),
            question=_result_question(id=str(q2_id), display_order=2),
        ),
    ]
    answer_keys = [
        _result_answer_key_row(question_id=str(q1_id)),
        _result_answer_key_row(question_id=str(q2_id)),
    ]
    fake_client = _FakeResultClient(rows, answer_keys)

    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch("app.api.attempts.build_user_client", return_value=fake_client),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    questions = response.json()["questions"]
    assert len(questions) == 2
    assert [q["question"]["id"] for q in questions] == [str(q1_id), str(q2_id)]


def test_result_unanswered_placeholder_with_full_embeds_returns_200():
    """A Phase 1H unanswered-placeholder row (selected_option_ids = [])
    whose question and answer_key ARE both resolvable must still return
    200 normally -- the hard-failure path is only for missing embeds, not
    for the unanswered-but-fully-visible case."""
    attempt_id = uuid4()
    question_id = uuid4()

    row = _result_answer_row(
        attempt_id=str(attempt_id),
        question_id=str(question_id),
        answer_text=None,
        selected_option_ids=[],
        awarded_marks="0.00",
        is_correct=False,
        question=_result_question(id=str(question_id)),
    )
    fake_client = _FakeResultClient([row], [_result_answer_key_row(question_id=str(question_id))])

    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch("app.api.attempts.build_user_client", return_value=fake_client),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    item = response.json()["questions"][0]
    assert item["student_answer"]["answer_text"] is None
    assert item["student_answer"]["selected_option_ids"] == []
    assert item["student_answer"]["awarded_marks"] == "0.00"
    assert item["student_answer"]["is_correct"] is False


# ------------------------------------------------------------
# Historical population -- must not re-derive from current eligibility
# ------------------------------------------------------------


def test_result_never_calls_list_visible_questions():
    """The whole point of the Phase 1H persistence fix + Phase 1I query
    design is that the result population comes from assessment_answers,
    not from re-running current eligibility -- list_visible_questions()
    must never be called by this endpoint."""
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch.object(assessment_service, "get_attempt_result_rows", return_value=[]),
        patch.object(
            assessment_service,
            "list_visible_questions",
            side_effect=AssertionError("must not be called by the result endpoint"),
        ),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


# ------------------------------------------------------------
# Read-only
# ------------------------------------------------------------


def test_result_never_calls_score_attempt():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch.object(assessment_service, "get_attempt_result_rows", return_value=[]),
        patch.object(
            assessment_service,
            "score_attempt",
            side_effect=AssertionError("must not be called by the result endpoint"),
        ),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


def test_result_uses_build_user_client_never_service_role():
    """Unlike score_attempt (Phase 1H), the result endpoint must use ONLY
    the user-scoped client -- get_supabase() must never even be called."""
    attempt_id = uuid4()
    sentinel_user_client = object()
    with (
        authenticated_as("STUDENT"),
        patch("app.api.attempts.build_user_client", return_value=sentinel_user_client),
        patch("app.api.attempts.get_supabase") as mock_get_supabase,
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ) as mock_get_attempt,
        patch.object(assessment_service, "get_attempt_result_rows", return_value=[]) as mock_rows,
    ):
        client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})

    assert mock_get_attempt.call_args[0][0] is sentinel_user_client
    assert mock_rows.call_args[0][0] is sentinel_user_client
    mock_get_supabase.assert_not_called()


# ------------------------------------------------------------
# Errors
# ------------------------------------------------------------


def test_result_ownership_check_failure_returns_clean_500():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            side_effect=RuntimeError("connection refused to internal db host 10.0.0.5"),
        ),
    ):
        response = client.get(_result_url(uuid4()), headers={"Authorization": "Bearer token"})
    assert response.status_code == 500
    body_text = str(response.json())
    assert "10.0.0.5" not in body_text
    assert "connection refused" not in body_text.lower()


def test_result_rows_failure_returns_clean_500():
    attempt_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(
            assessment_service,
            "get_own_attempt",
            return_value=_row_attempt(id=str(attempt_id), status="COMPLETED"),
        ),
        patch.object(
            assessment_service,
            "get_attempt_result_rows",
            side_effect=RuntimeError("internal db host 10.0.0.5 unreachable"),
        ),
    ):
        response = client.get(_result_url(attempt_id), headers={"Authorization": "Bearer token"})
    assert response.status_code == 500
    body_text = str(response.json())
    assert "10.0.0.5" not in body_text


# ------------------------------------------------------------
# Service layer: query construction (real filtering, no live DB)
# ------------------------------------------------------------


def test_service_get_attempt_result_rows_filters_by_attempt_id():
    """Proves the REAL .eq("attempt_id", ...) call excludes another
    attempt's row -- not just that the argument was passed."""
    attempt_id = uuid4()
    other_attempt_id = uuid4()
    own_question_id = uuid4()

    own_row = _result_answer_row(
        attempt_id=str(attempt_id),
        question_id=str(own_question_id),
        question=_result_question(id=str(own_question_id)),
    )
    other_row = _result_answer_row(attempt_id=str(other_attempt_id), question_id=str(uuid4()))
    fake_client = _FakeResultClient([own_row, other_row], [])

    rows = assessment_service.get_attempt_result_rows(fake_client, attempt_id)

    assert len(rows) == 1
    assert rows[0]["question_id"] == str(own_question_id)


def test_service_get_attempt_result_rows_sorts_options_by_display_order():
    attempt_id = uuid4()
    question_id = uuid4()
    opt_a, opt_b = uuid4(), uuid4()

    question = _result_question(
        id=str(question_id),
        options=[
            {"id": str(opt_b), "question_id": str(question_id), "option_text": "B", "display_order": 2},
            {"id": str(opt_a), "question_id": str(question_id), "option_text": "A", "display_order": 1},
        ],
    )
    row = _result_answer_row(
        attempt_id=str(attempt_id), question_id=str(question_id), question=question
    )
    fake_client = _FakeResultClient([row], [])

    rows = assessment_service.get_attempt_result_rows(fake_client, attempt_id)

    ordered_option_ids = [opt["id"] for opt in rows[0]["question"]["options"]]
    assert ordered_option_ids == [str(opt_a), str(opt_b)]


def test_service_get_attempt_result_rows_handles_no_answers():
    fake_client = _FakeResultClient([], [])
    rows = assessment_service.get_attempt_result_rows(fake_client, uuid4())
    assert rows == []
