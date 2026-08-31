"""Tests for Industry job management (Phase 6): /api/v1/jobs.

Route tests mock app.services.job_service and use
tests.conftest.authenticated_as, exactly like tests/test_internships.py.
Service tests drive the functions with a MagicMock Supabase client and
patched helpers -- no live project or real token.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import jobs as job_routes
from app.main import app
from app.services import job_service
from tests.conftest import authenticated_as

client = TestClient(app)

_SKILL_ID = str(uuid4())


def _row(**overrides):
    row = {
        "id": "job-1",
        "industry_id": "industry-1",
        "title": "Backend Engineer",
        "description": "Own our API platform.",
        "location": "Pune",
        "work_mode": "HYBRID",
        "employment_type": "FULL_TIME",
        "salary_min": 1800000.0,
        "salary_max": 2600000.0,
        "salary_currency": "INR",
        "experience_min_years": 2.0,
        "openings": 3,
        "eligibility_criteria": None,
        "application_deadline": "2026-12-01",
        "status": "DRAFT",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "skills": [
            {
                "skill_id": _SKILL_ID,
                "skill_name": "Python",
                "category_name": "Programming",
                "required_level": "Advanced",
                "importance": "CORE",
            }
        ],
    }
    row.update(overrides)
    return row


def _create_body(**overrides):
    body = {"title": "Backend Engineer", "description": "Own our API platform."}
    body.update(overrides)
    return body


# ============================================================
# Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/jobs"),
    ("post", "/api/v1/jobs"),
    ("get", f"/api/v1/jobs/{uuid4()}"),
    ("put", f"/api/v1/jobs/{uuid4()}"),
    ("post", f"/api/v1/jobs/{uuid4()}/publish"),
    ("post", f"/api/v1/jobs/{uuid4()}/close"),
    ("post", f"/api/v1/jobs/{uuid4()}/archive"),
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


def test_list_returns_only_callers_jobs():
    captured = {}

    def fake_list(_client, industry_id, *, status=None, search=None):
        captured.update({"industry_id": industry_id, "status": status, "search": search})
        return [_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(job_service, "list_jobs", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/jobs?status=PUBLISHED&search=backend",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"industry_id": "industry-1", "status": "PUBLISHED", "search": "backend"}
    assert resp.json()["jobs"][0]["id"] == "job-1"


def test_list_rejects_unknown_status_filter():
    with authenticated_as("INDUSTRY"):
        resp = client.get("/api/v1/jobs?status=NONSENSE", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 422


# ============================================================
# Create
# ============================================================


def test_create_derives_owner_from_token_and_starts_draft():
    captured = {}

    def fake_create(_client, industry_id, data, skills):
        captured.update({"industry_id": industry_id, "data": data, "skills": skills})
        return _row(industry_id=industry_id, status="DRAFT")

    with (
        authenticated_as("INDUSTRY", user_id="industry-99"),
        patch.object(job_service, "create_job", side_effect=fake_create),
    ):
        resp = client.post(
            "/api/v1/jobs", json=_create_body(location="Pune"), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 201
    assert captured["industry_id"] == "industry-99"
    assert "industry_id" not in captured["data"]
    assert "status" not in captured["data"]
    assert resp.json()["status"] == "DRAFT"


def test_create_rejects_client_supplied_industry_id():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/jobs",
            json=_create_body(industry_id="attacker-owned"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_client_supplied_status():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/jobs",
            json=_create_body(status="PUBLISHED"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_missing_title():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/jobs", json={"description": "no title"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_rejects_inverted_salary_range():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/jobs",
            json=_create_body(salary_min=200000, salary_max=100000),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_negative_experience():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/jobs",
            json=_create_body(experience_min_years=-1),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_unknown_employment_type():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/jobs",
            json=_create_body(employment_type="INTERNSHIP"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_maps_invalid_skill_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            job_service, "create_job", side_effect=job_service.InvalidSkillError(["bad-id"])
        ),
    ):
        resp = client.post(
            "/api/v1/jobs",
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
        patch.object(job_service, "get_job", return_value=None) as mock_get,
    ):
        resp = client.get(f"/api/v1/jobs/{uuid4()}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "industry-A"


def test_update_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(job_service, "update_job", return_value=None),
    ):
        resp = client.put(
            f"/api/v1/jobs/{uuid4()}",
            json={"title": "New title"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_update_rejects_status_field():
    with authenticated_as("INDUSTRY"):
        resp = client.put(
            f"/api/v1/jobs/{uuid4()}",
            json={"status": "PUBLISHED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_update_passes_owner_id_to_service():
    captured = {}

    def fake_update(_client, industry_id, job_id, data, skills):
        captured["industry_id"] = industry_id
        return _row()

    with (
        authenticated_as("INDUSTRY", user_id="industry-7"),
        patch.object(job_service, "update_job", side_effect=fake_update),
    ):
        resp = client.put(
            f"/api/v1/jobs/{uuid4()}",
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
        patch.object(job_service, "publish_job", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/jobs/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_publish_missing_fields_maps_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            job_service,
            "publish_job",
            side_effect=job_service.PublishValidationError(["location", "employment_type"]),
        ),
    ):
        resp = client.post(
            f"/api/v1/jobs/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422
    assert "location" in resp.json()["detail"]


def test_publish_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            job_service,
            "publish_job",
            side_effect=job_service.InvalidStatusTransitionError("ARCHIVED", "PUBLISHED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/jobs/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def test_close_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(job_service, "close_job", return_value=None),
    ):
        resp = client.post(f"/api/v1/jobs/{uuid4()}/close", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_archive_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(job_service, "archive_job", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/jobs/{uuid4()}/archive", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_archive_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            job_service,
            "archive_job",
            side_effect=job_service.InvalidStatusTransitionError("ARCHIVED", "ARCHIVED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/jobs/{uuid4()}/archive", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


# ============================================================
# Service layer
# ============================================================


def test_dedupe_skills_keeps_last_occurrence():
    out = job_service._dedupe_skills(
        [
            {"skill_id": "s1", "required_level": "Beginner", "importance": "OPTIONAL"},
            {"skill_id": "s1", "required_level": "Advanced", "importance": "CORE"},
            {"skill_id": "s2", "required_level": "Intermediate"},
        ]
    )
    assert len(out) == 2
    s1 = next(s for s in out if s["skill_id"] == "s1")
    assert s1["required_level"] == "Advanced" and s1["importance"] == "CORE"
    assert next(s for s in out if s["skill_id"] == "s2")["importance"] == "IMPORTANT"


def test_create_forces_draft_and_owner_and_drops_junk():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "new-1"}]

    with (
        patch.object(job_service, "_validate_skill_ids"),
        patch.object(job_service, "get_job", return_value=_row(id="new-1")),
    ):
        job_service.create_job(
            supabase,
            "industry-1",
            {"title": "T", "description": "D", "status": "PUBLISHED", "industry_id": "attacker", "id": "x"},
            [],
        )

    inserted = supabase.table.return_value.insert.call_args_list[0].args[0]
    assert inserted["status"] == "DRAFT"
    assert inserted["industry_id"] == "industry-1"
    assert "id" not in inserted


def test_create_validates_skills_before_inserting_job():
    supabase = MagicMock()
    with (
        patch.object(
            job_service, "_validate_skill_ids", side_effect=job_service.InvalidSkillError(["bad"])
        ),
        patch.object(job_service, "get_job", return_value=_row()),
    ):
        try:
            job_service.create_job(
                supabase,
                "industry-1",
                {"title": "T", "description": "D"},
                [{"skill_id": "bad", "required_level": "Beginner"}],
            )
            raised = False
        except job_service.InvalidSkillError:
            raised = True

    assert raised
    supabase.table.return_value.insert.assert_not_called()


def test_update_never_writes_status():
    supabase = MagicMock()
    with patch.object(
        job_service, "get_job", side_effect=[_row(id="job-1"), _row(id="job-1", title="Updated")]
    ):
        job_service.update_job(
            supabase, "industry-1", "job-1", {"title": "Updated", "status": "PUBLISHED"}, None
        )
    updated = supabase.table.return_value.update.call_args.args[0]
    assert updated == {"title": "Updated"}


def test_update_returns_none_when_not_owned():
    supabase = MagicMock()
    with patch.object(job_service, "get_job", return_value=None):
        result = job_service.update_job(
            supabase, "industry-1", "job-x", {"title": "Updated"}, None
        )
    assert result is None
    supabase.table.return_value.update.assert_not_called()


def test_update_replaces_skills_when_provided():
    supabase = MagicMock()
    with (
        patch.object(job_service, "get_job", side_effect=[_row(), _row()]),
        patch.object(job_service, "_replace_skills") as mock_replace,
    ):
        job_service.update_job(
            supabase,
            "industry-1",
            "job-1",
            {},
            [{"skill_id": "s1", "required_level": "Beginner", "importance": "CORE"}],
        )
    mock_replace.assert_called_once()


def test_publish_blocks_when_required_fields_missing():
    supabase = MagicMock()
    with patch.object(
        job_service, "get_job", return_value=_row(location=None, employment_type=None)
    ):
        try:
            job_service.publish_job(supabase, "industry-1", "job-1")
            missing = None
        except job_service.PublishValidationError as exc:
            missing = exc.missing
    assert missing is not None
    assert "location" in missing and "employment_type" in missing
    supabase.table.return_value.update.assert_not_called()


def test_publish_blocks_when_no_skills():
    supabase = MagicMock()
    with patch.object(job_service, "get_job", return_value=_row(skills=[])):
        try:
            job_service.publish_job(supabase, "industry-1", "job-1")
            missing = None
        except job_service.PublishValidationError as exc:
            missing = exc.missing
    assert missing == ["at least one required skill"]


def test_publish_sets_status_when_valid():
    supabase = MagicMock()
    with patch.object(
        job_service, "get_job", side_effect=[_row(status="DRAFT"), _row(status="PUBLISHED")]
    ):
        result = job_service.publish_job(supabase, "industry-1", "job-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "PUBLISHED"}
    assert result["status"] == "PUBLISHED"


def test_publish_rejects_from_archived():
    supabase = MagicMock()
    with patch.object(job_service, "get_job", return_value=_row(status="ARCHIVED")):
        try:
            job_service.publish_job(supabase, "industry-1", "job-1")
            raised = False
        except job_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_close_only_from_published():
    supabase = MagicMock()
    with patch.object(job_service, "get_job", return_value=_row(status="DRAFT")):
        try:
            job_service.close_job(supabase, "industry-1", "job-1")
            raised = False
        except job_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_archive_allowed_from_draft():
    supabase = MagicMock()
    with patch.object(
        job_service, "get_job", side_effect=[_row(status="DRAFT"), _row(status="ARCHIVED")]
    ):
        result = job_service.archive_job(supabase, "industry-1", "job-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "ARCHIVED"}
    assert result["status"] == "ARCHIVED"


def test_archive_rejects_when_already_archived():
    supabase = MagicMock()
    with patch.object(job_service, "get_job", return_value=_row(status="ARCHIVED")):
        try:
            job_service.archive_job(supabase, "industry-1", "job-1")
            raised = False
        except job_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_validate_skill_ids_raises_on_unknown():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.return_value.data = [
        {"id": "good"}
    ]
    try:
        job_service._validate_skill_ids(supabase, ["good", "missing"])
        raised = False
    except job_service.InvalidSkillError as exc:
        raised = True
        assert exc.skill_ids == ["missing"]
    assert raised


# ============================================================
# No service-role anywhere on this path
# ============================================================


def test_job_modules_do_not_use_service_role():
    assert not hasattr(job_service, "get_supabase")
    assert not hasattr(job_routes, "get_supabase")
    assert hasattr(job_routes, "build_user_client")
