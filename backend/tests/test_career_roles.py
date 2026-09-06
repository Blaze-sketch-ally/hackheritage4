"""Tests for the Career Role / Skill Gap API (Phase 1L):
app.services.assessment_service.get_student_skill_scores,
app.services.career_role_service, and the /career-roles routes.

No live Supabase project or real token is used anywhere in this file --
the auth dependency chain is mocked (see conftest.py), and the Supabase
client/service layer is mocked directly, matching the existing pattern in
test_assessments.py.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import assessment_service, career_role_service
from app.services.skill_alignment_service import SkillRequirement
from tests.conftest import authenticated_as

client = TestClient(app)


# ============================================================
# get_student_skill_scores (Phase 1L, assessment_service.py)
# ============================================================


def _completed_attempt_row(
    skill_id: str,
    percentage: str,
    evaluation_status: str = "NOT_REQUIRED",
    final_percentage: str | None = None,
):
    return {
        "percentage": percentage,
        "evaluation_status": evaluation_status,
        "final_percentage": final_percentage,
        "assessment": {"skill_id": skill_id},
    }


def _mock_rows(mock_client, rows):
    response = MagicMock()
    response.data = rows
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute
    ).return_value = response


def test_skill_scores_only_from_completed_attempts():
    """Case 10: an IN_PROGRESS/ABANDONED attempt must never contribute --
    this is enforced by the .eq('status', 'COMPLETED') filter itself, so
    this test verifies that filter is actually applied."""
    mock_client = MagicMock()
    _mock_rows(mock_client, [_completed_attempt_row("skill-1", "80.00")])

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    mock_client.table.assert_called_with("assessment_attempts")
    status_filter_call = mock_client.table.return_value.select.return_value.eq.call_args_list[0]
    assert status_filter_call.args == ("student_id", "student-1")
    assert scores == {"skill-1": Decimal("80.00")}


def test_skill_scores_takes_best_of_multiple_completed_attempts():
    """Case 9: multiple completed attempts for the same skill -> the
    documented 'best percentage' behavior, not the most recent or an
    average."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [
            _completed_attempt_row("skill-1", "55.00"),
            _completed_attempt_row("skill-1", "90.00"),
            _completed_attempt_row("skill-1", "70.00"),
        ],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-1": Decimal("90.00")}


def test_skill_scores_excludes_rows_with_deactivated_assessment_embed():
    """A None 'assessment' embed (parent assessment deactivated after
    completion) is excluded from the aggregate, not treated as a crash --
    see the function's own docstring for why this differs from
    get_attempt_result_rows()'s hard-failure behavior."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [
            {"percentage": "80.00", "evaluation_status": "NOT_REQUIRED", "final_percentage": None, "assessment": None},
            _completed_attempt_row("skill-2", "60.00"),
        ],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-2": Decimal("60.00")}


def test_skill_scores_empty_when_no_completed_attempts():
    mock_client = MagicMock()
    _mock_rows(mock_client, [])

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {}


# ------------------------------------------------------------
# F8.4 eligibility: NOT_REQUIRED/COMPLETE contribute, everything else
# (PENDING/PARTIAL/NEEDS_RECONCILIATION/unknown) is excluded -- see
# get_student_skill_scores()'s own docstring for the full contract.
# ------------------------------------------------------------


def test_skill_scores_objective_only_uses_percentage():
    """Test 1: COMPLETED + NOT_REQUIRED + percentage 80 -> skill score 80."""
    mock_client = MagicMock()
    _mock_rows(mock_client, [_completed_attempt_row("skill-1", "80.00", "NOT_REQUIRED")])

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-1": Decimal("80.00")}


def test_skill_scores_ai_pending_excluded_despite_high_raw_percentage():
    """Test 2: COMPLETED + PENDING + raw percentage 100 -> excluded
    entirely. This is exactly the bug this fix closes -- an all-
    AI_EVALUATED attempt's raw percentage is hard-coded to 100 by
    score_assessment_attempt() (048) and must never be read as if it
    were a real result."""
    mock_client = MagicMock()
    _mock_rows(mock_client, [_completed_attempt_row("skill-1", "100.00", "PENDING")])

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {}


def test_skill_scores_ai_finalized_uses_final_percentage_not_raw():
    """Test 3: COMPLETED + COMPLETE + percentage 100 + final_percentage 75
    -> skill score 75. The raw percentage must never be used once
    evaluation_status is COMPLETE."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [_completed_attempt_row("skill-1", "100.00", "COMPLETE", "75.00")],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-1": Decimal("75.00")}


