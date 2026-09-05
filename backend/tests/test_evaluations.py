"""Tests for the F8.3 evaluator workflow API:
database/migrations/045_evaluation_foundation.sql,
database/migrations/046_evaluator_answer_access.sql,
app.schemas.evaluation, app.services.evaluation_service,
app.api.faculty_evaluations.

No live Supabase project or real token is used anywhere in this file --
tests mock the auth dependency chain (see conftest.py) and, where
appropriate, the Supabase client/service layer directly, matching the
pattern established in test_questions.py.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from pydantic import ValidationError

from app.main import app
from app.schemas.evaluation import (
    EvaluationDetailResponse,
    EvaluationSummaryResponse,
    SaveEvaluationRequest,
    UpdateEvaluationStatusRequest,
)
from app.schemas.faculty_permissions import AssessmentCapability
from app.services import evaluation_service
from tests.conftest import authenticated_as

client = TestClient(app)

_EVALUATOR = {AssessmentCapability.EVALUATOR}


def _as_evaluator():
    """Mirrors test_questions.py's _as_author()/_as_reviewer() -- the
    evaluator routes require assessment_evaluator
    (041_assessment_capability_authorization.sql's own capability
    pattern, reused unchanged by F8.1/F8.2/F8.3)."""
    return patch(
        "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
        return_value=_EVALUATOR,
    )


def _no_capabilities():
    return patch(
        "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
        return_value=set(),
    )


# ============================================================
# Schemas
# ============================================================


def test_save_evaluation_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        SaveEvaluationRequest(status="FINALIZED")


def test_save_evaluation_request_rejects_feedback_over_max_length():
    with pytest.raises(ValidationError):
        SaveEvaluationRequest(feedback="x" * 5_001)
    SaveEvaluationRequest(feedback="x" * 5_000)


def test_save_evaluation_request_rejects_negative_marks():
    with pytest.raises(ValidationError):
        SaveEvaluationRequest(awarded_marks=Decimal(-1))
    SaveEvaluationRequest(awarded_marks=Decimal(0))


def test_save_evaluation_request_all_fields_optional():
    req = SaveEvaluationRequest()
    assert req.model_dump(exclude_unset=True) == {}


def test_save_evaluation_request_exclude_unset_distinguishes_omitted_from_null():
    req = SaveEvaluationRequest(feedback=None)
    assert req.model_dump(exclude_unset=True) == {"feedback": None}


def test_update_evaluation_status_request_rejects_assigned_target():
    with pytest.raises(ValidationError):
        UpdateEvaluationStatusRequest(status="ASSIGNED")


def test_update_evaluation_status_request_accepts_valid_targets():
    for target in ("IN_PROGRESS", "SUBMITTED", "FINALIZED"):
        assert UpdateEvaluationStatusRequest(status=target).status.value == target


def test_update_evaluation_status_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        UpdateEvaluationStatusRequest(status="FINALIZED", finalized_by=str(uuid4()))
    with pytest.raises(ValidationError):
        UpdateEvaluationStatusRequest(status="SUBMITTED", submitted_at="2026-01-01T00:00:00Z")


def test_update_evaluation_status_request_rejects_invalid_status_value():
    with pytest.raises(ValidationError):
        UpdateEvaluationStatusRequest(status="NOT_A_REAL_STATUS")


def _detail_kwargs(**overrides) -> dict:
    base = {
        "evaluation_id": uuid4(),
        "assignment_id": uuid4(),
        "status": "ASSIGNED",
        "awarded_marks": None,
        "feedback": None,
        "rubric_id": None,
        "submitted_at": None,
        "finalized_at": None,
        "finalized_by": None,
        "attempt_id": uuid4(),
        "question_id": uuid4(),
        "student_id": uuid4(),
        "assessment_title": "Java Fundamentals",
        "assigned_at": "2026-01-01T00:00:00Z",
        "question": {
            "id": uuid4(),
            "assessment_id": uuid4(),
            "question_text": "Explain closures.",
            "question_type": "SUBJECTIVE",
            "scoring_method": "AI_EVALUATED",
            "difficulty": "Intermediate",
            "points": "5.00",
            "display_order": 0,
            "options": [],
        },
        "student_answer": None,
        "rubric": None,
    }
    base.update(overrides)
    return base


def test_evaluation_detail_response_parses_with_no_answer_and_no_rubric():
    parsed = EvaluationDetailResponse(**_detail_kwargs())
    assert parsed.student_answer is None
    assert parsed.rubric is None


def test_evaluation_detail_response_parses_with_rubric_and_criteria():
    parsed = EvaluationDetailResponse(
        **_detail_kwargs(
            rubric_id=uuid4(),
            rubric={
                "id": uuid4(),
                "question_id": uuid4(),
                "name": "Correctness",
                "description": None,
                "max_marks": "5.00",
                "status": "ACTIVE",
                "criteria": [
                    {
                        "id": uuid4(),
                        "rubric_id": uuid4(),
                        "criterion": "Accuracy",
                        "description": None,
                        "max_marks": "5.00",
                        "display_order": 0,
                    }
                ],
            },
        )
    )
    assert parsed.rubric is not None
    assert len(parsed.rubric.criteria) == 1


def test_evaluation_summary_response_has_no_answer_key_field():
    """Structural guard: an evaluator-facing summary schema must never
    grow an answer-key-shaped field -- see F8.2 decision C."""
    assert "answer_key" not in EvaluationSummaryResponse.model_fields
    assert "correct_option_ids" not in EvaluationSummaryResponse.model_fields


# ============================================================
# Service layer -- list/detail
# ============================================================


def test_list_my_evaluations_builds_summaries_with_batched_student_lookup():
    mock_client = MagicMock()
    eval_id, assignment_id, attempt_id, question_id, student_id = (
        str(uuid4()) for _ in range(5)
    )
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "id": eval_id,
            "assignment_id": assignment_id,
            "status": "ASSIGNED",
            "awarded_marks": None,
            "evaluator_assignments": {
                "attempt_id": attempt_id,
                "question_id": question_id,
                "created_at": "2026-01-01T00:00:00Z",
            },
        }
    ]
    mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": attempt_id, "student_id": student_id, "assessments": {"title": "Java Fundamentals"}}
    ]

    rows = evaluation_service.list_my_evaluations(mock_client, "evaluator-1")

    assert rows == [
        {
            "evaluation_id": eval_id,
            "assignment_id": assignment_id,
            "status": "ASSIGNED",
            "awarded_marks": None,
            "attempt_id": attempt_id,
            "question_id": question_id,
            "assigned_at": "2026-01-01T00:00:00Z",
            "student_id": student_id,
            "assessment_title": "Java Fundamentals",
        }
    ]


def test_list_my_evaluations_filters_by_status_when_given():
    mock_client = MagicMock()
    eq_chain = mock_client.table.return_value.select.return_value.eq.return_value
    eq_chain.eq.return_value.execute.return_value.data = []

    evaluation_service.list_my_evaluations(mock_client, "evaluator-1", status="FINALIZED")

    eq_chain.eq.assert_called_once_with("status", "FINALIZED")


def test_get_evaluation_detail_returns_none_when_not_found():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = None
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = response

    result = evaluation_service.get_evaluation_detail(mock_client, "evaluator-1", uuid4())

    assert result is None


def test_get_evaluation_detail_returns_none_when_assignment_no_longer_active():
    """The evaluations row itself stays visible after revocation (045's
    own historical-record design), but the detail view must treat a
    non-ACTIVE assignment identically to not-found -- see F8.2.1's
    regression discovery for why."""
    mock_client = MagicMock()
    eval_response = MagicMock()
    eval_response.data = {
        "id": "eval-1", "assignment_id": "assign-1", "status": "ASSIGNED",
        "awarded_marks": None, "feedback": None, "rubric_id": None,
        "submitted_at": None, "finalized_at": None, "finalized_by": None,
        "evaluator_assignments": {"attempt_id": "attempt-1", "question_id": "question-1"},
    }
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = eval_response

    assignment_response = MagicMock()
    assignment_response.data = {"status": "REVOKED"}
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = assignment_response

    result = evaluation_service.get_evaluation_detail(mock_client, "evaluator-1", uuid4())

    assert result is None


# ============================================================
# Service layer -- save
# ============================================================


def test_save_evaluation_returns_none_for_zero_rows():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = []
    mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = response

    result = evaluation_service.save_evaluation(mock_client, "evaluator-1", uuid4(), {"feedback": "ok"})

    assert result is None


def test_save_evaluation_converts_decimal_marks_to_string_for_the_wire():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = []
    update_mock = mock_client.table.return_value.update
    update_mock.return_value.eq.return_value.eq.return_value.execute.return_value = response

    evaluation_service.save_evaluation(mock_client, "evaluator-1", uuid4(), {"awarded_marks": Decimal("4.50")})

    update_mock.assert_called_once_with({"awarded_marks": "4.50"})


def test_save_evaluation_maps_finalized_immutability_error():
    mock_client = MagicMock()
    mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.side_effect = APIError(
        {"code": "42501", "message": "Cannot modify a finalized evaluation."}
    )
    with pytest.raises(evaluation_service.EvaluationFinalizedError):
        evaluation_service.save_evaluation(mock_client, "evaluator-1", uuid4(), {"feedback": "x"})


def test_save_evaluation_maps_validation_error():
    mock_client = MagicMock()
    mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.side_effect = APIError(
        {"code": "23514", "message": "Awarded marks exceed the rubric's maximum."}
    )
    with pytest.raises(evaluation_service.EvaluationValidationError):
        evaluation_service.save_evaluation(mock_client, "evaluator-1", uuid4(), {"awarded_marks": Decimal(999)})


def test_save_evaluation_reraises_unmapped_api_error():
    mock_client = MagicMock()
    mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.side_effect = APIError(
        {"code": "99999", "message": "Something else entirely."}
    )
    with pytest.raises(APIError):
        evaluation_service.save_evaluation(mock_client, "evaluator-1", uuid4(), {"feedback": "x"})


# ============================================================
# Service layer -- status transitions
# ============================================================


def _mock_current_status(mock_client: MagicMock, status: str) -> MagicMock:
    response = MagicMock()
    response.data = {"id": "eval-1", "assignment_id": "assign-1", "status": status, "awarded_marks": None}
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = response
    return response


def _mock_assignment_status(mock_client: MagicMock, status: str | None) -> MagicMock:
    """Phase F8.4.2.1, Fix B: mocks the NEW evaluator_assignments status
    lookup update_evaluation_status's idempotent branch performs --
    a distinct call chain (one .eq(), not two) from _mock_current_status
    above, so the two can be configured independently on the same
    mock_client without colliding."""
    response = MagicMock()
    response.data = {"status": status} if status is not None else None
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = response
    return response


def test_update_evaluation_status_returns_none_when_evaluation_not_found():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = None
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = response

    result = evaluation_service.update_evaluation_status(mock_client, "evaluator-1", uuid4(), "IN_PROGRESS")

    assert result is None


def test_update_evaluation_status_rejects_invalid_transition_before_any_write():
    mock_client = MagicMock()
    _mock_current_status(mock_client, "ASSIGNED")

    with pytest.raises(evaluation_service.EvaluationInvalidStatusTransitionError):
        evaluation_service.update_evaluation_status(mock_client, "evaluator-1", uuid4(), "FINALIZED")

    mock_client.table.return_value.update.assert_not_called()


def test_update_evaluation_status_rejects_backward_transition():
    mock_client = MagicMock()
    _mock_current_status(mock_client, "SUBMITTED")

    with pytest.raises(evaluation_service.EvaluationInvalidStatusTransitionError):
        evaluation_service.update_evaluation_status(mock_client, "evaluator-1", uuid4(), "IN_PROGRESS")


def test_update_evaluation_status_same_status_is_idempotent_no_write():
    mock_client = MagicMock()
    _mock_current_status(mock_client, "IN_PROGRESS")
    _mock_assignment_status(mock_client, "ACTIVE")

    with patch.object(evaluation_service, "_assignment_scope", return_value=None):
        result = evaluation_service.update_evaluation_status(mock_client, "evaluator-1", uuid4(), "IN_PROGRESS")

    assert result["status"] == "IN_PROGRESS"
    mock_client.table.return_value.update.assert_not_called()


def test_update_evaluation_status_idempotent_resend_returns_none_when_assignment_revoked():
    """Phase F8.4.2.1, Fix B: the idempotent short-circuit must not
    return a summary once the assignment is no longer ACTIVE -- this is
    the exact bug the fix closes (previously this fell through to
    _to_summary(), whose _student_id_for_attempt() call would silently
    resolve to None, failing EvaluationSummaryResponse's non-nullable
    student_id at the route layer). None here maps to 404, matching
    get_evaluation_detail's own identical F8.2.1 precedent."""
    mock_client = MagicMock()
    _mock_current_status(mock_client, "FINALIZED")
    _mock_assignment_status(mock_client, "REVOKED")

    result = evaluation_service.update_evaluation_status(mock_client, "evaluator-1", uuid4(), "FINALIZED")

    assert result is None
    mock_client.table.return_value.update.assert_not_called()


