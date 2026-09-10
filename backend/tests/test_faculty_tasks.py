"""Tests for the deterministic Faculty task/recommendation surface:
GET /api/v1/faculty/tasks and app.services.faculty_recommendation_service.

No live Supabase project or real token is used anywhere in this file --
service tests mock the three canonical sources this module composes over
(question_bank_service, evaluation_service, faculty_student_mentorship_service),
matching the existing pattern in test_student_recommendations.py. Route
tests mock the service layer directly and use tests.conftest.authenticated_as.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.faculty_permissions import AssessmentCapability
from app.services import faculty_recommendation_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_URL = "/api/v1/faculty/tasks"


# ============================================================
# Auth / role
# ============================================================


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_read_faculty_tasks(role):
    with authenticated_as(role):
        response = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_rejects_unauthenticated():
    assert client.get(_URL).status_code == 401


# ============================================================
# Route: composition + response shape
# ============================================================


def _patched(*, capabilities=None, tasks=None):
    return (
        patch(
            "app.api.faculty.faculty_permission_service.get_effective_capabilities",
            return_value=capabilities or set(),
        ),
        patch(
            "app.api.faculty.faculty_recommendation_service.get_faculty_tasks",
            return_value=tasks
            or {"pending_reviews": [], "pending_evaluations": [], "mentorship_attention": []},
        ),
    )


def test_returns_empty_categories_honestly():
    cap, tasks = _patched()
    with authenticated_as("FACULTY"), cap, tasks:
        response = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "pending_reviews": [],
        "pending_evaluations": [],
        "mentorship_attention": [],
        "pending_reconciliations": [],
    }


def test_returns_populated_categories():
    tasks = {
        "pending_reviews": [
            {
                "question_id": "q-1",
                "assessment_id": "a-1",
                "question_text": "What is a closure?",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
        "pending_evaluations": [
            {
                "evaluation_id": "e-1",
                "attempt_id": "at-1",
                "assessment_title": "Python Basics",
                "status": "ASSIGNED",
                "assigned_at": "2026-01-02T00:00:00Z",
            }
        ],
        "mentorship_attention": [
            {
                "mentorship_id": "m-1",
                "student_id": "s-1",
                "student_name": "Jane Doe",
                "status": "REQUESTED",
                "reason": "Awaiting your response to a student's mentorship request.",
                "updated_at": "2026-01-03T00:00:00Z",
            }
        ],
    }
    cap, tasks_patch = _patched(tasks=tasks)
    with authenticated_as("FACULTY"), cap, tasks_patch:
        response = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()
    assert body["pending_reviews"][0]["question_id"] == "q-1"
    assert body["pending_evaluations"][0]["status"] == "ASSIGNED"
    assert body["mentorship_attention"][0]["status"] == "REQUESTED"


def test_route_passes_capabilities_and_current_user_id_to_the_service():
    seen = {}

    def fake_get_tasks(_client, faculty_id, capabilities):
        seen["faculty_id"] = faculty_id
        seen["capabilities"] = capabilities
        return {"pending_reviews": [], "pending_evaluations": [], "mentorship_attention": []}

    with (
        authenticated_as("FACULTY", user_id="the-caller"),
        patch(
            "app.api.faculty.faculty_permission_service.get_effective_capabilities",
            return_value={AssessmentCapability.REVIEWER},
        ),
        patch("app.api.faculty.faculty_recommendation_service.get_faculty_tasks", side_effect=fake_get_tasks),
    ):
        response = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert seen["faculty_id"] == "the-caller"
    assert seen["capabilities"] == {AssessmentCapability.REVIEWER}


def test_unexpected_service_error_returns_500_not_a_crash():
    with (
        authenticated_as("FACULTY"),
        patch(
            "app.api.faculty.faculty_permission_service.get_effective_capabilities",
            side_effect=RuntimeError("boom"),
        ),
    ):
        response = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert response.status_code == 500
    assert "boom" not in response.text


# ============================================================
# Service: list_pending_reviews
# ============================================================


def _question(**overrides):
    row = {
        "id": "q-1",
        "assessment_id": "a-1",
        "question_text": "What is a closure?",
        "review_status": "PENDING",
        "created_by": "other-faculty",
        "created_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_list_pending_reviews_excludes_own_questions():
    """A reviewer's own PENDING question must never appear in their own
    review queue -- mirrors the backend's own self-review block."""
    from app.services import question_bank_service as qb_svc

    with patch.object(
        qb_svc,
        "list_my_questions",
        return_value=[_question(created_by="me"), _question(created_by="other-faculty")],
    ):
        result = svc.list_pending_reviews(object(), "me")
    assert len(result) == 1
    assert result[0]["question_id"] == "q-1"


