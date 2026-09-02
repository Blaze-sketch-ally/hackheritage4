"""Tests for the Skill-Gap -> Learning recommendation integration (Phase 6D):
GET /api/v1/student/learning/recommended and
app.services.learning_recommendation_service.

Route tests mock app.services.skill_gap_service (the canonical gap engine)
and app.services.learning_recommendation_service, and use
tests.conftest.authenticated_as -- exactly like tests/test_student_learning.py
and tests/test_skill_gap.py. Service tests drive the adapter with a
MagicMock Supabase client. Nothing here re-verifies live RLS.

The canonical Skill Gap algorithm is NOT re-implemented or re-tested here
-- it stays covered by tests/test_skill_gap.py. These tests only assert
that this endpoint *consumes* that engine's output and maps it, via the
canonical learning_resource_skills.skill_id relationship, to resources.
"""

import inspect
import re
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import student_learning as routes
from app.main import app
from app.services import learning_recommendation_service as rec_svc
from app.services import skill_gap_service
from app.services import student_learning_service as sl_svc
from tests.conftest import authenticated_as

client = TestClient(app)

_URL = "/api/v1/student/learning/recommended"
_RID = "11111111-1111-1111-1111-111111111111"
_RID2 = "22222222-2222-2222-2222-222222222222"
_SKILL_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_SKILL_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_SKILL_C = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _rec(skill_id, skill_name, *, reason="because gap", priority="HIGH", **extra):
    """Shaped like one item of skill_gap_service's `recommendations` list --
    with the engine's extra internal fields present, so we can prove the
    route trims them."""
    row = {
        "skill_id": skill_id,
        "skill_name": skill_name,
        "reason": reason,
        "current_level": None,
        "target_level": "Intermediate",
        "gap": 2,
        "priority": priority,
        "relationship_type": None,
        "is_missing": True,
        "is_verified": False,
        "assessment_available": False,
        "assessment_id": None,
    }
    row.update(extra)
    return row


def _shaped_resource(rid=_RID, title="Python for Everybody", **overrides):
    row = {
        "id": rid,
        "title": title,
        "description": "A gentle intro.",
        "url": "https://www.py4e.com/",
        "provider": "py4e",
        "resource_type": "COURSE",
        "difficulty": "Beginner",
        "estimated_minutes": 1200,
        "skills": [{"skill_id": _SKILL_A, "skill_name": "Python", "target_level": "Beginner"}],
        "progress": None,
    }
    row.update(overrides)
    return row


def _code_only(module_or_fn) -> str:
    """Source with triple-quoted strings (docstrings) and `#` comment lines
    removed -- so an assertion about what the *code* does isn't tripped by
    the prose that explains it."""
    src = inspect.getsource(module_or_fn)
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    return "\n".join(
        ln for ln in src.splitlines() if not ln.lstrip().startswith("#")
    )


def _fluent(final_data):
    q = MagicMock()
    for method in ("select", "eq", "in_", "order", "maybe_single"):
        getattr(q, method).return_value = q
    q.execute.return_value.data = final_data
    return q


# ============================================================
# A. Authentication / role
# ============================================================


def test_recommended_rejects_unauthenticated():
    assert client.get(_URL).status_code == 401


def test_recommended_forbids_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.get(_URL, headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, role


# ============================================================
# B. Identity -- server-derived only
# ============================================================


def test_route_takes_no_student_id_or_skill_parameter():
    params = set(inspect.signature(routes.list_recommended_resources).parameters)
    assert params == {"current_user"}


def test_route_ignores_client_supplied_skill_and_student_id_query_params():
    """A malicious client cannot ask for someone else's recommendations or
    for an arbitrary skill: unknown query params are simply ignored and
    the gap is still computed from the authenticated identity."""
    captured = {}

    def fake_get(_client, student_id, gap_skills):
        captured["student_id"] = student_id
        captured["skill_ids"] = [s["skill_id"] for s in gap_skills]
        return []

    with (
        authenticated_as("STUDENT", user_id="student-real"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=None),
        patch.object(
            skill_gap_service,
            "compute_personal_analysis",
            return_value={"recommendations": [_rec(_SKILL_A, "Python")]},
        ),
        patch.object(rec_svc, "get_recommended_resources", side_effect=fake_get),
    ):
        resp = client.get(
            f"{_URL}?student_id=victim&skill_id={_SKILL_C}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["student_id"] == "student-real"
    assert captured["skill_ids"] == [_SKILL_A]  # from the engine, not the query string


# ============================================================
# C. Skill Gap integration -- consumes the canonical engine
# ============================================================


def test_personal_mode_consumes_compute_personal_analysis_recommendations():
    captured = {}

    def fake_get(_client, _student_id, gap_skills):
        captured["gap_skills"] = gap_skills
        return []

    recs = [_rec(_SKILL_A, "Python"), _rec(_SKILL_B, "Docker", priority="MEDIUM")]
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=None),
        patch.object(
            skill_gap_service,
            "compute_personal_analysis",
            return_value={"recommendations": recs, "counts": {}, "progressable_skills": []},
        ),
        patch.object(rec_svc, "get_recommended_resources", side_effect=fake_get),
    ):
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "PERSONAL"
    assert captured["gap_skills"] == recs