def test_update_evaluation_status_idempotent_resend_returns_none_when_assignment_lookup_missing():
    """Defensive: an assignment lookup that itself resolves to no row at
    all (should not normally happen, since the assignment_id always came
    from the caller's own evaluations row) is treated identically to a
    non-ACTIVE status -- None, not a crash."""
    mock_client = MagicMock()
    _mock_current_status(mock_client, "FINALIZED")
    _mock_assignment_status(mock_client, None)

    result = evaluation_service.update_evaluation_status(mock_client, "evaluator-1", uuid4(), "FINALIZED")

    assert result is None


def test_update_evaluation_status_valid_transition_performs_update():
    mock_client = MagicMock()
    _mock_current_status(mock_client, "ASSIGNED")
    update_response = MagicMock()
    update_response.data = [{"id": "eval-1", "assignment_id": "assign-1", "status": "IN_PROGRESS", "awarded_marks": None}]
    mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = update_response

    with patch.object(evaluation_service, "_assignment_scope", return_value=None):
        result = evaluation_service.update_evaluation_status(mock_client, "evaluator-1", uuid4(), "IN_PROGRESS")

    mock_client.table.return_value.update.assert_called_once_with({"status": "IN_PROGRESS"})
    assert result["status"] == "IN_PROGRESS"


