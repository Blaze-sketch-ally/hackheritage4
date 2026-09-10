"""Tests for the Student side of opportunities + applications:
/api/v1/student/opportunities and /api/v1/student/applications.

Route tests mock app.services.student_opportunity_service and use
tests.conftest.authenticated_as, exactly like tests/test_applications.py.
Service tests drive the functions with a MagicMock Supabase client -- no
live project or real token. The existing `applications` schema
(database/migrations/020_applications.sql) is used unchanged: no
opportunity_id, no new status enum.
"""

from pathlib import Path
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
_APP_ID = "33333333-3333-3333-3333-333333333333"


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
    ("post", f"/api/v1/student/applications/{_APP_ID}/withdraw"),
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
    # Core params forwarded; the new filter/sort params default cleanly.
    assert captured["student_id"] == "student-9"
    assert captured["source_type"] == "INTERNSHIP"
    assert captured["search"] == "backend"
    assert captured["work_mode"] is None
    assert captured["order_by"] == "newest"
    assert captured["min_stipend"] is None
    assert captured["min_salary"] is None
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
# Browse -- filters & sorting (Tier 1)
# ============================================================


def _posting_row(**overrides):
    """A minimal row as `_SUMMARY_COLUMNS` would return it -- enough for
    `_summary()` to shape."""
    row = {
        "id": "p-1",
        "industry_id": "industry-1",
        "title": "Backend Intern",
        "description": "Build APIs.",
        "location": "Pune",
        "work_mode": "REMOTE",
        "application_deadline": "2026-12-01",
        "status": "PUBLISHED",
        "created_at": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _self_returning_query(rows):
    q = MagicMock()
    for method in ("select", "eq", "ilike", "gte", "lte", "in_", "order"):
        getattr(q, method).return_value = q
    q.execute.return_value.data = rows
    return q


def _list_client(*, internships=None, jobs=None, applications=None):
    """A Supabase client mock whose internships/jobs/applications/
    industry_profiles query chains each terminate in `.execute().data`,
    and whose per-table query object is returned for call assertions."""
    internships_q = _self_returning_query(internships or [])
    jobs_q = _self_returning_query(jobs or [])
    apps_q = _self_returning_query(applications or [])
    industry_q = _self_returning_query([])
    client = MagicMock()
    client.table.side_effect = lambda name: {
        "internships": internships_q,
        "jobs": jobs_q,
        "applications": apps_q,
        "industry_profiles": industry_q,
    }.get(name, _self_returning_query([]))
    return client, internships_q, jobs_q


def _eq_args(query_mock):
    return [c.args for c in query_mock.eq.call_args_list]


def _order_calls(query_mock):
    return query_mock.order.call_args_list


# ---- route param validation ----


@pytest.mark.parametrize(
    "query",
    [
        "work_mode=REMOTE",
        "order_by=deadline",
        "min_stipend=20000",
        "min_salary=1000000",
        "work_mode=HYBRID&order_by=deadline&min_stipend=10000",
    ],
)
def test_list_accepts_valid_filter_params(query):
    captured = {}

    def fake_list(_client, student_id, **kwargs):
        captured.update(kwargs)
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_opportunities", side_effect=fake_list),
    ):
        resp = client.get(
            f"/api/v1/student/opportunities?{query}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    if "work_mode=REMOTE" in query:
        assert captured["work_mode"] == "REMOTE"
    if "order_by=deadline" in query:
        assert captured["order_by"] == "deadline"
    if "min_stipend=20000" in query:
        assert captured["min_stipend"] == 20000
    if "min_salary=1000000" in query:
        assert captured["min_salary"] == 1000000


@pytest.mark.parametrize(
    "query",
    [
        "work_mode=banana",
        "work_mode=remote",  # case-sensitive enum
        "order_by=cheapest",
        "order_by=oldest",
        "min_stipend=-1",
        "min_stipend=abc",
        "min_salary=-5",
        "min_salary=9999999999999",  # over the ceiling
    ],
)
def test_list_rejects_invalid_filter_params(query):
    with authenticated_as("STUDENT"):
        resp = client.get(
            f"/api/v1/student/opportunities?{query}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422, query


def test_list_order_by_defaults_to_newest():
    captured = {}

    def fake_list(_client, _student_id, **kwargs):
        captured.update(kwargs)
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_opportunities", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/opportunities",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["order_by"] == "newest"


# ---- service: filters compose onto status=PUBLISHED ----


def test_service_applies_work_mode_and_min_stipend_to_internships():
    supabase, internships_q, _jobs_q = _list_client(internships=[])
    svc.list_opportunities(
        supabase,
        "student-1",
        source_type="INTERNSHIP",
        work_mode="REMOTE",
        min_stipend=20000,
    )
    assert ("status", "PUBLISHED") in _eq_args(internships_q)
    assert ("work_mode", "REMOTE") in _eq_args(internships_q)
    internships_q.gte.assert_any_call("stipend_amount", 20000)


def test_service_applies_work_mode_and_min_salary_to_jobs():
    supabase, _internships_q, jobs_q = _list_client(jobs=[])
    svc.list_opportunities(
        supabase,
        "student-1",
        source_type="JOB",
        work_mode="HYBRID",
        min_salary=1_000_000,
    )
    assert ("status", "PUBLISHED") in _eq_args(jobs_q)
    assert ("work_mode", "HYBRID") in _eq_args(jobs_q)
    jobs_q.gte.assert_any_call("salary_max", 1_000_000)


def test_service_search_is_applied_server_side():
    supabase, internships_q, jobs_q = _list_client(internships=[], jobs=[])
    svc.list_opportunities(supabase, "student-1", search="  data  ")
    internships_q.ilike.assert_any_call("title", "%data%")
    jobs_q.ilike.assert_any_call("title", "%data%")


def test_service_internship_ignores_min_salary_and_job_ignores_min_stipend():
    supabase, internships_q, jobs_q = _list_client(internships=[], jobs=[])
    svc.list_opportunities(
        supabase,
        "student-1",
        min_stipend=15000,
        min_salary=800000,
    )
    # internship query filtered by stipend only
    internships_q.gte.assert_any_call("stipend_amount", 15000)
    assert all(c.args[0] != "salary_max" for c in internships_q.gte.call_args_list)
    # job query filtered by salary only
    jobs_q.gte.assert_any_call("salary_max", 800000)
    assert all(c.args[0] != "stipend_amount" for c in jobs_q.gte.call_args_list)


def test_service_published_pinned_with_every_filter():
    supabase, internships_q, jobs_q = _list_client(internships=[], jobs=[])
    svc.list_opportunities(
        supabase,
        "student-1",
        search="x",
        work_mode="REMOTE",
        order_by="deadline",
        min_stipend=10000,
        min_salary=500000,
    )
    assert ("status", "PUBLISHED") in _eq_args(internships_q)
    assert ("status", "PUBLISHED") in _eq_args(jobs_q)


def test_service_deadline_sort_orders_by_application_deadline_nulls_last():
    supabase, internships_q, _jobs_q = _list_client(internships=[])
    svc.list_opportunities(supabase, "student-1", source_type="INTERNSHIP", order_by="deadline")
    calls = _order_calls(internships_q)
    assert calls, "expected an .order(...) call"
    args, kwargs = calls[-1]
    assert args[0] == "application_deadline"
    assert kwargs.get("desc") is False
    assert kwargs.get("nullsfirst") is False  # -> ".nullslast"


def test_service_newest_sort_orders_by_created_at_desc():
    supabase, internships_q, _jobs_q = _list_client(internships=[])
    svc.list_opportunities(supabase, "student-1", source_type="INTERNSHIP")  # default
    args, kwargs = _order_calls(internships_q)[-1]
    assert args[0] == "created_at"
    assert kwargs.get("desc") is True


def test_service_bad_order_by_falls_back_to_newest():
    supabase, internships_q, _jobs_q = _list_client(internships=[])
    svc.list_opportunities(
        supabase, "student-1", source_type="INTERNSHIP", order_by="garbage"
    )
    args, _kwargs = _order_calls(internships_q)[-1]
    assert args[0] == "created_at"


def test_service_combined_source_type_none_is_deterministic_by_deadline():
    internships = [
        _posting_row(id="i-late", application_deadline="2026-12-20"),
        _posting_row(id="i-none", application_deadline=None),
    ]
    jobs = [
        _posting_row(id="j-soon", application_deadline="2026-12-01"),
        _posting_row(id="j-none", application_deadline=None),
    ]
    supabase, _iq, _jq = _list_client(internships=internships, jobs=jobs)
    out = svc.list_opportunities(supabase, "student-1", order_by="deadline")
    ids = [o["id"] for o in out]
    # dated deadlines ascending, then NULLs, then id tie-break among NULLs
    assert ids == [
        "job_j-soon",
        "internship_i-late",
        "internship_i-none",
        "job_j-none",
    ]


def test_service_combined_source_type_none_is_deterministic_by_newest():
    internships = [_posting_row(id="i-1", created_at="2026-09-05T00:00:00Z")]
    jobs = [
        _posting_row(id="j-1", created_at="2026-09-10T00:00:00Z"),
        _posting_row(id="j-2", created_at="2026-09-01T00:00:00Z"),
    ]
    supabase, _iq, _jq = _list_client(internships=internships, jobs=jobs)
    out = svc.list_opportunities(supabase, "student-1")
    assert [o["id"] for o in out] == ["job_j-1", "internship_i-1", "job_j-2"]


def test_list_empty_filtered_result_returns_200_and_empty_list():
    def fake_list(_client, _student_id, **_kwargs):
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_opportunities", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/opportunities?work_mode=ONSITE&min_stipend=30000",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"opportunities": []}


def test_service_zero_min_compensation_is_treated_as_no_filter():
    supabase, internships_q, jobs_q = _list_client(internships=[], jobs=[])
    svc.list_opportunities(supabase, "student-1", min_stipend=0, min_salary=0)
    internships_q.gte.assert_not_called()
    jobs_q.gte.assert_not_called()


def test_service_min_compensation_uses_gte_so_null_rows_are_excluded():
    """A posting with NULL stipend / salary must never satisfy a minimum
    compensation filter. Enforced by `.gte(...)`: in Postgres `NULL >= n`
    is NULL, so the row is filtered out server-side. The service must not
    fall back to a broader operator that could re-admit NULLs."""
    supabase, internships_q, jobs_q = _list_client(internships=[], jobs=[])
    svc.list_opportunities(supabase, "student-1", min_stipend=10000, min_salary=500000)
    internships_q.gte.assert_any_call("stipend_amount", 10000)
    jobs_q.gte.assert_any_call("salary_max", 500000)
    assert not internships_q.or_.called
    assert not jobs_q.or_.called


def test_student_opportunity_list_still_uses_user_scoped_client_only():
    """No service-role client is introduced by the filter/sort work."""
    from app.api import student_opportunities as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")


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
# Withdrawal  (POST /api/v1/student/applications/{id}/withdraw)
# ============================================================


def test_withdraw_uses_auth_identity_and_path_id_only():
    """student_id comes from the token, application id from the path --
    never from a request body."""
    captured = {}

    def fake_withdraw(_client, student_id, application_id):
        captured.update(student_id=student_id, application_id=application_id)
        return _application(id=_APP_ID, status="WITHDRAWN")

    with (
        authenticated_as("STUDENT", user_id="student-91"),
        patch.object(svc, "withdraw_application", side_effect=fake_withdraw),
    ):
        resp = client.post(
            f"/api/v1/student/applications/{_APP_ID}/withdraw",
            json={"student_id": "someone-else", "status": "SELECTED"},  # ignored
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"student_id": "student-91", "application_id": _APP_ID}
    assert resp.json()["status"] == "WITHDRAWN"


def test_withdraw_404_for_application_the_student_does_not_own():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "withdraw_application", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/student/applications/{_APP_ID}/withdraw",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_withdraw_409_when_status_is_not_withdrawable():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            svc,
            "withdraw_application",
            side_effect=svc.ApplicationNotWithdrawableError("SELECTED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/student/applications/{_APP_ID}/withdraw",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409
    assert "SELECTED" in resp.json()["detail"]


def test_withdraw_rejects_non_uuid_application_id():
    with authenticated_as("STUDENT"):
        resp = client.post(
            "/api/v1/student/applications/not-a-uuid/withdraw",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


# ---- service layer ----


def _withdraw_client():
    """MagicMock Supabase client whose applications UPDATE chain resolves,
    and whose per-table query object is returned for call assertions."""
    apps_q = MagicMock()
    for method in ("select", "eq", "update", "in_", "order", "maybe_single"):
        getattr(apps_q, method).return_value = apps_q
    apps_q.execute.return_value.data = []
    client = MagicMock()
    client.table.return_value = apps_q
    return client, apps_q


@pytest.mark.parametrize(
    "status_",
    ["APPLIED", "UNDER_REVIEW", "SHORTLISTED", "INTERVIEW_SCHEDULED"],
)
def test_service_withdraw_allows_active_statuses(status_):
    client, apps_q = _withdraw_client()
    with patch.object(
        svc,
        "_get_own_application",
        side_effect=[
            {"id": _APP_ID, "status": status_},
            {"id": _APP_ID, "status": "WITHDRAWN"},
        ],
    ):
        out = svc.withdraw_application(client, "student-1", _APP_ID)
    apps_q.update.assert_called_once_with({"status": "WITHDRAWN"})
    # scoped both by id and by the authenticated student's own id
    eq_args = [c.args for c in apps_q.eq.call_args_list]
    assert ("id", _APP_ID) in eq_args
    assert ("student_id", "student-1") in eq_args
    assert out["status"] == "WITHDRAWN"


@pytest.mark.parametrize("status_", ["SELECTED", "REJECTED", "WITHDRAWN"])
def test_service_withdraw_rejects_terminal_statuses(status_):
    client, apps_q = _withdraw_client()
    with (
        patch.object(
            svc, "_get_own_application", return_value={"id": _APP_ID, "status": status_}
        ),
        pytest.raises(svc.ApplicationNotWithdrawableError) as excinfo,
    ):
        svc.withdraw_application(client, "student-1", _APP_ID)
    assert excinfo.value.current_status == status_
    apps_q.update.assert_not_called()  # no write on a rejected transition


def test_service_withdraw_returns_none_for_unowned_application_and_never_writes():
    client, apps_q = _withdraw_client()
    with patch.object(svc, "_get_own_application", return_value=None):
        out = svc.withdraw_application(client, "student-1", _APP_ID)
    assert out is None
    apps_q.update.assert_not_called()


def test_service_withdraw_never_uses_service_role():
    assert not hasattr(svc, "get_supabase")
    from app.api import student_opportunities as routes

    assert not hasattr(routes, "get_supabase")


def test_withdrawable_statuses_match_active_candidate_stages():
    assert svc.WITHDRAWABLE_STATUSES == frozenset(
        {"APPLIED", "UNDER_REVIEW", "SHORTLISTED", "INTERVIEW_SCHEDULED"}
    )


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


# ============================================================
# Student interview details (083_student_interview_visibility.sql)
# ============================================================

_SCHEDULED_INTERVIEW = {
    "id": "iv-1",
    "application_id": "app-1",
    "scheduled_at": "2026-09-12T15:00:00+00:00",
    "duration_minutes": 30,
    "mode": "ONLINE",
    "location": "https://meet.example.com/abc",
    "status": "SCHEDULED",
    "created_at": "2026-09-10T00:00:00+00:00",
    "updated_at": "2026-09-10T00:00:00+00:00",
    # notes is Industry-private -- it must never reach a student. The RPC
    # does not return it; this key is here only to prove _interview_index
    # would drop it even if it somehow appeared.
    "notes": "ask about system design",
}


def _interview_row(**overrides):
    row = dict(_SCHEDULED_INTERVIEW)
    row.update(overrides)
    return row


def _app_row(**overrides):
    row = {
        "id": "app-1",
        "student_id": "student-1",
        "opportunity_type": "INTERNSHIP",
        "internship_id": "int-1",
        "job_id": None,
        "status": "INTERVIEW_SCHEDULED",
        "cover_note": None,
        "match_score": None,
        "applied_at": "2026-09-02T00:00:00Z",
        "created_at": None,
        "updated_at": None,
        # industry_id None -> _fetch_industries is a no-op, keeping the mock simple
        "internship": {
            "id": "int-1",
            "title": "Backend Intern",
            "location": "Pune",
            "work_mode": "HYBRID",
            "industry_id": None,
        },
        "job": None,
    }
    row.update(overrides)
    return row


def _mock_client_for_list(app_rows, interview_rows):
    supabase = MagicMock()
    (
        supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data
    ) = app_rows
    supabase.rpc.return_value.execute.return_value.data = interview_rows
    return supabase


def test_interview_index_calls_rpc_once_and_maps_by_application_id():
    supabase = MagicMock()
    supabase.rpc.return_value.execute.return_value.data = [_interview_row()]

    index = svc._interview_index(supabase, ["app-1", "app-1", "app-2"])

    supabase.rpc.assert_called_once_with(
        "student_interviews", {"application_ids": ["app-1", "app-2"]}
    )
    assert set(index) == {"app-1"}
    assert index["app-1"] == {
        "id": "iv-1",
        "application_id": "app-1",
        "scheduled_at": "2026-09-12T15:00:00+00:00",
        "duration_minutes": 30,
        "mode": "ONLINE",
        "location": "https://meet.example.com/abc",
        "status": "SCHEDULED",
    }
    assert "notes" not in index["app-1"]


def test_interview_index_empty_without_application_ids():
    supabase = MagicMock()
    assert svc._interview_index(supabase, []) == {}
    supabase.rpc.assert_not_called()


def test_interview_index_drops_non_scheduled_rows():
    supabase = MagicMock()
    supabase.rpc.return_value.execute.return_value.data = [
        _interview_row(id="iv-old", status="CANCELLED"),
    ]
    assert svc._interview_index(supabase, ["app-1"]) == {}


def test_interview_index_prefers_scheduled_when_cancelled_and_scheduled_coexist():
    supabase = MagicMock()
    supabase.rpc.return_value.execute.return_value.data = [
        _interview_row(id="iv-old", status="CANCELLED"),
        _interview_row(id="iv-live", status="SCHEDULED"),
    ]
    index = svc._interview_index(supabase, ["app-1"])
    assert index["app-1"]["id"] == "iv-live"
    assert index["app-1"]["status"] == "SCHEDULED"


def test_interview_index_is_best_effort_on_rpc_failure():
    supabase = MagicMock()
    supabase.rpc.return_value.execute.side_effect = RuntimeError("boom")
    assert svc._interview_index(supabase, ["app-1"]) == {}


def test_list_my_applications_attaches_scheduled_interview():
    supabase = _mock_client_for_list([_app_row()], [_interview_row()])

    result = svc.list_my_applications(supabase, "student-1")

    assert result[0]["interview"] == {
        "id": "iv-1",
        "application_id": "app-1",
        "scheduled_at": "2026-09-12T15:00:00+00:00",
        "duration_minutes": 30,
        "mode": "ONLINE",
        "location": "https://meet.example.com/abc",
        "status": "SCHEDULED",
    }
    assert "notes" not in result[0]["interview"]


def test_list_my_applications_interview_none_when_no_live_interview():
    supabase = _mock_client_for_list([_app_row()], [])
    result = svc.list_my_applications(supabase, "student-1")
    assert result[0]["interview"] is None


def test_list_my_applications_interview_none_when_only_cancelled():
    supabase = _mock_client_for_list(
        [_app_row()], [_interview_row(status="CANCELLED")]
    )
    result = svc.list_my_applications(supabase, "student-1")
    assert result[0]["interview"] is None


def test_list_my_applications_survives_interview_rpc_failure():
    supabase = _mock_client_for_list([_app_row()], [])
    supabase.rpc.return_value.execute.side_effect = RuntimeError("rpc down")

    result = svc.list_my_applications(supabase, "student-1")

    assert len(result) == 1
    assert result[0]["interview"] is None
    assert result[0]["status"] == "INTERVIEW_SCHEDULED"


def test_list_my_applications_uses_one_interview_query_not_n_plus_one():
    supabase = _mock_client_for_list(
        [_app_row(id="app-1"), _app_row(id="app-2"), _app_row(id="app-3")],
        [_interview_row(application_id="app-2")],
    )

    result = svc.list_my_applications(supabase, "student-1")

    assert supabase.rpc.call_count == 1
    supabase.rpc.assert_called_once_with(
        "student_interviews", {"application_ids": ["app-1", "app-2", "app-3"]}
    )
    by_id = {r["id"]: r for r in result}
    assert by_id["app-2"]["interview"] is not None
    assert by_id["app-1"]["interview"] is None
    assert by_id["app-3"]["interview"] is None


def test_application_select_has_no_nested_interview_embed():
    assert "interview" not in svc._APPLICATION_SELECT
    assert "interviews(" not in svc._APPLICATION_SELECT


def test_get_own_application_attaches_interview_via_rpc():
    supabase = MagicMock()
    (
        supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data
    ) = _app_row()
    supabase.rpc.return_value.execute.return_value.data = [_interview_row()]

    row = svc._get_own_application(supabase, "student-1", "app-1")

    supabase.rpc.assert_called_once_with(
        "student_interviews", {"application_ids": ["app-1"]}
    )
    assert row["interview"]["id"] == "iv-1"
    assert "notes" not in row["interview"]


def test_my_applications_route_exposes_interview_without_notes():
    row = _application(status="INTERVIEW_SCHEDULED")
    row["interview"] = {
        "id": "iv-1",
        "application_id": row["id"],
        "scheduled_at": "2026-09-12T15:00:00+00:00",
        "duration_minutes": 30,
        "mode": "ONLINE",
        "location": "https://meet.example.com/abc",
        "status": "SCHEDULED",
    }
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_my_applications", return_value=[row]),
    ):
        resp = client.get(
            "/api/v1/student/applications", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    interview = resp.json()["applications"][0]["interview"]
    assert interview["mode"] == "ONLINE"
    assert interview["scheduled_at"] == "2026-09-12T15:00:00+00:00"
    assert "notes" not in interview


def test_my_applications_route_interview_null_still_200():
    row = _application(status="INTERVIEW_SCHEDULED")
    row["interview"] = None
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_my_applications", return_value=[row]),
    ):
        resp = client.get(
            "/api/v1/student/applications", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json()["applications"][0]["interview"] is None


def test_student_interviews_migration_is_scoped_and_hides_private_columns():
    sql = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "083_student_interview_visibility.sql"
    ).read_text()

    # student can only reach their OWN interviews, and only as a student
    assert "i.student_id = auth.uid()" in sql
    assert "public.is_student(auth.uid())" in sql
    # only live interviews
    assert "i.status = 'SCHEDULED'" in sql
    # hardening consistent with the other SECURITY DEFINER helpers
    assert "security definer" in sql
    assert "set search_path = ''" in sql
    assert "grant execute on function public.student_interviews(uuid[]) to authenticated;" in sql
    assert "from anon" in sql
    # Industry-private columns are not in the result type
    assert "notes" not in sql.split("returns table")[1].split("$$")[0]
    # 030 is not touched by this migration
    assert "alter table interviews" not in sql.lower()
    assert "drop policy" not in sql.lower()