def test_list_pending_reviews_excludes_non_pending():
    from app.services import question_bank_service as qb_svc

    with patch.object(
        qb_svc,
        "list_my_questions",
        return_value=[_question(review_status="APPROVED"), _question(review_status="REJECTED")],
    ):
        result = svc.list_pending_reviews(object(), "me")
    assert result == []


def test_list_pending_reviews_sorts_oldest_first():
    from app.services import question_bank_service as qb_svc

    with patch.object(
        qb_svc,
        "list_my_questions",
        return_value=[
            _question(assessment_id="new", created_at="2026-01-03T00:00:00Z"),
            _question(assessment_id="old", created_at="2026-01-01T00:00:00Z"),
        ],
    ):
        result = svc.list_pending_reviews(object(), "me")
    assert [r["assessment_id"] for r in result] == ["old", "new"]


# ============================================================
# Service: list_pending_evaluations
# ============================================================


def _evaluation(**overrides):
    row = {
        "evaluation_id": "e-1",
        "attempt_id": "at-1",
        "assessment_title": "Python Basics",
        "status": "ASSIGNED",
        "assigned_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_list_pending_evaluations_includes_assigned_and_in_progress():
    from app.services import evaluation_service as eval_svc

    with patch.object(
        eval_svc,
        "list_my_evaluations",
        return_value=[
            _evaluation(evaluation_id="e-assigned", status="ASSIGNED"),
            _evaluation(evaluation_id="e-in-progress", status="IN_PROGRESS"),
        ],
    ):
        result = svc.list_pending_evaluations(object(), "evaluator-1")
    assert {r["evaluation_id"] for r in result} == {"e-assigned", "e-in-progress"}


def test_list_pending_evaluations_excludes_submitted_and_finalized():
    from app.services import evaluation_service as eval_svc

    with patch.object(
        eval_svc,
        "list_my_evaluations",
        return_value=[
            _evaluation(status="SUBMITTED"),
            _evaluation(status="FINALIZED"),
        ],
    ):
        result = svc.list_pending_evaluations(object(), "evaluator-1")
    assert result == []


def test_list_pending_evaluations_sorts_oldest_assigned_first():
    from app.services import evaluation_service as eval_svc

    with patch.object(
        eval_svc,
        "list_my_evaluations",
        return_value=[
            _evaluation(evaluation_id="new", assigned_at="2026-01-05T00:00:00Z"),
            _evaluation(evaluation_id="old", assigned_at="2026-01-01T00:00:00Z"),
        ],
    ):
        result = svc.list_pending_evaluations(object(), "evaluator-1")
    assert [r["evaluation_id"] for r in result] == ["old", "new"]


# ============================================================
# Service: list_mentorships_needing_attention
# ============================================================


def _mentorship(**overrides):
    row = {
        "id": "m-1",
        "faculty_id": "me",
        "student_id": "s-1",
        "requested_by": "s-1",
        "status": "REQUESTED",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_mentorships_needing_attention_includes_student_requested_and_accepted():
    from app.services import faculty_student_mentorship_service as m_svc

    with patch.object(
        m_svc,
        "list_for_faculty",
        return_value=[
            _mentorship(id="m-requested", status="REQUESTED", requested_by="s-1"),
            _mentorship(id="m-accepted", status="ACCEPTED", student_id="s-2"),
        ],
    ):
        mock_client = _mock_profiles_client({"s-1": "Alice", "s-2": "Bob"})
        result = svc.list_mentorships_needing_attention(mock_client, "me")
    assert {r["mentorship_id"] for r in result} == {"m-requested", "m-accepted"}


def test_mentorships_needing_attention_excludes_self_requested():
    """A mentorship the FACULTY member themselves requested is not
    'awaiting my decision' -- it's awaiting the student's."""
    from app.services import faculty_student_mentorship_service as m_svc

    with patch.object(
        m_svc, "list_for_faculty", return_value=[_mentorship(status="REQUESTED", requested_by="me")]
    ):
        result = svc.list_mentorships_needing_attention(_mock_profiles_client({}), "me")
    assert result == []


def test_mentorships_needing_attention_excludes_terminal_and_active_statuses():
    from app.services import faculty_student_mentorship_service as m_svc

    with patch.object(
        m_svc,
        "list_for_faculty",
        return_value=[
            _mentorship(status="ACTIVE"),
            _mentorship(status="DECLINED"),
            _mentorship(status="WITHDRAWN"),
            _mentorship(status="COMPLETED"),
            _mentorship(status="ENDED"),
        ],
    ):
        result = svc.list_mentorships_needing_attention(_mock_profiles_client({}), "me")
    assert result == []


def test_mentorships_needing_attention_ranks_requested_before_accepted():
    from app.services import faculty_student_mentorship_service as m_svc

    with patch.object(
        m_svc,
        "list_for_faculty",
        return_value=[
            _mentorship(id="m-accepted", status="ACCEPTED", student_id="s-1", updated_at="2026-01-01T00:00:00Z"),
            _mentorship(id="m-requested", status="REQUESTED", requested_by="s-2", student_id="s-2", updated_at="2026-01-05T00:00:00Z"),
        ],
    ):
        result = svc.list_mentorships_needing_attention(_mock_profiles_client({"s-1": "A", "s-2": "B"}), "me")
    assert [r["mentorship_id"] for r in result] == ["m-requested", "m-accepted"]


def _mock_profiles_client(name_by_student_id: dict):
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    rows = [{"id": sid, "full_name": name, "username": None} for sid, name in name_by_student_id.items()]
    mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value.data = rows
    return mock_client


# ============================================================
# get_faculty_tasks: capability gating
# ============================================================


def test_get_faculty_tasks_skips_reviews_without_reviewer_capability():
    from app.services import question_bank_service as qb_svc

    with patch.object(qb_svc, "list_my_questions") as mocked:
        result = svc.get_faculty_tasks(_mock_profiles_client({}), "me", set())
    mocked.assert_not_called()
    assert result["pending_reviews"] == []


def test_get_faculty_tasks_skips_evaluations_without_evaluator_capability():
    from app.services import evaluation_service as eval_svc

    with patch.object(eval_svc, "list_my_evaluations") as mocked:
        result = svc.get_faculty_tasks(_mock_profiles_client({}), "me", set())
    mocked.assert_not_called()
    assert result["pending_evaluations"] == []


def test_get_faculty_tasks_includes_reviews_with_reviewer_capability():
    from app.services import question_bank_service as qb_svc

    with patch.object(qb_svc, "list_my_questions", return_value=[_question(created_by="other")]):
        result = svc.get_faculty_tasks(_mock_profiles_client({}), "me", {AssessmentCapability.REVIEWER})
    assert len(result["pending_reviews"]) == 1


def test_get_faculty_tasks_skips_reconciliations_without_moderator_capability():
    from app.services import reconciliation_service as recon_svc

    with patch.object(recon_svc, "list_cases") as mocked:
        result = svc.get_faculty_tasks(_mock_profiles_client({}), "me", set())
    mocked.assert_not_called()
    assert result["pending_reconciliations"] == []


def test_get_faculty_tasks_includes_reconciliations_with_moderator_capability():
    from app.services import reconciliation_service as recon_svc

    case = {
        "attempt_id": "at-1",
        "assessment_id": "a-1",
        "assessment_title": "Python Basics",
        "student_label": "Student abcd1234",
        "question_id": "q-1",
        "question_text": "Explain closures.",
        "points": "10.00",
    }
    with patch.object(recon_svc, "list_cases", return_value=[case]):
        result = svc.get_faculty_tasks(_mock_profiles_client({}), "me", {AssessmentCapability.MODERATOR})
    assert result["pending_reconciliations"] == [case]


def test_get_faculty_tasks_never_writes_and_has_no_service_role():
    import inspect

    assert not hasattr(svc, "get_supabase")
    source = inspect.getsource(svc)
    for banned in (".insert(", ".update(", ".upsert(", ".delete("):
        assert banned not in source, f"faculty_recommendation_service must not {banned}"
