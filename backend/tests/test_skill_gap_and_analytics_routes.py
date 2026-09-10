"""Route tests for the two routers that were implemented but left
UNMOUNTED from app.main until the integration pass that added
`app.include_router(skill_gap.router)` / `app.include_router(analytics.router)`:

  * app.api.skill_gap  -- GET /job-roles, GET /job-roles/{id},
    GET|PUT|DELETE /student/target-job-role, GET /skill-gap,
    GET /skill-gap/job-role/{id}
  * app.api.analytics  -- GET /analytics/industry

Same convention as test_career_roles.py / test_institution_analytics.py:
no live Supabase project or real token -- the auth dependency chain is
mocked (see conftest.authenticated_as) and the service layer is patched
directly.

The final section is a deliberate REGRESSION guard: it fails if either
router is dropped from app.main again.
"""

from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import analytics_service, skill_gap_service
from tests.conftest import authenticated_as

client = TestClient(app)

AUTH = {"Authorization": "Bearer token"}


# ============================================================
# fixtures
# ============================================================


def _job_role_row(**overrides):
    row = {
        "id": str(uuid4()),
        "name": "Backend Engineer",
        "description": "Designs and builds APIs and services.",
        "category": "Engineering",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _requirement_row(**overrides):
    row = {
        "skill_id": str(uuid4()),
        "skill_name": "Python",
        "category_name": "Programming",
        "required_level": "Intermediate",
        "importance": "CORE",
    }
    row.update(overrides)
    return row


def _target_row(job_role=None):
    return {
        "id": str(uuid4()),
        "job_role": job_role or _job_role_row(),
        "created_at": "2026-02-01T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
    }


def _job_role_gap():
    """What skill_gap_service.compute_job_role_gap returns -- the route
    adds `mode` and `job_role` on top."""
    return {
        "readiness_percentage": 50,
        "summary": {"matched": 1, "needs_improvement": 1, "missing": 0, "unverified": 0},
        "skills": [],
        "recommendations": [],
    }


def _personal_analysis():
    """What skill_gap_service.compute_personal_analysis returns -- the
    route adds `mode` on top."""
    return {
        "counts": {
            "total_active_skills": 0,
            "verified_skills": 0,
            "unverified_skills": 0,
            "beginner_skills": 0,
            "intermediate_skills": 0,
            "advanced_skills": 0,
            "expert_skills": 0,
        },
        "progressable_skills": [],
        "recommendations": [],
        "prerequisite_gaps": [],
    }


def _empty_analytics():
    return {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "kpis": {
            "opportunities_total": 0,
            "opportunities_published": 0,
            "applications_total": 0,
            "shortlisted": 0,
            "interviews_total": 0,
            "interviews_upcoming": 0,
            "selected": 0,
            "collaborations_total": 0,
            "collaborations_active": 0,
        },
        "funnel_counts": {},
        "funnel_total": 0,
        "application_status_distribution": [],
        "opportunity_breakdown": [],
        "interview_metrics": {
            "total": 0,
            "scheduled": 0,
            "completed": 0,
            "cancelled": 0,
            "upcoming": 0,
        },
        "top_opportunities": [],
        "timeline": [],
        "historical_note": "Only record-creation dates are available.",
        "interviews_available": False,
    }


# ============================================================
# GET /api/v1/job-roles
# ============================================================


def test_list_job_roles_requires_authentication():
    assert client.get("/api/v1/job-roles").status_code == 401


def test_list_job_roles_forbids_non_student_roles():
    for role in ("FACULTY", "INDUSTRY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get("/api/v1/job-roles", headers=AUTH)
        assert resp.status_code == 403, role


def test_list_job_roles_authenticated_student_returns_roles():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "list_active_job_roles", return_value=[_job_role_row()]),
    ):
        resp = client.get("/api/v1/job-roles", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["job_roles"][0]["name"] == "Backend Engineer"


def test_list_job_roles_empty_state_is_200_not_error():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "list_active_job_roles", return_value=[]),
    ):
        resp = client.get("/api/v1/job-roles", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"job_roles": []}


# ============================================================
# GET /api/v1/job-roles/{id}
# ============================================================


def test_get_job_role_requires_authentication():
    assert client.get(f"/api/v1/job-roles/{uuid4()}").status_code == 401