def test_job_role_mode_consumes_compute_job_role_gap_recommendations():
    role = {"id": str(uuid4()), "name": "Backend Developer"}
    target_row = {"id": str(uuid4()), "job_role": role}
    recs = [_rec(_SKILL_A, "Python")]
    captured = {}

    def fake_get(_client, _student_id, gap_skills):
        captured["gap_skills"] = gap_skills
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=target_row),
        patch.object(skill_gap_service, "get_job_role_requirements", return_value=[]),
        patch.object(
            skill_gap_service,
            "compute_job_role_gap",
            return_value={"recommendations": recs, "skills": [], "readiness_percentage": 10},
        ),
        patch.object(rec_svc, "get_recommended_resources", side_effect=fake_get),
    ):
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "JOB_ROLE"
    assert captured["gap_skills"] == recs


def test_route_does_not_reimplement_the_gap_engine():
    """The route dispatches to skill_gap_service exactly like GET
    /skill-gap; the adapter never imports skill_gap_service and computes no
    proficiency/readiness/status of its own."""
    adapter_src = _code_only(rec_svc)
    assert "skill_gap_service" not in adapter_src
    for banned in ("readiness", "calculate_status", "calculate_priority", "LEVEL_ORDER", "proficiency"):
        assert banned not in adapter_src, banned
    route_src = inspect.getsource(routes.list_recommended_resources)
    assert "skill_gap_service.get_target_job_role" in route_src
    assert "skill_gap_service.compute_personal_analysis" in route_src
    assert "skill_gap_service.compute_job_role_gap" in route_src


