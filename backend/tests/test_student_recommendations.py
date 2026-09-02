"""Tests for the aggregate Student recommendation API:
GET /api/v1/student/recommendations.

Route tests mock app.services.student_recommendation_service and use
tests.conftest.authenticated_as, exactly like tests/test_student_events.py.
Service tests mock the THREE canonical sources the composer sits on top of
(skill_gap_service, student_opportunity_service,
learning_recommendation_service) -- no live project or real token.

S7 adds NO migration and NO new matching algorithm: ranking reuses
match_service.compute_match via
student_opportunity_service.compute_opportunity_match, and learning reuses
learning_recommendation_service.get_recommended_resources verbatim.
"""

import inspect
import re
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import student_recommendation_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_URL = "/api/v1/student/recommendations"


def _opp(**overrides):
    row = {
        "type": "INTERNSHIP",
        "id": "internship_11111111-1111-1111-1111-111111111111",
        "title": "Backend Intern",
        "description": "Build APIs.",
        "company": "Acme",
        "location": "Pune",
        "work_mode": "HYBRID",
        "detail_path": "/student/internships/internship_11111111-1111-1111-1111-111111111111",
        "match_score": 72,
        "match_band": "GOOD",
        "matched_skill_count": 3,
        "required_skill_count": 5,
        "relevant_skills": ["Python", "PostgreSQL", "Docker"],
    }
    row.update(overrides)
    return row


def _learning_entry(**overrides):
    entry = {
        "resource": {
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "title": "Python for Everybody",
            "description": "Intro to Python.",
            "url": "https://www.py4e.com/",
            "provider": "py4e",
            "resource_type": "COURSE",
            "difficulty": "Beginner",
            "estimated_minutes": 1200,
            "skills": [],
            "progress": None,
        },
        "matched_skills": [
            {"skill_id": "s1", "skill_name": "Python", "reason": "Core gap.", "priority": "HIGH"},
        ],
    }
    entry.update(overrides)
    return entry


# ============================================================
# 1-2. Auth / role
# ============================================================


def test_rejects_unauthenticated():
    assert client.get(_URL).status_code == 401


