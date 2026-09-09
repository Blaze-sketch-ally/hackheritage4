"""Tests for Industry interview scheduling: /api/v1/interviews.

Route tests mock app.services.interview_service and use
tests.conftest.authenticated_as; service tests drive the functions with a
MagicMock Supabase client and patched helpers -- no live project or real
token.

The "route + real service" block at the end drives the ACTUAL
interview_service through the route with a scoped fake Supabase client
(_ScopedFakeClient): it proves GET /api/v1/interviews succeeds without the
fragile interviews -> applications PostgREST embed that used to 500 the
endpoint, and that both the interview read and the opportunity-enrichment
read are scoped to the caller's own industry_id.

RLS isolation (an Industry account can never read/write another's
interview rows) is enforced at the database layer by 030's policies
(auth.uid() = industry_id AND public.is_industry(auth.uid())), exactly
like every prior Industry module -- not re-verified against a live DB
here. What IS verified: the Python service always scopes its query by the
caller's own industry_id, the require_industry guard gates every route,
identity fields (industry_id/student_id/status) can never be supplied by
the client, and the lifecycle/eligibility/conflict rules hold.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import interview_service
from tests.conftest import authenticated_as

client = TestClient(app)


def _future_iso(hours: int = 48) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _row(**overrides):
    row = {
        "id": "interview-1",
        "application_id": "app-1",
        "industry_id": "industry-1",
        "student_id": "student-1",
        "scheduled_at": _future_iso(),
        "duration_minutes": 30,
        "mode": "ONLINE",
        "location": "https://meet.example.com/abc",
        "notes": None,
        "status": "SCHEDULED",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "opportunity": {"id": "job-1", "title": "Backend Engineer", "status": "PUBLISHED"},
        "opportunity_type": "JOB",
    }
    row.update(overrides)
    return row


def _create_body(**overrides):
    body = {
        "application_id": str(uuid4()),
        "scheduled_at": _future_iso(),
        "duration_minutes": 45,
        "mode": "ONLINE",
        "location": "https://meet.example.com/xyz",
    }
    body.update(overrides)
    return body


_ENDPOINTS = [
    ("get", "/api/v1/interviews"),
    ("post", "/api/v1/interviews"),
    ("get", f"/api/v1/interviews/{uuid4()}"),
    ("patch", f"/api/v1/interviews/{uuid4()}"),
    ("post", f"/api/v1/interviews/{uuid4()}/complete"),
    ("post", f"/api/v1/interviews/{uuid4()}/cancel"),
]


def _call(method: str, url: str, *, headers=None, json=None):
    kwargs = {"headers": headers}
    if method in {"post", "patch"}:
        kwargs["json"] = json if json is not None else _create_body()
    return getattr(client, method)(url, **kwargs)


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# Create: ownership + immutable fields
# ============================================================


def test_create_derives_owner_and_starts_scheduled():
    captured = {}

    def fake_create(_client, industry_id, data):
        captured.update({"industry_id": industry_id, "data": data})
        return _row(industry_id=industry_id, status="SCHEDULED")

    with (
        authenticated_as("INDUSTRY", user_id="industry-77"),
        patch.object(interview_service, "create_interview", side_effect=fake_create),
    ):
        resp = client.post(
            "/api/v1/interviews", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 201
    assert captured["industry_id"] == "industry-77"
    assert "industry_id" not in captured["data"]
    assert "student_id" not in captured["data"]
    assert "status" not in captured["data"]
    assert resp.json()["status"] == "SCHEDULED"


def test_create_rejects_client_supplied_industry_id():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/interviews",
            json=_create_body(industry_id="attacker"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_client_supplied_student_id_and_status():
    for smuggled in ({"student_id": "s-9"}, {"status": "COMPLETED"}):
        with authenticated_as("INDUSTRY"):
            resp = client.post(
                "/api/v1/interviews",
                json=_create_body(**smuggled),
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 422, smuggled


def test_create_rejects_missing_required_fields():
    for drop in ("application_id", "scheduled_at", "mode"):
        body = _create_body()
        del body[drop]
        with authenticated_as("INDUSTRY"):
            resp = client.post(
                "/api/v1/interviews", json=body, headers={"Authorization": "Bearer token"}
            )
        assert resp.status_code == 422, drop


def test_create_rejects_bad_mode_and_out_of_range_duration():
    for bad in ({"mode": "TELEPATHY"}, {"duration_minutes": 3}, {"duration_minutes": 9000}):
        with authenticated_as("INDUSTRY"):
            resp = client.post(
                "/api/v1/interviews",
                json=_create_body(**bad),
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 422, bad


def test_create_ineligible_application_maps_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "create_interview",
            side_effect=interview_service.IneligibleApplicationError("not shortlisted"),
        ),
    ):
        resp = client.post(
            "/api/v1/interviews", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_past_time_maps_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "create_interview",
            side_effect=interview_service.InvalidInterviewTimeError("in the past"),
        ),
    ):
        resp = client.post(
            "/api/v1/interviews", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_conflict_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "create_interview",
            side_effect=interview_service.SchedulingConflictError("already scheduled"),
        ),
    ):
        resp = client.post(
            "/api/v1/interviews", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


# ============================================================
# Ownership isolation on read / update / lifecycle
# ============================================================


def test_get_detail_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(interview_service, "get_interview", return_value=None) as mock_get,
    ):
        resp = client.get(
            f"/api/v1/interviews/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "industry-A"


def test_list_passes_owner_and_filters_to_service():
    captured = {}

    def fake_list(_client, industry_id, *, status=None, application_id=None, upcoming=None):
        captured.update(
            {"industry_id": industry_id, "status": status, "upcoming": upcoming}
        )
        return [_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(interview_service, "list_interviews", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/interviews?status=SCHEDULED&upcoming=true",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"industry_id": "industry-1", "status": "SCHEDULED", "upcoming": True}


def test_reschedule_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(interview_service, "reschedule_interview", return_value=None),
    ):
        resp = client.patch(
            f"/api/v1/interviews/{uuid4()}",
            json={"scheduled_at": _future_iso()},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_reschedule_rejects_application_id_change():
    with authenticated_as("INDUSTRY"):
        resp = client.patch(
            f"/api/v1/interviews/{uuid4()}",
            json={"application_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_reschedule_on_terminal_interview_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "reschedule_interview",
            side_effect=interview_service.InvalidStatusTransitionError("COMPLETED", "SCHEDULED"),
        ),
    ):
        resp = client.patch(
            f"/api/v1/interviews/{uuid4()}",
            json={"notes": "x"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_complete_and_cancel_404_when_not_owned():
    for action in ("complete", "cancel"):
        with (
            authenticated_as("INDUSTRY", user_id="industry-A"),
            patch.object(interview_service, f"{action}_interview", return_value=None),
        ):
            resp = client.post(
                f"/api/v1/interviews/{uuid4()}/{action}",
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 404, action


def test_complete_invalid_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "complete_interview",
            side_effect=interview_service.InvalidStatusTransitionError("CANCELLED", "COMPLETED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/interviews/{uuid4()}/complete", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


# ============================================================
# Service layer -- eligibility / lifecycle / scoping
# ============================================================


def test_service_create_rejects_unowned_or_missing_application():
    mock = MagicMock()
    with patch(
        "app.services.interview_service.application_service.get_application", return_value=None
    ):
        try:
            interview_service.create_interview(
                mock, "industry-1", {"application_id": "app-x", "scheduled_at": _future_iso()}
            )
            raise AssertionError("expected IneligibleApplicationError")
        except interview_service.IneligibleApplicationError:
            pass


def test_service_create_rejects_application_not_shortlisted():
    mock = MagicMock()
    with patch(
        "app.services.interview_service.application_service.get_application",
        return_value={"id": "app-1", "status": "APPLIED"},
    ):
        try:
            interview_service.create_interview(
                mock, "industry-1", {"application_id": "app-1", "scheduled_at": _future_iso()}
            )
            raise AssertionError("expected IneligibleApplicationError")
        except interview_service.IneligibleApplicationError:
            pass


def test_service_create_rejects_past_time():
    mock = MagicMock()
    with patch(
        "app.services.interview_service.application_service.get_application",
        return_value={"id": "app-1", "status": "SHORTLISTED"},
    ):
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        try:
            interview_service.create_interview(
                mock, "industry-1", {"application_id": "app-1", "scheduled_at": past}
            )
            raise AssertionError("expected InvalidInterviewTimeError")
        except interview_service.InvalidInterviewTimeError:
            pass


def test_service_create_rejects_when_application_already_has_live_interview():
    mock = MagicMock()
    with (
        patch(
            "app.services.interview_service.application_service.get_application",
            return_value={"id": "app-1", "status": "INTERVIEW_SCHEDULED"},
        ),
        patch.object(interview_service, "list_interviews", return_value=[_row()]),
    ):
        try:
            interview_service.create_interview(
                mock, "industry-1", {"application_id": "app-1", "scheduled_at": _future_iso()}
            )
            raise AssertionError("expected SchedulingConflictError")
        except interview_service.SchedulingConflictError:
            pass


def test_service_overlap_detection():
    base = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    others = [{"scheduled_at": base.isoformat(), "duration_minutes": 60}]
    # 10:30 start, 30 min -> overlaps 10:00-11:00
    assert interview_service._overlaps(base + timedelta(minutes=30), 30, others) is True
    # 11:30 start -> no overlap
    assert interview_service._overlaps(base + timedelta(minutes=90), 30, others) is False


def test_service_transitions_are_scheduled_only():
    assert interview_service._COMPLETE_FROM == frozenset({"SCHEDULED"})
    assert interview_service._CANCEL_FROM == frozenset({"SCHEDULED"})


def test_service_complete_rejects_non_scheduled():
    mock = MagicMock()
    with patch.object(interview_service, "get_interview", return_value=_row(status="CANCELLED")):
        try:
            interview_service.complete_interview(mock, "industry-1", "interview-1")
            raise AssertionError("expected InvalidStatusTransitionError")
        except interview_service.InvalidStatusTransitionError:
            pass


def test_service_list_scopes_by_industry_id():
    mock = MagicMock()
    table = mock.table.return_value
    table.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    interview_service.list_interviews(mock, "industry-42")
    mock.table.assert_called_with("interviews")
    table.select.return_value.eq.assert_called_with("industry_id", "industry-42")


# ------------------------------------------------------------
# Regression: the interviews read must NOT depend on a PostgREST
# interviews -> applications embed (that relationship is not guaranteed to
# be in the schema cache; when it was missing every interview list 500'd
# and the Interview panel showed nothing). The opportunity is stitched on
# from a separate, ownership-scoped `applications` read instead.
# ------------------------------------------------------------


def test_service_select_has_no_cross_table_embed():
    assert "applications(" not in interview_service._SELECT
    assert "internships(" not in interview_service._SELECT


def test_service_list_stitches_opportunity_from_separate_applications_read():
    mock = MagicMock()

    interviews_tbl = MagicMock()
    interviews_tbl.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "iv-1", "application_id": "app-1", "industry_id": "industry-1", "status": "SCHEDULED"},
    ]
    applications_tbl = MagicMock()
    applications_tbl.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
        {
            "id": "app-1",
            "opportunity_type": "JOB",
            "internship": None,
            "job": {"id": "job-1", "title": "Backend Engineer", "status": "PUBLISHED"},
        },
    ]
    mock.table.side_effect = lambda name: {
        "interviews": interviews_tbl,
        "applications": applications_tbl,
    }[name]

    rows = interview_service.list_interviews(mock, "industry-1")

    assert rows[0]["opportunity"] == {"id": "job-1", "title": "Backend Engineer", "status": "PUBLISHED"}
    assert rows[0]["opportunity_type"] == "JOB"
    # the enrichment read is scoped to the caller's own applications, both
    # by an explicit industry_id filter and by the id list of the batch
    applications_tbl.select.return_value.eq.assert_called_with("industry_id", "industry-1")
    applications_tbl.select.return_value.eq.return_value.in_.assert_called_with("id", ["app-1"])


def test_service_list_tolerates_failed_opportunity_lookup():
    mock = MagicMock()
    interviews_tbl = MagicMock()
    interviews_tbl.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "iv-1", "application_id": "app-1", "industry_id": "industry-1", "status": "SCHEDULED"},
    ]
    applications_tbl = MagicMock()
    applications_tbl.select.return_value.eq.return_value.in_.return_value.execute.side_effect = (
        RuntimeError("boom")
    )
    mock.table.side_effect = lambda name: {
        "interviews": interviews_tbl,
        "applications": applications_tbl,
    }[name]

    rows = interview_service.list_interviews(mock, "industry-1")

    assert rows[0]["opportunity"] is None
    assert rows[0]["opportunity_type"] is None


# ------------------------------------------------------------
# Applicant name: the scheduled-interview view must show the same real
# name the Applicants list shows, resolved through the SAME
# ownership-scoped `application_applicant_names` RPC -- name only, and
# best-effort (a lookup failure falls back to the id placeholder).
# ------------------------------------------------------------


def test_service_list_attaches_applicant_name_from_ownership_scoped_rpc():
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row(id="iv-1", application_id="app-1", industry_id="industry-1")],
        applications=[_app_db_row(id="app-1", industry_id="industry-1")],
        applicant_names={"app-1": "Priya Menon"},
    )
    rows = interview_service.list_interviews(fake, "industry-1")
    assert rows[0]["student_name"] == "Priya Menon"


def test_service_get_attaches_applicant_name():
    iv_id = "iv-9"
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row(id=iv_id, application_id="app-1", industry_id="industry-1")],
        applications=[_app_db_row(id="app-1", industry_id="industry-1")],
        applicant_names={"app-1": "Priya Menon"},
    )
    row = interview_service.get_interview(fake, "industry-1", iv_id)
    assert row["student_name"] == "Priya Menon"


def test_service_list_tolerates_failed_applicant_name_lookup():
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row(id="iv-1", application_id="app-1", industry_id="industry-1")],
        applications=[_app_db_row(id="app-1", industry_id="industry-1")],
        applicant_names={"app-1": "Priya Menon"},
        raise_on="rpc",
    )
    rows = interview_service.list_interviews(fake, "industry-1")
    assert rows[0]["student_name"] is None


def test_service_applicant_name_rpc_is_scoped_to_owned_applications_only():
    """The RPC only returns a name for applications the caller owns; an
    interview whose application id is not in the owned set gets no name."""
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row(id="iv-1", application_id="app-x", industry_id="industry-1")],
        applications=[_app_db_row(id="app-x", industry_id="industry-1")],
        applicant_names={},  # RPC resolves nothing for this caller
    )
    rows = interview_service.list_interviews(fake, "industry-1")
    assert rows[0]["student_name"] is None


# ============================================================
# Route + REAL service: GET /api/v1/interviews must not 500 on a missing
# PostgREST embed, and both reads must be industry-scoped
# ============================================================
#
# At HEAD a8e00a0 the service did ONE query:
#   interviews.select("... application:applications(... internships(...),
#                       jobs(...))")
# The interviews -> applications relationship is not guaranteed to be in
# PostgREST's schema cache; when it was missing the query raised, the
# route caught it as a blanket 500, and the Interview panel rendered its
# error state -- i.e. NO candidates. These tests drive the real service
# through the route with a scoped fake client that has no such embed
# relationship at all, and assert the endpoint succeeds.


class _FakeQuery:
    """Minimal PostgREST-query stand-in: `select` is a no-op, `eq` / `in_`
    actually filter the row list (so scoping is real), everything else
    chains. It knows NOTHING about embeds -- a `select` string asking for a
    nested `applications(...)` relationship simply returns the flat rows,
    exactly as a live PostgREST would once the relationship it could not
    resolve is gone."""

    def __init__(self, rows: list[dict], *, raises: bool = False):
        self._rows = [dict(r) for r in rows]
        self._raises = raises
        self._single = False

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self._rows = [r for r in self._rows if r.get(column) == value]
        return self

    def in_(self, column, values):
        self._rows = [r for r in self._rows if r.get(column) in set(values)]
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def execute(self):
        if self._raises:
            raise RuntimeError("Could not find a relationship in the schema cache")
        if self._single:
            return SimpleNamespace(data=self._rows[0] if self._rows else None)
        return SimpleNamespace(data=list(self._rows))


class _FakeRpc:
    """Stand-in for the `application_applicant_names` SECURITY DEFINER RPC:
    given a list of application ids it returns `{application_id,
    student_name}` rows, but ONLY for ids in `names` (mirroring the
    function's ownership scoping -- an application the caller does not own
    simply yields no row). `raises=True` simulates the RPC being
    unavailable."""

    def __init__(self, params: dict, names: dict[str, str], *, raises: bool = False):
        self._ids = list((params or {}).get("application_ids") or [])
        self._names = names
        self._raises = raises

    def execute(self):
        if self._raises:
            raise RuntimeError("function public.application_applicant_names does not exist")
        return SimpleNamespace(
            data=[
                {"application_id": aid, "student_name": self._names[aid]}
                for aid in self._ids
                if aid in self._names
            ]
        )


class _ScopedFakeClient:
    """A fake user-scoped Supabase client backing exactly the two tables
    interview_service reads, plus the ownership-scoped applicant-name RPC.
    `raise_on` names a table (or "rpc") whose `.execute()` should blow up
    (used to simulate an unavailable enrichment read)."""

    def __init__(
        self,
        *,
        interviews: list[dict],
        applications: list[dict],
        applicant_names: dict[str, str] | None = None,
        raise_on: str = "",
    ):
        self._data = {"interviews": interviews, "applications": applications}
        self._applicant_names = applicant_names or {}
        self._raise_on = raise_on

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self._data.get(name, []), raises=(name == self._raise_on))

    def rpc(self, name: str, params: dict) -> _FakeRpc:
        return _FakeRpc(params, self._applicant_names, raises=(self._raise_on == "rpc"))


def _iv_db_row(**overrides) -> dict:
    """A raw `interviews` row as the flat _SELECT returns it -- NO
    `opportunity` / `opportunity_type` (those are stitched on by the
    service, not columns)."""
    row = {
        "id": "iv-A",
        "application_id": "app-A",
        "industry_id": "industry-A",
        "student_id": "student-A",
        "scheduled_at": _future_iso(),
        "duration_minutes": 30,
        "mode": "ONLINE",
        "location": None,
        "notes": None,
        "status": "SCHEDULED",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _app_db_row(**overrides) -> dict:
    row = {
        "id": "app-A",
        "industry_id": "industry-A",
        "opportunity_type": "JOB",
        "internship": None,
        "job": {"id": "job-A", "title": "Platform Engineer", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


def test_route_list_interviews_succeeds_without_the_applications_embed():
    fake = _ScopedFakeClient(interviews=[_iv_db_row()], applications=[_app_db_row()])
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch("app.api.interviews.build_user_client", return_value=fake),
    ):
        resp = client.get("/api/v1/interviews", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 200
    body = resp.json()["interviews"]
    assert len(body) == 1
    assert body[0]["id"] == "iv-A"
    assert body[0]["application_id"] == "app-A"
    # opportunity was stitched from the SEPARATE applications read
    assert body[0]["opportunity"] == {
        "id": "job-A",
        "title": "Platform Engineer",
        "status": "PUBLISHED",
    }
    assert body[0]["opportunity_type"] == "JOB"


def test_route_list_interviews_still_200_when_opportunity_enrichment_fails():
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row()], applications=[_app_db_row()], raise_on="applications"
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch("app.api.interviews.build_user_client", return_value=fake),
    ):
        resp = client.get("/api/v1/interviews", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 200
    body = resp.json()["interviews"]
    assert len(body) == 1
    assert body[0]["id"] == "iv-A"
    # enrichment failed -> the interview still lists, just without opportunity
    assert body[0]["opportunity"] is None
    assert body[0]["opportunity_type"] is None


def test_route_list_interviews_is_scoped_to_the_caller_industry():
    """Industry B asks for interviews; the store also holds an Industry A
    interview + application. B must get ONLY its own row, and the
    enrichment read must not surface A's application either."""
    fake = _ScopedFakeClient(
        interviews=[
            _iv_db_row(id="iv-A", application_id="app-A", industry_id="industry-A"),
            _iv_db_row(id="iv-B", application_id="app-B", industry_id="industry-B"),
        ],
        applications=[
            _app_db_row(id="app-A", industry_id="industry-A"),
            _app_db_row(
                id="app-B",
                industry_id="industry-B",
                job={"id": "job-B", "title": "SRE", "status": "PUBLISHED"},
            ),
        ],
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-B"),
        patch("app.api.interviews.build_user_client", return_value=fake),
    ):
        resp = client.get("/api/v1/interviews", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 200
    body = resp.json()["interviews"]
    assert [row["id"] for row in body] == ["iv-B"]
    assert body[0]["opportunity"] == {"id": "job-B", "title": "SRE", "status": "PUBLISHED"}
    # nothing belonging to Industry A leaked through either read
    assert all(row["industry_id"] == "industry-B" for row in body)


def test_route_get_one_interview_succeeds_without_the_applications_embed():
    iv_id = str(uuid4())
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row(id=iv_id)], applications=[_app_db_row()]
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch("app.api.interviews.build_user_client", return_value=fake),
    ):
        resp = client.get(
            f"/api/v1/interviews/{iv_id}", headers={"Authorization": "Bearer token"}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == iv_id
    assert body["opportunity_type"] == "JOB"
    assert body["opportunity"]["title"] == "Platform Engineer"


def test_route_get_one_interview_404_for_another_industry():
    iv_id = str(uuid4())
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row(id=iv_id, industry_id="industry-A")],
        applications=[_app_db_row()],
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-B"),
        patch("app.api.interviews.build_user_client", return_value=fake),
    ):
        resp = client.get(
            f"/api/v1/interviews/{iv_id}", headers={"Authorization": "Bearer token"}
        )

    assert resp.status_code == 404