def test_response_matched_skills_are_trimmed_to_four_fields():
    entry = {
        "resource": _shaped_resource(),
        "matched_skills": [_rec(_SKILL_A, "Python", reason="Python is core.")],
    }
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=None),
        patch.object(
            skill_gap_service, "compute_personal_analysis", return_value={"recommendations": []}
        ),
        patch.object(rec_svc, "get_recommended_resources", return_value=[entry]),
    ):
        resp = client.get(_URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()
    matched = body["recommendations"][0]["matched_skills"][0]
    assert set(matched) == {"skill_id", "skill_name", "reason", "priority"}
    assert matched == {
        "skill_id": _SKILL_A,
        "skill_name": "Python",
        "reason": "Python is core.",
        "priority": "HIGH",
    }
    # the resource itself never leaks internal columns
    assert "is_active" not in body["recommendations"][0]["resource"]


# ============================================================
# D. Resource matching (adapter service layer)
# ============================================================


def test_adapter_matches_resources_by_canonical_skill_id():
    supabase = MagicMock()
    supabase.table.return_value = _fluent([{"resource_id": _RID, "skill_id": _SKILL_A}])
    with patch.object(
        sl_svc, "list_resources_by_ids", return_value=[_shaped_resource(_RID)]
    ) as mock_list:
        out = rec_svc.get_recommended_resources(
            supabase, "student-1", [_rec(_SKILL_A, "Python")]
        )
    mock_list.assert_called_once_with(supabase, "student-1", [_RID])
    assert len(out) == 1
    assert out[0]["resource"]["id"] == _RID
    assert [s["skill_id"] for s in out[0]["matched_skills"]] == [_SKILL_A]


def test_adapter_ignores_links_for_skills_not_in_the_gap():
    supabase = MagicMock()
    supabase.table.return_value = _fluent(
        [
            {"resource_id": _RID, "skill_id": _SKILL_A},
            {"resource_id": _RID2, "skill_id": _SKILL_C},  # not a gap skill
        ]
    )
    with patch.object(
        sl_svc, "list_resources_by_ids", return_value=[_shaped_resource(_RID)]
    ) as mock_list:
        rec_svc.get_recommended_resources(supabase, "student-1", [_rec(_SKILL_A, "Python")])
    # only the resource mapped to the actual gap skill is looked up
    mock_list.assert_called_once_with(supabase, "student-1", [_RID])


def test_adapter_returns_each_resource_once_with_all_matched_gap_skills():
    supabase = MagicMock()
    supabase.table.return_value = _fluent(
        [
            {"resource_id": _RID, "skill_id": _SKILL_A},
            {"resource_id": _RID, "skill_id": _SKILL_B},
        ]
    )
    with patch.object(sl_svc, "list_resources_by_ids", return_value=[_shaped_resource(_RID)]):
        out = rec_svc.get_recommended_resources(
            supabase,
            "student-1",
            [_rec(_SKILL_A, "Python", priority="MEDIUM"), _rec(_SKILL_B, "Docker", priority="HIGH")],
        )
    assert len(out) == 1
    matched = out[0]["matched_skills"]
    assert [s["skill_id"] for s in matched] == [_SKILL_B, _SKILL_A]  # HIGH before MEDIUM


def test_adapter_orders_resources_by_best_matched_priority_then_title():
    supabase = MagicMock()
    supabase.table.return_value = _fluent(
        [
            {"resource_id": _RID, "skill_id": _SKILL_A},   # MEDIUM
            {"resource_id": _RID2, "skill_id": _SKILL_B},  # HIGH
        ]
    )
    resources = [
        _shaped_resource(_RID, title="AAA course"),
        _shaped_resource(_RID2, title="ZZZ course"),
    ]
    with patch.object(sl_svc, "list_resources_by_ids", return_value=resources):
        out = rec_svc.get_recommended_resources(
            supabase,
            "student-1",
            [_rec(_SKILL_A, "Python", priority="MEDIUM"), _rec(_SKILL_B, "Docker", priority="HIGH")],
        )
    assert [e["resource"]["id"] for e in out] == [_RID2, _RID]  # HIGH resource first


def test_adapter_inactive_resource_is_absent_because_list_by_ids_filters_it():
    supabase = MagicMock()
    supabase.table.return_value = _fluent([{"resource_id": _RID, "skill_id": _SKILL_A}])
    # list_resources_by_ids applies .eq("is_active", True) -> an inactive
    # resource simply isn't returned, so it never reaches the output.
    with patch.object(sl_svc, "list_resources_by_ids", return_value=[]):
        out = rec_svc.get_recommended_resources(
            supabase, "student-1", [_rec(_SKILL_A, "Python")]
        )
    assert out == []


# ============================================================
# E. Empty states
# ============================================================


def test_adapter_empty_when_no_gap_recommendations():
    supabase = MagicMock()
    assert rec_svc.get_recommended_resources(supabase, "student-1", []) == []
    supabase.table.assert_not_called()


def test_adapter_empty_when_gap_exists_but_no_mapped_resources():
    supabase = MagicMock()
    supabase.table.return_value = _fluent([])  # no learning_resource_skills rows
    with patch.object(sl_svc, "list_resources_by_ids") as mock_list:
        out = rec_svc.get_recommended_resources(
            supabase, "student-1", [_rec(_SKILL_A, "Python")]
        )
    assert out == []
    mock_list.assert_not_called()


# ============================================================
# list_resources_by_ids (added to student_learning_service in Phase 6D)
# ============================================================


def test_list_resources_by_ids_filters_active_and_uses_id_in():
    supabase = MagicMock()
    q = _fluent([])
    supabase.table.return_value = q
    with patch.object(sl_svc, "_own_progress_map", return_value={}):
        sl_svc.list_resources_by_ids(supabase, "student-1", [_RID, _RID, _RID2])
    eq_calls = [c.args for c in q.eq.call_args_list]
    in_calls = [c.args for c in q.in_.call_args_list]
    assert ("is_active", True) in eq_calls
    assert ("id", [_RID, _RID2]) in in_calls  # de-duped + sorted
    q.order.assert_called_with("title")


def test_list_resources_by_ids_empty_input_short_circuits():
    supabase = MagicMock()
    assert sl_svc.list_resources_by_ids(supabase, "student-1", []) == []
    supabase.table.assert_not_called()


# ============================================================
# F. Security
# ============================================================


def test_recommendation_path_never_uses_service_role():
    assert not hasattr(rec_svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")


def test_adapter_never_writes_anything():
    src = inspect.getsource(rec_svc).replace("\n", "").replace(" ", "")
    for write in (".insert(", ".update(", ".upsert(", ".delete("):
        assert write not in src, f"learning_recommendation_service must not {write}"


def test_adapter_never_touches_student_skills_or_assessment_tables():
    src = _code_only(rec_svc)
    for banned in ("student_skills", "assessment_attempts", "assessment_answers", "assessments"):
        assert banned not in src, banned


def test_adapter_only_reads_learning_resource_skills_directly():
    """The adapter's own Supabase call is a single read against
    learning_resource_skills; resource fetching is delegated to
    student_learning_service."""
    compact = inspect.getsource(rec_svc).replace("\n", "").replace(" ", "")
    tables = set(re.findall(r'\.table\("([a-z_]+)"\)', compact))
    assert tables == {"learning_resource_skills"}


def test_no_import_cycle_between_adapter_and_gap_service():
    assert "learning_recommendation_service" not in _code_only(skill_gap_service)
    assert "skill_gap_service" not in _code_only(rec_svc)