def test_get_job_role_forbids_non_student():
    with authenticated_as("INDUSTRY"):
        resp = client.get(f"/api/v1/job-roles/{uuid4()}", headers=AUTH)
    assert resp.status_code == 403


def test_get_job_role_rejects_non_uuid_id():
    with authenticated_as("STUDENT"):
        resp = client.get("/api/v1/job-roles/not-a-uuid", headers=AUTH)
    assert resp.status_code == 422


def test_get_job_role_missing_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=None),
    ):
        resp = client.get(f"/api/v1/job-roles/{uuid4()}", headers=AUTH)
    assert resp.status_code == 404


def test_get_job_role_found_returns_role_and_requirements():
    role_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=_job_role_row(id=str(role_id))),
        patch.object(skill_gap_service, "get_job_role_requirements", return_value=[_requirement_row()]),
    ):
        resp = client.get(f"/api/v1/job-roles/{role_id}", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"]["id"] == str(role_id)
    assert body["requirements"][0]["skill_name"] == "Python"


# ============================================================
# GET /api/v1/student/target-job-role
# ============================================================


def test_get_target_job_role_requires_authentication():
    assert client.get("/api/v1/student/target-job-role").status_code == 401


def test_get_target_job_role_forbids_non_student():
    with authenticated_as("FACULTY"):
        resp = client.get("/api/v1/student/target-job-role", headers=AUTH)
    assert resp.status_code == 403


def test_get_target_job_role_none_set_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=None),
    ):
        resp = client.get("/api/v1/student/target-job-role", headers=AUTH)
    assert resp.status_code == 404


def test_get_target_job_role_resolves_from_token_not_a_query_param():
    with (
        authenticated_as("STUDENT", user_id="real-student"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=_target_row()) as mock_get,
    ):
        resp = client.get(
            "/api/v1/student/target-job-role?student_id=someone-else", headers=AUTH
        )
    assert resp.status_code == 200
    _client_arg, student_id_arg = mock_get.call_args.args
    assert student_id_arg == "real-student"


# ============================================================
# PUT /api/v1/student/target-job-role
# ============================================================


def test_put_target_job_role_requires_authentication():
    assert client.put("/api/v1/student/target-job-role", json={"job_role_id": str(uuid4())}).status_code == 401


def test_put_target_job_role_forbids_non_student():
    with authenticated_as("INDUSTRY"):
        resp = client.put(
            "/api/v1/student/target-job-role", json={"job_role_id": str(uuid4())}, headers=AUTH
        )
    assert resp.status_code == 403


def test_put_target_job_role_missing_body_is_422():
    with authenticated_as("STUDENT"):
        resp = client.put("/api/v1/student/target-job-role", headers=AUTH)
    assert resp.status_code == 422


def test_put_target_job_role_rejects_smuggled_student_id():
    with authenticated_as("STUDENT"):
        resp = client.put(
            "/api/v1/student/target-job-role",
            json={"job_role_id": str(uuid4()), "student_id": "someone-else"},
            headers=AUTH,
        )
    assert resp.status_code == 422  # SetTargetJobRoleRequest is extra="forbid"


def test_put_target_job_role_rejects_non_uuid_job_role_id():
    with authenticated_as("STUDENT"):
        resp = client.put(
            "/api/v1/student/target-job-role", json={"job_role_id": "nope"}, headers=AUTH
        )
    assert resp.status_code == 422


def test_put_target_job_role_unknown_role_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=None),
        patch.object(skill_gap_service, "set_target_job_role") as mock_set,
    ):
        resp = client.put(
            "/api/v1/student/target-job-role", json={"job_role_id": str(uuid4())}, headers=AUTH
        )
    assert resp.status_code == 404
    mock_set.assert_not_called()


def test_put_target_job_role_success_uses_token_identity():
    role_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="real-student"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=_job_role_row(id=str(role_id))),
        patch.object(skill_gap_service, "set_target_job_role", return_value=_target_row(_job_role_row(id=str(role_id)))) as mock_set,
    ):
        resp = client.put(
            "/api/v1/student/target-job-role", json={"job_role_id": str(role_id)}, headers=AUTH
        )
    assert resp.status_code == 200
    assert resp.json()["job_role"]["id"] == str(role_id)
    _client_arg, student_id_arg, job_role_id_arg = mock_set.call_args.args
    assert student_id_arg == "real-student"
    assert str(job_role_id_arg) == str(role_id)