def test_route_list_interviews_includes_applicant_name_and_nothing_else():
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row(id="iv-A", application_id="app-A", industry_id="industry-A")],
        applications=[_app_db_row(id="app-A", industry_id="industry-A")],
        applicant_names={"app-A": "Priya Menon"},
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch("app.api.interviews.build_user_client", return_value=fake),
    ):
        resp = client.get("/api/v1/interviews", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 200
    body = resp.json()["interviews"][0]
    assert body["student_name"] == "Priya Menon"
    # only the NAME is exposed -- no email / phone / avatar / profile fields
    assert "email" not in body
    assert "phone" not in body
    assert "avatar_url" not in body


def test_route_get_one_interview_includes_applicant_name():
    iv_id = str(uuid4())
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row(id=iv_id, application_id="app-A", industry_id="industry-A")],
        applications=[_app_db_row(id="app-A", industry_id="industry-A")],
        applicant_names={"app-A": "Priya Menon"},
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch("app.api.interviews.build_user_client", return_value=fake),
    ):
        resp = client.get(
            f"/api/v1/interviews/{iv_id}", headers={"Authorization": "Bearer token"}
        )

    assert resp.status_code == 200
    assert resp.json()["student_name"] == "Priya Menon"


def test_route_list_interviews_still_200_when_applicant_name_rpc_unavailable():
    fake = _ScopedFakeClient(
        interviews=[_iv_db_row(id="iv-A", application_id="app-A", industry_id="industry-A")],
        applications=[_app_db_row(id="app-A", industry_id="industry-A")],
        applicant_names={"app-A": "Priya Menon"},
        raise_on="rpc",
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch("app.api.interviews.build_user_client", return_value=fake),
    ):
        resp = client.get("/api/v1/interviews", headers={"Authorization": "Bearer token"})

    assert resp.status_code == 200
    body = resp.json()["interviews"][0]
    assert body["id"] == "iv-A"
    assert body["student_name"] is None
