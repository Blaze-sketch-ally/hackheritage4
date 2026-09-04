"""Phase 2 -- Internship Workspace provisioning + the minimal read surface.

Route tests mock the service and use tests.conftest.authenticated_as
(same convention as tests/test_applications.py / tests/test_interviews.py).
Service tests drive provision_for_selection() and the two list functions
with a small purpose-built fake Supabase client -- no live project.

RLS is the real access-control boundary (038_internship_workspace.sql,
verified live in Phase 1): a student can never read another student's
workspace, an industry can never read another industry's, and workspace
access never depends on internships.status. This suite verifies the
Python layer's half -- the service always scopes its query by the
caller's own id, the role guards gate every route, provisioning is
idempotent and eligibility-gated, and provisioning never mutates
applications / internships.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.services import application_service, internship_workspace_service
from app.services.internship_workspace_service import (
    ApplicationNotFoundError,
    ProvisionRejectedError,
)
from tests.conftest import authenticated_as

client = TestClient(app)

svc = internship_workspace_service


# ============================================================
# fake Supabase client
# ============================================================


def _ws_row(**overrides):
    row = {
        "id": "ws-1",
        "application_id": "app-1",
        "internship_id": "int-1",
        "student_id": "student-1",
        "industry_id": "industry-1",
        "work_mode": "REMOTE",
        "workspace_status": "PENDING_ACCEPTANCE",
        "accepted_at": None,
        "started_at": None,
        "completed_at": None,
        "declined_at": None,
        "decline_reason": None,
        "rescinded_at": None,
        "rescind_reason": None,
        "created_at": "2026-09-04T00:00:00Z",
        "updated_at": "2026-09-04T00:00:00Z",
        "internship": {"id": "int-1", "title": "ML Intern", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


class _FakeQuery:
    def __init__(self, fake, table):
        self._fake = fake
        self._table = table
        self._is_single = False
        self._insert = None

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def eq(self, field, value):
        self._fake.filters.append((self._table, field, value))
        return self

    def maybe_single(self):
        self._is_single = True
        return self

    def insert(self, payload):
        self._insert = payload
        return self

    def update(self, payload):
        self._fake.updates.append((self._table, payload))
        return self

    def execute(self):
        return self._fake._execute(self._table, self)


class _FakeSupabase:
    def __init__(
        self,
        *,
        application=None,
        internship=None,
        program=None,
        workspace=None,
        workspace_after_provision=None,
        workspace_list=None,
        insert_error=None,
    ):
        self.application = application
        self.internship = internship
        self.program = program
        self.workspace = workspace
        self.workspace_after_provision = workspace_after_provision or _ws_row()
        self.workspace_list = workspace_list or []
        self.insert_error = insert_error
        self.inserts: list[tuple[str, dict]] = []
        self.updates: list[tuple[str, dict]] = []
        self.reads: list[str] = []
        self.filters: list[tuple[str, str, object]] = []
        self._insert_attempted = False

    def table(self, name):
        return _FakeQuery(self, name)

    def _execute(self, table, q: _FakeQuery):
        if q._insert is not None:
            self.inserts.append((table, q._insert))
            self._insert_attempted = True
            if self.insert_error is not None:
                raise self.insert_error
            return SimpleNamespace(data=[{"id": "ws-created"}])
        self.reads.append(table)
        if table == "applications":
            return SimpleNamespace(data=self.application)
        if table == "internships":
            return SimpleNamespace(data=self.internship)
        if table == "internship_programs":
            return SimpleNamespace(data=self.program)
        if table == "internship_workspaces":
            if q._is_single:
                # pre-insert reads see the current DB state; a read AFTER an
                # insert attempt (success or 23505 race) sees the row that
                # now exists.
                if self._insert_attempted:
                    return SimpleNamespace(data=self.workspace_after_provision)
                return SimpleNamespace(data=self.workspace)
            return SimpleNamespace(data=self.workspace_list)
        raise AssertionError(f"unexpected table {table!r}")


def _fake(**kwargs) -> _FakeSupabase:
    kwargs.setdefault("application", {
        "id": "app-1", "internship_id": "int-1", "opportunity_type": "INTERNSHIP",
        "status": "SELECTED",
    })
    kwargs.setdefault("internship", {"id": "int-1", "work_mode": "REMOTE"})
    kwargs.setdefault("program", {"id": "prog-1", "status": "PUBLISHED"})
    return _FakeSupabase(**kwargs)


# ============================================================
# A-B. eligible: REMOTE / HYBRID + SELECTED -> workspace created
# ============================================================


def test_remote_selected_creates_a_workspace():
    fake = _fake(internship={"id": "int-1", "work_mode": "REMOTE"})
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "CREATED"
    assert result.created is True
    assert result.work_mode == "REMOTE"
    assert fake.inserts == [("internship_workspaces", {"application_id": "app-1"})]


def test_hybrid_selected_creates_a_workspace():
    fake = _fake(internship={"id": "int-1", "work_mode": "HYBRID"})
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "CREATED"
    assert result.work_mode == "HYBRID"
    assert len(fake.inserts) == 1


# ============================================================
# C-D. ineligible work mode -> no workspace
# ============================================================


def test_onsite_selected_creates_no_workspace():
    fake = _fake(internship={"id": "int-1", "work_mode": "ONSITE"})
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "SKIPPED_WORK_MODE"
    assert result.workspace is None
    assert fake.inserts == []


def test_null_work_mode_selected_creates_no_workspace():
    fake = _fake(internship={"id": "int-1", "work_mode": None})
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "SKIPPED_WORK_MODE"
    assert fake.inserts == []


# ============================================================
# E, K. idempotency
# ============================================================


def test_provisioning_twice_creates_exactly_one_workspace():
    fake = _fake()
    first = svc.provision_for_selection(fake, "app-1")
    second = svc.provision_for_selection(fake, "app-1")
    assert first.outcome == "CREATED"
    assert second.outcome == "ALREADY_EXISTS"
    assert len(fake.inserts) == 1  # the second call inserted nothing


def test_existing_workspace_is_returned_not_duplicated():
    existing = _ws_row(id="ws-existing", workspace_status="ACCEPTED")
    fake = _fake(workspace=existing)
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "ALREADY_EXISTS"
    assert result.workspace["id"] == "ws-existing"
    assert fake.inserts == []


def test_concurrent_unique_violation_is_treated_as_already_exists():
    fake = _fake(
        insert_error=APIError({"code": "23505", "message": "duplicate key"}),
        workspace_after_provision=_ws_row(id="ws-race"),
    )
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "ALREADY_EXISTS"
    assert result.workspace["id"] == "ws-race"


# ============================================================
# F. missing program -> clear no-op, no partial workspace
# ============================================================


def test_missing_program_skips_without_creating_a_partial_workspace():
    fake = _fake(program=None)
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "SKIPPED_NO_PROGRAM"
    assert result.workspace is None
    assert fake.inserts == []


def test_missing_program_is_provisioned_on_a_later_call_once_it_exists():
    without = _fake(program=None)
    assert svc.provision_for_selection(without, "app-1").outcome == "SKIPPED_NO_PROGRAM"
    with_program = _fake(program={"id": "prog-1", "status": "DRAFT"})
    assert svc.provision_for_selection(with_program, "app-1").outcome == "CREATED"


# ============================================================
# J. non-SELECTED / non-internship -> no provisioning
# ============================================================


def test_non_selected_application_is_not_provisioned():
    fake = _fake(application={
        "id": "app-1", "internship_id": "int-1", "opportunity_type": "INTERNSHIP",
        "status": "INTERVIEW_SCHEDULED",
    })
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "SKIPPED_NOT_SELECTED"
    assert fake.inserts == []


def test_job_application_is_not_provisioned():
    fake = _fake(application={
        "id": "app-1", "internship_id": None, "job_id": "job-1",
        "opportunity_type": "JOB", "status": "SELECTED",
    })
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "SKIPPED_NOT_INTERNSHIP"
    assert fake.inserts == []


# ============================================================
# provisioning never mutates applications / internships
# ============================================================


def test_provisioning_never_updates_applications_or_internships():
    for work_mode in ("REMOTE", "HYBRID", "ONSITE", None):
        fake = _fake(internship={"id": "int-1", "work_mode": work_mode})
        svc.provision_for_selection(fake, "app-1")
        assert fake.updates == [], f"work_mode={work_mode}: provisioning wrote {fake.updates}"


def test_application_not_found_raises_a_domain_error():
    fake = _fake(application=None)
    try:
        svc.provision_for_selection(fake, "missing")
        raised = False
    except ApplicationNotFoundError:
        raised = True
    assert raised
    assert fake.inserts == []


def test_rls_rejection_of_the_insert_raises_provision_rejected():
    fake = _fake(insert_error=APIError({"code": "42501", "message": "rls"}))
    try:
        svc.provision_for_selection(fake, "app-1")
        raised = False
    except ProvisionRejectedError:
        raised = True
    assert raised


# ============================================================
# I. workspace stays readable regardless of internship status
# ============================================================


def test_student_list_resolves_the_internship_even_for_a_closed_posting():
    # A CLOSED/ARCHIVED internship is invisible to student RLS on
    # `internships`. Phase 3: the title/details are resolved via the
    # narrow service-role _resolve_internship_summaries, so the workspace
    # keeps its label. The workspace row itself is always returned.
    fake = _FakeSupabase(workspace_list=[_ws_row(id="ws-a", workspace_status="ACCEPTED")])
    with patch.object(
        svc,
        "_resolve_internship_summaries",
        return_value={
            "int-1": {
                "id": "int-1", "title": "ML Intern", "description": "Build models.",
                "work_mode": "REMOTE", "status": "CLOSED",
            }
        },
    ):
        rows = svc.list_student_workspaces(fake, "student-1")
    assert len(rows) == 1
    assert rows[0]["id"] == "ws-a"
    assert rows[0]["internship"]["title"] == "ML Intern"
    assert rows[0]["internship"]["status"] == "CLOSED"


def test_list_functions_never_gate_on_the_internship_posting_status():
    import ast
    import inspect

    for fn in (svc.list_student_workspaces, svc.list_industry_workspaces):
        tree = ast.parse(inspect.getsource(fn).lstrip())
        # every string CONSTANT in the function body (docstring excluded via
        # the ast walk of executable nodes only)
        eq_fields = [
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "eq"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ]
        assert set(eq_fields) <= {
            "student_id", "industry_id", "internship_id", "workspace_status",
        }, f"{fn.__name__} filters on unexpected field(s): {eq_fields}"
        assert "status" not in eq_fields  # never the internship posting status


# ============================================================
# G-H. the service always scopes list reads to the caller's own id
# ============================================================


def test_student_list_is_scoped_to_the_caller():
    fake = _FakeSupabase(workspace_list=[_ws_row()])
    with patch.object(svc, "_resolve_internship_summaries", return_value={}):
        svc.list_student_workspaces(fake, "student-9")
    assert ("internship_workspaces", "student_id", "student-9") in fake.filters
    assert not any(f[1] == "industry_id" for f in fake.filters)


def test_industry_list_is_scoped_to_the_caller():
    fake = _FakeSupabase(workspace_list=[_ws_row()])
    svc.list_industry_workspaces(fake, "industry-9", internship_id="int-3", workspace_status="ACCEPTED")
    assert ("internship_workspaces", "industry_id", "industry-9") in fake.filters
    assert ("internship_workspaces", "internship_id", "int-3") in fake.filters
    assert ("internship_workspaces", "workspace_status", "ACCEPTED") in fake.filters


# ============================================================
# integration: the SELECTED transition provisions (best-effort)
# ============================================================


def test_update_status_to_selected_calls_provisioning_once():
    supabase = MagicMock()
    with (
        patch.object(
            application_service,
            "get_application",
            side_effect=[_app_row(status="INTERVIEW_SCHEDULED"), _app_row(status="SELECTED")],
        ),
        patch.object(
            internship_workspace_service, "provision_for_selection"
        ) as provision,
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    provision.assert_called_once_with(supabase, "app-1")


def test_update_status_to_a_non_selected_status_does_not_provision():
    supabase = MagicMock()
    with (
        patch.object(
            application_service,
            "get_application",
            side_effect=[_app_row(status="SHORTLISTED"), _app_row(status="INTERVIEW_SCHEDULED")],
        ),
        patch.object(internship_workspace_service, "provision_for_selection") as provision,
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "INTERVIEW_SCHEDULED")
    provision.assert_not_called()


def test_update_status_still_succeeds_when_provisioning_raises():
    supabase = MagicMock()
    with (
        patch.object(
            application_service,
            "get_application",
            side_effect=[_app_row(status="INTERVIEW_SCHEDULED"), _app_row(status="SELECTED")],
        ),
        patch.object(
            internship_workspace_service,
            "provision_for_selection",
            side_effect=RuntimeError("provisioning blew up"),
        ),
    ):
        result = application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    assert result["status"] == "SELECTED"


def test_update_status_to_selected_only_writes_the_status_field():
    supabase = MagicMock()
    with (
        patch.object(
            application_service,
            "get_application",
            side_effect=[_app_row(status="INTERVIEW_SCHEDULED"), _app_row(status="SELECTED")],
        ),
        patch.object(internship_workspace_service, "provision_for_selection"),
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "SELECTED"}


def _app_row(**overrides):
    row = {
        "id": "app-1",
        "student_id": "student-7",
        "industry_id": "industry-1",
        "opportunity_type": "INTERNSHIP",
        "internship_id": "int-1",
        "job_id": None,
        "status": "APPLIED",
        "cover_note": None,
        "match_score": None,
        "applied_at": "2026-09-01T00:00:00Z",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "opportunity": {"id": "int-1", "title": "ML Intern", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


# ============================================================
# routes -- auth / role guards
# ============================================================

_STUDENT_EP = ("get", "/api/v1/student/internship-workspaces")
_INDUSTRY_EP = ("get", "/api/v1/internship-workspaces")
_PROVISION_EP = ("post", f"/api/v1/applications/{uuid4()}/provision-workspace")


def test_endpoints_reject_unauthenticated():
    for method, url in (_STUDENT_EP, _INDUSTRY_EP, _PROVISION_EP):
        assert getattr(client, method)(url).status_code == 401, url


def test_student_endpoint_forbids_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(
                "/api/v1/student/internship-workspaces", headers={"Authorization": "Bearer t"}
            )
        assert resp.status_code == 403, role


def test_industry_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in (_INDUSTRY_EP, _PROVISION_EP):
            with authenticated_as(role):
                resp = getattr(client, method)(url, headers={"Authorization": "Bearer t"})
            assert resp.status_code == 403, (role, url)


# ============================================================
# routes -- behaviour
# ============================================================


def test_student_list_endpoint_scopes_to_the_caller():
    captured = {}

    def fake_list(_client, student_id):
        captured["student_id"] = student_id
        return [_ws_row(student_id=student_id)]

    with (
        authenticated_as("STUDENT", user_id="student-42"),
        patch.object(internship_workspace_service, "list_student_workspaces", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/internship-workspaces", headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 200
    assert captured["student_id"] == "student-42"
    assert resp.json()["workspaces"][0]["student_id"] == "student-42"


def test_industry_list_endpoint_scopes_to_the_caller_and_passes_filters():
    captured = {}

    def fake_list(_client, industry_id, *, internship_id=None, workspace_status=None):
        captured.update(
            industry_id=industry_id, internship_id=internship_id, workspace_status=workspace_status
        )
        return [_ws_row(industry_id=industry_id)]

    iid = uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-88"),
        patch.object(internship_workspace_service, "list_industry_workspaces", side_effect=fake_list),
    ):
        resp = client.get(
            f"/api/v1/internship-workspaces?internship_id={iid}&status=ACCEPTED",
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-88"
    assert captured["internship_id"] == str(iid)
    assert captured["workspace_status"] == "ACCEPTED"


def test_industry_list_endpoint_rejects_a_bad_status_filter():
    with authenticated_as("INDUSTRY"):
        resp = client.get(
            "/api/v1/internship-workspaces?status=BOGUS", headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 422


def test_provision_endpoint_returns_the_outcome():
    result = internship_workspace_service.ProvisionResult(
        "CREATED", "Internship workspace provisioned.", "app-1", work_mode="REMOTE",
        workspace=_ws_row(),
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_application", return_value=_app_row(status="SELECTED")),
        patch.object(
            internship_workspace_service, "provision_for_selection", return_value=result
        ),
    ):
        resp = client.post(
            f"/api/v1/applications/{uuid4()}/provision-workspace",
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "CREATED"
    assert body["workspace"]["id"] == "ws-1"


def test_provision_endpoint_404_when_application_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "get_application", return_value=None),
        patch.object(internship_workspace_service, "provision_for_selection") as provision,
    ):
        resp = client.post(
            f"/api/v1/applications/{uuid4()}/provision-workspace",
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 404
    provision.assert_not_called()


def test_provision_endpoint_maps_provision_rejected_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "get_application", return_value=_app_row(status="SELECTED")),
        patch.object(
            internship_workspace_service,
            "provision_for_selection",
            side_effect=ProvisionRejectedError("state changed"),
        ),
    ):
        resp = client.post(
            f"/api/v1/applications/{uuid4()}/provision-workspace",
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 409


def test_provision_endpoint_reports_a_skipped_outcome_without_error():
    result = internship_workspace_service.ProvisionResult(
        "SKIPPED_WORK_MODE", "Internship work_mode is 'ONSITE' ...", "app-1", work_mode="ONSITE",
    )
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "get_application", return_value=_app_row(status="SELECTED")),
        patch.object(
            internship_workspace_service, "provision_for_selection", return_value=result
        ),
    ):
        resp = client.post(
            f"/api/v1/applications/{uuid4()}/provision-workspace",
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "SKIPPED_WORK_MODE"
    assert resp.json()["workspace"] is None


# ============================================================
# backfill script -- shape only (never executed against a DB here)
# ============================================================


def test_backfill_script_is_dry_run_by_default_and_reuses_the_service():
    from scripts import backfill_internship_workspaces as backfill

    src = __import__("inspect").getsource(backfill)
    assert "internship_workspace_service.provision_for_selection" in src
    assert "--apply" in src
    # not importable from / callable by the app or a migration
    assert "backfill" not in __import__("app.main", fromlist=["app"]).__dict__

    sb = _FakeSupabase(workspace_list=[])
    sb.application = None  # not used by the dry-run path
    with patch.object(backfill, "get_supabase", return_value=_BackfillFake()):
        assert backfill.run(apply=False) == 0  # dry run: no writes, exit 0


class _BackfillFake:
    """Minimal stub for the backfill's two dry-run queries."""

    def table(self, name):
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        return SimpleNamespace(data=[])
