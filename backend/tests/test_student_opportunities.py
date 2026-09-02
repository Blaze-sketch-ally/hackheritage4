"""Tests for the Student side of opportunities + applications:
/api/v1/student/opportunities and /api/v1/student/applications.

Route tests mock app.services.student_opportunity_service and use
tests.conftest.authenticated_as, exactly like tests/test_applications.py.
Service tests drive the functions with a MagicMock Supabase client -- no
live project or real token. The existing `applications` schema
(database/migrations/020_applications.sql) is used unchanged: no
opportunity_id, no new status enum.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.services import student_opportunity_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_INT_OPP_ID = "internship_11111111-1111-1111-1111-111111111111"
_JOB_OPP_ID = "job_22222222-2222-2222-2222-222222222222"


def _summary(**overrides):
    row = {
        "id": _INT_OPP_ID,
        "source_type": "INTERNSHIP",
        "title": "Backend Intern",
        "description": "Build APIs.",
        "location": "Pune",
        "work_mode": "HYBRID",
        "status": "PUBLISHED",
        "industry": {"id": "industry-1", "company_name": "Acme", "industry_sector": None, "logo_url": None},
        "application_deadline": "2026-12-01",
        "created_at": "2026-09-01T00:00:00Z",
        "has_applied": False,
    }
    row.update(overrides)
    return row


def _detail(**overrides):
    row = _summary()
    row.update(
        {
            "eligibility_criteria": "CS students",
            "openings": 2,
            "duration_months": 6,
            "stipend_amount": 15000.0,
            "stipend_currency": "INR",
            "start_date": None,
            "employment_type": None,
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
            "experience_min_years": None,
            "skills": [
                {
                    "skill_id": "s1",
                    "skill_name": "Python",
                    "category_name": "Programming",
                    "required_level": "Intermediate",
                    "importance": "CORE",
                }
            ],
        }
    )
    row.update(overrides)
    return row


def _application(**overrides):
    row = {
        "id": "app-1",
        "student_id": "student-1",
        "opportunity_type": "INTERNSHIP",
        "internship_id": "11111111-1111-1111-1111-111111111111",
        "job_id": None,
        "status": "APPLIED",
        "cover_note": "Keen to join.",
        "match_score": None,
        "applied_at": "2026-09-02T00:00:00Z",
        "created_at": "2026-09-02T00:00:00Z",
        "updated_at": "2026-09-02T00:00:00Z",
        "opportunity": {
            "id": _INT_OPP_ID,
            "source_type": "INTERNSHIP",
            "title": "Backend Intern",
            "location": "Pune",
            "industry": {"id": "industry-1", "company_name": "Acme"},
        },
    }
    row.update(overrides)
    return row


# ============================================================
# Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/student/opportunities"),
    ("get", f"/api/v1/student/opportunities/{_INT_OPP_ID}"),
    ("get", f"/api/v1/student/opportunities/{_INT_OPP_ID}/match"),
    ("post", f"/api/v1/student/opportunities/{_INT_OPP_ID}/applications"),
    ("get", "/api/v1/student/applications"),
]


def _call(method, url, *, headers=None):
    if method == "post":
        return client.post(url, json={"cover_note": "hi"}, headers=headers)
    return getattr(client, method)(url, headers=headers)


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", None):
        for method, url in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# Browse -- published only
# ============================================================


def test_list_returns_normalized_opportunities():
    captured = {}

    def fake_list(_client, student_id, **kwargs):
        captured.update({"student_id": student_id, **kwargs})
        return [_summary(), _summary(id=_JOB_OPP_ID, source_type="JOB", title="Platform Engineer")]

    with (
        authenticated_as("STUDENT", user_id="student-9"),
        patch.object(svc, "list_opportunities", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/opportunities?source_type=INTERNSHIP&search=backend",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"student_id": "student-9", "source_type": "INTERNSHIP", "search": "backend"}
    body = resp.json()["opportunities"]
    assert body[0]["id"] == _INT_OPP_ID
    assert body[1]["source_type"] == "JOB"


def test_list_rejects_unknown_source_type():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/opportunities?source_type=GIG",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_service_list_filters_to_published_only():
    """A student must never see a DRAFT/CLOSED/ARCHIVED posting -- the
    service pins status=PUBLISHED on top of RLS."""
    supabase = MagicMock()
    exec_mock = supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute
    exec_mock.return_value.data = []
    # applied-postings lookup + industry lookup
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = []

    svc.list_opportunities(supabase, "student-1", source_type="INTERNSHIP")

    eq_calls = supabase.table.return_value.select.return_value.eq.call_args_list
    assert ("status", "PUBLISHED") in [c.args for c in eq_calls]


# ============================================================
# Detail
# ============================================================


def test_get_detail_returns_opportunity():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(svc, "get_opportunity", return_value=_detail()),
    ):
        resp = client.get(
            f"/api/v1/student/opportunities/{_INT_OPP_ID}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Backend Intern"
    assert body["skills"][0]["skill_name"] == "Python"


def test_get_detail_404_when_not_visible():
    """An unpublished / other-tenant / private posting is indistinguishable
    from one that does not exist."""
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_opportunity", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/student/opportunities/{_JOB_OPP_ID}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_get_detail_404_for_malformed_id():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            svc, "get_opportunity", side_effect=svc.InvalidOpportunityIdError("nonsense")
        ),
    ):
        resp = client.get(
            "/api/v1/student/opportunities/nonsense",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


# ============================================================
# Apply
# ============================================================


def test_apply_with_cover_note_derives_student_id():
    captured = {}

    def fake_apply(_client, student_id, opportunity_id, cover_note):
        captured.update(
            {"student_id": student_id, "opportunity_id": opportunity_id, "cover_note": cover_note}
        )
        return _application(cover_note=cover_note)

    with (
        authenticated_as("STUDENT", user_id="student-42"),
        patch.object(svc, "get_opportunity", return_value=_detail()),
        patch.object(svc, "apply_to_opportunity", side_effect=fake_apply),
    ):
        resp = client.post(
            f"/api/v1/student/opportunities/{_INT_OPP_ID}/applications",
            json={"cover_note": "  I would love to work here.  "},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert captured["student_id"] == "student-42"
    assert captured["opportunity_id"] == _INT_OPP_ID
    body = resp.json()
    assert body["status"] == "APPLIED"
    assert body["student_id"] == "student-1"


@pytest.mark.parametrize(
    "payload",
    [
        {"cover_note": "hi", "student_id": "victim"},
        {"cover_note": "hi", "industry_id": "attacker"},
        {"cover_note": "hi", "status": "SELECTED"},
        {"cover_note": "hi", "match_score": 99},
        {"cover_note": "hi", "internship_id": "other-posting"},
        {"cover_note": "hi", "job_id": "other-posting"},
        {"cover_note": "hi", "opportunity_type": "JOB"},
    ],
)
def test_apply_rejects_smuggled_industry_owned_fields(payload):
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_opportunity", return_value=_detail()),
        patch.object(svc, "apply_to_opportunity", return_value=_application()),
    ):
        resp = client.post(
            f"/api/v1/student/opportunities/{_INT_OPP_ID}/applications",
            json=payload,
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422, payload


def test_apply_404_when_opportunity_not_visible():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_opportunity", return_value=None),
        patch.object(svc, "apply_to_opportunity") as apply_mock,
    ):
        resp = client.post(
            f"/api/v1/student/opportunities/{_INT_OPP_ID}/applications",
            json={"cover_note": "hi"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404
    apply_mock.assert_not_called()


def test_apply_duplicate_returns_409():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_opportunity", return_value=_detail()),
        patch.object(
            svc,
            "apply_to_opportunity",
            side_effect=svc.DuplicateApplicationError(_INT_OPP_ID),
        ),
    ):
        resp = client.post(
            f"/api/v1/student/opportunities/{_INT_OPP_ID}/applications",
            json={"cover_note": "hi"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_apply_unpublished_race_returns_409():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_opportunity", return_value=_detail()),
        patch.object(
            svc,
            "apply_to_opportunity",
            side_effect=svc.OpportunityNotPublishedError(_INT_OPP_ID),
        ),
    ):
        resp = client.post(
            f"/api/v1/student/opportunities/{_INT_OPP_ID}/applications",
            json={"cover_note": "hi"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


# ============================================================
# My Applications
# ============================================================


def test_my_applications_scopes_to_caller():
    captured = {}

    def fake_list(_client, student_id):
        captured["student_id"] = student_id
        return [_application(), _application(id="app-2", status="SHORTLISTED")]

    with (
        authenticated_as("STUDENT", user_id="student-77"),
        patch.object(svc, "list_my_applications", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/applications", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured["student_id"] == "student-77"
    assert [a["status"] for a in resp.json()["applications"]] == ["APPLIED", "SHORTLISTED"]


def test_my_applications_exposes_all_seven_statuses():
    """Whatever status the owning Industry account last set is what the
    student sees -- the seven DB values pass through unchanged."""
    seven = [
        "APPLIED",
        "UNDER_REVIEW",
        "SHORTLISTED",
        "INTERVIEW_SCHEDULED",
        "SELECTED",
        "REJECTED",
        "WITHDRAWN",
    ]
    rows = [_application(id=f"app-{i}", status=s) for i, s in enumerate(seven)]
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_my_applications", return_value=rows),
    ):
        resp = client.get(
            "/api/v1/student/applications", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert [a["status"] for a in resp.json()["applications"]] == seven


# ============================================================
# Match
# ============================================================


def test_match_returns_deterministic_result():
    match_result = {
        "opportunity_id": _INT_OPP_ID,
        "score": 72,
        "recommendation": "GOOD",
        "skill_coverage": "1 / 2",
        "required_count": 2,
        "matched_count": 1,
        "needs_improvement_count": 0,
        "missing_count": 1,
        "matched_skills": [],
        "needs_improvement_skills": [],
        "missing_skills": [],
    }
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_opportunity", return_value=_detail()),
        patch.object(svc, "compute_opportunity_match", return_value=match_result),
    ):
        resp = client.get(
            f"/api/v1/student/opportunities/{_INT_OPP_ID}/match",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert resp.json()["score"] == 72


def test_match_404_when_opportunity_not_visible():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_opportunity", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/student/opportunities/{_INT_OPP_ID}/match",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


# ============================================================
# Service layer
# ============================================================


def test_decode_opportunity_id_internship_and_job():
    assert svc.decode_opportunity_id("internship_abc") == ("INTERNSHIP", "abc")
    assert svc.decode_opportunity_id("job_xyz") == ("JOB", "xyz")


@pytest.mark.parametrize("bad", ["", "internship_", "job_", "abc", "internshipabc", "internship"])
def test_decode_opportunity_id_rejects_malformed(bad):
    with pytest.raises(svc.InvalidOpportunityIdError):
        svc.decode_opportunity_id(bad)


def test_encode_decode_round_trip():
    raw = "11111111-1111-1111-1111-111111111111"
    for kind in ("INTERNSHIP", "JOB"):
        enc = svc.encode_opportunity_id(kind, raw)
        assert svc.decode_opportunity_id(enc) == (kind, raw)


def test_apply_sends_only_student_controlled_fields_internship():
    supabase = MagicMock()
    insert_exec = supabase.table.return_value.insert.return_value.execute
    insert_exec.return_value.data = [{"id": "app-1"}]
    with patch.object(svc, "_get_own_application", return_value=_application()):
        svc.apply_to_opportunity(supabase, "student-1", _INT_OPP_ID, "  hello  ")
    written = supabase.table.return_value.insert.call_args.args[0]
    assert written == {
        "student_id": "student-1",
        "opportunity_type": "INTERNSHIP",
        "cover_note": "hello",
        "internship_id": "11111111-1111-1111-1111-111111111111",
    }
    assert "industry_id" not in written
    assert "status" not in written
    assert "match_score" not in written
    assert "job_id" not in written


def test_apply_sends_job_id_for_job_opportunity():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "app-2"}]
    with patch.object(svc, "_get_own_application", return_value=_application()):
        svc.apply_to_opportunity(supabase, "student-1", _JOB_OPP_ID, None)
    written = supabase.table.return_value.insert.call_args.args[0]
    assert written["job_id"] == "22222222-2222-2222-2222-222222222222"
    assert written["opportunity_type"] == "JOB"
    assert "internship_id" not in written
    assert written["cover_note"] is None


def test_apply_translates_unique_violation_to_duplicate_error():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.side_effect = APIError(
        {"code": "23505", "message": "duplicate key"}
    )
    with pytest.raises(svc.DuplicateApplicationError):
        svc.apply_to_opportunity(supabase, "student-1", _INT_OPP_ID, None)


def test_apply_translates_rls_rejection_to_not_published_error():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.side_effect = APIError(
        {"code": "42501", "message": "new row violates row-level security policy"}
    )
    with pytest.raises(svc.OpportunityNotPublishedError):
        svc.apply_to_opportunity(supabase, "student-1", _INT_OPP_ID, None)


def test_list_my_applications_scopes_query_to_student():
    supabase = MagicMock()
    (
        supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data
    ) = []
    svc.list_my_applications(supabase, "student-55")
    eq_call = supabase.table.return_value.select.return_value.eq.call_args
    assert eq_call.args == ("student_id", "student-55")


def test_shape_application_maps_internship_to_encoded_id():
    row = {
        "id": "app-1",
        "student_id": "student-1",
        "opportunity_type": "INTERNSHIP",
        "internship_id": "abc",
        "job_id": None,
        "status": "SELECTED",
        "cover_note": None,
        "match_score": None,
        "applied_at": None,
        "created_at": None,
        "updated_at": None,
        "internship": {"id": "abc", "title": "Intern", "location": "Pune", "industry_id": "industry-1"},
        "job": None,
    }
    shaped = svc._shape_application(row, {"industry-1": {"company_name": "Acme"}})
    assert shaped["opportunity"]["id"] == "internship_abc"
    assert shaped["opportunity"]["source_type"] == "INTERNSHIP"
    assert shaped["opportunity"]["title"] == "Intern"
    assert shaped["opportunity"]["industry"]["company_name"] == "Acme"
    assert shaped["status"] == "SELECTED"


def test_compute_opportunity_match_reuses_match_service():
    supabase = MagicMock()
    # posting required skills
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "skill_id": "s1",
            "required_level": "Intermediate",
            "importance": "CORE",
            "skill": {"name": "Python"},
        }
    ]
    with patch.object(svc, "_own_skill_levels", return_value={"s1": {"proficiency_level": "Advanced", "is_verified": True}}):
        result = svc.compute_opportunity_match(supabase, "student-1", _INT_OPP_ID)
    assert result["opportunity_id"] == _INT_OPP_ID
    assert "application_id" not in result
    assert result["score"] == 100
    assert result["matched_count"] == 1


def test_student_opportunity_modules_do_not_use_service_role():
    from app.api import student_opportunities as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")