def test_forbids_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(_URL, headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, role


# ============================================================
# 3-8. Composition + response shape
# ============================================================


def _patched(*, mode="PERSONAL", job_role=None, opportunities=None, learning=None):
    return (
        patch.object(svc, "resolve_context", return_value=(mode, job_role, {"recommendations": []})),
        patch.object(svc, "recommend_opportunities", return_value=opportunities or []),
        patch.object(svc, "recommend_learning", return_value=learning or []),
    )


def test_returns_grouped_opportunities_and_learning():
    ctx, opps, learn = _patched(
        mode="JOB_ROLE",
        job_role={"id": "r-1", "name": "Backend Developer"},
        opportunities=[_opp(), _opp(id="job_22222222-2222-2222-2222-222222222222", type="JOB", title="Platform Engineer")],
        learning=[_learning_entry()],
    )
    with authenticated_as("STUDENT", user_id="s-1"), ctx, opps, learn:
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "JOB_ROLE"
    assert body["target_role"] == {"id": "r-1", "name": "Backend Developer"}
    assert [o["type"] for o in body["opportunities"]] == ["INTERNSHIP", "JOB"]
    assert body["opportunities"][0]["match_band"] == "GOOD"
    assert body["opportunities"][0]["matched_skill_count"] == 3
    assert body["opportunities"][0]["required_skill_count"] == 5
    assert body["learning"][0]["resource"]["title"] == "Python for Everybody"
    assert body["learning"][0]["matched_skills"][0]["reason"] == "Core gap."
    # opportunity detail path is a fixed-prefix student route
    assert body["opportunities"][0]["detail_path"].startswith("/student/internships/internship_")


def test_personal_mode_has_null_target_role():
    ctx, opps, learn = _patched(mode="PERSONAL", job_role=None)
    with authenticated_as("STUDENT"), ctx, opps, learn:
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "PERSONAL"
    assert body["target_role"] is None


def test_completely_empty_is_honest_not_fabricated():
    ctx, opps, learn = _patched()
    with authenticated_as("STUDENT"), ctx, opps, learn:
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    body = resp.json()
    assert body["opportunities"] == []
    assert body["learning"] == []


def test_response_never_exposes_a_probability_or_percentage_field():
    ctx, opps, learn = _patched(opportunities=[_opp()])
    with authenticated_as("STUDENT"), ctx, opps, learn:
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    text = resp.text.lower()
    for banned in ("probability", "confidence", "success_rate", "hiring", "percent", "ai_score"):
        assert banned not in text, banned


def test_limit_is_bounded():
    with authenticated_as("STUDENT"):
        assert client.get(f"{_URL}?limit=0", headers={"Authorization": "Bearer token"}).status_code == 422
        assert client.get(f"{_URL}?limit=21", headers={"Authorization": "Bearer token"}).status_code == 422


def test_limit_is_passed_through_to_both_sections():
    captured = {}

    def fake_opps(_c, _sid, *, limit):
        captured["opps"] = limit
        return []

    def fake_learn(_c, _sid, _analysis, *, limit):
        captured["learn"] = limit
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "resolve_context", return_value=("PERSONAL", None, {"recommendations": []})),
        patch.object(svc, "recommend_opportunities", side_effect=fake_opps),
        patch.object(svc, "recommend_learning", side_effect=fake_learn),
    ):
        resp = client.get(f"{_URL}?limit=10", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured == {"opps": 10, "learn": 10}


# ============================================================
# 9-13. Context ownership -- client cannot supply personalization inputs
# ============================================================


def test_context_is_resolved_from_current_user_id_only():
    seen = {}

    def fake_ctx(_client, student_id):
        seen["student_id"] = student_id
        return "PERSONAL", None, {"recommendations": []}

    with (
        authenticated_as("STUDENT", user_id="the-caller"),
        patch.object(svc, "resolve_context", side_effect=fake_ctx),
        patch.object(svc, "recommend_opportunities", return_value=[]),
        patch.object(svc, "recommend_learning", return_value=[]),
    ):
        # every one of these is an attempt to inject context
        resp = client.get(
            f"{_URL}?student_id=victim&skill_ids=x,y&target_job_role_id=r-9"
            "&match_score=99&recommendation_score=99&user_id=victim",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert seen["student_id"] == "the-caller"


def test_route_signature_has_no_context_parameters():
    from app.api import student_recommendations as routes

    params = set(inspect.signature(routes.get_recommendations).parameters)
    for banned in (
        "student_id",
        "user_id",
        "skill_id",
        "skill_ids",
        "target_job_role_id",
        "job_role_id",
        "match_score",
        "recommendation_score",
    ):
        assert banned not in params, banned
    assert params <= {"limit", "current_user"}


def test_route_passes_only_current_user_id_to_the_service():
    from app.api import student_recommendations as routes

    code = re.sub(r'""".*?"""', "", inspect.getsource(routes), flags=re.DOTALL)
    for call in re.findall(
        r"student_recommendation_service\.\w+\((?:[^()]|\([^()]*\))*\)", code.replace("\n", " ")
    ):
        assert "current_user.id" in call, call
        for banned in ("student_id=", "skill_ids=", "target_job_role_id=", "match_score="):
            assert banned not in call, call


# ============================================================
# 14-20. Service: canonical composition + deterministic ranking
# ============================================================


def test_resolve_context_uses_skill_gap_target_role_dispatch():
    """PERSONAL when no target role, JOB_ROLE (with the canonical job-role
    gap) when there is one -- identical to GET /api/v1/skill-gap."""
    from app.services import skill_gap_service

    with (
        patch.object(skill_gap_service, "get_target_job_role", return_value=None),
        patch.object(skill_gap_service, "compute_personal_analysis", return_value={"x": 1}) as personal,
    ):
        mode, role, analysis = svc.resolve_context(object(), "s-1")
    assert (mode, role, analysis) == ("PERSONAL", None, {"x": 1})
    personal.assert_called_once()

    role_row = {"job_role": {"id": "00000000-0000-0000-0000-000000000001", "name": "BE Dev"}}
    with (
        patch.object(skill_gap_service, "get_target_job_role", return_value=role_row),
        patch.object(skill_gap_service, "get_job_role_requirements", return_value=[{"skill_id": "s"}]),
        patch.object(skill_gap_service, "compute_job_role_gap", return_value={"recommendations": []}) as gap,
    ):
        mode, role, analysis = svc.resolve_context(object(), "s-1")
    assert mode == "JOB_ROLE"
    assert role == role_row["job_role"]
    gap.assert_called_once()


def test_recommend_opportunities_reuses_canonical_match_and_ranks_deterministically():
    from app.services import student_opportunity_service as opp_svc

    summaries = [
        {"id": "internship_a", "source_type": "INTERNSHIP", "title": "Zeta", "description": "d",
         "location": "X", "work_mode": "REMOTE", "industry": {"company_name": "C1"},
         "created_at": "2026-01-01T00:00:00Z", "has_applied": False},
        {"id": "job_b", "source_type": "JOB", "title": "Alpha", "description": "d",
         "location": "Y", "work_mode": "ONSITE", "industry": {"company_name": "C2"},
         "created_at": "2026-02-01T00:00:00Z", "has_applied": False},
        {"id": "internship_c", "source_type": "INTERNSHIP", "title": "Applied", "description": "d",
         "location": "Z", "work_mode": "HYBRID", "industry": {"company_name": "C3"},
         "created_at": "2026-03-01T00:00:00Z", "has_applied": True},
        {"id": "internship_d", "source_type": "INTERNSHIP", "title": "NoOverlap", "description": "d",
         "location": "Z", "work_mode": "HYBRID", "industry": {"company_name": "C4"},
         "created_at": "2026-03-01T00:00:00Z", "has_applied": False},
    ]
    match_by_id = {
        "internship_a": {"score": 60, "recommendation": "GOOD", "matched_count": 2,
                         "required_count": 4, "matched_skills": [{"skill_name": "Python"}]},
        "job_b": {"score": 90, "recommendation": "STRONG", "matched_count": 4,
                  "required_count": 4, "matched_skills": [{"skill_name": "Go"}]},
        "internship_d": {"score": 0, "recommendation": "LOW", "matched_count": 0,
                         "required_count": 3, "matched_skills": []},
    }

    def fake_match(_c, _sid, opp_id):
        return match_by_id[opp_id]

    with (
        patch.object(opp_svc, "list_opportunities", return_value=summaries),
        patch.object(opp_svc, "compute_opportunity_match", side_effect=fake_match),
    ):
        result = svc.recommend_opportunities(object(), "s-1")

    ids = [r["id"] for r in result]
    # job_b (score 90) ranks above internship_a (60); the applied one and
    # the zero-overlap one are dropped entirely.
    assert ids == ["job_b", "internship_a"]
    assert result[0]["detail_path"] == "/student/jobs/job_b"
    assert result[0]["match_band"] == "STRONG"
    assert result[0]["relevant_skills"] == ["Go"]
    assert all("_created_at" not in r for r in result)


def test_recommend_opportunities_respects_the_limit():
    from app.services import student_opportunity_service as opp_svc

    summaries = [
        {"id": f"internship_{i}", "source_type": "INTERNSHIP", "title": f"T{i}", "description": "d",
         "location": None, "work_mode": None, "industry": {}, "created_at": f"2026-01-0{i}T00:00:00Z",
         "has_applied": False}
        for i in range(1, 6)
    ]
    with (
        patch.object(opp_svc, "list_opportunities", return_value=summaries),
        patch.object(
            opp_svc, "compute_opportunity_match",
            return_value={"score": 50, "recommendation": "PARTIAL", "matched_count": 1,
                          "required_count": 3, "matched_skills": [{"skill_name": "X"}]},
        ),
    ):
        result = svc.recommend_opportunities(object(), "s-1", limit=2)
    assert len(result) == 2


def test_recommend_learning_reuses_canonical_service_verbatim():
    from app.services import learning_recommendation_service as lr_svc

    analysis = {"recommendations": [{"skill_id": "s1", "skill_name": "Python", "reason": "r", "priority": "HIGH"}]}
    with patch.object(lr_svc, "get_recommended_resources", return_value=[_learning_entry(), _learning_entry()]) as m:
        out = svc.recommend_learning(object(), "s-1", analysis, limit=1)
    m.assert_called_once_with(m.call_args.args[0], "s-1", analysis["recommendations"])
    assert len(out) == 1


def test_clamp_limit():
    assert svc.clamp_limit(None) == svc.DEFAULT_LIMIT
    assert svc.clamp_limit(0) == svc.DEFAULT_LIMIT
    assert svc.clamp_limit(-5) == svc.DEFAULT_LIMIT
    assert svc.clamp_limit(99) == svc.MAX_LIMIT
    assert svc.clamp_limit(5) == 5


# ============================================================
# 21-26. Security / architecture
# ============================================================


def test_service_never_writes_and_has_no_service_role():
    from app.api import student_recommendations as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")

    source = inspect.getsource(svc)
    for banned in (
        ".insert(", ".update(", ".upsert(", ".delete(",
        "set_target_job_role", "clear_target_job_role", "score_assessment_attempt",
        "apply_to_opportunity", "set_progress", "mark_read",
    ):
        assert banned not in source, f"recommendation service must not call {banned}"


def test_service_does_not_reimplement_matching_or_gap_logic():
    """The composer must not carry its own scoring maths -- no proficiency
    ordinal tables, no importance weights, no readiness formula."""
    source = inspect.getsource(svc)
    for banned in ("IMPORTANCE_WEIGHT", "LEVEL_ORDER", "readiness", "_UNVERIFIED_FACTOR", "compute_match("):
        assert banned not in source, f"composer must delegate, not reimplement ({banned})"
    # it delegates to exactly the three canonical services
    assert "skill_gap_service" in source
    assert "student_opportunity_service.compute_opportunity_match" in source
    assert "learning_recommendation_service.get_recommended_resources" in source


def test_router_registered_and_get_only():
    paths = app.openapi()["paths"]
    assert "/api/v1/student/recommendations" in paths
    assert set(paths["/api/v1/student/recommendations"]) == {"get"}