def test_skill_scores_mixed_finalized_uses_final_percentage():
    """Test 4: mixed assessment, COMPLETE, final_percentage 82 -> 82."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [_completed_attempt_row("skill-1", "60.00", "COMPLETE", "82.00")],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-1": Decimal("82.00")}


def test_skill_scores_partial_evaluation_excluded():
    """Test 5: COMPLETED + PARTIAL -> excluded."""
    mock_client = MagicMock()
    _mock_rows(mock_client, [_completed_attempt_row("skill-1", "90.00", "PARTIAL")])

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {}


def test_skill_scores_needs_reconciliation_excluded():
    """Test 6: COMPLETED + NEEDS_RECONCILIATION -> excluded, even though
    the row may still carry a stale raw percentage."""
    mock_client = MagicMock()
    _mock_rows(mock_client, [_completed_attempt_row("skill-1", "90.00", "NEEDS_RECONCILIATION")])

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {}


def test_skill_scores_incomplete_attempt_excluded_by_status_filter():
    """Test 7: an IN_PROGRESS/ABANDONED attempt never reaches this
    function's rows at all -- the .eq('status', 'COMPLETED') filter
    (asserted in test_skill_scores_only_from_completed_attempts) is what
    excludes it; this test documents the expectation for a fully mocked
    'no COMPLETED rows returned' scenario."""
    mock_client = MagicMock()
    _mock_rows(mock_client, [])

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {}


def test_skill_scores_multiple_attempts_best_score_behavior_unchanged():
    """Test 8: several eligible attempts for the same skill -> existing
    best-score behavior is unaffected by the eligibility fix."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [
            _completed_attempt_row("skill-1", "50.00", "NOT_REQUIRED"),
            _completed_attempt_row("skill-1", "65.00", "COMPLETE", "65.00"),
        ],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-1": Decimal("65.00")}