def test_update_evaluation_status_maps_finalized_immutability_error():
    mock_client = MagicMock()
    _mock_current_status(mock_client, "SUBMITTED")
    mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.side_effect = APIError(
        {"code": "42501", "message": "Cannot modify a finalized evaluation."}
    )
    with pytest.raises(evaluation_service.EvaluationFinalizedError):
        evaluation_service.update_evaluation_status(mock_client, "evaluator-1", uuid4(), "FINALIZED")


def test_update_evaluation_status_maps_missing_marks_at_finalization():
    mock_client = MagicMock()
    _mock_current_status(mock_client, "SUBMITTED")
    mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.side_effect = APIError(
        {"code": "23514", "message": "evaluations_finalized_requires_marks"}
    )
    with pytest.raises(evaluation_service.EvaluationValidationError):
        evaluation_service.update_evaluation_status(mock_client, "evaluator-1", uuid4(), "FINALIZED")


# ============================================================
# Routes
# ============================================================


def test_list_evaluations_requires_evaluator_capability():
    with authenticated_as("FACULTY", user_id="faculty-a"), _no_capabilities():
        response = client.get("/api/v1/faculty/evaluations", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_list_evaluations_requires_faculty_role():
    with authenticated_as("STUDENT", user_id="student-a"):
        response = client.get("/api/v1/faculty/evaluations", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_list_evaluations_unauthenticated_returns_401():
    response = client.get("/api/v1/faculty/evaluations")
    assert response.status_code == 401


def test_list_evaluations_success():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "list_my_evaluations", return_value=[]) as mock_list,
    ):
        response = client.get("/api/v1/faculty/evaluations", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json() == []
    mock_list.assert_called_once()
    assert mock_list.call_args[0][1] == "faculty-a"


def test_list_evaluations_passes_status_filter_through():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "list_my_evaluations", return_value=[]) as mock_list,
    ):
        response = client.get(
            "/api/v1/faculty/evaluations?status_filter=FINALIZED", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert mock_list.call_args[0][2] == "FINALIZED"


def test_get_evaluation_returns_404_when_not_found():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "get_evaluation_detail", return_value=None),
    ):
        response = client.get(f"/api/v1/faculty/evaluations/{uuid4()}", headers={"Authorization": "Bearer token"})
    assert response.status_code == 404


