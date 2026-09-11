"""Tests for the shared skill catalog: app.services.skill_service and
GET /api/v1/skills (app.api.skills).

Same convention as test_career_roles.py / test_skill_gap_and_analytics_
routes.py: no live Supabase project or real token -- the auth dependency
chain is mocked (see conftest.py), and the service layer is patched
directly for route tests / driven with a MagicMock client for service
tests.

This endpoint was previously an empty `APIRouter()` with no route
handlers, never mounted on app.main -- every Industry/Institution page
that reads the catalog (Create Internship, Create Job, the skill-
requirements picker) got a 404 and fell back to its "skill catalog
couldn't be loaded" warning. The final section is a regression guard for
exactly that: it fails if `app.include_router(skills.router)` is dropped
from app.main again.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import skill_service
from tests.conftest import authenticated_as

client = TestClient(app)

AUTH = {"Authorization": "Bearer token"}
URL = "/api/v1/skills"


def _skill_row(**overrides):
    row = {
        "id": "skill-1",
        "name": "Python",
        "category_name": "Programming Languages",
        "description": "General-purpose language widely used in web, data, and AI.",
    }
    row.update(overrides)
    return row


# ============================================================
# skill_service.list_active_skills
# ============================================================


def _mock_skills_response(mock_client, rows):
    response = MagicMock()
    response.data = rows
    (
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute
    ).return_value = response
    (
        mock_client.table.return_value.select.return_value.eq.return_value.ilike.return_value.order.return_value.execute
    ).return_value = response


def test_list_active_skills_filters_is_active_true():
    mock_client = MagicMock()
    _mock_skills_response(
        mock_client,
        [{"id": "s1", "name": "Python", "description": None, "category": {"name": "Programming"}}],
    )

    rows = skill_service.list_active_skills(mock_client)

    mock_client.table.assert_called_with("skills")
    eq_call = mock_client.table.return_value.select.return_value.eq.call_args
    assert eq_call.args == ("is_active", True)
    assert rows == [{"id": "s1", "name": "Python", "description": None, "category_name": "Programming"}]


def test_list_active_skills_flattens_category_name():
    mock_client = MagicMock()
    _mock_skills_response(
        mock_client,
        [{"id": "s1", "name": "SQL", "description": "Query language.", "category": {"name": "Data"}}],
    )

    rows = skill_service.list_active_skills(mock_client)

    assert rows[0]["category_name"] == "Data"
    assert "category" not in rows[0]


def test_list_active_skills_handles_missing_category_embed():
    """A skill whose category was deactivated/removed comes back with
    category_name=None rather than crashing -- same defensive pattern as
    internship_service._shape's skill embed handling."""
    mock_client = MagicMock()
    _mock_skills_response(
        mock_client,
        [{"id": "s1", "name": "Orphaned Skill", "description": None, "category": None}],
    )

    rows = skill_service.list_active_skills(mock_client)

    assert rows[0]["category_name"] is None


def test_list_active_skills_empty_catalog_returns_empty_list():
    mock_client = MagicMock()
    _mock_skills_response(mock_client, [])

    rows = skill_service.list_active_skills(mock_client)

    assert rows == []


def test_list_active_skills_no_data_returns_empty_list_not_none():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = None
    (
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute
    ).return_value = response

    rows = skill_service.list_active_skills(mock_client)

    assert rows == []


def test_list_active_skills_applies_search_as_ilike():
    mock_client = MagicMock()
    _mock_skills_response(mock_client, [])

    skill_service.list_active_skills(mock_client, search="pyth")

    ilike_call = (
        mock_client.table.return_value.select.return_value.eq.return_value.ilike.call_args
    )
    assert ilike_call.args == ("name", "%pyth%")


def test_list_active_skills_no_search_never_calls_ilike():
    mock_client = MagicMock()
    _mock_skills_response(mock_client, [])

    skill_service.list_active_skills(mock_client)

    mock_client.table.return_value.select.return_value.eq.return_value.ilike.assert_not_called()


def test_list_active_skills_blank_search_is_treated_as_no_filter():
    mock_client = MagicMock()
    _mock_skills_response(mock_client, [])

    skill_service.list_active_skills(mock_client, search="")

    mock_client.table.return_value.select.return_value.eq.return_value.ilike.assert_not_called()


