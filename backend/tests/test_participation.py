"""Targeted tests for the shared Participation Workspace domain
(app.services.participation_*, database/migrations/062-065).

Service-level tests drive the functions with a MagicMock Supabase client,
matching the shape of tests/test_internship_workspace_provisioning.py.
Route tests confirm role guards and wiring, matching
tests/test_workshop_applications.py.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    participation_evaluation_service as eval_service,
)
from app.services import (
    participation_program_service as program_service,
)
from app.services import (
    participation_workspace_service as workspace_service,
)
from tests.conftest import authenticated_as

client = TestClient(app)


# ============================================================
# Auth / role guards
# ============================================================


def test_industry_routes_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.get(
                "/api/v1/participation/workspaces", headers={"Authorization": "Bearer token"}
            )
        assert resp.status_code == 403, role


def test_student_routes_forbid_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.get(
                "/api/v1/student/participation/workspaces", headers={"Authorization": "Bearer token"}
            )
        assert resp.status_code == 403, role


# ============================================================
# Program: exactly-one-opportunity validation (schema level)
# ============================================================


def test_program_create_rejects_mismatched_opportunity_id():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        resp = client.post(
            "/api/v1/participation/programs",
            json={"kind": "PROJECT", "training_id": str(uuid4()), "title": "x"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_program_create_rejects_missing_opportunity_id():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        resp = client.post(
            "/api/v1/participation/programs",
            json={"kind": "WORKSHOP", "title": "x"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_program_conflicts_when_one_already_exists():
    fake_client = MagicMock()
    with (
        patch.object(program_service, "_own_opportunity", return_value=True),
        patch.object(program_service, "get_program_for_opportunity", return_value={"id": "existing"}),
    ):
        try:
            program_service.create_program(
                fake_client, "industry-1", {"kind": "PROJECT", "project_id": "p1", "title": "x"}
            )
            raised = False
        except program_service.ProgramAlreadyExistsError:
            raised = True
    assert raised


# ============================================================
# Workspace: eligibility + idempotent ensure
# ============================================================


def test_ensure_workspace_rejects_ineligible_application_status():
    workspaces_table = MagicMock()
    workspaces_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    applications_table = MagicMock()
    applications_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"id": "app-1", "industry_id": "industry-1", "status": "APPLIED"}
    )

    fake_client = MagicMock()
    fake_client.table.side_effect = lambda name: {
        "participation_workspaces": workspaces_table,
        "industry_project_applications": applications_table,
    }[name]

    try:
        workspace_service.ensure_workspace(fake_client, "industry-1", "PROJECT", "app-1")
        raised = False
    except workspace_service.ApplicationNotEligibleError as exc:
        raised = True
        assert exc.current_status == "APPLIED"
    assert raised


def test_ensure_workspace_route_maps_ineligible_to_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            workspace_service,
            "ensure_workspace",
            side_effect=workspace_service.ApplicationNotEligibleError("APPLIED"),
        ),
    ):
        resp = client.post(
            "/api/v1/participation/workspaces/ensure",
            json={"kind": "WORKSHOP", "workshop_application_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


# ============================================================
# Progress: no division by zero
# ============================================================


def test_progress_zero_published_required_assignments_is_zero_percent_not_a_crash():
    workspaces_table = MagicMock()
    workspaces_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"kind": "TRAINING", "training_id": "t1"}
    )
    programs_table = MagicMock()
    programs_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"id": "program-1"}
    )
    assignments_table = MagicMock()
    assignments_table.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    fake_client = MagicMock()
    fake_client.table.side_effect = lambda name: {
        "participation_workspaces": workspaces_table,
        "participation_programs": programs_table,
        "participation_assignments": assignments_table,
    }[name]

    result = workspace_service.get_progress(fake_client, "ws-1")
    assert result["published_required"] == 0
    assert result["percent"] == 0


# ============================================================
# Evaluation: weighted score calculation + finalize immutability
# ============================================================


def test_finalize_evaluation_requires_every_criterion_scored():
    with (
        patch.object(
            eval_service,
            "ensure_evaluation",
            return_value={"id": "eval-1", "status": "DRAFT", "scores": []},
        ),
        patch.object(
            eval_service,
            "list_criteria",
            return_value=[{"id": "c1", "name": "Technical Quality", "max_score": 10, "weight": 50}],
        ),
    ):
        try:
            eval_service.finalize_evaluation(MagicMock(), "program-1", "ws-1")
            raised = False
        except eval_service.IncompleteRubricError as exc:
            raised = True
            assert "Technical Quality" in exc.missing
    assert raised


def test_finalize_evaluation_computes_weighted_overall_score():
    fake_client = MagicMock()
    criteria = [
        {"id": "c1", "name": "Technical Quality", "max_score": 10, "weight": 60},
        {"id": "c2", "name": "Communication", "max_score": 10, "weight": 40},
    ]
    scores = [
        {"criterion_id": "c1", "score": 8},   # 80% at weight 60
        {"criterion_id": "c2", "score": 10},  # 100% at weight 40
    ]
    # weighted = (80*60 + 100*40) / 100 = 88
    with (
        patch.object(
            eval_service,
            "ensure_evaluation",
            return_value={"id": "eval-1", "status": "DRAFT", "scores": scores},
        ),
        patch.object(eval_service, "list_criteria", return_value=criteria),
        patch.object(eval_service, "get_evaluation", return_value={"id": "eval-1", "status": "FINALIZED", "overall_score": 88.0}),
    ):
        result = eval_service.finalize_evaluation(fake_client, "program-1", "ws-1")
    fake_client.table.return_value.update.assert_called_once()
    update_payload = fake_client.table.return_value.update.call_args.args[0]
    assert update_payload["overall_score"] == 88.0
    assert update_payload["status"] == "FINALIZED"
    assert result["overall_score"] == 88.0


def test_finalize_evaluation_rejects_already_finalized():
    with patch.object(
        eval_service, "ensure_evaluation", return_value={"id": "eval-1", "status": "FINALIZED", "scores": []}
    ):
        try:
            eval_service.finalize_evaluation(MagicMock(), "program-1", "ws-1")
            raised = False
        except eval_service.EvaluationFinalizedError:
            raised = True
    assert raised


# ============================================================
# Completion: requires a finalized evaluation when criteria exist
# ============================================================


def test_completion_blocked_without_finalized_evaluation_when_criteria_exist():
    with (
        patch.object(eval_service, "get_completion", return_value=None),
        patch.object(eval_service, "get_evaluation", return_value={"id": "eval-1", "status": "DRAFT"}),
        patch.object(eval_service, "list_criteria", return_value=[{"id": "c1"}]),
    ):
        try:
            eval_service.create_completion(MagicMock(), "program-1", "ws-1")
            raised = False
        except eval_service.CompletionNotAllowedError:
            raised = True
    assert raised


def test_completion_allowed_without_evaluation_when_no_criteria_defined():
    fake_client = MagicMock()
    fake_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "completion-1"}]
    with (
        patch.object(eval_service, "get_completion", return_value=None),
        patch.object(eval_service, "get_evaluation", return_value=None),
        patch.object(eval_service, "list_criteria", return_value=[]),
    ):
        eval_service.create_completion(fake_client, None, "ws-1")
    insert_payload = fake_client.table.return_value.insert.call_args.args[0]
    assert "final_evaluation_id" not in insert_payload