def test_get_evaluation_success():
    row = _detail_kwargs()
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "get_evaluation_detail", return_value=row),
    ):
        response = client.get(f"/api/v1/faculty/evaluations/{row['evaluation_id']}", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["status"] == "ASSIGNED"
    assert "answer_key" not in response.json()["question"]


# ============================================================
# Phase 2: GET /faculty/evaluations/{id}/rubrics (candidate rubrics)
# ============================================================


def test_list_candidate_rubrics_returns_404_when_not_found():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "list_candidate_rubrics", return_value=None),
    ):
        response = client.get(
            f"/api/v1/faculty/evaluations/{uuid4()}/rubrics", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_list_candidate_rubrics_success():
    rubric_id = str(uuid4())
    rows = [
        {
            "id": rubric_id,
            "question_id": str(uuid4()),
            "name": "Correctness",
            "description": None,
            "max_marks": "10.00",
            "status": "ACTIVE",
            "criteria": [],
        }
    ]
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "list_candidate_rubrics", return_value=rows) as mock_list,
    ):
        response = client.get(
            f"/api/v1/faculty/evaluations/{uuid4()}/rubrics", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()[0]["id"] == rubric_id
    assert mock_list.call_args[0][1] == "faculty-a"


def test_list_candidate_rubrics_requires_evaluator_capability():
    with authenticated_as("FACULTY", user_id="faculty-a"), _no_capabilities():
        response = client.get(
            f"/api/v1/faculty/evaluations/{uuid4()}/rubrics", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_service_list_candidate_rubrics_returns_none_when_assignment_not_active():
    mock_client = MagicMock()
    _mock_current_status(mock_client, "IN_PROGRESS")
    _mock_assignment_status(mock_client, "REVOKED")

    result = evaluation_service.list_candidate_rubrics(mock_client, "evaluator-1", uuid4())

    assert result is None


def test_service_list_candidate_rubrics_only_returns_active_rubrics_for_the_right_question():
    mock_client = MagicMock()
    row = {
        "id": "eval-1",
        "assignment_id": "assign-1",
        "status": "IN_PROGRESS",
        "awarded_marks": None,
        "feedback": None,
        "rubric_id": None,
        "submitted_at": None,
        "finalized_at": None,
        "finalized_by": None,
        "evaluator_assignments": {"attempt_id": "attempt-1", "question_id": "question-1", "created_at": "2026-01-01T00:00:00Z"},
    }
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = row
    _mock_assignment_status(mock_client, "ACTIVE")
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {
            "id": "rubric-1",
            "question_id": "question-1",
            "name": "Correctness",
            "description": None,
            "max_marks": "10.00",
            "status": "ACTIVE",
            "criteria": [
                {"id": "c2", "rubric_id": "rubric-1", "criterion": "B", "description": None, "max_marks": "5.00", "display_order": 1},
                {"id": "c1", "rubric_id": "rubric-1", "criterion": "A", "description": None, "max_marks": "5.00", "display_order": 0},
            ],
        }
    ]

    result = evaluation_service.list_candidate_rubrics(mock_client, "evaluator-1", uuid4())

    assert result is not None
    assert len(result) == 1
    assert result[0]["id"] == "rubric-1"
    # Criteria sorted by display_order regardless of query order.
    assert [c["id"] for c in result[0]["criteria"]] == ["c1", "c2"]


def test_save_evaluation_returns_404_when_not_found_or_not_owned():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "save_evaluation", return_value=None),
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}",
            json={"feedback": "Nice work."},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_save_evaluation_returns_409_when_finalized():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "save_evaluation", side_effect=evaluation_service.EvaluationFinalizedError()),
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}",
            json={"feedback": "too late"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_save_evaluation_returns_422_on_validation_error():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(
            evaluation_service,
            "save_evaluation",
            side_effect=evaluation_service.EvaluationValidationError("Awarded marks exceed the rubric's maximum."),
        ),
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}",
            json={"awarded_marks": "999.00"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_save_evaluation_forwards_exclude_unset_payload_only():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(
            evaluation_service,
            "save_evaluation",
            return_value={
                "evaluation_id": str(uuid4()),
                "assignment_id": str(uuid4()),
                "status": "IN_PROGRESS",
                "awarded_marks": None,
                "attempt_id": str(uuid4()),
                "question_id": str(uuid4()),
                "student_id": str(uuid4()),
                "assessment_title": "Java Fundamentals",
                "assigned_at": "2026-01-01T00:00:00Z",
            },
        ) as mock_save,
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}",
            json={"feedback": "Only feedback sent."},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    forwarded_payload = mock_save.call_args[0][3]
    assert forwarded_payload == {"feedback": "Only feedback sent."}