def test_list_active_skills_orders_by_name():
    mock_client = MagicMock()
    _mock_skills_response(mock_client, [])

    skill_service.list_active_skills(mock_client)

    mock_client.table.return_value.select.return_value.eq.return_value.order.assert_called_with("name")


# ============================================================
# API: GET /api/v1/skills
# ============================================================


def test_list_skills_requires_authentication():
    assert client.get(URL).status_code == 401


def test_list_skills_allowed_for_every_role():
    """Reference-data read, same precedent as GET /career-roles and
    GET /assessments -- RLS itself never role-restricts the active skill
    catalog, so no role is rejected here."""
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "INSTITUTION", "ADMIN"):
        with (
            authenticated_as(role),
            patch.object(skill_service, "list_active_skills", return_value=[_skill_row()]),
        ):
            resp = client.get(URL, headers=AUTH)
        assert resp.status_code == 200, role


def test_list_skills_unauthenticated_role_is_403_not_200():
    """A signed-in user whose profile has no role yet (mid-onboarding) is
    still authenticated but has no assigned role -- get_current_user
    resolves role=None for them, which is a valid caller identity, not a
    401. This endpoint has no role Depends() at all, so it must still
    succeed (same as career-roles) rather than silently reject."""
    with (
        authenticated_as(None),
        patch.object(skill_service, "list_active_skills", return_value=[]),
    ):
        resp = client.get(URL, headers=AUTH)
    assert resp.status_code == 200


def test_list_skills_returns_the_full_catalog_shape():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(skill_service, "list_active_skills", return_value=[_skill_row()]) as mock_list,
    ):
        resp = client.get(URL, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "skills": [
            {
                "id": "skill-1",
                "name": "Python",
                "category_name": "Programming Languages",
                "description": "General-purpose language widely used in web, data, and AI.",
            }
        ]
    }
    mock_list.assert_called_once()


def test_list_skills_empty_catalog_is_200_with_empty_list_not_an_error():
    """A successfully-empty catalog must never be indistinguishable from a
    failed request -- this is a 200 with `skills: []`, not a 500/404."""
    with (
        authenticated_as("INDUSTRY"),
        patch.object(skill_service, "list_active_skills", return_value=[]),
    ):
        resp = client.get(URL, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"skills": []}


def test_list_skills_forwards_search_query_param():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(skill_service, "list_active_skills", return_value=[]) as mock_list,
    ):
        resp = client.get(f"{URL}?search=python", headers=AUTH)
    assert resp.status_code == 200
    assert mock_list.call_args.kwargs == {"search": "python"}


def test_list_skills_no_search_param_passes_none():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(skill_service, "list_active_skills", return_value=[]) as mock_list,
    ):
        client.get(URL, headers=AUTH)
    assert mock_list.call_args.kwargs == {"search": None}


def test_list_skills_service_failure_returns_500_not_a_raw_exception():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(skill_service, "list_active_skills", side_effect=RuntimeError("db unreachable")),
    ):
        resp = client.get(URL, headers=AUTH)
    assert resp.status_code == 500
    assert "Could not load the skill catalog" in resp.json()["detail"]


# ============================================================
# REGRESSION: this router must stay mounted in app.main
# ============================================================
#
# app/api/skills.py previously existed as an empty `APIRouter()` with no
# handlers and was never included in app.main -- every caller of GET
# /api/v1/skills (Industry's Create Internship / Create Job pages, the
# skill-requirements picker, Institution's placement-drive form) got a
# plain 404 and silently fell back to "the skill catalog couldn't be
# loaded". These tests fail if the route/router disappears again.


def test_skills_route_is_registered_in_the_openapi_schema():
    paths = app.openapi()["paths"]
    assert URL in paths, f"{URL} is not registered -- is skills.router still in app.main?"
    assert "get" in paths[URL]


def test_every_route_the_skills_router_declares_is_mounted_on_the_app():
    from app.api import skills

    mounted = set(app.openapi()["paths"])
    declared = {"/api/v1" + r.path for r in skills.router.routes}
    assert declared, "skills.router declares no routes -- test needs updating"
    assert declared <= mounted, f"skills routes not mounted in app.main: {sorted(declared - mounted)}"


def test_skills_route_answers_401_when_unauthenticated_never_404():
    """The clearest symptom of an unmounted/unhandled router is a 404
    where a 401 belongs."""
    resp = client.get(URL)
    assert resp.status_code == 401, f"GET {URL} -> {resp.status_code} (router unmounted?)"
