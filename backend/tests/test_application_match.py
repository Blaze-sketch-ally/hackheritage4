"""Tests for Industry candidate/opportunity matching (Phase 9):
GET /api/v1/applications/{id}/match + the pure match_service.

Route tests mock app.services.application_service / match_service and use
tests.conftest.authenticated_as. Service tests are pure (match_service) or
drive a MagicMock client (the RPC caller) -- no live project, no token.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import applications as application_routes
from app.main import app
from app.services import application_service, match_service
from tests.conftest import authenticated_as

client = TestClient(app)

_APP_ID = str(uuid4())


def _application(**overrides):
    row = {
        "id": "app-1",
        "student_id": "student-7",
        "industry_id": "industry-1",
        "opportunity_type": "INTERNSHIP",
        "internship_id": "int-1",
        "job_id": None,
        "status": "APPLIED",
        "cover_note": None,
        "match_score": None,
        "applied_at": "2026-09-01T00:00:00Z",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "opportunity": {"id": "int-1", "title": "Backend Intern", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


def _req(skill_id, name, required_level, importance, *, has, level=None, verified=False):
    return {
        "skill_id": skill_id,
        "skill_name": name,
        "required_level": required_level,
        "importance": importance,
        "candidate_has": has,
        "candidate_level": level,
        "candidate_verified": verified,
    }


# ============================================================
# Auth / role guards
# ============================================================


def test_match_unauthenticated_returns_401():
    assert client.get(f"/api/v1/applications/{uuid4()}/match").status_code == 401


def test_match_forbids_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.get(
                f"/api/v1/applications/{uuid4()}/match", headers={"Authorization": "Bearer token"}
            )
        assert resp.status_code == 403, role


def test_match_industry_allowed():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_application", return_value=_application()),
        patch.object(application_service, "get_skill_match_rows", return_value=[]),
        patch.object(application_service, "set_match_score"),
    ):
        resp = client.get(
            f"/api/v1/applications/{uuid4()}/match", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200


# ============================================================
# Ownership
# ============================================================


def test_match_404_when_application_not_owned_or_missing():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(application_service, "get_application", return_value=None) as mock_get,
        patch.object(application_service, "get_skill_match_rows") as mock_rpc,
    ):
        resp = client.get(
            f"/api/v1/applications/{uuid4()}/match", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "industry-A"
    # No attempt to fetch candidate data for an application we don't own.
    mock_rpc.assert_not_called()


def test_match_passes_owner_id_and_application_id_to_services():
    captured = {}

    def fake_get(_client, industry_id, application_id):
        captured["get"] = (industry_id, application_id)
        return _application()

    def fake_rows(_client, application_id):
        captured["rpc"] = application_id
        return []

    app_id = str(uuid4())
    with (
        authenticated_as("INDUSTRY", user_id="industry-9"),
        patch.object(application_service, "get_application", side_effect=fake_get),
        patch.object(application_service, "get_skill_match_rows", side_effect=fake_rows),
        patch.object(application_service, "set_match_score"),
    ):
        resp = client.get(
            f"/api/v1/applications/{app_id}/match", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured["get"] == ("industry-9", app_id)
    assert captured["rpc"] == app_id


# ============================================================
# Response shape + error handling
# ============================================================


def test_match_response_shape():
    rows = [
        _req("s1", "Python", "Intermediate", "CORE", has=True, level="Advanced", verified=True),
        _req("s2", "Docker", "Intermediate", "IMPORTANT", has=False),
    ]
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_application", return_value=_application()),
        patch.object(application_service, "get_skill_match_rows", return_value=rows),
        patch.object(application_service, "set_match_score"),
    ):
        resp = client.get(
            f"/api/v1/applications/{_APP_ID}/match", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "application_id",
        "score",
        "recommendation",
        "skill_coverage",
        "required_count",
        "matched_count",
        "needs_improvement_count",
        "missing_count",
        "matched_skills",
        "needs_improvement_skills",
        "missing_skills",
    }
    assert body["skill_coverage"] == "1 / 2"
    assert body["recommendation"] in {"STRONG", "GOOD", "PARTIAL", "LOW"}
    # skill entries carry no student profile fields
    skill = body["matched_skills"][0]
    assert set(skill) == {
        "skill_id",
        "skill_name",
        "required_level",
        "importance",
        "candidate_has",
        "candidate_level",
        "candidate_verified",
        "status",
    }
    for leaked in ("email", "full_name", "student_id", "cgpa", "date_of_birth"):
        assert leaked not in skill


def test_match_rpc_error_becomes_safe_500():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "get_application", return_value=_application()),
        patch.object(
            application_service, "get_skill_match_rows", side_effect=RuntimeError("pg exploded")
        ),
    ):
        resp = client.get(
            f"/api/v1/applications/{_APP_ID}/match", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 500
    assert "pg exploded" not in resp.text
    assert resp.json()["detail"] == "Could not calculate the match. Please try again."


def test_match_is_get_only():
    with authenticated_as("INDUSTRY"):
        assert (
            client.post(
                f"/api/v1/applications/{_APP_ID}/match",
                json={"score": 100},
                headers={"Authorization": "Bearer token"},
            ).status_code
            == 405
        )


# ============================================================
# Persistence
# ============================================================


def test_match_persists_server_computed_score_when_requirements_exist():
    rows = [_req("s1", "Python", "Beginner", "CORE", has=True, level="Expert", verified=True)]
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_application", return_value=_application()),
        patch.object(application_service, "get_skill_match_rows", return_value=rows),
        patch.object(application_service, "set_match_score") as mock_set,
    ):
        resp = client.get(
            f"/api/v1/applications/{_APP_ID}/match", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    mock_set.assert_called_once()
    args = mock_set.call_args.args
    assert args[1] == "industry-1"  # owner id, server-derived
    assert args[2] == _APP_ID
    assert args[3] == resp.json()["score"]  # exactly the computed score


def test_match_does_not_persist_when_no_requirements():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "get_application", return_value=_application()),
        patch.object(application_service, "get_skill_match_rows", return_value=[]),
        patch.object(application_service, "set_match_score") as mock_set,
    ):
        resp = client.get(
            f"/api/v1/applications/{_APP_ID}/match", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json()["required_count"] == 0
    mock_set.assert_not_called()


def test_match_persistence_failure_does_not_fail_the_response():
    rows = [_req("s1", "Python", "Beginner", "CORE", has=True, level="Expert", verified=True)]
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "get_application", return_value=_application()),
        patch.object(application_service, "get_skill_match_rows", return_value=rows),
        patch.object(
            application_service, "set_match_score", side_effect=RuntimeError("write failed")
        ),
    ):
        resp = client.get(
            f"/api/v1/applications/{_APP_ID}/match", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json()["score"] == 100


def test_set_match_score_uses_user_scoped_client_and_scopes_to_owner():
    supabase = MagicMock()
    application_service.set_match_score(supabase, "industry-1", "app-1", 87)
    supabase.table.assert_called_with("applications")
    supabase.table.return_value.update.assert_called_with({"match_score": 87})
    eq_calls = supabase.table.return_value.update.return_value.eq.call_args_list
    assert eq_calls[0].args == ("id", "app-1")


def test_get_skill_match_rows_calls_the_rpc():
    supabase = MagicMock()
    supabase.rpc.return_value.execute.return_value.data = [{"skill_id": "s1"}]
    out = application_service.get_skill_match_rows(supabase, "app-1")
    supabase.rpc.assert_called_once_with(
        "application_skill_match", {"p_application_id": "app-1"}
    )
    assert out == [{"skill_id": "s1"}]


def test_get_skill_match_rows_none_becomes_empty_list():
    supabase = MagicMock()
    supabase.rpc.return_value.execute.return_value.data = None
    assert application_service.get_skill_match_rows(supabase, "app-1") == []


# ============================================================
# Deterministic scoring engine
# ============================================================


def test_exact_match_all_verified_is_100():
    rows = [
        _req("s1", "Python", "Advanced", "CORE", has=True, level="Advanced", verified=True),
        _req("s2", "SQL", "Intermediate", "IMPORTANT", has=True, level="Expert", verified=True),
    ]
    result = match_service.compute_match("app-1", rows)
    assert result["score"] == 100
    assert result["recommendation"] == "STRONG"
    assert result["skill_coverage"] == "2 / 2"
    assert result["matched_count"] == 2
    assert result["missing_count"] == 0


def test_unverified_matched_scores_below_verified():
    verified = match_service.compute_match(
        "a", [_req("s1", "Python", "Beginner", "CORE", has=True, level="Beginner", verified=True)]
    )
    unverified = match_service.compute_match(
        "a", [_req("s1", "Python", "Beginner", "CORE", has=True, level="Beginner", verified=False)]
    )
    assert verified["score"] == 100
    assert unverified["score"] == 85  # _UNVERIFIED_FACTOR
    assert verified["score"] > unverified["score"]


def test_candidate_below_required_level_is_needs_improvement_partial_credit():
    rows = [_req("s1", "Python", "Expert", "CORE", has=True, level="Beginner", verified=True)]
    result = match_service.compute_match("a", rows)
    assert result["needs_improvement_count"] == 1
    assert result["matched_count"] == 0
    # Beginner(1) / Expert(4) = 0.25 -> 25
    assert result["score"] == 25
    assert result["needs_improvement_skills"][0]["status"] == "NEEDS_IMPROVEMENT"


def test_candidate_level_meets_required_is_matched():
    rows = [_req("s1", "Python", "Intermediate", "CORE", has=True, level="Intermediate", verified=True)]
    result = match_service.compute_match("a", rows)
    assert result["matched_count"] == 1
    assert result["score"] == 100


def test_missing_skill_earns_nothing_and_lists_as_missing():
    rows = [
        _req("s1", "Python", "Advanced", "CORE", has=True, level="Advanced", verified=True),
        _req("s2", "Docker", "Advanced", "CORE", has=False),
    ]
    result = match_service.compute_match("a", rows)
    assert result["missing_count"] == 1
    assert result["missing_skills"][0]["skill_name"] == "Docker"
    assert result["missing_skills"][0]["candidate_has"] is False
    assert result["missing_skills"][0]["candidate_level"] is None
    # one of two equal-weight CORE skills matched -> 50
    assert result["score"] == 50


def test_no_matching_skills_is_zero_and_low():
    rows = [
        _req("s1", "Python", "Advanced", "CORE", has=False),
        _req("s2", "Docker", "Advanced", "IMPORTANT", has=False),
    ]
    result = match_service.compute_match("a", rows)
    assert result["score"] == 0
    assert result["recommendation"] == "LOW"
    assert result["skill_coverage"] == "0 / 2"


def test_core_missing_hurts_more_than_optional_missing():
    core_missing = match_service.compute_match(
        "a",
        [
            _req("s1", "A", "Beginner", "CORE", has=False),
            _req("s2", "B", "Beginner", "OPTIONAL", has=True, level="Beginner", verified=True),
        ],
    )
    optional_missing = match_service.compute_match(
        "a",
        [
            _req("s1", "A", "Beginner", "CORE", has=True, level="Beginner", verified=True),
            _req("s2", "B", "Beginner", "OPTIONAL", has=False),
        ],
    )
    # CORE weight 5, OPTIONAL weight 1 -> missing the CORE costs far more
    assert core_missing["score"] < optional_missing["score"]
    assert core_missing["score"] == round(100 * 1 / 6)
    assert optional_missing["score"] == round(100 * 5 / 6)


def test_missing_core_caps_recommendation_at_partial():
    # 9 matched CORE + 1 missing IMPORTANT would be ~STRONG on score alone;
    # a missing CORE forces the cap.
    rows = [
        _req(f"s{i}", f"Skill{i}", "Beginner", "CORE", has=True, level="Beginner", verified=True)
        for i in range(9)
    ] + [_req("sx", "Kubernetes", "Beginner", "CORE", has=False)]
    result = match_service.compute_match("a", rows)
    assert result["score"] >= 80  # numerically strong
    assert result["recommendation"] == "PARTIAL"  # but a core skill is missing


def test_score_cannot_exceed_100_even_when_candidate_far_exceeds_level():
    rows = [_req("s1", "Python", "Beginner", "CORE", has=True, level="Expert", verified=True)]
    result = match_service.compute_match("a", rows)
    assert result["score"] == 100


def test_duplicate_required_skill_rows_do_not_inflate_score():
    single = match_service.compute_match(
        "a", [_req("s1", "Python", "Advanced", "CORE", has=False)]
    )
    duped = match_service.compute_match(
        "a",
        [
            _req("s1", "Python", "Advanced", "CORE", has=False),
            _req("s1", "Python", "Advanced", "CORE", has=False),
        ],
    )
    assert duped["score"] == single["score"] == 0
    assert duped["required_count"] == 1
    assert duped["missing_count"] == 1


def test_no_requirements_is_zero_score_empty_lists():
    result = match_service.compute_match("a", [])
    assert result["score"] == 0
    assert result["required_count"] == 0
    assert result["skill_coverage"] == "0 / 0"
    assert result["matched_skills"] == []
    assert result["missing_skills"] == []


def test_recommendation_bands():
    def band(score_rows):
        return match_service.compute_match("a", score_rows)["recommendation"]

    # tune with one CORE skill: earned fraction = target/100 via level ratio
    assert band([_req("s", "x", "Expert", "CORE", has=True, level="Expert", verified=True)]) == "STRONG"
    assert (
        band([_req("s", "x", "Expert", "CORE", has=True, level="Advanced", verified=True)]) == "GOOD"
    )  # 3/4 = 75
    assert (
        band([_req("s", "x", "Expert", "CORE", has=True, level="Intermediate", verified=True)])
        == "PARTIAL"
    )  # 2/4 = 50
    assert (
        band([_req("s", "x", "Expert", "CORE", has=True, level="Beginner", verified=True)]) == "LOW"
    )  # 1/4 = 25


def test_compute_match_is_deterministic():
    rows = [
        _req("s1", "Python", "Advanced", "CORE", has=True, level="Intermediate", verified=False),
        _req("s2", "Docker", "Beginner", "OPTIONAL", has=False),
        _req("s3", "SQL", "Intermediate", "IMPORTANT", has=True, level="Expert", verified=True),
    ]
    first = match_service.compute_match("app-1", rows)
    second = match_service.compute_match("app-1", list(reversed(rows)))
    assert first["score"] == second["score"]
    assert first["recommendation"] == second["recommendation"]
    assert {s["skill_id"] for s in first["matched_skills"]} == {
        s["skill_id"] for s in second["matched_skills"]
    }


def test_skills_sorted_core_first():
    rows = [
        _req("s1", "Zebra", "Beginner", "OPTIONAL", has=True, level="Beginner", verified=True),
        _req("s2", "Alpha", "Beginner", "CORE", has=True, level="Beginner", verified=True),
    ]
    result = match_service.compute_match("a", rows)
    assert [s["skill_name"] for s in result["matched_skills"]] == ["Alpha", "Zebra"]


# ============================================================
# No service-role
# ============================================================


def test_match_modules_do_not_use_service_role():
    assert not hasattr(match_service, "get_supabase")
    assert not hasattr(application_routes, "get_supabase")
    # match_service is pure -- no supabase Client dependency at all
    assert not hasattr(match_service, "Client")
