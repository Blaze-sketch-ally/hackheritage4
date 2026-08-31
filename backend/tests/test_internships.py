"""Tests for Industry internship management (Phase 5):
/api/v1/internships (+ the shared GET /api/v1/skills).

Route tests mock app.services.internship_service and use
tests.conftest.authenticated_as, exactly like tests/test_skill_gap.py.
Service tests drive the functions with a MagicMock Supabase client and
patched helpers -- no live project or real token.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import internships as internship_routes
from app.main import app
from app.services import internship_service
from tests.conftest import authenticated_as

client = TestClient(app)

_SKILL_ID = str(uuid4())


def _row(**overrides):
    row = {
        "id": "int-1",
        "industry_id": "industry-1",
        "title": "Backend Intern",
        "description": "Work on APIs.",
        "location": "Pune",
        "work_mode": "HYBRID",
        "duration_months": 6,
        "stipend_amount": 15000.0,
        "stipend_currency": "INR",
        "openings": 2,
        "eligibility_criteria": None,
        "application_deadline": "2026-12-01",
        "start_date": None,
        "status": "DRAFT",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "skills": [
            {
                "skill_id": _SKILL_ID,
                "skill_name": "Python",
                "category_name": "Programming",
                "required_level": "Intermediate",
                "importance": "CORE",
            }
        ],
    }
    row.update(overrides)
    return row


def _create_body(**overrides):
    body = {"title": "Backend Intern", "description": "Work on APIs."}
    body.update(overrides)
    return body


# ============================================================
# Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/internships"),
    ("post", "/api/v1/internships"),
    ("get", f"/api/v1/internships/{uuid4()}"),
    ("put", f"/api/v1/internships/{uuid4()}"),
    ("post", f"/api/v1/internships/{uuid4()}/publish"),
    ("post", f"/api/v1/internships/{uuid4()}/close"),
    ("post", f"/api/v1/internships/{uuid4()}/archive"),
]


def _call(method: str, url: str, *, headers=None):
    if method in {"post", "put"}:
        return getattr(client, method)(url, json={"title": "x", "description": "y"}, headers=headers)
    return getattr(client, method)(url, headers=headers)


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        for method, url in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# List
# ============================================================


def test_list_returns_only_callers_internships():
    captured = {}

    def fake_list(_client, industry_id, *, status=None, search=None):
        captured["industry_id"] = industry_id
        captured["status"] = status
        captured["search"] = search
        return [_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(internship_service, "list_internships", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/internships?status=PUBLISHED&search=backend",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"industry_id": "industry-1", "status": "PUBLISHED", "search": "backend"}
    assert resp.json()["internships"][0]["id"] == "int-1"


def test_list_rejects_unknown_status_filter():
    with authenticated_as("INDUSTRY"):
        resp = client.get(
            "/api/v1/internships?status=NONSENSE", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


# ============================================================
# Create
# ============================================================


def test_create_derives_owner_from_token_and_starts_draft():
    captured = {}

    def fake_create(_client, industry_id, data, skills):
        captured["industry_id"] = industry_id
        captured["data"] = data
        captured["skills"] = skills
        return _row(industry_id=industry_id, status="DRAFT")

    with (
        authenticated_as("INDUSTRY", user_id="industry-99"),
        patch.object(internship_service, "create_internship", side_effect=fake_create),
    ):
        resp = client.post(
            "/api/v1/internships",
            json=_create_body(location="Pune"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert captured["industry_id"] == "industry-99"
    assert "industry_id" not in captured["data"]
    assert "status" not in captured["data"]
    assert resp.json()["status"] == "DRAFT"
    assert resp.json()["industry_id"] == "industry-99"


def test_create_rejects_client_supplied_industry_id():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/internships",
            json=_create_body(industry_id="attacker-owned"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_client_supplied_status():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/internships",
            json=_create_body(status="PUBLISHED"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_missing_title():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/internships",
            json={"description": "no title"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_maps_invalid_skill_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            internship_service,
            "create_internship",
            side_effect=internship_service.InvalidSkillError(["bad-id"]),
        ),
    ):
        resp = client.post(
            "/api/v1/internships",
            json=_create_body(skills=[{"skill_id": str(uuid4()), "required_level": "Beginner"}]),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


# ============================================================
# Detail / update -- ownership
# ============================================================


def test_get_detail_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(internship_service, "get_internship", return_value=None) as mock_get,
    ):
        resp = client.get(
            f"/api/v1/internships/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "industry-A"


def test_update_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(internship_service, "update_internship", return_value=None),
    ):
        resp = client.put(
            f"/api/v1/internships/{uuid4()}",
            json={"title": "New title"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_update_rejects_status_field():
    with authenticated_as("INDUSTRY"):
        resp = client.put(
            f"/api/v1/internships/{uuid4()}",
            json={"status": "PUBLISHED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_update_passes_owner_id_to_service():
    captured = {}

    def fake_update(_client, industry_id, internship_id, data, skills):
        captured["industry_id"] = industry_id
        return _row()

    with (
        authenticated_as("INDUSTRY", user_id="industry-7"),
        patch.object(internship_service, "update_internship", side_effect=fake_update),
    ):
        resp = client.put(
            f"/api/v1/internships/{uuid4()}",
            json={"title": "Updated"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-7"


# ============================================================
# Lifecycle endpoints -- ownership + error mapping
# ============================================================


def test_publish_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(internship_service, "publish_internship", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/internships/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_publish_missing_fields_maps_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            internship_service,
            "publish_internship",
            side_effect=internship_service.PublishValidationError(["location", "work_mode"]),
        ),
    ):
        resp = client.post(
            f"/api/v1/internships/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422
    assert "location" in resp.json()["detail"]


def test_publish_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            internship_service,
            "publish_internship",
            side_effect=internship_service.InvalidStatusTransitionError("ARCHIVED", "PUBLISHED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/internships/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def test_close_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(internship_service, "close_internship", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/internships/{uuid4()}/close", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_archive_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(internship_service, "archive_internship", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/internships/{uuid4()}/archive", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_archive_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            internship_service,
            "archive_internship",
            side_effect=internship_service.InvalidStatusTransitionError("ARCHIVED", "ARCHIVED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/internships/{uuid4()}/archive", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


# ============================================================
# Service layer
# ============================================================


def test_dedupe_skills_keeps_last_occurrence():
    out = internship_service._dedupe_skills(
        [
            {"skill_id": "s1", "required_level": "Beginner", "importance": "OPTIONAL"},
            {"skill_id": "s1", "required_level": "Advanced", "importance": "CORE"},
            {"skill_id": "s2", "required_level": "Intermediate"},
        ]
    )
    assert len(out) == 2
    s1 = next(s for s in out if s["skill_id"] == "s1")
    assert s1["required_level"] == "Advanced"
    assert s1["importance"] == "CORE"
    s2 = next(s for s in out if s["skill_id"] == "s2")
    assert s2["importance"] == "IMPORTANT"  # default applied


def test_create_forces_draft_and_owner_and_drops_junk():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "new-1"}]

    with (
        patch.object(internship_service, "_validate_skill_ids"),
        patch.object(internship_service, "get_internship", return_value=_row(id="new-1")),
    ):
        internship_service.create_internship(
            supabase,
            "industry-1",
            {"title": "T", "description": "D", "status": "PUBLISHED", "industry_id": "attacker", "id": "x"},
            [],
        )

    inserted = supabase.table.return_value.insert.call_args_list[0].args[0]
    assert inserted["status"] == "DRAFT"
    assert inserted["industry_id"] == "industry-1"
    assert "id" not in inserted


def test_create_validates_skills_before_inserting_internship():
    supabase = MagicMock()
    with (
        patch.object(
            internship_service,
            "_validate_skill_ids",
            side_effect=internship_service.InvalidSkillError(["bad"]),
        ),
        patch.object(internship_service, "get_internship", return_value=_row()),
    ):
        try:
            internship_service.create_internship(
                supabase,
                "industry-1",
                {"title": "T", "description": "D"},
                [{"skill_id": "bad", "required_level": "Beginner"}],
            )
            raised = False
        except internship_service.InvalidSkillError:
            raised = True

    assert raised
    supabase.table.return_value.insert.assert_not_called()


def test_update_never_writes_status():
    supabase = MagicMock()
    with patch.object(
        internship_service,
        "get_internship",
        side_effect=[_row(id="int-1"), _row(id="int-1", title="Updated")],
    ):
        internship_service.update_internship(
            supabase,
            "industry-1",
            "int-1",
            {"title": "Updated", "status": "PUBLISHED"},
            None,
        )
    updated = supabase.table.return_value.update.call_args.args[0]
    assert "status" not in updated
    assert updated == {"title": "Updated"}


def test_update_returns_none_when_not_owned():
    supabase = MagicMock()
    with patch.object(internship_service, "get_internship", return_value=None):
        result = internship_service.update_internship(
            supabase, "industry-1", "int-x", {"title": "Updated"}, None
        )
    assert result is None
    supabase.table.return_value.update.assert_not_called()


def test_publish_blocks_when_required_fields_missing():
    supabase = MagicMock()
    incomplete = _row(location=None, work_mode=None)
    with patch.object(internship_service, "get_internship", return_value=incomplete):
        try:
            internship_service.publish_internship(supabase, "industry-1", "int-1")
            missing = None
        except internship_service.PublishValidationError as exc:
            missing = exc.missing
    assert missing is not None
    assert "location" in missing and "work_mode" in missing
    supabase.table.return_value.update.assert_not_called()


def test_publish_blocks_when_no_skills():
    supabase = MagicMock()
    with patch.object(internship_service, "get_internship", return_value=_row(skills=[])):
        try:
            internship_service.publish_internship(supabase, "industry-1", "int-1")
            missing = None
        except internship_service.PublishValidationError as exc:
            missing = exc.missing
    assert missing == ["at least one required skill"]


def test_publish_sets_status_when_valid():
    supabase = MagicMock()
    with patch.object(
        internship_service,
        "get_internship",
        side_effect=[_row(status="DRAFT"), _row(status="PUBLISHED")],
    ):
        result = internship_service.publish_internship(supabase, "industry-1", "int-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "PUBLISHED"}
    assert result["status"] == "PUBLISHED"


def test_publish_rejects_from_archived():
    supabase = MagicMock()
    with patch.object(internship_service, "get_internship", return_value=_row(status="ARCHIVED")):
        try:
            internship_service.publish_internship(supabase, "industry-1", "int-1")
            raised = False
        except internship_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_close_only_from_published():
    supabase = MagicMock()
    with patch.object(internship_service, "get_internship", return_value=_row(status="DRAFT")):
        try:
            internship_service.close_internship(supabase, "industry-1", "int-1")
            raised = False
        except internship_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_archive_allowed_from_draft():
    supabase = MagicMock()
    with patch.object(
        internship_service,
        "get_internship",
        side_effect=[_row(status="DRAFT"), _row(status="ARCHIVED")],
    ):
        result = internship_service.archive_internship(supabase, "industry-1", "int-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "ARCHIVED"}
    assert result["status"] == "ARCHIVED"


def test_validate_skill_ids_raises_on_unknown():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.return_value.data = [
        {"id": "good"}
    ]
    try:
        internship_service._validate_skill_ids(supabase, ["good", "missing"])
        raised = False
    except internship_service.InvalidSkillError as exc:
        raised = True
        assert exc.skill_ids == ["missing"]
    assert raised


# ============================================================
# No service-role anywhere on this path
# ============================================================


def test_internship_modules_do_not_use_service_role():
    assert not hasattr(internship_service, "get_supabase")
    assert not hasattr(internship_routes, "get_supabase")
    assert hasattr(internship_routes, "build_user_client")


# ============================================================
# Skill catalog endpoint
# ============================================================


def test_skill_catalog_requires_auth():
    assert client.get("/api/v1/skills").status_code == 401


def test_skill_catalog_available_to_any_signed_in_user():
    from app.services import skill_service

    for role in ("STUDENT", "INDUSTRY", "FACULTY"):
        with (
            authenticated_as(role),
            patch.object(
                skill_service,
                "list_active_skills",
                return_value=[{"id": "s1", "name": "Python", "category_name": "Prog", "description": None}],
            ),
        ):
            resp = client.get("/api/v1/skills", headers={"Authorization": "Bearer token"})
        assert resp.status_code == 200
        assert resp.json()["skills"][0]["name"] == "Python"
