"""Phase J3 -- Job Training enrollment PROVISIONING + the SELECTED
transition integration + the industry self-heal endpoint.

Route tests mock the service and use tests.conftest.authenticated_as
(same convention as tests/test_internship_workspace_provisioning.py).
Service tests drive provision_for_selection() with a small purpose-built
fake Supabase client -- no live project.

The J1 database trigger set_job_training_enrollment_derived_ids is the
FINAL gate (JOB + SELECTED only, ids derived from the application). This
suite verifies the Python layer's half: the service refuses invalid
applications with a clean typed result, provisioning is idempotent, a
REVOKED enrollment is never silently resurrected, the insert payload is
only {"application_id": ...} (student / industry / job ids are never
client-supplied), and the SELECTED transition branches correctly by
opportunity type without disturbing the existing Internship Workspace
branch.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.services import application_service, internship_workspace_service, job_training_service
from app.services.job_training_service import (
    ApplicationNotFoundError,
    ProvisionRejectedError,
)
from tests.conftest import authenticated_as

client = TestClient(app)
svc = job_training_service


# ============================================================
# fake Supabase client
# ============================================================


def _enr_row(**overrides):
    row = {
        "id": "enr-1",
        "application_id": "app-1",
        "job_id": "job-1",
        "student_id": "student-1",
        "industry_id": "industry-1",
        "enrollment_status": "ACTIVE",
        "completed_at": None,
        "revoked_at": None,
        "revoke_reason": None,
        "created_at": "2026-09-08T00:00:00Z",
        "updated_at": "2026-09-08T00:00:00Z",
    }
    row.update(overrides)
    return row


class _FakeQuery:
    def __init__(self, fake, table):
        self._fake = fake
        self._table = table
        self._single = False
        self._insert = None

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def eq(self, field, value):
        self._fake.filters.append((self._table, field, value))
        return self

    def neq(self, field, value):
        self._fake.filters.append((self._table, f"neq:{field}", value))
        return self

    def in_(self, field, values):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload):
        self._insert = payload
        return self

    def execute(self):
        return self._fake._execute(self._table, self)


class _FakeSupabase:
    def __init__(
        self,
        *,
        application=None,
        program=None,
        enrollment=None,
        enrollment_after=None,
        insert_error=None,
    ):
        self.application = application
        self.program = program
        self.enrollment = enrollment
        self.enrollment_after = enrollment_after or _enr_row()
        self.insert_error = insert_error
        self.inserts: list[tuple[str, dict]] = []
        self.filters: list[tuple] = []
        self._insert_attempted = False

    def table(self, name):
        return _FakeQuery(self, name)

    def _execute(self, table, q: _FakeQuery):
        if q._insert is not None:
            self.inserts.append((table, q._insert))
            self._insert_attempted = True
            if self.insert_error is not None:
                raise self.insert_error
            return SimpleNamespace(data=[{"id": "enr-created"}])
        if table == "applications":
            return SimpleNamespace(data=self.application)
        if table == "job_programs":
            return SimpleNamespace(data=self.program)
        if table == "job_training_enrollments":
            if q._single:
                return SimpleNamespace(
                    data=self.enrollment_after if self._insert_attempted else self.enrollment
                )
            return SimpleNamespace(data=[])
        raise AssertionError(f"unexpected table {table!r}")


def _fake(**kwargs) -> _FakeSupabase:
    kwargs.setdefault(
        "application",
        {"id": "app-1", "job_id": "job-1", "opportunity_type": "JOB", "status": "SELECTED"},
    )
    kwargs.setdefault("program", {"id": "prog-1", "status": "PUBLISHED"})
    return _FakeSupabase(**kwargs)


def _api_error(code: str) -> APIError:
    return APIError({"code": code, "message": code, "details": "", "hint": ""})


# ============================================================
# A. provisioning eligibility (tests 1-14)
# ============================================================


def test_job_selected_with_program_creates_an_enrollment():
    fake = _fake()
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "CREATED"
    assert result.created is True
    assert fake.inserts == [("job_training_enrollments", {"application_id": "app-1"})]


def test_job_selected_without_a_program_is_skipped_safely():
    fake = _fake(program=None)
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "SKIPPED_NO_PROGRAM"
    assert fake.inserts == []


def test_job_selected_with_a_draft_program_still_provisions():
    # provisioning only needs the program to EXIST; PUBLISHED gates student
    # access, not enrollment creation (same as the internship analog).
    fake = _fake(program={"id": "prog-1", "status": "DRAFT"})
    assert svc.provision_for_selection(fake, "app-1").outcome == "CREATED"


def test_job_at_every_non_selected_status_is_skipped():
    for status_value in ("APPLIED", "UNDER_REVIEW", "SHORTLISTED", "INTERVIEW_SCHEDULED",
                         "REJECTED", "WITHDRAWN"):
        fake = _fake(application={
            "id": "app-1", "job_id": "job-1", "opportunity_type": "JOB", "status": status_value,
        })
        result = svc.provision_for_selection(fake, "app-1")
        assert result.outcome == "SKIPPED_NOT_SELECTED", status_value
        assert fake.inserts == [], status_value


def test_internship_selected_is_skipped_not_job():
    fake = _fake(application={
        "id": "app-1", "job_id": None, "internship_id": "int-1",
        "opportunity_type": "INTERNSHIP", "status": "SELECTED",
    })
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "SKIPPED_NOT_JOB"
    assert fake.inserts == []


def test_internship_at_any_status_is_skipped_not_job():
    for status_value in ("APPLIED", "SHORTLISTED", "SELECTED", "REJECTED"):
        fake = _fake(application={
            "id": "app-1", "job_id": None, "opportunity_type": "INTERNSHIP", "status": status_value,
        })
        assert svc.provision_for_selection(fake, "app-1").outcome == "SKIPPED_NOT_JOB"


def test_a_job_row_with_no_job_id_is_skipped_not_job():
    fake = _fake(application={
        "id": "app-1", "job_id": None, "opportunity_type": "JOB", "status": "SELECTED",
    })
    assert svc.provision_for_selection(fake, "app-1").outcome == "SKIPPED_NOT_JOB"


def test_duplicate_provisioning_is_idempotent():
    fake = _fake(enrollment=_enr_row(enrollment_status="ACTIVE"))
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "ALREADY_EXISTS"
    assert fake.inserts == []
    assert result.enrollment["id"] == "enr-1"


def test_completed_enrollment_is_treated_as_already_provisioned():
    fake = _fake(enrollment=_enr_row(enrollment_status="COMPLETED"))
    assert svc.provision_for_selection(fake, "app-1").outcome == "ALREADY_EXISTS"
    assert fake.inserts == []


def test_revoked_enrollment_is_not_silently_resurrected():
    fake = _fake(enrollment=_enr_row(enrollment_status="REVOKED", revoked_at="2026-09-01T00:00:00Z"))
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "REVOKED_BLOCKED"
    assert fake.inserts == []


def test_concurrent_insert_race_23505_is_treated_as_already_exists():
    fake = _fake(insert_error=_api_error("23505"))
    result = svc.provision_for_selection(fake, "app-1")
    assert result.outcome == "ALREADY_EXISTS"


def test_concurrent_insert_race_into_a_revoked_row_reports_revoked_blocked():
    fake = _fake(insert_error=_api_error("23505"))
    fake.enrollment_after = _enr_row(enrollment_status="REVOKED", revoked_at="2026-09-01T00:00:00Z")
    assert svc.provision_for_selection(fake, "app-1").outcome == "REVOKED_BLOCKED"


def test_the_insert_payload_never_carries_client_identity_fields():
    # The J1 trigger derives student_id / industry_id / job_id from the
    # application. The service must send ONLY the application_id.
    fake = _fake(application={
        "id": "app-1", "job_id": "job-1", "opportunity_type": "JOB", "status": "SELECTED",
        "student_id": "student-EVIL", "industry_id": "industry-EVIL",
    })
    svc.provision_for_selection(fake, "app-1")
    assert fake.inserts[0][1] == {"application_id": "app-1"}
    assert "student_id" not in fake.inserts[0][1]
    assert "industry_id" not in fake.inserts[0][1]
    assert "job_id" not in fake.inserts[0][1]


def test_missing_application_raises_application_not_found():
    fake = _fake(application=None)
    try:
        svc.provision_for_selection(fake, "missing")
        raised = False
    except ApplicationNotFoundError:
        raised = True
    assert raised
    assert fake.inserts == []


def test_database_rejecting_a_well_formed_insert_42501_raises_provision_rejected():
    fake = _fake(insert_error=_api_error("42501"))
    try:
        svc.provision_for_selection(fake, "app-1")
        raised = False
    except ProvisionRejectedError:
        raised = True
    assert raised


def test_provisioning_never_writes_applications_or_job_program_tables():
    fake = _fake()
    svc.provision_for_selection(fake, "app-1")
    written = {t for t, _ in fake.inserts}
    assert written == {"job_training_enrollments"}


# ============================================================
# B. SELECTED transition integration (tests 15-21)
# ============================================================


def _app_row(**overrides):
    row = {
        "id": "app-1",
        "student_id": "student-7",
        "industry_id": "industry-1",
        "opportunity_type": "JOB",
        "internship_id": None,
        "job_id": "job-1",
        "status": "APPLIED",
        "cover_note": None,
        "match_score": None,
        "applied_at": "2026-09-01T00:00:00Z",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "opportunity": {"id": "job-1", "title": "Platform Engineer", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


def test_job_interview_scheduled_to_selected_provisions_job_training():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_app_row(status="INTERVIEW_SCHEDULED"), _app_row(status="SELECTED")],
        ),
        patch.object(job_training_service, "provision_for_selection") as job_provision,
        patch.object(internship_workspace_service, "provision_for_selection") as int_provision,
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    job_provision.assert_called_once_with(supabase, "app-1")
    int_provision.assert_not_called()


def test_job_entering_selected_from_an_earlier_pipeline_status_provisions():
    # whatever the prior status, ENTERING SELECTED provisions job training
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_app_row(status="SHORTLISTED"), _app_row(status="SELECTED")],
        ),
        patch.object(job_training_service, "provision_for_selection") as job_provision,
        patch.dict(
            application_service._STATUS_TRANSITIONS,
            {"SHORTLISTED": {"INTERVIEW_SCHEDULED", "SELECTED", "REJECTED"}},
        ),
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    job_provision.assert_called_once_with(supabase, "app-1")


def test_job_selected_to_selected_is_rejected_and_never_reprovisions():
    supabase = MagicMock()
    with (
        patch.object(application_service, "get_application", return_value=_app_row(status="SELECTED")),
        patch.object(job_training_service, "provision_for_selection") as job_provision,
    ):
        try:
            application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
            raised = False
        except application_service.InvalidStatusTransitionError:
            raised = True
    assert raised
    job_provision.assert_not_called()


def test_job_selected_without_a_program_still_succeeds_as_selected():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_app_row(status="INTERVIEW_SCHEDULED"), _app_row(status="SELECTED")],
        ),
        patch.object(
            job_training_service, "provision_for_selection",
            return_value=job_training_service.ProvisionResult(
                "SKIPPED_NO_PROGRAM", "no program", "app-1"
            ),
        ),
    ):
        result = application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    assert result["status"] == "SELECTED"


def test_job_selected_still_succeeds_when_job_provisioning_raises():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_app_row(status="INTERVIEW_SCHEDULED"), _app_row(status="SELECTED")],
        ),
        patch.object(
            job_training_service, "provision_for_selection",
            side_effect=RuntimeError("provisioning blew up"),
        ),
    ):
        result = application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    assert result["status"] == "SELECTED"


def test_internship_selected_still_uses_internship_workspace_only():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[
                _app_row(status="INTERVIEW_SCHEDULED", opportunity_type="INTERNSHIP",
                         job_id=None, internship_id="int-1"),
                _app_row(status="SELECTED", opportunity_type="INTERNSHIP",
                         job_id=None, internship_id="int-1"),
            ],
        ),
        patch.object(internship_workspace_service, "provision_for_selection") as int_provision,
        patch.object(job_training_service, "provision_for_selection") as job_provision,
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    int_provision.assert_called_once_with(supabase, "app-1")
    job_provision.assert_not_called()


def test_unrelated_status_transition_provisions_nothing():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_app_row(status="SHORTLISTED"), _app_row(status="INTERVIEW_SCHEDULED")],
        ),
        patch.object(internship_workspace_service, "provision_for_selection") as int_provision,
        patch.object(job_training_service, "provision_for_selection") as job_provision,
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "INTERVIEW_SCHEDULED")
    int_provision.assert_not_called()
    job_provision.assert_not_called()


def test_selected_transition_only_writes_the_status_field():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_app_row(status="INTERVIEW_SCHEDULED"), _app_row(status="SELECTED")],
        ),
        patch.object(job_training_service, "provision_for_selection"),
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "SELECTED"}


# ------------------------------------------------------------
# J3 review hardening: EXACTLY ONE guarded provisioning branch.
# The SELECTED hook must never invoke internship provisioning
# unconditionally -- the two systems are mutually exclusive per
# opportunity_type.
# ------------------------------------------------------------


def _internship_app(status: str) -> dict:
    return _app_row(status=status, opportunity_type="INTERNSHIP", job_id=None,
                    internship_id="int-1")


def test_job_selected_calls_job_training_exactly_once_and_never_internship():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_app_row(status="INTERVIEW_SCHEDULED"), _app_row(status="SELECTED")],
        ),
        patch.object(job_training_service, "provision_for_selection") as job_p,
        patch.object(internship_workspace_service, "provision_for_selection") as int_p,
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    assert job_p.call_count == 1
    job_p.assert_called_once_with(supabase, "app-1")
    assert int_p.call_count == 0


def test_internship_selected_calls_internship_exactly_once_and_never_job_training():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_internship_app("INTERVIEW_SCHEDULED"), _internship_app("SELECTED")],
        ),
        patch.object(job_training_service, "provision_for_selection") as job_p,
        patch.object(internship_workspace_service, "provision_for_selection") as int_p,
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "SELECTED")
    assert int_p.call_count == 1
    int_p.assert_called_once_with(supabase, "app-1")
    assert job_p.call_count == 0


def test_non_selected_internship_transition_provisions_neither():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_internship_app("SHORTLISTED"), _internship_app("INTERVIEW_SCHEDULED")],
        ),
        patch.object(job_training_service, "provision_for_selection") as job_p,
        patch.object(internship_workspace_service, "provision_for_selection") as int_p,
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "INTERVIEW_SCHEDULED")
    job_p.assert_not_called()
    int_p.assert_not_called()


def test_non_selected_job_transition_provisions_neither():
    supabase = MagicMock()
    with (
        patch.object(
            application_service, "get_application",
            side_effect=[_app_row(status="SHORTLISTED"), _app_row(status="INTERVIEW_SCHEDULED")],
        ),
        patch.object(job_training_service, "provision_for_selection") as job_p,
        patch.object(internship_workspace_service, "provision_for_selection") as int_p,
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "INTERVIEW_SCHEDULED")
    job_p.assert_not_called()
    int_p.assert_not_called()


def test_source_has_exactly_one_guarded_call_per_provisioning_service():
    """No unconditional internship_workspace_service.provision_for_selection
    remains anywhere in application_service: there is exactly one call to
    each provisioning service in the module, and the SELECTED hook
    dispatches to each under its own opportunity_type guard (internship
    branch before job branch)."""
    import inspect

    src = inspect.getsource(application_service)
    assert src.count("internship_workspace_service.provision_for_selection(") == 1
    assert src.count("job_training_service.provision_for_selection(") == 1

    # The SELECTED hook branches on opportunity_type: internship provisioning
    # dispatched first, job provisioning second. The single call to each
    # provisioning service lives in its dispatched helper (wrapped so a
    # provisioning failure never fails the status change).
    hook = src.split('if target_status == "SELECTED":', 1)[1].split("\n\n", 1)[0]
    int_guard = hook.index('if opportunity_type == "INTERNSHIP":')
    int_dispatch = hook.index("_provision_internship_workspace(")
    job_guard = hook.index('elif opportunity_type == "JOB":')
    job_dispatch = hook.index("_provision_job_training(")
    assert int_guard < int_dispatch < job_guard < job_dispatch

    int_helper = src.split("def _provision_internship_workspace(", 1)[1].split("\ndef ", 1)[0]
    job_helper = src.split("def _provision_job_training(", 1)[1].split("\ndef ", 1)[0]
    assert "internship_workspace_service.provision_for_selection(" in int_helper
    assert "job_training_service.provision_for_selection(" in job_helper
    # each provisioning call is wrapped so it cannot fail the transition
    assert "try:" in int_helper and "except" in int_helper
    assert "try:" in job_helper and "except" in job_helper


# ============================================================
# F. self-heal endpoint (industry-side, mirrors /provision-workspace)
# ============================================================

_HEAL_URL = f"/api/v1/applications/{uuid4()}/provision-job-training"


def _heal_app(**over):
    row = {
        "id": "app-1", "student_id": "student-7", "industry_id": "industry-1",
        "opportunity_type": "JOB", "internship_id": None, "job_id": "job-1",
        "status": "SELECTED", "cover_note": None, "match_score": None,
        "applied_at": None, "created_at": None, "updated_at": None,
        "opportunity": {"id": "job-1", "title": "Platform Engineer", "status": "PUBLISHED"},
    }
    row.update(over)
    return row


def test_heal_endpoint_returns_the_created_outcome():
    result = job_training_service.ProvisionResult(
        "CREATED", "Job training enrollment provisioned.", "app-1", enrollment=_enr_row()
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_application", return_value=_heal_app()),
        patch.object(job_training_service, "provision_for_selection", return_value=result),
    ):
        resp = client.post(_HEAL_URL, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "CREATED"
    assert body["enrollment"]["id"] == "enr-1"


def test_heal_endpoint_is_idempotent_reports_already_exists():
    result = job_training_service.ProvisionResult(
        "ALREADY_EXISTS", "already", "app-1", enrollment=_enr_row()
    )
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_application", return_value=_heal_app()),
        patch.object(job_training_service, "provision_for_selection", return_value=result),
    ):
        resp = client.post(_HEAL_URL, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "ALREADY_EXISTS"


def test_heal_endpoint_404_when_application_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "get_application", return_value=None),
        patch.object(job_training_service, "provision_for_selection") as provision,
    ):
        resp = client.post(_HEAL_URL, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 404
    provision.assert_not_called()


def test_heal_endpoint_maps_provision_rejected_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "get_application", return_value=_heal_app()),
        patch.object(
            job_training_service, "provision_for_selection",
            side_effect=ProvisionRejectedError("state changed"),
        ),
    ):
        resp = client.post(_HEAL_URL, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 409


def test_heal_endpoint_reports_a_skipped_outcome_without_error():
    for outcome in ("SKIPPED_NOT_JOB", "SKIPPED_NOT_SELECTED", "SKIPPED_NO_PROGRAM",
                    "REVOKED_BLOCKED"):
        result = job_training_service.ProvisionResult(outcome, "n/a", "app-1")
        with (
            authenticated_as("INDUSTRY"),
            patch.object(application_service, "get_application", return_value=_heal_app()),
            patch.object(job_training_service, "provision_for_selection", return_value=result),
        ):
            resp = client.post(_HEAL_URL, headers={"Authorization": "Bearer t"})
        assert resp.status_code == 200, outcome
        assert resp.json()["outcome"] == outcome
        assert resp.json()["enrollment"] is None


def test_heal_endpoint_rejects_a_student_caller():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.post(_HEAL_URL, headers={"Authorization": "Bearer t"})
        assert resp.status_code == 403, role


def test_heal_endpoint_rejects_unauthenticated():
    assert client.post(_HEAL_URL).status_code == 401


def test_heal_endpoint_end_to_end_refuses_an_internship_application():
    # the real service (fake DB) -- an internship application the industry
    # owns comes back SKIPPED_NOT_JOB, never an enrollment.
    fake = _FakeSupabase(application={
        "id": "app-1", "job_id": None, "opportunity_type": "INTERNSHIP", "status": "SELECTED",
    })
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_application", return_value=_heal_app(
            opportunity_type="INTERNSHIP", job_id=None, internship_id="int-1")),
        patch("app.api.applications.build_user_client", return_value=fake),
    ):
        resp = client.post(_HEAL_URL, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "SKIPPED_NOT_JOB"
    assert fake.inserts == []


# ============================================================
# G. backfill script -- shape only (never executed against a DB here)
# ============================================================


class _BackfillFake:
    def table(self, name):
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


def test_backfill_script_is_dry_run_by_default_and_reuses_the_service():
    from scripts import backfill_job_training_enrollments as backfill

    src = __import__("inspect").getsource(backfill)
    assert "job_training_service.provision_for_selection" in src
    assert "--apply" in src
    assert 'eq("opportunity_type", "JOB")' in src
    assert 'eq("status", "SELECTED")' in src
    # not importable from / callable by the app or a migration
    assert "backfill" not in __import__("app.main", fromlist=["app"]).__dict__

    with patch.object(backfill, "get_supabase", return_value=_BackfillFake()):
        assert backfill.run(apply=False) == 0
