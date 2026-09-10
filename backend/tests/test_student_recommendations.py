"""Tests for the aggregate Student recommendation API:
GET /api/v1/student/recommendations.

Adopted from a collaborator branch during a cross-branch integration pass
and adapted: `resolve_context()` used the source branch's own
skill_gap_service (PERSONAL / JOB_ROLE target-role dispatch). This
project has no persisted target-role concept, so it always resolves to
one mode ("AGGREGATE") via app.services.skill_recommendation_service --
see that module's own docstring, and app.api.student_learning's identical
adaptation for /student/learning/recommended.

Route tests mock app.services.student_recommendation_service and use
tests.conftest.authenticated_as, exactly like tests/test_student_events.py.
Service tests mock the three canonical sources the composer sits on top of
(skill_recommendation_service, student_opportunity_service,
learning_recommendation_service) -- no live project or real token.

This integration pass adds NO migration and NO new matching algorithm:
ranking reuses match_service.compute_match via
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


def _assessment(**overrides):
    row = {
        "id": "a-1",
        "title": "Python Fundamentals",
        "skill_id": "s1",
        "skill_name": "Python",
        "difficulty": "Beginner",
        "duration_minutes": 30,
        "reason_type": "NOT_ASSESSED",
        "reason": "You have not demonstrated this skill yet.",
        "priority": "HIGH",
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


def _patched(*, mode="AGGREGATE", job_role=None, assessments=None, opportunities=None, learning=None):
    return (
        patch.object(svc, "resolve_context", return_value=(mode, job_role, {"recommendations": []})),
        patch.object(svc, "recommend_assessments", return_value=assessments or []),
        patch.object(svc, "recommend_opportunities", return_value=opportunities or []),
        patch.object(svc, "recommend_learning", return_value=learning or []),
    )


def test_returns_grouped_assessments_opportunities_and_learning():
    ctx, assess, opps, learn = _patched(
        assessments=[_assessment()],
        opportunities=[_opp(), _opp(id="job_22222222-2222-2222-2222-222222222222", type="JOB", title="Platform Engineer")],
        learning=[_learning_entry()],
    )
    with authenticated_as("STUDENT", user_id="s-1"), ctx, assess, opps, learn:
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "AGGREGATE"
    assert body["assessments"][0]["title"] == "Python Fundamentals"
    assert body["assessments"][0]["reason_type"] == "NOT_ASSESSED"
    assert body["assessments"][0]["priority"] == "HIGH"
    assert [o["type"] for o in body["opportunities"]] == ["INTERNSHIP", "JOB"]
    assert body["opportunities"][0]["match_band"] == "GOOD"
    assert body["opportunities"][0]["matched_skill_count"] == 3
    assert body["opportunities"][0]["required_skill_count"] == 5
    assert body["learning"][0]["resource"]["title"] == "Python for Everybody"
    assert body["learning"][0]["matched_skills"][0]["reason"] == "Core gap."
    # opportunity detail path is a fixed-prefix student route
    assert body["opportunities"][0]["detail_path"].startswith("/student/internships/internship_")


def test_aggregate_mode_always_has_a_null_target_role():
    """This project has no persisted target-role concept -- target_role
    is always null, mode is always AGGREGATE."""
    ctx, assess, opps, learn = _patched()
    with authenticated_as("STUDENT"), ctx, assess, opps, learn:
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "AGGREGATE"
    assert body["target_role"] is None


def test_completely_empty_is_honest_not_fabricated():
    ctx, assess, opps, learn = _patched()
    with authenticated_as("STUDENT"), ctx, assess, opps, learn:
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    body = resp.json()
    assert body["assessments"] == []
    assert body["opportunities"] == []
    assert body["learning"] == []


def test_response_never_exposes_a_probability_or_percentage_field():
    ctx, assess, opps, learn = _patched(opportunities=[_opp()])
    with authenticated_as("STUDENT"), ctx, assess, opps, learn:
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    text = resp.text.lower()
    for banned in ("probability", "confidence", "success_rate", "hiring", "percent", "ai_score"):
        assert banned not in text, banned


def test_unexpected_assessment_recommendation_error_returns_500_not_a_crash():
    """An unexpected failure inside recommend_assessments must not surface
    a raw traceback, and must not prevent the route from responding at all
    -- same generic 500-wrapping behavior the route already applies to
    resolve_context/recommend_opportunities/recommend_learning failures."""
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "resolve_context", return_value=("AGGREGATE", None, {"recommendations": []})),
        patch.object(svc, "recommend_assessments", side_effect=RuntimeError("boom")),
        patch.object(svc, "recommend_opportunities", return_value=[]),
        patch.object(svc, "recommend_learning", return_value=[]),
    ):
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 500
    assert "boom" not in resp.text


def test_empty_assessment_category_does_not_affect_other_categories():
    ctx, assess, opps, learn = _patched(
        assessments=[],
        opportunities=[_opp()],
        learning=[_learning_entry()],
    )
    with authenticated_as("STUDENT"), ctx, assess, opps, learn:
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["assessments"] == []
    assert len(body["opportunities"]) == 1
    assert len(body["learning"]) == 1


def test_limit_is_bounded():
    with authenticated_as("STUDENT"):
        assert client.get(f"{_URL}?limit=0", headers={"Authorization": "Bearer token"}).status_code == 422
        assert client.get(f"{_URL}?limit=21", headers={"Authorization": "Bearer token"}).status_code == 422


def test_limit_is_passed_through_to_all_sections():
    captured = {}

    def fake_assess(_c, _sid, _analysis, *, limit):
        captured["assess"] = limit
        return []

    def fake_opps(_c, _sid, *, limit):
        captured["opps"] = limit
        return []

    def fake_learn(_c, _sid, _analysis, *, limit):
        captured["learn"] = limit
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "resolve_context", return_value=("AGGREGATE", None, {"recommendations": []})),
        patch.object(svc, "recommend_assessments", side_effect=fake_assess),
        patch.object(svc, "recommend_opportunities", side_effect=fake_opps),
        patch.object(svc, "recommend_learning", side_effect=fake_learn),
    ):
        resp = client.get(f"{_URL}?limit=10", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured == {"assess": 10, "opps": 10, "learn": 10}


# ============================================================
# 9-13. Context ownership -- client cannot supply personalization inputs
# ============================================================


def test_context_is_resolved_from_current_user_id_only():
    seen = {}

    def fake_ctx(_client, student_id):
        seen["student_id"] = student_id
        return "AGGREGATE", None, {"recommendations": []}

    with (
        authenticated_as("STUDENT", user_id="the-caller"),
        patch.object(svc, "resolve_context", side_effect=fake_ctx),
        patch.object(svc, "recommend_assessments", return_value=[]),
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


def test_resolve_context_uses_the_aggregate_skill_gap_engine():
    """Always AGGREGATE mode, null job_role, and `analysis["recommendations"]`
    is exactly skill_recommendation_service.get_aggregate_skill_gaps's own
    output -- this project has no persisted target-role concept to
    dispatch on (unlike GET /api/v1/career-roles/{id}/skill-gap, which
    compares against one EXPLICITLY CHOSEN role, not an implicit target)."""
    from app.services import skill_recommendation_service

    gaps = [{"skill_id": "s1", "skill_name": "Python", "reason": "r", "priority": "HIGH"}]
    with patch.object(
        skill_recommendation_service, "get_aggregate_skill_gaps", return_value=gaps
    ) as aggregate:
        mode, role, analysis = svc.resolve_context(object(), "s-1")
    assert mode == "AGGREGATE"
    assert role is None
    assert analysis == {"recommendations": gaps}
    aggregate.assert_called_once()


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


def _catalog(**overrides):
    row = {
        "id": "a-1",
        "skill_id": "s1",
        "title": "Python Basics",
        "difficulty": "Beginner",
        "duration_minutes": 20,
        "is_active": True,
    }
    row.update(overrides)
    return row


def _gap(**overrides):
    row = {
        "skill_id": "s1",
        "skill_name": "Python",
        "priority": "HIGH",
        "reason": "A skill gap in 3 of 6 career roles in the catalog.",
        "status": "NOT_ASSESSED",
    }
    row.update(overrides)
    return row


# ============================================================
# 27-41. recommend_assessments (Phase 3D)
# ============================================================


def test_recommend_assessments_not_assessed_gap_is_recommended():
    from app.services import assessment_service as a_svc

    analysis = {"recommendations": [_gap(status="NOT_ASSESSED")]}
    with (
        patch.object(a_svc, "list_active_assessments", return_value=[_catalog()]),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert len(result) == 1
    assert result[0]["id"] == "a-1"
    assert result[0]["reason_type"] == "NOT_ASSESSED"


def test_recommend_assessments_gap_status_maps_to_skill_gap_reason_type():
    from app.services import assessment_service as a_svc

    analysis = {"recommendations": [_gap(status="GAP")]}
    with (
        patch.object(a_svc, "list_active_assessments", return_value=[_catalog()]),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert result[0]["reason_type"] == "SKILL_GAP"


def test_recommend_assessments_preserves_gap_reason_and_priority():
    from app.services import assessment_service as a_svc

    analysis = {"recommendations": [_gap(reason="Custom reason text.", priority="MEDIUM")]}
    with (
        patch.object(a_svc, "list_active_assessments", return_value=[_catalog()]),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert result[0]["reason"] == "Custom reason text."
    assert result[0]["priority"] == "MEDIUM"


def test_recommend_assessments_excludes_eligible_completed_attempt():
    """Test 5/6: whether the eligible attempt was NOT_REQUIRED or a
    finalized AI evaluation (COMPLETE), get_completed_assessment_ids
    already folded that into the returned set -- this function only needs
    to honor the exclusion, not re-derive it."""
    from app.services import assessment_service as a_svc

    analysis = {"recommendations": [_gap()]}
    with (
        patch.object(a_svc, "list_active_assessments", return_value=[_catalog()]),
        patch.object(a_svc, "get_completed_assessment_ids", return_value={"a-1"}),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert result == []


def test_recommend_assessments_pending_partial_reconciliation_remain_eligible():
    """Test 7/8/9: an assessment with only a PENDING/PARTIAL/
    NEEDS_RECONCILIATION attempt is NOT in get_completed_assessment_ids'
    returned set (that function's own contract), so it must still be
    recommended -- verified here via the empty set this function receives
    for exactly that situation."""
    from app.services import assessment_service as a_svc

    analysis = {"recommendations": [_gap()]}
    with (
        patch.object(a_svc, "list_active_assessments", return_value=[_catalog()]),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert len(result) == 1
    assert result[0]["id"] == "a-1"


def test_recommend_assessments_inactive_assessment_not_recommended():
    """Relies on list_active_assessments' own is_active filter -- an
    inactive assessment simply never appears in its return value, so this
    function needs no separate is_active check of its own."""
    from app.services import assessment_service as a_svc

    analysis = {"recommendations": [_gap()]}
    with (
        patch.object(a_svc, "list_active_assessments", return_value=[]),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert result == []


def test_recommend_assessments_ranks_priority_then_duration_then_title():
    from app.services import assessment_service as a_svc

    analysis = {
        "recommendations": [
            _gap(skill_id="s1", skill_name="Python", priority="HIGH"),
            _gap(skill_id="s2", skill_name="SQL", priority="MEDIUM"),
        ]
    }
    catalog = [
        _catalog(id="py-slow", skill_id="s1", title="Python Intermediate", duration_minutes=30),
        _catalog(id="py-fast", skill_id="s1", title="Python Basics", duration_minutes=20),
        _catalog(id="sql-1", skill_id="s2", title="SQL Basics", duration_minutes=15),
    ]
    with (
        patch.object(a_svc, "list_active_assessments", return_value=catalog),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert [r["id"] for r in result] == ["py-fast", "py-slow", "sql-1"]


def test_recommend_assessments_null_duration_sorts_deterministically_last():
    from app.services import assessment_service as a_svc

    analysis = {"recommendations": [_gap(skill_id="s1", skill_name="Python", priority="HIGH")]}
    catalog = [
        _catalog(id="no-duration", skill_id="s1", title="A Assessment", duration_minutes=None),
        _catalog(id="has-duration", skill_id="s1", title="Z Assessment", duration_minutes=10),
    ]
    with (
        patch.object(a_svc, "list_active_assessments", return_value=catalog),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert [r["id"] for r in result] == ["has-duration", "no-duration"]


def test_recommend_assessments_respects_the_limit():
    from app.services import assessment_service as a_svc

    analysis = {"recommendations": [_gap(skill_id="s1", skill_name="Python")]}
    catalog = [_catalog(id=f"a-{i}", skill_id="s1", title=f"T{i}") for i in range(5)]
    with (
        patch.object(a_svc, "list_active_assessments", return_value=catalog),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis, limit=2)
    assert len(result) == 2


def test_recommend_assessments_multiple_skills_deterministic_ordering():
    from app.services import assessment_service as a_svc

    analysis = {
        "recommendations": [
            _gap(skill_id="s1", skill_name="Python", priority="HIGH"),
            _gap(skill_id="s2", skill_name="SQL", priority="MEDIUM"),
            _gap(skill_id="s3", skill_name="React", priority="LOW"),
        ]
    }
    catalog = [
        _catalog(id="react-1", skill_id="s3", title="React Basics", duration_minutes=10),
        _catalog(id="sql-1", skill_id="s2", title="SQL Basics", duration_minutes=10),
        _catalog(id="py-1", skill_id="s1", title="Python Basics", duration_minutes=10),
    ]
    with (
        patch.object(a_svc, "list_active_assessments", return_value=catalog),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert [r["id"] for r in result] == ["py-1", "sql-1", "react-1"]


def test_recommend_assessments_no_matching_assessment_returns_empty():
    from app.services import assessment_service as a_svc

    analysis = {"recommendations": [_gap(skill_id="s-no-assessment")]}
    with (
        patch.object(a_svc, "list_active_assessments", return_value=[_catalog(skill_id="s1")]),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        result = svc.recommend_assessments(object(), "s-1", analysis)
    assert result == []


def test_recommend_assessments_no_gaps_returns_empty_without_querying_catalog():
    from app.services import assessment_service as a_svc

    with (
        patch.object(a_svc, "list_active_assessments") as catalog_call,
        patch.object(a_svc, "get_completed_assessment_ids") as completed_call,
    ):
        result = svc.recommend_assessments(object(), "s-1", {"recommendations": []})
    assert result == []
    catalog_call.assert_not_called()
    completed_call.assert_not_called()


def test_recommend_assessments_is_repeatable_for_the_same_input():
    from app.services import assessment_service as a_svc

    analysis = {
        "recommendations": [
            _gap(skill_id="s1", skill_name="Python", priority="HIGH"),
            _gap(skill_id="s2", skill_name="SQL", priority="MEDIUM"),
        ]
    }
    catalog = [
        _catalog(id="py-1", skill_id="s1", title="Python Basics", duration_minutes=10),
        _catalog(id="sql-1", skill_id="s2", title="SQL Basics", duration_minutes=10),
    ]
    with (
        patch.object(a_svc, "list_active_assessments", return_value=catalog),
        patch.object(a_svc, "get_completed_assessment_ids", return_value=set()),
    ):
        first = svc.recommend_assessments(object(), "s-1", analysis)
        second = svc.recommend_assessments(object(), "s-1", analysis)
    assert first == second


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
    # it delegates to exactly the four canonical services
    assert "skill_recommendation_service" in source
    assert "assessment_service.list_active_assessments" in source
    assert "assessment_service.get_completed_assessment_ids" in source
    assert "student_opportunity_service.compute_opportunity_match" in source
    assert "learning_recommendation_service.get_recommended_resources" in source


def test_router_registered_and_get_only():
    paths = app.openapi()["paths"]
    assert "/api/v1/student/recommendations" in paths
    assert set(paths["/api/v1/student/recommendations"]) == {"get"}
