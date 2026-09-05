"""Tests for Phase 2 (Evaluator Assignment + Real Evaluation Workspace)
ADMIN-facing surface:
app.api.admin_evaluator_assignments,
app.services.evaluation_service (admin_* functions),
app.services.faculty_permission_service.admin_list_eligible_evaluators.

No live Supabase project or real token is used anywhere in this file --
tests mock the auth dependency chain (see conftest.py) and the Supabase
client/service layer directly, matching the pattern established in
test_faculty_mentor_permissions.py / test_evaluations.py.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.schemas.faculty_permissions import AssessmentCapability
from app.services import evaluation_service, faculty_permission_service
from tests.conftest import authenticated_as

client = TestClient(app)


# ============================================================
# Route-layer authorization: ADMIN only, on every new route
# ============================================================


def test_list_eligible_evaluators_requires_admin():
    with authenticated_as("FACULTY", user_id="faculty-a"):
        response = client.get(
            "/api/v1/admin/evaluator-assignments/eligible-evaluators",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_list_attempts_for_assignment_requires_admin():
    with authenticated_as("FACULTY", user_id="faculty-a"):
        response = client.get(
            f"/api/v1/admin/evaluator-assignments/attempts?assessment_id={uuid4()}",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_create_assignment_requires_admin():
    with authenticated_as("FACULTY", user_id="faculty-a"):
        response = client.post(
            "/api/v1/admin/evaluator-assignments",
            json={"evaluator_id": str(uuid4()), "attempt_id": str(uuid4()), "question_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_revoke_assignment_requires_admin():
    with authenticated_as("FACULTY", user_id="faculty-a"):
        response = client.post(
            f"/api/v1/admin/evaluator-assignments/{uuid4()}/revoke",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_create_assignment_rejects_a_plain_evaluator_caller():
    """An evaluator must never be able to assign themselves or anyone
    else -- only ADMIN, regardless of holding assessment_evaluator."""
    with (
        authenticated_as("FACULTY", user_id="evaluator-a"),
        patch(
            "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
            return_value={AssessmentCapability.EVALUATOR},
        ),
    ):
        response = client.post(
            "/api/v1/admin/evaluator-assignments",
            json={"evaluator_id": "evaluator-a", "attempt_id": str(uuid4()), "question_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


# ============================================================
# Route-layer: success + error mapping
# ============================================================


def test_list_eligible_evaluators_success():
    rows = [{"faculty_id": str(uuid4()), "email": "e@example.com", "full_name": "Dr. Eval"}]
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch.object(faculty_permission_service, "admin_list_eligible_evaluators", return_value=rows),
    ):
        response = client.get(
            "/api/v1/admin/evaluator-assignments/eligible-evaluators",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json() == rows


def test_list_attempts_for_assignment_success():
    attempt_id, question_id = str(uuid4()), str(uuid4())
    rows = [
        {
            "attempt_id": attempt_id,
            "student_label": "Student 1234abcd…",
            "status": "COMPLETED",
            "questions": [
                {
                    "question_id": question_id,
                    "question_text": "Explain closures.",
                    "points": "10.00",
                    "existing_assignments": [],
                }
            ],
        }
    ]
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch("app.api.admin_evaluator_assignments.get_supabase", return_value=MagicMock()),
        patch.object(evaluation_service, "admin_list_attempts_for_assignment", return_value=rows),
    ):
        response = client.get(
            f"/api/v1/admin/evaluator-assignments/attempts?assessment_id={uuid4()}",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()[0]["attempt_id"] == attempt_id


def test_create_assignment_success():
    row = {
        "id": str(uuid4()),
        "evaluator_id": str(uuid4()),
        "attempt_id": str(uuid4()),
        "question_id": str(uuid4()),
        "status": "ACTIVE",
        "created_at": "2026-01-01T00:00:00Z",
        "revoked_at": None,
    }
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch("app.api.admin_evaluator_assignments.get_supabase", return_value=MagicMock()),
        patch.object(evaluation_service, "admin_create_assignment", return_value=row) as mock_create,
    ):
        response = client.post(
            "/api/v1/admin/evaluator-assignments",
            json={"evaluator_id": row["evaluator_id"], "attempt_id": row["attempt_id"], "question_id": row["question_id"]},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    assert response.json()["assignment_id"] == row["id"]
    assert response.json()["status"] == "ACTIVE"
    mock_create.assert_called_once()
    # created_by (last positional arg) is derived from the authenticated
    # admin -- never accepted from the request body (schema has no such
    # field at all, extra="forbid").
    assert mock_create.call_args.args[-1] == "admin-1"


def test_create_assignment_returns_422_when_evaluator_ineligible():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch("app.api.admin_evaluator_assignments.get_supabase", return_value=MagicMock()),
        patch.object(
            evaluation_service,
            "admin_create_assignment",
            side_effect=evaluation_service.EvaluatorIneligibleError("not eligible"),
        ),
    ):
        response = client.post(
            "/api/v1/admin/evaluator-assignments",
            json={"evaluator_id": str(uuid4()), "attempt_id": str(uuid4()), "question_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_assignment_returns_409_on_duplicate():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch("app.api.admin_evaluator_assignments.get_supabase", return_value=MagicMock()),
        patch.object(
            evaluation_service,
            "admin_create_assignment",
            side_effect=evaluation_service.EvaluatorAssignmentDuplicateError("already assigned"),
        ),
    ):
        response = client.post(
            "/api/v1/admin/evaluator-assignments",
            json={"evaluator_id": str(uuid4()), "attempt_id": str(uuid4()), "question_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_create_assignment_returns_422_on_invalid_target():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch("app.api.admin_evaluator_assignments.get_supabase", return_value=MagicMock()),
        patch.object(
            evaluation_service,
            "admin_create_assignment",
            side_effect=evaluation_service.InvalidAssignmentTargetError("no such attempt-question"),
        ),
    ):
        response = client.post(
            "/api/v1/admin/evaluator-assignments",
            json={"evaluator_id": str(uuid4()), "attempt_id": str(uuid4()), "question_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_assignment_rejects_unknown_body_fields():
    """extra=\"forbid\" -- created_by can never be smuggled in."""
    with authenticated_as("ADMIN", user_id="admin-1"):
        response = client.post(
            "/api/v1/admin/evaluator-assignments",
            json={
                "evaluator_id": str(uuid4()),
                "attempt_id": str(uuid4()),
                "question_id": str(uuid4()),
                "created_by": str(uuid4()),
            },
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_revoke_assignment_success():
    row = {
        "id": str(uuid4()),
        "evaluator_id": str(uuid4()),
        "attempt_id": str(uuid4()),
        "question_id": str(uuid4()),
        "status": "REVOKED",
        "created_at": "2026-01-01T00:00:00Z",
        "revoked_at": "2026-01-02T00:00:00Z",
    }
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch("app.api.admin_evaluator_assignments.get_supabase", return_value=MagicMock()),
        patch.object(evaluation_service, "admin_revoke_assignment", return_value=row) as mock_revoke,
    ):
        response = client.post(
            f"/api/v1/admin/evaluator-assignments/{row['id']}/revoke",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "REVOKED"
    assert mock_revoke.call_args.args[-1] == "admin-1"


def test_revoke_assignment_returns_404_when_not_found():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch("app.api.admin_evaluator_assignments.get_supabase", return_value=MagicMock()),
        patch.object(
            evaluation_service,
            "admin_revoke_assignment",
            side_effect=evaluation_service.EvaluatorAssignmentNotFoundError("not found"),
        ),
    ):
        response = client.post(
            f"/api/v1/admin/evaluator-assignments/{uuid4()}/revoke",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_revoke_assignment_returns_409_when_already_revoked():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch("app.api.admin_evaluator_assignments.get_supabase", return_value=MagicMock()),
        patch.object(
            evaluation_service,
            "admin_revoke_assignment",
            side_effect=evaluation_service.EvaluatorAssignmentAlreadyRevokedError("already revoked"),
        ),
    ):
        response = client.post(
            f"/api/v1/admin/evaluator-assignments/{uuid4()}/revoke",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


# ============================================================
# Service layer: faculty_permission_service.admin_list_eligible_evaluators
# ============================================================


def test_admin_list_eligible_evaluators_filters_to_granted_unexpired_evaluator_only():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value.data = [
        {
            "faculty_id": "f-author",
            "faculty_email": "a@example.com",
            "faculty_full_name": "Author Only",
            "capability": "assessment_author",
            "status": "GRANTED",
            "expires_at": None,
        },
        {
            "faculty_id": "f-eval-active",
            "faculty_email": "e1@example.com",
            "faculty_full_name": "Eval Active",
            "capability": "assessment_evaluator",
            "status": "GRANTED",
            "expires_at": None,
        },
        {
            "faculty_id": "f-eval-expired",
            "faculty_email": "e2@example.com",
            "faculty_full_name": "Eval Expired",
            "capability": "assessment_evaluator",
            "status": "GRANTED",
            "expires_at": "2000-01-01T00:00:00Z",
        },
        {
            "faculty_id": "f-eval-revoked",
            "faculty_email": "e3@example.com",
            "faculty_full_name": "Eval Revoked",
            "capability": "assessment_evaluator",
            "status": "REVOKED",
            "expires_at": None,
        },
    ]

    result = faculty_permission_service.admin_list_eligible_evaluators(mock_client)

    assert [r["faculty_id"] for r in result] == ["f-eval-active"]


def test_admin_list_eligible_evaluators_maps_authorization_error():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError({"code": "42501", "message": "not admin"})


    with pytest.raises(faculty_permission_service.AdminAuthorizationError):
        faculty_permission_service.admin_list_eligible_evaluators(mock_client)


# ============================================================
# Service layer: evaluation_service admin_* functions
# ============================================================


def test_admin_create_assignment_rejects_ineligible_evaluator_before_any_write():
    user_client = MagicMock()
    service_client = MagicMock()
    user_client.rpc.return_value.execute.return_value.data = False


    with pytest.raises(evaluation_service.EvaluatorIneligibleError):
        evaluation_service.admin_create_assignment(
            user_client, service_client, str(uuid4()), uuid4(), uuid4(), "admin-1"
        )
    service_client.rpc.assert_not_called()


def test_admin_create_assignment_maps_duplicate_error():
    user_client = MagicMock()
    service_client = MagicMock()
    user_client.rpc.return_value.execute.return_value.data = True
    service_client.rpc.return_value.execute.side_effect = APIError({"code": "23505", "message": "duplicate"})


    with pytest.raises(evaluation_service.EvaluatorAssignmentDuplicateError):
        evaluation_service.admin_create_assignment(
            user_client, service_client, str(uuid4()), uuid4(), uuid4(), "admin-1"
        )


def test_admin_create_assignment_maps_invalid_target_errors():
    user_client = MagicMock()
    service_client = MagicMock()
    user_client.rpc.return_value.execute.return_value.data = True


    for code in ("42501", "P0002"):
        service_client.rpc.return_value.execute.side_effect = APIError({"code": code, "message": "bad target"})
        with pytest.raises(evaluation_service.InvalidAssignmentTargetError):
            evaluation_service.admin_create_assignment(
                user_client, service_client, str(uuid4()), uuid4(), uuid4(), "admin-1"
            )


def test_admin_create_assignment_success_calls_rpc_with_correct_args():
    user_client = MagicMock()
    service_client = MagicMock()
    user_client.rpc.return_value.execute.return_value.data = True
    row = {
        "id": str(uuid4()),
        "evaluator_id": "eval-1",
        "attempt_id": "attempt-1",
        "question_id": "question-1",
        "status": "ACTIVE",
        "created_at": "2026-01-01T00:00:00Z",
        "revoked_at": None,
    }
    service_client.rpc.return_value.execute.return_value.data = row

    result = evaluation_service.admin_create_assignment(
        user_client, service_client, "eval-1", "attempt-1", "question-1", "admin-1"
    )

    assert result == row
    service_client.rpc.assert_called_once_with(
        "create_evaluator_assignment",
        {
            "p_evaluator_id": "eval-1",
            "p_attempt_id": "attempt-1",
            "p_question_id": "question-1",
            "p_created_by": "admin-1",
        },
    )


def test_admin_revoke_assignment_maps_not_found():
    service_client = MagicMock()
    service_client.rpc.return_value.execute.side_effect = APIError({"code": "P0002", "message": "not found"})


    with pytest.raises(evaluation_service.EvaluatorAssignmentNotFoundError):
        evaluation_service.admin_revoke_assignment(service_client, uuid4(), "admin-1")


def test_admin_revoke_assignment_maps_already_revoked():
    service_client = MagicMock()
    service_client.rpc.return_value.execute.side_effect = APIError({"code": "55000", "message": "already revoked"})


    with pytest.raises(evaluation_service.EvaluatorAssignmentAlreadyRevokedError):
        evaluation_service.admin_revoke_assignment(service_client, uuid4(), "admin-1")


def test_admin_list_attempts_for_assignment_only_includes_ai_evaluated_questions():
    service_client = MagicMock()
    attempt_id, ai_question_id, objective_question_id = "a1", "q-ai", "q-obj"
    service_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": attempt_id, "student_id": "student-1", "status": "COMPLETED"}
    ]

    def table_side_effect(name):
        mock_table = MagicMock()
        if name == "assessment_attempt_questions":
            mock_table.select.return_value.in_.return_value.execute.return_value.data = [
                {
                    "attempt_id": attempt_id,
                    "question_id": ai_question_id,
                    "assessment_questions": {
                        "id": ai_question_id,
                        "question_text": "Explain closures.",
                        "points": "10.00",
                        "scoring_method": "AI_EVALUATED",
                    },
                },
                {
                    "attempt_id": attempt_id,
                    "question_id": objective_question_id,
                    "assessment_questions": {
                        "id": objective_question_id,
                        "question_text": "2 + 2 = ?",
                        "points": "5.00",
                        "scoring_method": "OBJECTIVE",
                    },
                },
            ]
        elif name == "evaluator_assignments":
            mock_table.select.return_value.in_.return_value.execute.return_value.data = []
        else:
            mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                {"id": attempt_id, "student_id": "student-1", "status": "COMPLETED"}
            ]
        return mock_table

    service_client.table.side_effect = table_side_effect

    result = evaluation_service.admin_list_attempts_for_assignment(service_client, uuid4())

    assert len(result) == 1
    assert len(result[0]["questions"]) == 1
    assert result[0]["questions"][0]["question_id"] == ai_question_id
    assert result[0]["student_label"] == "Student student-…"


def test_admin_list_attempts_for_assignment_omits_attempts_with_no_ai_evaluated_question():
    service_client = MagicMock()

    def table_side_effect(name):
        mock_table = MagicMock()
        if name == "assessment_attempts":
            mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                {"id": "a1", "student_id": "student-1", "status": "COMPLETED"}
            ]
        elif name == "assessment_attempt_questions":
            mock_table.select.return_value.in_.return_value.execute.return_value.data = [
                {
                    "attempt_id": "a1",
                    "question_id": "q-obj",
                    "assessment_questions": {
                        "id": "q-obj",
                        "question_text": "2 + 2 = ?",
                        "points": "5.00",
                        "scoring_method": "OBJECTIVE",
                    },
                }
            ]
        else:
            mock_table.select.return_value.in_.return_value.execute.return_value.data = []
        return mock_table

    service_client.table.side_effect = table_side_effect

    result = evaluation_service.admin_list_attempts_for_assignment(service_client, uuid4())

    assert result == []