# ============================================================
# DELETE /api/v1/student/target-job-role
# ============================================================


def test_delete_target_job_role_requires_authentication():
    assert client.delete("/api/v1/student/target-job-role").status_code == 401


def test_delete_target_job_role_forbids_non_student():
    with authenticated_as("ADMIN"):
        resp = client.delete("/api/v1/student/target-job-role", headers=AUTH)
    assert resp.status_code == 403


def test_delete_target_job_role_is_204_and_idempotent():
    with (
        authenticated_as("STUDENT", user_id="real-student"),
        patch.object(skill_gap_service, "clear_target_job_role", return_value=None) as mock_clear,
    ):
        resp = client.delete("/api/v1/student/target-job-role", headers=AUTH)
    assert resp.status_code == 204
    assert resp.content == b""
    _client_arg, student_id_arg = mock_clear.call_args.args
    assert student_id_arg == "real-student"


# ============================================================
# GET /api/v1/skill-gap  (own analysis: target role, else personal)
# ============================================================


def test_skill_gap_requires_authentication():
    assert client.get("/api/v1/skill-gap").status_code == 401


def test_skill_gap_forbids_non_student():
    with authenticated_as("FACULTY"):
        resp = client.get("/api/v1/skill-gap", headers=AUTH)
    assert resp.status_code == 403


def test_skill_gap_no_target_role_returns_personal_mode_empty_state():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=None),
        patch.object(skill_gap_service, "compute_personal_analysis", return_value=_personal_analysis()),
    ):
        resp = client.get("/api/v1/skill-gap", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "PERSONAL"
    assert body["counts"]["total_active_skills"] == 0
    assert body["recommendations"] == []


def test_skill_gap_with_target_role_returns_job_role_mode():
    role = _job_role_row()
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=_target_row(role)),
        patch.object(skill_gap_service, "get_job_role_requirements", return_value=[_requirement_row()]),
        patch.object(skill_gap_service, "compute_job_role_gap", return_value=_job_role_gap()),
    ):
        resp = client.get("/api/v1/skill-gap", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "JOB_ROLE"
    assert body["job_role"]["id"] == role["id"]
    assert body["readiness_percentage"] == 50


def test_skill_gap_resolves_student_from_token():
    with (
        authenticated_as("STUDENT", user_id="real-student"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=None) as mock_target,
        patch.object(skill_gap_service, "compute_personal_analysis", return_value=_personal_analysis()) as mock_personal,
    ):
        resp = client.get("/api/v1/skill-gap?student_id=someone-else", headers=AUTH)
    assert resp.status_code == 200
    assert mock_target.call_args.args[1] == "real-student"
    assert mock_personal.call_args.args[1] == "real-student"


# ============================================================
# GET /api/v1/skill-gap/job-role/{id}
# ============================================================


def test_skill_gap_for_job_role_requires_authentication():
    assert client.get(f"/api/v1/skill-gap/job-role/{uuid4()}").status_code == 401


def test_skill_gap_for_job_role_forbids_non_student():
    with authenticated_as("INDUSTRY"):
        resp = client.get(f"/api/v1/skill-gap/job-role/{uuid4()}", headers=AUTH)
    assert resp.status_code == 403


def test_skill_gap_for_job_role_rejects_non_uuid():
    with authenticated_as("STUDENT"):
        resp = client.get("/api/v1/skill-gap/job-role/not-a-uuid", headers=AUTH)
    assert resp.status_code == 422


def test_skill_gap_for_job_role_unknown_role_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=None),
        patch.object(skill_gap_service, "compute_job_role_gap") as mock_gap,
    ):
        resp = client.get(f"/api/v1/skill-gap/job-role/{uuid4()}", headers=AUTH)
    assert resp.status_code == 404
    mock_gap.assert_not_called()