def test_update_status_returns_404_when_not_found():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "update_evaluation_status", return_value=None),
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}/status",
            json={"status": "IN_PROGRESS"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_update_status_returns_409_on_invalid_transition():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(
            evaluation_service,
            "update_evaluation_status",
            side_effect=evaluation_service.EvaluationInvalidStatusTransitionError("ASSIGNED", "FINALIZED"),
        ),
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}/status",
            json={"status": "FINALIZED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_update_status_rejects_assigned_target_before_reaching_the_service():
    with authenticated_as("FACULTY", user_id="faculty-a"), _as_evaluator():
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}/status",
            json={"status": "ASSIGNED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_update_status_success():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(
            evaluation_service,
            "update_evaluation_status",
            return_value={
                "evaluation_id": str(uuid4()),
                "assignment_id": str(uuid4()),
                "status": "SUBMITTED",
                "awarded_marks": "4.50",
                "attempt_id": str(uuid4()),
                "question_id": str(uuid4()),
                "student_id": str(uuid4()),
                "assessment_title": "Java Fundamentals",
                "assigned_at": "2026-01-01T00:00:00Z",
            },
        ) as mock_status,
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}/status",
            json={"status": "SUBMITTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "SUBMITTED"
    assert mock_status.call_args[0][3] == "SUBMITTED"


# ============================================================
# Phase F8.4.2: fold-in trigger after FINALIZED
# ============================================================


def test_evaluation_service_has_no_get_supabase_import():
    """evaluation_service never imports get_supabase directly -- every
    caller (including fold_in_attempt) must be handed a client, matching
    assessment_service's own established purity (see
    test_assessments.py's identical assertion)."""
    assert not hasattr(evaluation_service, "get_supabase")


def test_faculty_evaluations_route_has_get_supabase_import():
    """app.api.faculty_evaluations DOES import get_supabase as of F8.4.2
    -- the one place in this module allowed to construct a service-role
    client, and only after a user-scoped transition has already
    committed. Mirrors test_attempts.py's identical assertion for
    app.api.attempts."""
    from app.api import faculty_evaluations as faculty_evaluations_routes

    assert hasattr(faculty_evaluations_routes, "get_supabase")


def _finalized_summary(**overrides) -> dict:
    row = {
        "evaluation_id": str(uuid4()),
        "assignment_id": str(uuid4()),
        "status": "FINALIZED",
        "awarded_marks": "7.00",
        "attempt_id": str(uuid4()),
        "question_id": str(uuid4()),
        "student_id": str(uuid4()),
        "assessment_title": "Java Fundamentals",
        "assigned_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_update_status_finalized_triggers_fold_in():
    """Reaching FINALIZED -- whether by a real transition or an
    idempotent re-send -- must invoke evaluation_service.fold_in_attempt
    for the evaluation's own attempt_id, via get_supabase()'s return
    value, never the caller's own RLS-scoped client."""
    row = _finalized_summary()
    sentinel_service_client = MagicMock()
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "update_evaluation_status", return_value=row),
        patch("app.api.faculty_evaluations.get_supabase", return_value=sentinel_service_client),
        patch.object(evaluation_service, "fold_in_attempt") as mock_fold_in,
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}/status",
            json={"status": "FINALIZED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "FINALIZED"
    mock_fold_in.assert_called_once_with(sentinel_service_client, row["attempt_id"])


def test_update_status_non_finalized_does_not_trigger_fold_in():
    """A transition to SUBMITTED (or IN_PROGRESS) must never invoke the
    fold-in trigger -- only reaching FINALIZED does."""
    row = _finalized_summary(status="SUBMITTED")
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "update_evaluation_status", return_value=row),
        patch("app.api.faculty_evaluations.get_supabase", return_value=MagicMock()),
        patch.object(evaluation_service, "fold_in_attempt") as mock_fold_in,
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}/status",
            json={"status": "SUBMITTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    mock_fold_in.assert_not_called()


def test_update_status_finalized_fold_in_not_eligible_returns_200_silently():
    """EvaluationFoldInNotEligibleError (the attempt is not yet
    COMPLETED, SQLSTATE 55000) is benign, not a failure -- see
    evaluation_service.EvaluationFoldInNotEligibleError's own docstring.
    The endpoint must still return 200: the evaluation itself genuinely
    finalized, there is simply nothing yet to fold in."""
    row = _finalized_summary()
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "update_evaluation_status", return_value=row) as mock_status,
        patch("app.api.faculty_evaluations.get_supabase", return_value=MagicMock()),
        patch.object(
            evaluation_service, "fold_in_attempt", side_effect=evaluation_service.EvaluationFoldInNotEligibleError()
        ),
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}/status",
            json={"status": "FINALIZED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "FINALIZED"
    mock_status.assert_called_once()


def test_update_status_finalized_fold_in_failure_returns_500_but_evaluation_stays_finalized():
    """If fold_in_attempt raises, the endpoint must surface a 500
    (never swallow the error silently) while making clear in the detail
    message that the evaluation itself is already safely finalized and
    that retrying is the correct recovery -- see
    app.api.faculty_evaluations.update_evaluation_status's own
    docstring for the full contract. Critically, the underlying
    evaluation_service.update_evaluation_status call (the actual
    FINALIZED write) already succeeded and is never retried or undone by
    this failure -- only the separate fold-in call failed."""
    row = _finalized_summary()
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_evaluator(),
        patch.object(evaluation_service, "update_evaluation_status", return_value=row) as mock_status,
        patch("app.api.faculty_evaluations.get_supabase", return_value=MagicMock()),
        patch.object(evaluation_service, "fold_in_attempt", side_effect=APIError({"message": "boom"})),
    ):
        response = client.patch(
            f"/api/v1/faculty/evaluations/{uuid4()}/status",
            json={"status": "FINALIZED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 500
    assert "finalized successfully" in response.json()["detail"]
    assert "try again" in response.json()["detail"].lower()
    mock_status.assert_called_once()


def test_fold_in_attempt_invokes_the_rpc_with_the_service_client():
    """evaluation_service.fold_in_attempt is a pure trigger: it must call
    exactly fold_in_attempt_evaluation via .rpc(...).execute() on
    whatever client it is handed, and return nothing meaningful for the
    caller to (mis)interpret."""
    mock_client = MagicMock()
    attempt_id = uuid4()
    result = evaluation_service.fold_in_attempt(mock_client, attempt_id)
    mock_client.rpc.assert_called_once_with("fold_in_attempt_evaluation", {"p_attempt_id": str(attempt_id)})
    mock_client.rpc.return_value.execute.assert_called_once()
    assert result is None


def test_fold_in_attempt_maps_not_completed_attempt_error():
    """SQLSTATE 55000 (the attempt is not yet COMPLETED) must translate
    to the typed, benign EvaluationFoldInNotEligibleError -- never a raw
    APIError, and never silently swallowed here (the route layer decides
    how to respond, not this function)."""
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "55000", "message": "Attempt is not eligible for evaluation fold-in."}
    )
    with pytest.raises(evaluation_service.EvaluationFoldInNotEligibleError):
        evaluation_service.fold_in_attempt(mock_client, uuid4())


def test_fold_in_attempt_reraises_other_api_errors_untouched():
    """Any other APIError code is a genuine, unexpected failure and must
    propagate as-is, never mapped to EvaluationFoldInNotEligibleError."""
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError({"code": "XX000", "message": "boom"})
    with pytest.raises(APIError):
        evaluation_service.fold_in_attempt(mock_client, uuid4())