def test_skill_scores_pending_attempt_never_beats_eligible_lower_score():
    """Test 9: an eligible attempt at 70 alongside a PENDING attempt whose
    raw percentage is 100 -> result is 70, not 100. Directly matches the
    worked example in the task's own eligibility rule."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [
            _completed_attempt_row("skill-1", "70.00", "NOT_REQUIRED"),
            _completed_attempt_row("skill-1", "100.00", "PENDING"),
        ],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-1": Decimal("70.00")}


def test_skill_scores_finalized_result_contributes_regardless_of_revocation():
    """Test 10: the service only ever reads the attempt row itself --
    there is no evaluator_assignments join or check here, so a FINALIZED/
    folded-in result contributes exactly the same whether or not the
    evaluator who produced it was later revoked (revocation never
    touches evaluation_status/final_percentage -- see
    fold_in_attempt_evaluation()'s own eligibility join, 049)."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [_completed_attempt_row("skill-1", "40.00", "COMPLETE", "88.00")],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-1": Decimal("88.00")}
    mock_client.table.assert_called_with("assessment_attempts")


def test_skill_scores_co_evaluation_agreement_contributes_final_percentage():
    """Test 11: co-evaluators agreeing resolves to a single COMPLETE
    result with one final_percentage -- indistinguishable, from this
    function's point of view, from any other COMPLETE row."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [_completed_attempt_row("skill-1", "50.00", "COMPLETE", "77.00")],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-1": Decimal("77.00")}


def test_skill_scores_unexpected_evaluation_status_safely_excluded():
    """Test 12: an unrecognized/unexpected evaluation_status value (which
    the DB's own NOT NULL + CHECK constraint should never actually
    produce, but this function must not trust the JSON boundary blindly)
    is excluded, never treated as NOT_REQUIRED."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [{"percentage": "99.00", "evaluation_status": "SOMETHING_UNEXPECTED", "final_percentage": None, "assessment": {"skill_id": "skill-1"}}],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {}


def test_skill_scores_null_evaluation_status_safely_excluded():
    """Test 12b: a null evaluation_status (should never happen given the
    NOT NULL DEFAULT, but defensively excluded rather than assumed
    NOT_REQUIRED)."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [{"percentage": "99.00", "evaluation_status": None, "final_percentage": None, "assessment": {"skill_id": "skill-1"}}],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {}


def test_skill_scores_complete_with_null_final_percentage_safely_excluded():
    """Defense in depth: even if evaluation_status somehow says COMPLETE
    while final_percentage is null (the DB CHECK constraint should make
    this impossible), the row is excluded rather than crashing or
    silently contributing a null-derived value."""
    mock_client = MagicMock()
    _mock_rows(
        mock_client,
        [_completed_attempt_row("skill-1", "99.00", "COMPLETE", None)],
    )

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {}


# ============================================================
# career_role_service
# ============================================================


def test_get_career_role_requirements_skips_deactivated_skill_embed():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [
        {"skill_id": "s1", "required_level": "70.00", "weight": "1.00", "skill": {"name": "Python"}},
        {"skill_id": "s2", "required_level": "60.00", "weight": "1.00", "skill": None},
    ]
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = response

    requirements = career_role_service.get_career_role_requirements(mock_client, uuid4())

    assert len(requirements) == 1
    assert requirements[0] == SkillRequirement(
        skill_id="s1", skill_name="Python", required_level=Decimal("70.00"), weight=Decimal("1.00")
    )


# ============================================================
# API: GET /career-roles, GET /career-roles/{id}
# ============================================================


def _role_row(**overrides):
    row = {
        "id": str(uuid4()),
        "title": "Software Engineer",
        "description": "Builds backend and full-stack applications.",
        "category": "Engineering",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_list_career_roles_requires_authentication():
    response = client.get("/api/v1/career-roles")
    assert response.status_code == 401


def test_list_career_roles_authenticated_student():
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "list_career_roles", return_value=[_role_row()]),
    ):
        response = client.get("/api/v1/career-roles", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["career_roles"][0]["title"] == "Software Engineer"


def test_list_career_roles_also_allowed_for_faculty():
    """Same precedent as GET /assessments -- reference-data reads are not
    role-restricted; RLS itself never restricts this by role."""
    with (
        authenticated_as("FACULTY"),
        patch.object(career_role_service, "list_career_roles", return_value=[]),
    ):
        response = client.get("/api/v1/career-roles", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


def test_get_career_role_not_found():
    role_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "get_career_role", return_value=None),
    ):
        response = client.get(f"/api/v1/career-roles/{role_id}", headers={"Authorization": "Bearer token"})
    assert response.status_code == 404


def test_get_career_role_found():
    role_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "get_career_role", return_value=_role_row(id=str(role_id))),
    ):
        response = client.get(f"/api/v1/career-roles/{role_id}", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["id"] == str(role_id)


# ============================================================
# API: GET /career-roles/{id}/skill-gap
# ============================================================


def test_skill_gap_requires_student_role():
    role_id = uuid4()
    with authenticated_as("FACULTY"):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_skill_gap_nonexistent_role_returns_404():
    role_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "get_career_role", return_value=None),
    ):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_skill_gap_with_completed_attempts():
    role_id = uuid4()
    python_id, sql_id = str(uuid4()), str(uuid4())
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(career_role_service, "get_career_role", return_value=_role_row(id=str(role_id))),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[
                SkillRequirement(python_id, "Python", Decimal(70), Decimal("1.0")),
                SkillRequirement(sql_id, "SQL", Decimal(60), Decimal("1.0")),
            ],
        ),
        patch.object(
            assessment_service, "get_student_skill_scores", return_value={python_id: Decimal(85)}
        ),
    ):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap", headers={"Authorization": "Bearer token"}
        )

    assert response.status_code == 200
    body = response.json()
    statuses = {row["skill_name"]: row["status"] for row in body["skills"]}
    assert statuses["Python"] == "STRONG"
    assert statuses["SQL"] == "NOT_ASSESSED"


def test_skill_gap_no_completed_assessments_still_returns_role_requirements():
    """A student with no completed assessments still sees the role's
    requirements -- every skill NOT_ASSESSED, never a fabricated score."""
    role_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "get_career_role", return_value=_role_row(id=str(role_id))),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[SkillRequirement(str(uuid4()), "Python", Decimal(70), Decimal("1.0"))],
        ),
        patch.object(assessment_service, "get_student_skill_scores", return_value={}),
    ):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap", headers={"Authorization": "Bearer token"}
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["skills"]) == 1
    assert body["skills"][0]["status"] == "NOT_ASSESSED"


def test_skill_gap_never_accepts_client_supplied_student_id():
    """No request body/query param exists to override the authenticated
    identity -- the endpoint takes only the career_role_id from the path.
    A client-supplied student_id in the query string is simply ignored
    (FastAPI drops unrecognized query params for a route with no such
    parameter declared) -- this test proves get_student_skill_scores is
    still called with the AUTHENTICATED user's id, not anything from the
    request."""
    role_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="real-student-id"),
        patch.object(career_role_service, "get_career_role", return_value=_role_row(id=str(role_id))),
        patch.object(career_role_service, "get_career_role_requirements", return_value=[]),
        patch.object(
            assessment_service, "get_student_skill_scores", return_value={}
        ) as mock_scores,
    ):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap?student_id=someone-elses-id",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    mock_scores.assert_called_once()
    _called_client, called_student_id = mock_scores.call_args.args
    assert called_student_id == "real-student-id"