def test_skill_gap_for_job_role_success():
    role_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="real-student"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=_job_role_row(id=str(role_id))),
        patch.object(skill_gap_service, "get_job_role_requirements", return_value=[_requirement_row()]),
        patch.object(skill_gap_service, "compute_job_role_gap", return_value=_job_role_gap()) as mock_gap,
    ):
        resp = client.get(f"/api/v1/skill-gap/job-role/{role_id}", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "JOB_ROLE"
    assert body["job_role"]["id"] == str(role_id)
    assert mock_gap.call_args.args[1] == "real-student"


# ============================================================
# GET /api/v1/analytics/industry
# ============================================================


def test_analytics_industry_requires_authentication():
    assert client.get("/api/v1/analytics/industry").status_code == 401


def test_analytics_industry_forbids_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get("/api/v1/analytics/industry", headers=AUTH)
        assert resp.status_code == 403, role


def test_analytics_industry_empty_account_returns_all_zeros_not_error():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(analytics_service, "compute_industry_analytics", return_value=_empty_analytics()) as mock_compute,
    ):
        resp = client.get("/api/v1/analytics/industry", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["kpis"]["applications_total"] == 0
    assert body["interviews_available"] is False
    assert mock_compute.call_args.args[1] == "industry-1"


def test_analytics_industry_scopes_to_authenticated_industry_not_a_param():
    with (
        authenticated_as("INDUSTRY", user_id="the-real-industry"),
        patch.object(analytics_service, "compute_industry_analytics", return_value=_empty_analytics()) as mock_compute,
    ):
        resp = client.get(
            "/api/v1/analytics/industry?industry_id=someone-else", headers=AUTH
        )
    assert resp.status_code == 200
    assert mock_compute.call_args.args[1] == "the-real-industry"


# ============================================================
# REGRESSION: these routers must stay mounted in app.main
# ============================================================
#
# skill_gap.py and analytics.py are fully implemented but were left out of
# app.main.include_router() for a long time, so every route below 404'd in
# production while unit tests (which build their own app or mock at the
# service layer) stayed green. These tests fail if either
# `app.include_router(skill_gap.router, ...)` or
# `app.include_router(analytics.router, ...)` is removed again.


SKILL_GAP_ROUTES = [
    ("GET", "/api/v1/job-roles"),
    ("GET", "/api/v1/job-roles/{job_role_id}"),
    ("GET", "/api/v1/student/target-job-role"),
    ("PUT", "/api/v1/student/target-job-role"),
    ("DELETE", "/api/v1/student/target-job-role"),
    ("GET", "/api/v1/skill-gap"),
    ("GET", "/api/v1/skill-gap/job-role/{job_role_id}"),
]
ANALYTICS_ROUTES = [("GET", "/api/v1/analytics/industry")]


def test_skill_gap_and_analytics_routes_are_registered_in_the_openapi_schema():
    paths = app.openapi()["paths"]
    for method, path in SKILL_GAP_ROUTES + ANALYTICS_ROUTES:
        assert path in paths, f"{path} is not registered -- is its router still in app.main?"
        assert method.lower() in paths[path], f"{method} {path} is missing"


def test_every_route_the_skill_gap_router_declares_is_mounted_on_the_app():
    """Ties the router OBJECT to app.main: every path skill_gap.router
    declares must be reachable in the app's OpenAPI schema under the
    /api/v1 prefix. Removing include_router(skill_gap.router) drops all of
    them and fails this."""
    from app.api import skill_gap

    mounted = set(app.openapi()["paths"])
    declared = {"/api/v1" + r.path for r in skill_gap.router.routes}
    assert declared, "skill_gap.router declares no routes -- test needs updating"
    assert declared <= mounted, (
        f"skill_gap routes not mounted in app.main: {sorted(declared - mounted)}"
    )


def test_every_route_the_analytics_router_declares_is_mounted_on_the_app():
    from app.api import analytics

    mounted = set(app.openapi()["paths"])
    declared = {"/api/v1" + r.path for r in analytics.router.routes}
    assert declared, "analytics.router declares no routes -- test needs updating"
    assert declared <= mounted, (
        f"analytics routes not mounted in app.main: {sorted(declared - mounted)}"
    )


def test_mounted_routes_answer_401_when_unauthenticated_never_404():
    """The clearest symptom of an unmounted router is a 404 where a 401
    belongs. Every route below is auth-guarded, so an unauthenticated hit
    must be 401 -- never 404."""
    for method, path in SKILL_GAP_ROUTES + ANALYTICS_ROUTES:
        concrete = path.replace("{job_role_id}", str(uuid4()))
        resp = client.request(method, concrete)
        assert resp.status_code == 401, f"{method} {concrete} -> {resp.status_code} (router unmounted?)"
