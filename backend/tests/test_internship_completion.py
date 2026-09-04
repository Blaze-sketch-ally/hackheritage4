"""Phase 7 -- internship completion + certificate.

Three surfaces:

* INDUSTRY   GET/POST /api/v1/internship-workspaces/{id}/completion[/verify]
             -- read-only summary, and the explicit verification action.
* STUDENT    GET /api/v1/student/internship-workspaces/{id}/completion
             -- read-only summary of their own workspace.
* PUBLIC     GET /api/v1/certificates/verify/{certificate_number}
             -- no auth, calls ONLY public.verify_internship_certificate.

"Requirements met" is always computed live from program_assignments
(is_required + is_published) and workspace_submissions (an ACCEPTED
attempt) -- never a stored percentage. Verification persists exactly one
internship_completions row (PASS) and exactly one internship_certificates
row per workspace, both append-only / idempotent via read-back-on-23505.
This suite verifies the Python layer's half: correct requirement
computation, ownership boundaries, idempotency, snapshot immutability,
the public verifier's safe field set, and every documented phase
boundary.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.api import certificates as certificates_api
from app.api import internship_workspaces as industry_api
from app.main import app
from app.services import internship_workspace_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_WID = "11111111-1111-1111-1111-111111111111"
_IID = "22222222-2222-2222-2222-222222222222"
_SID = "33333333-3333-3333-3333-333333333333"
_A1 = "44444444-4444-4444-4444-444444444444"
_A2 = "55555555-5555-5555-5555-555555555555"


# ============================================================
# fake Supabase client
# ============================================================


class _Q:
    def __init__(self, fake, table):
        self.fake, self.table = fake, table
        self._select = "*"
        self._filters: list[tuple] = []
        self._single = False
        self._op = "select"
        self._payload = None

    def select(self, s="*", *a, **k):
        self._select = s
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        self.fake.filters.append((self.table, field, value))
        return self

    def order(self, *a, **k):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def _match(self, row):
        return all(row.get(f) == v for f, v in self._filters)

    def _embed(self, row):
        row = dict(row)
        if "skill:skills(" in self._select:
            skill = next((s for s in self.fake.rows("skills") if s["id"] == row.get("skill_id")), None)
            row["skill"] = {"name": skill["name"]} if skill else None
        return row

    def execute(self):
        return self.fake._exec(self)


class _RpcQ:
    def __init__(self, fake, name, params):
        self.fake, self.name, self.params = fake, name, params

    def execute(self):
        if self.name == "application_applicant_names":
            ids = (self.params or {}).get("application_ids", [])
            return SimpleNamespace(
                data=[
                    {"application_id": i, "student_name": self.fake.applicant_names[i]}
                    for i in ids
                    if i in self.fake.applicant_names
                ]
            )
        raise AssertionError(f"unexpected rpc {self.name!r}")


class _Fake:
    def __init__(self, **tables):
        self.tables: dict[str, list] = {k: list(v) for k, v in tables.items()}
        self.filters: list[tuple] = []
        self.inserts: list[tuple] = []
        self.updates: list[tuple] = []
        self.insert_errors: dict[str, Exception] = {}
        self.applicant_names: dict[str, str] = {}

    def rows(self, table):
        return self.tables.setdefault(table, [])

    def table(self, name):
        return _Q(self, name)

    def rpc(self, name, params=None):
        return _RpcQ(self, name, params)

    def _exec(self, q: _Q):
        if q._op == "insert":
            self.inserts.append((q.table, dict(q._payload)))
            err = self.insert_errors.get(q.table)
            if err is not None:
                raise err
            row = dict(q._payload)
            row.setdefault("id", f"{q.table[:4]}-{len(self.rows(q.table)) + 1}")
            row.setdefault("created_at", "2026-09-10T00:00:00Z")
            row.setdefault("issued_at", "2026-09-10T00:00:00Z")
            if q.table == "internship_completions":
                row.setdefault("verified_by", "industry-1")
                row.setdefault("verified_at", "2026-09-10T00:00:00Z")
            if q.table == "internship_certificates":
                row.setdefault(
                    "certificate_number",
                    f"AIC-INT-2026-{'A' * 12}{len(self.rows(q.table))}",
                )
            self.rows(q.table).append(row)
            return SimpleNamespace(data=[row])
        if q._op == "update":
            self.updates.append((q.table, dict(q._payload)))
            for row in self.rows(q.table):
                if q._match(row):
                    row.update(q._payload)
            return SimpleNamespace(data=[])
        rows = [r for r in self.rows(q.table) if q._match(r)]
        rows = [q._embed(r) for r in rows]
        if q._single:
            return SimpleNamespace(data=rows[0] if rows else None)
        return SimpleNamespace(data=rows)


# ---- row builders ----


def _ws(**over):
    row = {
        "id": _WID,
        "application_id": "app-1",
        "internship_id": _IID,
        "student_id": _SID,
        "industry_id": "industry-1",
        "work_mode": "REMOTE",
        "workspace_status": "IN_PROGRESS",
        "accepted_at": "2026-09-01T00:00:00Z",
        "started_at": None,
        "completed_at": None,
        "declined_at": None,
        "decline_reason": None,
        "rescinded_at": None,
        "rescind_reason": None,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
    }
    row.update(over)
    return row


def _assignment(id_, title, *, required=True, published=True, program_id="prog-1"):
    return {
        "id": id_,
        "title": title,
        "program_id": program_id,
        "is_required": required,
        "is_published": published,
    }


def _sub(assignment_id, status, **over):
    row = {"workspace_id": _WID, "assignment_id": assignment_id, "submission_status": status}
    row.update(over)
    return row


def _completion(**over):
    row = {
        "id": "comp-1",
        "workspace_id": _WID,
        "verified_by": "industry-1",
        "completion_status": "COMPLETED",
        "outcome": "PASS",
        "summary": None,
        "verified_at": "2026-09-10T00:00:00Z",
        "created_at": "2026-09-10T00:00:00Z",
        "updated_at": "2026-09-10T00:00:00Z",
    }
    row.update(over)
    return row


def _certificate(**over):
    row = {
        "id": "cert-1",
        "completion_id": "comp-1",
        "workspace_id": _WID,
        "student_id": _SID,
        "industry_id": "industry-1",
        "internship_id": _IID,
        "certificate_number": "AIC-INT-2026-AAAAAAAAAAAAA",
        "details": {"student_name": "Asha Rao", "company_name": "TechNova", "title": "ML Intern", "skills": []},
        "issued_at": "2026-09-10T00:00:00Z",
        "pdf_url": None,
        "revoked_at": None,
        "revoke_reason": None,
    }
    row.update(over)
    return row


def _db(
    *,
    workspace=None,
    assignments=None,
    submissions=None,
    completions=None,
    certificates=None,
    program=True,
    program_skills=None,
):
    return _Fake(
        internship_workspaces=[workspace or _ws()],
        internship_programs=[{"id": "prog-1", "internship_id": _IID}] if program else [],
        program_assignments=assignments or [],
        workspace_submissions=submissions or [],
        internship_completions=completions or [],
        internship_certificates=certificates or [],
        industry_profiles=[{"id": "industry-1", "company_name": "TechNova"}],
        internships=[{"id": _IID, "title": "ML Intern"}],
        program_skills=program_skills or [],
        skills=[{"id": "sk-py", "name": "Python"}],
    )


# ============================================================
# completion calculation (service)
# ============================================================


def test_all_required_accepted_means_requirements_met():
    fake = _db(
        assignments=[_assignment(_A1, "Project"), _assignment(_A2, "Deploy")],
        submissions=[_sub(_A1, "ACCEPTED"), _sub(_A2, "ACCEPTED")],
    )
    summary = svc.get_industry_completion(fake, "industry-1", _WID)
    assert summary["requirements_met"] is True
    assert summary["required_count"] == 2
    assert summary["completed_count"] == 2
    assert summary["outstanding"] == []


def test_missing_required_assignment_blocks_completion():
    fake = _db(
        assignments=[_assignment(_A1, "Project"), _assignment(_A2, "Deploy")],
        submissions=[_sub(_A1, "ACCEPTED")],
    )
    summary = svc.get_industry_completion(fake, "industry-1", _WID)
    assert summary["requirements_met"] is False
    assert [o["title"] for o in summary["outstanding"]] == ["Deploy"]


@pytest.mark.parametrize("status", ["SUBMITTED", "UNDER_REVIEW", "REVISION_REQUESTED", "REJECTED"])
def test_a_non_accepted_status_never_satisfies_a_requirement(status):
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, status)])
    summary = svc.get_industry_completion(fake, "industry-1", _WID)
    assert summary["requirements_met"] is False
    assert summary["completed_count"] == 0


def test_optional_assignment_missing_does_not_block_completion():
    fake = _db(
        assignments=[
            _assignment(_A1, "Required task"),
            _assignment(_A2, "Optional task", required=False),
        ],
        submissions=[_sub(_A1, "ACCEPTED")],  # optional task never submitted
    )
    summary = svc.get_industry_completion(fake, "industry-1", _WID)
    assert summary["requirements_met"] is True
    assert summary["required_count"] == 1  # the optional one is not even counted


def test_unpublished_required_assignment_does_not_block_completion():
    # invisible to the student (same rule as the student-facing assignment
    # list) -- so it can never gate completion either.
    fake = _db(
        assignments=[_assignment(_A1, "Draft task", published=False)],
        submissions=[],
    )
    summary = svc.get_industry_completion(fake, "industry-1", _WID)
    assert summary["requirements_met"] is True
    assert summary["required_count"] == 0


def test_no_required_assignments_is_vacuously_met():
    fake = _db(assignments=[], submissions=[])
    summary = svc.get_industry_completion(fake, "industry-1", _WID)
    assert summary["requirements_met"] is True
    assert summary["required_count"] == 0 and summary["completed_count"] == 0


def test_no_program_at_all_is_vacuously_met():
    fake = _db(program=False, assignments=[], submissions=[])
    summary = svc.get_industry_completion(fake, "industry-1", _WID)
    assert summary["requirements_met"] is True


def test_required_skills_are_not_a_separate_completion_gate():
    """program_skills (REQUIRED/OPTIONAL) has no independent verification
    signal anywhere in the schema -- 039's own docs say an internship
    workspace never reads/writes student_skills. So Phase 7 does not
    invent a second required-skill gate: completion is driven solely by
    program_assignments.is_required (037), exactly as sections 4 and 6 of
    the brief require. A REQUIRED program skill with no accepted work
    against it does not block completion."""
    fake = _db(
        assignments=[_assignment(_A1, "Project")],
        submissions=[_sub(_A1, "ACCEPTED")],
        program_skills=[{"skill_id": "sk-py", "requirement": "REQUIRED", "skill": None}],
    )
    summary = svc.get_industry_completion(fake, "industry-1", _WID)
    assert summary["requirements_met"] is True
    # program_skills is never queried for the summary/gate -- only for the
    # certificate snapshot, and only once verification actually succeeds.
    assert not any(t == "program_skills" for t, *_ in fake.filters)


def test_module_items_never_gate_completion():
    # module_items has no is_required column in the schema (037) -- content
    # is informational only. Confirm the service never even queries it.
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, "ACCEPTED")])
    svc.get_industry_completion(fake, "industry-1", _WID)
    assert "module_items" not in fake.tables or not any(
        t == "module_items" for t, *_ in fake.filters
    )


# ============================================================
# ownership / not-found (service)
# ============================================================


def test_industry_completion_summary_404s_for_a_foreign_workspace():
    fake = _db()
    assert svc.get_industry_completion(fake, "industry-999", _WID) is None


def test_student_completion_summary_is_scoped_to_the_caller():
    fake = _db()
    assert svc.get_student_completion(fake, "student-999", _WID) is None


def test_another_company_cannot_verify_this_workspace():
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, "ACCEPTED")])
    with pytest.raises(svc.WorkspaceNotFoundError):
        svc.verify_workspace_completion(fake, "industry-999", _WID)
    assert fake.inserts == []


# ============================================================
# verification (service)
# ============================================================


def test_verification_fails_with_outstanding_requirements():
    fake = _db(
        assignments=[_assignment(_A1, "Project"), _assignment(_A2, "Deploy")],
        submissions=[_sub(_A1, "ACCEPTED")],
    )
    with pytest.raises(svc.RequirementsNotMetError) as ei:
        svc.verify_workspace_completion(fake, "industry-1", _WID)
    assert [o["title"] for o in ei.value.outstanding] == ["Deploy"]
    assert fake.inserts == []  # nothing persisted on failure


@pytest.mark.parametrize("state", ["PENDING_ACCEPTANCE", "DECLINED", "RESCINDED"])
def test_verification_rejects_an_invalid_workspace_state(state):
    fake = _db(workspace=_ws(workspace_status=state))
    with pytest.raises(svc.InvalidWorkspaceStateError):
        svc.verify_workspace_completion(fake, "industry-1", _WID)
    assert fake.inserts == []


def test_successful_verification_persists_completion_and_certificate():
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, "ACCEPTED")])
    summary = svc.verify_workspace_completion(fake, "industry-1", _WID, "Great work overall.")

    assert summary["industry_verified"] is True
    assert summary["result"] == "PASS"
    assert summary["certificate"] is not None

    comp_insert = next(p for t, p in fake.inserts if t == "internship_completions")
    assert comp_insert == {
        "workspace_id": _WID,
        "completion_status": "COMPLETED",
        "outcome": "PASS",
        "summary": "Great work overall.",
    }
    cert_insert = next(p for t, p in fake.inserts if t == "internship_certificates")
    assert cert_insert["completion_id"] == fake.tables["internship_completions"][0]["id"]
    assert "certificate_number" not in cert_insert  # server-generated only


def test_verification_moves_the_workspace_to_completed():
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, "ACCEPTED")])
    svc.verify_workspace_completion(fake, "industry-1", _WID)
    written = next(p for t, p in fake.updates if t == "internship_workspaces")
    assert written["workspace_status"] == "COMPLETED"
    assert "completed_at" in written
    assert fake.tables["internship_workspaces"][0]["workspace_status"] == "COMPLETED"


def test_verification_never_accepts_reviewer_or_identity_fields_from_the_payload():
    # the service signature itself takes no student_id/industry_id/outcome/
    # certificate_number -- industry_id is a parameter derived from the
    # authenticated caller, never from a request body field.
    import inspect

    sig = inspect.signature(svc.verify_workspace_completion)
    assert list(sig.parameters) == ["client", "industry_id", "workspace_id", "summary"]


# ============================================================
# certificate: idempotency + uniqueness (service)
# ============================================================


def test_repeated_verify_returns_the_same_certificate_without_reinserting():
    completion = _completion()
    certificate = _certificate()
    fake = _db(
        assignments=[_assignment(_A1, "Project")],
        submissions=[_sub(_A1, "ACCEPTED")],
        completions=[completion],
        certificates=[certificate],
        workspace=_ws(workspace_status="COMPLETED"),
    )
    summary = svc.verify_workspace_completion(fake, "industry-1", _WID)
    assert summary["certificate"]["certificate_number"] == certificate["certificate_number"]
    assert fake.inserts == []  # no new completion, no new certificate


def test_concurrent_verify_cannot_create_a_duplicate_completion():
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, "ACCEPTED")])
    # simulate another request's INSERT winning the race first
    fake.insert_errors["internship_completions"] = APIError({"code": "23505", "message": "unique"})
    fake.tables["internship_completions"] = [_completion()]  # the winner's row

    summary = svc.verify_workspace_completion(fake, "industry-1", _WID)
    assert summary["industry_verified"] is True
    # exactly one completion row exists -- the loser never created a second
    assert len(fake.tables["internship_completions"]) == 1


def test_concurrent_verify_cannot_create_a_duplicate_certificate():
    fake = _db(
        assignments=[_assignment(_A1, "Project")],
        submissions=[_sub(_A1, "ACCEPTED")],
        completions=[],  # forces this call down the create path
    )
    fake.insert_errors["internship_certificates"] = APIError({"code": "23505", "message": "unique"})

    # After the completion insert succeeds, seed the "winner's" certificate
    # so the loser's read-back finds it instead of raising.
    def _after_completion_insert(orig):
        def wrapped(*a, **k):
            r = orig(*a, **k)
            if fake.tables.get("internship_completions") and not fake.tables.get("internship_certificates"):
                fake.tables["internship_certificates"] = [
                    {**_certificate(), "completion_id": fake.tables["internship_completions"][0]["id"]}
                ]
            return r
        return wrapped

    fake._exec = _after_completion_insert(fake._exec)
    summary = svc.verify_workspace_completion(fake, "industry-1", _WID)
    assert summary["certificate"] is not None
    assert len(fake.tables["internship_certificates"]) == 1


def test_certificate_number_is_never_client_supplied_and_looks_server_generated():
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, "ACCEPTED")])
    summary = svc.verify_workspace_completion(fake, "industry-1", _WID)
    number = summary["certificate"]["certificate_number"]
    assert number.startswith("AIC-INT-2026-")
    cert_insert = next(p for t, p in fake.inserts if t == "internship_certificates")
    assert "certificate_number" not in cert_insert


# ============================================================
# certificate snapshot: content + immutability
# ============================================================


def test_certificate_snapshot_contains_student_company_title_and_skills():
    fake = _db(
        assignments=[_assignment(_A1, "Project")],
        submissions=[_sub(_A1, "ACCEPTED")],
        program_skills=[{"skill_id": "sk-py", "requirement": "REQUIRED", "program_id": "prog-1"}],
    )
    fake.applicant_names = {"app-1": "Asha Rao"}
    svc.verify_workspace_completion(fake, "industry-1", _WID)
    cert_insert = next(p for t, p in fake.inserts if t == "internship_certificates")
    details = cert_insert["details"]
    assert details["student_name"] == "Asha Rao"
    assert details["company_name"] == "TechNova"
    assert details["title"] == "ML Intern"
    assert details["skills"] == [{"skill_id": "sk-py", "skill_name": "Python"}]


def test_certificate_snapshot_is_frozen_after_issuance():
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, "ACCEPTED")])
    fake.applicant_names = {"app-1": "Asha Rao"}
    svc.verify_workspace_completion(fake, "industry-1", _WID)

    # the underlying source data changes AFTER issuance
    fake.tables["industry_profiles"][0]["company_name"] = "TechNova Renamed Inc."
    fake.tables["internships"][0]["title"] = "Renamed Internship"
    fake.applicant_names["app-1"] = "Asha Rao-Changed"

    # re-reading the certificate must still show the ORIGINAL snapshot
    reread = svc.get_industry_completion(fake, "industry-1", _WID)
    assert reread["certificate"]["company_name"] == "TechNova"
    assert reread["certificate"]["internship_title"] == "ML Intern"
    assert reread["certificate"]["student_name"] == "Asha Rao"


def test_a_verified_workspaces_requirements_stay_frozen_after_a_later_program_edit():
    """Phase 9 regression: the certificate/completion are already frozen
    (see test above), but the READ-side requirements summary used to
    recompute `outstanding` live against the CURRENT program every time --
    so adding a new required assignment to an already-certified
    workspace's program made the summary contradict its own certificate
    ("Outstanding: ..." next to "Completed -- Certificate issued"). Once
    verified, the requirements section must stay reported as fully
    satisfied regardless of what the program looks like now."""
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, "ACCEPTED")])
    svc.verify_workspace_completion(fake, "industry-1", _WID)

    # the industry adds a NEW required, published assignment to the SAME
    # program AFTER this workspace was already certified.
    fake.tables["program_assignments"].append(_assignment(_A2, "New Deliverable"))

    for reread in (
        svc.get_industry_completion(fake, "industry-1", _WID),
        svc.get_student_completion(fake, _SID, _WID),
    ):
        assert reread["industry_verified"] is True
        assert reread["certificate"] is not None
        assert reread["requirements_met"] is True
        assert reread["outstanding"] == []
        assert reread["completed_count"] == reread["required_count"]

    # a repeat verify call must show the same frozen, internally
    # consistent picture -- not raise RequirementsNotMetError.
    repeat = svc.verify_workspace_completion(fake, "industry-1", _WID)
    assert repeat["outstanding"] == []
    assert repeat["requirements_met"] is True


# ============================================================
# student visibility
# ============================================================


def test_student_can_see_their_own_completion_and_certificate():
    fake = _db(
        assignments=[_assignment(_A1, "Project")],
        submissions=[_sub(_A1, "ACCEPTED")],
        completions=[_completion()],
        certificates=[_certificate()],
    )
    summary = svc.get_student_completion(fake, _SID, _WID)
    assert summary["industry_verified"] is True
    assert summary["certificate"]["certificate_number"] == "AIC-INT-2026-AAAAAAAAAAAAA"


def test_student_pending_verification_shows_no_certificate():
    fake = _db(assignments=[_assignment(_A1, "Project")], submissions=[_sub(_A1, "ACCEPTED")])
    summary = svc.get_student_completion(fake, _SID, _WID)
    assert summary["requirements_met"] is True
    assert summary["industry_verified"] is False
    assert summary["certificate"] is None


# ============================================================
# routes -- auth guards
# ============================================================

_INDUSTRY_ENDPOINTS = [
    ("get", f"/api/v1/internship-workspaces/{_WID}/completion"),
    ("post", f"/api/v1/internship-workspaces/{_WID}/completion/verify"),
]
_STUDENT_ENDPOINT = ("get", f"/api/v1/student/internship-workspaces/{_WID}/completion")


def _call(method, url, **kw):
    body = {} if method == "post" else None
    return client.post(url, json=body, **kw) if method == "post" else client.get(url, **kw)


def test_industry_completion_endpoints_reject_unauthenticated():
    for method, url in _INDUSTRY_ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_industry_completion_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in _INDUSTRY_ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer t"})
            assert resp.status_code == 403, (role, method, url)


def test_student_completion_endpoint_rejects_unauthenticated():
    assert client.get(_STUDENT_ENDPOINT[1]).status_code == 401


def test_student_completion_endpoint_forbids_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(_STUDENT_ENDPOINT[1], headers={"Authorization": "Bearer t"})
        assert resp.status_code == 403, role


# ============================================================
# routes -- behaviour + error mapping
# ============================================================


def _summary_stub(**over):
    row = {
        "workspace_id": _WID,
        "required_count": 1,
        "completed_count": 1,
        "requirements_met": True,
        "outstanding": [],
        "industry_verified": True,
        "result": "PASS",
        "verified_at": "2026-09-10T00:00:00Z",
        "certificate": {
            "certificate_number": "AIC-INT-2026-AAAAAAAAAAAAA",
            "student_name": "Asha Rao",
            "company_name": "TechNova",
            "internship_title": "ML Intern",
            "issued_at": "2026-09-10T00:00:00Z",
            "skills": [],
            "revoked": False,
        },
        "_newly_verified": False,
        "_student_id": _SID,
    }
    row.update(over)
    return row


def test_verify_endpoint_rejects_unknown_fields():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        resp = client.post(
            f"/api/v1/internship-workspaces/{_WID}/completion/verify",
            json={"summary": "ok", "outcome": "PASS"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422


def test_verify_endpoint_maps_service_errors():
    cases = [
        (svc.WorkspaceNotFoundError("x"), 404),
        (svc.InvalidWorkspaceStateError("DECLINED"), 409),
        (svc.RequirementsNotMetError([{"kind": "ASSIGNMENT", "id": "a", "title": "Final Project"}]), 409),
    ]
    for exc, expected in cases:
        with (
            authenticated_as("INDUSTRY", user_id="industry-1"),
            patch.object(svc, "verify_workspace_completion", side_effect=exc),
        ):
            resp = client.post(
                f"/api/v1/internship-workspaces/{_WID}/completion/verify",
                json={},
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == expected, exc


def test_completion_endpoint_404s_when_service_returns_none():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "get_industry_completion", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/internship-workspaces/{_WID}/completion", headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 404


def test_successful_verify_returns_the_certificate_and_drops_internal_fields():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "verify_workspace_completion", return_value=_summary_stub(_newly_verified=True)),
        patch.object(industry_api.notification_producer, "emit_internship_completed"),
    ):
        resp = client.post(
            f"/api/v1/internship-workspaces/{_WID}/completion/verify",
            json={},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["certificate"]["certificate_number"] == "AIC-INT-2026-AAAAAAAAAAAAA"
    assert "_newly_verified" not in body and "_student_id" not in body


# ============================================================
# notification behaviour
# ============================================================


def test_a_first_time_verification_emits_exactly_one_notification():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "verify_workspace_completion", return_value=_summary_stub(_newly_verified=True)),
        patch.object(industry_api.notification_producer, "emit_internship_completed") as notify,
    ):
        client.post(
            f"/api/v1/internship-workspaces/{_WID}/completion/verify",
            json={},
            headers={"Authorization": "Bearer t"},
        )
    notify.assert_called_once_with(
        student_id=_SID,
        workspace_id=_WID,
        internship_title="ML Intern",
        certificate_number="AIC-INT-2026-AAAAAAAAAAAAA",
    )


def test_a_repeated_idempotent_verification_does_not_re_notify():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "verify_workspace_completion", return_value=_summary_stub(_newly_verified=False)),
        patch.object(industry_api.notification_producer, "emit_internship_completed") as notify,
    ):
        client.post(
            f"/api/v1/internship-workspaces/{_WID}/completion/verify",
            json={},
            headers={"Authorization": "Bearer t"},
        )
    notify.assert_not_called()


def test_notification_producer_writes_one_internship_workspace_row():
    from unittest.mock import MagicMock

    from app.services import notification_producer

    fake_sb = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake_sb):
        notification_producer.emit_internship_completed(
            student_id=_SID, workspace_id=_WID, internship_title="ML Intern",
            certificate_number="AIC-INT-2026-AAAAAAAAAAAAA",
        )
    row = fake_sb.table.return_value.insert.call_args[0][0]
    assert row["type"] == "INTERNSHIP"
    assert row["related_entity_type"] == "INTERNSHIP_WORKSPACE"
    assert row["related_entity_id"] == _WID


def test_notification_producer_swallows_its_own_errors():
    from unittest.mock import MagicMock

    from app.services import notification_producer

    fake_sb = MagicMock()
    fake_sb.table.side_effect = RuntimeError("db down")
    with patch.object(notification_producer, "get_supabase", return_value=fake_sb):
        notification_producer.emit_internship_completed(
            student_id=_SID, workspace_id=_WID, internship_title=None, certificate_number=None,
        )  # must not raise


# ============================================================
# public certificate verification
# ============================================================


class _AnonRpcQ:
    def __init__(self, rows):
        self._rows = rows

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _AnonClient:
    def __init__(self, rows):
        self._rows = rows

    def rpc(self, name, params):
        assert name == "verify_internship_certificate"
        assert set(params) == {"p_number"}
        return _AnonRpcQ(self._rows)


def _anon_client(rows):
    return _AnonClient(rows)


def test_public_verification_returns_only_the_safe_fields():
    rows = [
        {
            "certificate_number": "AIC-INT-2026-AAAAAAAAAAAAA",
            "student_name": "Asha Rao",
            "company_name": "TechNova",
            "title": "ML Intern",
            "issued_at": "2026-09-10T00:00:00Z",
            "status": "VALID",
        }
    ]
    with patch.object(certificates_api, "build_anon_client", return_value=_anon_client(rows)):
        resp = client.get("/api/v1/certificates/verify/AIC-INT-2026-AAAAAAAAAAAAA")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"certificate_number", "student_name", "company_name", "title", "issued_at", "status"}
    assert "email" not in body and "id" not in body and "workspace_id" not in body


def test_public_verification_requires_no_auth_header():
    with patch.object(certificates_api, "build_anon_client", return_value=_anon_client([])):
        resp = client.get("/api/v1/certificates/verify/AIC-INT-2026-AAAAAAAAAAAAA")
    assert resp.status_code == 404  # reached the handler, not blocked by auth


def test_invalid_certificate_number_is_404():
    with patch.object(certificates_api, "build_anon_client", return_value=_anon_client([])):
        resp = client.get("/api/v1/certificates/verify/AIC-INT-2026-ZZZZZZZZZZZZZ")
    assert resp.status_code == 404


def test_malformed_certificate_number_is_422_and_never_calls_the_db():
    with patch.object(certificates_api, "build_anon_client") as build:
        resp = client.get("/api/v1/certificates/verify/not-a-real-number")
    assert resp.status_code == 422
    build.assert_not_called()


def test_revoked_certificate_reports_revoked_status():
    rows = [
        {
            "certificate_number": "AIC-INT-2026-AAAAAAAAAAAAA",
            "student_name": "Asha Rao",
            "company_name": "TechNova",
            "title": "ML Intern",
            "issued_at": "2026-09-10T00:00:00Z",
            "status": "REVOKED",
        }
    ]
    with patch.object(certificates_api, "build_anon_client", return_value=_anon_client(rows)):
        resp = client.get("/api/v1/certificates/verify/AIC-INT-2026-AAAAAAAAAAAAA")
    assert resp.json()["status"] == "REVOKED"


# ============================================================
# isolation
# ============================================================


def test_student_a_cannot_read_student_bs_completion():
    fake = _db(
        assignments=[_assignment(_A1, "Project")],
        submissions=[_sub(_A1, "ACCEPTED")],
        completions=[_completion()],
        certificates=[_certificate()],
    )
    assert svc.get_student_completion(fake, "student-B-not-owner", _WID) is None


# ============================================================
# phase boundary (source inspection)
# ============================================================


_COMPLETION_FUNCTIONS = (
    "verify_workspace_completion",
    "_get_or_create_completion",
    "_get_or_create_certificate",
    "get_industry_completion",
    "get_student_completion",
    "_compute_requirements",
    "_required_assignments",
    "_accepted_assignment_ids",
    "_build_certificate_snapshot",
    "_required_program_skills",
)


def _completion_source() -> str:
    import inspect

    return "".join(inspect.getsource(getattr(svc, name)) for name in _COMPLETION_FUNCTIONS)


def test_completion_service_never_touches_applications_program_publication_or_stipend():
    completion_src = _completion_source()
    assert '.table("applications")' not in completion_src
    assert '.table("stipend_disbursements")' not in completion_src
    # program publication (internship_programs.status) is only ever moved
    # by internship_program_service.publish_program -- not from here. The
    # Phase 7 code only ever SELECTs internship_programs (to find the
    # program_id), never writes it.
    assert '.table("internship_programs").update' not in completion_src
    assert '.table("internship_programs").insert' not in completion_src
    assert '.table("internship_programs").delete' not in completion_src


def test_completion_service_never_rewrites_a_submission_or_a_review():
    completion_src = _completion_source()
    assert '.table("workspace_submissions").update' not in completion_src
    assert '.table("workspace_submissions").insert' not in completion_src
    assert '.table("workspace_submissions").delete' not in completion_src
    assert '"submission_reviews"' not in completion_src


def test_certificate_and_completion_writes_are_insert_only_from_this_flow():
    completion_src = _completion_source()
    assert '.table("internship_completions").update' not in completion_src
    assert '.table("internship_certificates").update' not in completion_src
