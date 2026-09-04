"""Phase 8 -- internship stipend record-keeping (stipend_disbursements).

RECORD-KEEPING ONLY: there is no payment gateway, no bank/UPI/card
integration, and no code anywhere that calls out to a network payment
provider. "RELEASED" means the industry recorded that a disbursement
happened; it never triggers one.

Independent of internship_completions / internship_certificates (Phase 7)
and of everything else in the workspace lifecycle: this suite verifies the
stipend service touches ONLY stipend_disbursements (plus a read of
internship_workspaces for ownership), enforces the exact state machine
(PENDING -> APPROVED -> RELEASED, PENDING -> CANCELLED, both terminal),
rejects a repeated transition rather than silently re-accepting it, is
race-safe via a compare-and-swap UPDATE, and keeps every ownership
boundary (industry-vs-industry, student-vs-student, student read-only).
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.api import internship_workspaces as industry_api
from app.main import app
from app.services import internship_workspace_service as svc
from app.services import notification_producer
from tests.conftest import authenticated_as

client = TestClient(app)

_WID = "11111111-1111-1111-1111-111111111111"
_IID = "22222222-2222-2222-2222-222222222222"
_SID = "33333333-3333-3333-3333-333333333333"


# ============================================================
# fake Supabase client
# ============================================================


class _Q:
    def __init__(self, fake, table):
        self.fake, self.table = fake, table
        self._filters: list[tuple] = []
        self._single = False
        self._op = "select"
        self._payload = None

    def select(self, *a, **k):
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

    def execute(self):
        return self.fake._exec(self)


class _Fake:
    def __init__(self, **tables):
        self.tables: dict[str, list] = {k: list(v) for k, v in tables.items()}
        self.filters: list[tuple] = []
        self.inserts: list[tuple] = []
        self.updates: list[tuple] = []
        self.deletes: list[tuple] = []
        self.insert_errors: dict[str, Exception] = {}
        self.update_errors: dict[str, Exception] = {}

    def rows(self, table):
        return self.tables.setdefault(table, [])

    def table(self, name):
        return _Q(self, name)

    def _exec(self, q: _Q):
        if q._op == "insert":
            self.inserts.append((q.table, dict(q._payload)))
            err = self.insert_errors.get(q.table)
            if err is not None:
                raise err
            row = dict(q._payload)
            row.setdefault("id", f"{q.table[:4]}-{len(self.rows(q.table)) + 1}")
            row.setdefault("released_by", None)
            row.setdefault("currency", "INR")
            row.setdefault("disbursement_status", "PENDING")
            row.setdefault("reference", None)
            row.setdefault("notes", None)
            row.setdefault("released_at", None)
            row.setdefault("created_at", "2026-09-15T00:00:00Z")
            row.setdefault("updated_at", "2026-09-15T00:00:00Z")
            self.rows(q.table).append(row)
            return SimpleNamespace(data=[row])
        if q._op == "update":
            self.updates.append((q.table, dict(q._payload)))
            err = self.update_errors.get(q.table)
            if err is not None:
                raise err
            matched = [r for r in self.rows(q.table) if q._match(r)]
            for row in matched:
                row.update(q._payload)
            return SimpleNamespace(data=[dict(r) for r in matched])
        if q._op == "delete":
            self.deletes.append((q.table, list(q._filters)))
            return SimpleNamespace(data=[])
        rows = [r for r in self.rows(q.table) if q._match(r)]
        if q._single:
            return SimpleNamespace(data=rows[0] if rows else None)
        return SimpleNamespace(data=rows)


class _RaceFake(_Fake):
    """The FIRST update call against stipend_disbursements simulates a
    concurrent writer that already flipped the row's status -- our own
    compare-and-swap predicate then matches nothing, exactly as it would
    live when two requests race."""

    def __init__(self, *a, race_to="RELEASED", **k):
        super().__init__(*a, **k)
        self._raced = False
        self._race_to = race_to

    def _exec(self, q: _Q):
        if q._op == "update" and q.table == "stipend_disbursements" and not self._raced:
            self._raced = True
            for row in self.rows(q.table):
                row["disbursement_status"] = self._race_to
            return SimpleNamespace(data=[])
        return super()._exec(q)


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


def _stipend(**over):
    row = {
        "id": "stip-1",
        "workspace_id": _WID,
        "released_by": None,
        "amount": 5000.0,
        "currency": "INR",
        "disbursement_status": "PENDING",
        "reference": None,
        "notes": None,
        "released_at": None,
        "created_at": "2026-09-10T00:00:00Z",
        "updated_at": "2026-09-10T00:00:00Z",
    }
    row.update(over)
    return row


def _db(*, workspace=None, stipends=None, fake_cls=_Fake, **kw):
    return fake_cls(
        internship_workspaces=[workspace or _ws()],
        stipend_disbursements=stipends or [],
        **kw,
    )


# ============================================================
# creation (service)
# ============================================================


def test_industry_creates_a_stipend_record_starting_pending():
    fake = _db()
    summary = svc.create_stipend(fake, "industry-1", _WID, {"amount": 5000, "currency": "INR"})
    assert summary["stipend"]["disbursement_status"] == "PENDING"
    assert summary["stipend"]["amount"] == 5000
    inserted = fake.inserts[0][1]
    assert inserted["workspace_id"] == _WID
    assert "disbursement_status" not in inserted  # server-defaulted, never client-set
    assert "released_by" not in inserted


def test_duplicate_creation_is_rejected():
    fake = _db(stipends=[_stipend()])
    with pytest.raises(svc.StipendExistsError):
        svc.create_stipend(fake, "industry-1", _WID, {"amount": 1000})
    assert len(fake.inserts) == 0


def test_a_23505_race_on_create_is_reported_as_already_exists_not_a_duplicate():
    fake = _db()
    fake.insert_errors["stipend_disbursements"] = APIError({"code": "23505", "message": "unique"})
    with pytest.raises(svc.StipendExistsError):
        svc.create_stipend(fake, "industry-1", _WID, {"amount": 1000})


def test_another_company_cannot_create_a_stipend():
    fake = _db()
    with pytest.raises(svc.WorkspaceNotFoundError):
        svc.create_stipend(fake, "industry-999", _WID, {"amount": 1000})
    assert fake.inserts == []


# ============================================================
# update while PENDING (service)
# ============================================================


def test_stipend_details_can_be_edited_while_pending():
    fake = _db(stipends=[_stipend(amount=5000)])
    summary = svc.update_stipend_details(fake, "industry-1", _WID, {"amount": 6000, "notes": "raise"})
    assert summary["stipend"]["amount"] == 6000
    assert summary["stipend"]["notes"] == "raise"


@pytest.mark.parametrize("status", ["APPROVED", "RELEASED", "CANCELLED"])
def test_stipend_details_cannot_be_edited_once_not_pending(status):
    fake = _db(stipends=[_stipend(disbursement_status=status)])
    with pytest.raises(svc.StipendImmutableError):
        svc.update_stipend_details(fake, "industry-1", _WID, {"amount": 1})
    assert fake.updates == []


def test_update_404s_when_no_stipend_exists_yet():
    fake = _db()
    with pytest.raises(svc.StipendNotFoundError):
        svc.update_stipend_details(fake, "industry-1", _WID, {"amount": 1})


# ============================================================
# state transitions (service)
# ============================================================


def test_approve_moves_pending_to_approved():
    fake = _db(stipends=[_stipend(disbursement_status="PENDING")])
    summary = svc.approve_stipend(fake, "industry-1", _WID)
    assert summary["stipend"]["disbursement_status"] == "APPROVED"


def test_release_moves_approved_to_released():
    fake = _db(stipends=[_stipend(disbursement_status="APPROVED")])
    summary = svc.release_stipend(fake, "industry-1", _WID)
    assert summary["stipend"]["disbursement_status"] == "RELEASED"


def test_cancel_moves_pending_to_cancelled():
    fake = _db(stipends=[_stipend(disbursement_status="PENDING")])
    summary = svc.cancel_stipend(fake, "industry-1", _WID)
    assert summary["stipend"]["disbursement_status"] == "CANCELLED"


@pytest.mark.parametrize("status", ["APPROVED", "RELEASED", "CANCELLED"])
def test_approve_is_rejected_from_any_non_pending_state(status):
    fake = _db(stipends=[_stipend(disbursement_status=status)])
    with pytest.raises(svc.InvalidStipendTransitionError) as ei:
        svc.approve_stipend(fake, "industry-1", _WID)
    assert ei.value.current == status and ei.value.target == "APPROVED"
    assert fake.updates == []


def test_a_repeated_approve_is_rejected_not_a_silent_no_op():
    fake = _db(stipends=[_stipend(disbursement_status="APPROVED")])
    with pytest.raises(svc.InvalidStipendTransitionError):
        svc.approve_stipend(fake, "industry-1", _WID)


@pytest.mark.parametrize("status", ["PENDING", "RELEASED", "CANCELLED"])
def test_release_is_rejected_from_any_non_approved_state(status):
    fake = _db(stipends=[_stipend(disbursement_status=status)])
    with pytest.raises(svc.InvalidStipendTransitionError):
        svc.release_stipend(fake, "industry-1", _WID)
    assert fake.updates == []


@pytest.mark.parametrize("status", ["APPROVED", "RELEASED", "CANCELLED"])
def test_cancel_is_rejected_from_any_non_pending_state(status):
    # in particular: APPROVED -> CANCELLED is not part of the approved
    # architecture and must not be invented here.
    fake = _db(stipends=[_stipend(disbursement_status=status)])
    with pytest.raises(svc.InvalidStipendTransitionError):
        svc.cancel_stipend(fake, "industry-1", _WID)
    assert fake.updates == []


def test_release_never_accepts_released_by_from_the_caller():
    import inspect

    assert list(inspect.signature(svc.release_stipend).parameters) == [
        "client", "industry_id", "workspace_id",
    ]


# ============================================================
# terminal states stay terminal
# ============================================================


def test_released_record_cannot_be_approved_again():
    fake = _db(stipends=[_stipend(disbursement_status="RELEASED")])
    with pytest.raises(svc.InvalidStipendTransitionError):
        svc.approve_stipend(fake, "industry-1", _WID)


def test_cancelled_record_cannot_be_approved():
    fake = _db(stipends=[_stipend(disbursement_status="CANCELLED")])
    with pytest.raises(svc.InvalidStipendTransitionError):
        svc.approve_stipend(fake, "industry-1", _WID)


# ============================================================
# concurrency: the compare-and-swap protects against a lost race
# ============================================================


def test_a_concurrent_transition_is_detected_and_rejected_not_corrupted():
    fake = _db(
        stipends=[_stipend(disbursement_status="PENDING")],
        fake_cls=_RaceFake,
        race_to="CANCELLED",
    )
    with pytest.raises(svc.InvalidStipendTransitionError) as ei:
        svc.approve_stipend(fake, "industry-1", _WID)
    # reports the ACTUAL state the concurrent writer left it in
    assert ei.value.current == "CANCELLED"
    # exactly one row exists, in a valid terminal state -- never corrupted
    assert len(fake.tables["stipend_disbursements"]) == 1
    assert fake.tables["stipend_disbursements"][0]["disbursement_status"] == "CANCELLED"


def test_concurrent_creation_cannot_create_two_records():
    fake = _db()
    fake.insert_errors["stipend_disbursements"] = APIError({"code": "23505", "message": "unique"})
    with pytest.raises(svc.StipendExistsError):
        svc.create_stipend(fake, "industry-1", _WID, {"amount": 1000})
    assert len(fake.tables["stipend_disbursements"]) == 0  # the loser inserted nothing


# ============================================================
# ownership / isolation
# ============================================================


def test_industry_stipend_summary_404s_for_a_foreign_workspace():
    fake = _db(stipends=[_stipend()])
    assert svc.get_industry_stipend(fake, "industry-999", _WID) is None


def test_another_company_cannot_approve_release_or_cancel():
    fake = _db(stipends=[_stipend(disbursement_status="PENDING")])
    with pytest.raises(svc.WorkspaceNotFoundError):
        svc.approve_stipend(fake, "industry-999", _WID)
    fake2 = _db(stipends=[_stipend(disbursement_status="APPROVED")])
    with pytest.raises(svc.WorkspaceNotFoundError):
        svc.release_stipend(fake2, "industry-999", _WID)
    fake3 = _db(stipends=[_stipend(disbursement_status="PENDING")])
    with pytest.raises(svc.WorkspaceNotFoundError):
        svc.cancel_stipend(fake3, "industry-999", _WID)
    assert fake.updates == fake2.updates == fake3.updates == []


def test_student_stipend_summary_is_scoped_to_the_caller():
    fake = _db(stipends=[_stipend()])
    assert svc.get_student_stipend(fake, "student-B-not-owner", _WID) is None


def test_student_sees_their_own_stipend():
    fake = _db(stipends=[_stipend(amount=7500, disbursement_status="APPROVED")])
    summary = svc.get_student_stipend(fake, _SID, _WID)
    assert summary["stipend"]["amount"] == 7500
    assert summary["stipend"]["disbursement_status"] == "APPROVED"


def test_no_stipend_configured_is_an_honest_null_not_a_404():
    fake = _db()
    summary = svc.get_student_stipend(fake, _SID, _WID)
    assert summary is not None
    assert summary["stipend"] is None


# ============================================================
# data integrity: nothing outside stipend_disbursements is touched
# ============================================================


def test_workspace_status_is_never_touched_by_any_stipend_action():
    fake = _db(workspace=_ws(workspace_status="IN_PROGRESS"), stipends=[_stipend()])
    svc.approve_stipend(fake, "industry-1", _WID)
    svc.release_stipend(fake, "industry-1", _WID)
    assert fake.tables["internship_workspaces"][0]["workspace_status"] == "IN_PROGRESS"
    assert all(t == "stipend_disbursements" for t, _ in fake.updates)


def test_workspace_id_is_never_reassigned_by_an_update():
    fake = _db(stipends=[_stipend()])
    svc.approve_stipend(fake, "industry-1", _WID)
    assert fake.tables["stipend_disbursements"][0]["workspace_id"] == _WID
    for _, payload in fake.updates:
        assert "workspace_id" not in payload


# ============================================================
# no payment integration (source inspection)
# ============================================================


def test_stipend_service_never_writes_completion_certificate_or_applications():
    import inspect

    stipend_fns = (
        "get_student_stipend", "get_industry_stipend", "create_stipend",
        "update_stipend_details", "_transition_stipend", "approve_stipend",
        "release_stipend", "cancel_stipend",
    )
    stipend_src = "".join(inspect.getsource(getattr(svc, name)) for name in stipend_fns)
    for forbidden in (
        '.table("internship_completions")',
        '.table("internship_certificates")',
        '.table("applications")',
        '.table("internship_workspaces").update',  # stipend never rewrites the workspace
        '.table("workspace_submissions")',
        '.table("submission_reviews")',
    ):
        assert forbidden not in stipend_src, forbidden
    # only stipend_disbursements is ever written from this section, and
    # never deleted (no DELETE policy exists either).
    assert '.table("stipend_disbursements").delete' not in stipend_src


def test_no_payment_gateway_or_network_client_is_used_anywhere():
    import inspect

    src = inspect.getsource(svc)
    for term in ("stripe", "razorpay", "paypal", "requests.", "httpx.", "upi://", "bank_api"):
        assert term not in src.lower(), f"unexpected payment-integration reference: {term}"


# ============================================================
# routes -- auth guards
# ============================================================

_INDUSTRY_GET = ("get", f"/api/v1/internship-workspaces/{_WID}/stipend")
_INDUSTRY_CREATE = ("post", f"/api/v1/internship-workspaces/{_WID}/stipend")
_INDUSTRY_UPDATE = ("put", f"/api/v1/internship-workspaces/{_WID}/stipend")
_INDUSTRY_APPROVE = ("post", f"/api/v1/internship-workspaces/{_WID}/stipend/approve")
_INDUSTRY_RELEASE = ("post", f"/api/v1/internship-workspaces/{_WID}/stipend/release")
_INDUSTRY_CANCEL = ("post", f"/api/v1/internship-workspaces/{_WID}/stipend/cancel")
_INDUSTRY_ENDPOINTS = [
    _INDUSTRY_GET, _INDUSTRY_CREATE, _INDUSTRY_UPDATE,
    _INDUSTRY_APPROVE, _INDUSTRY_RELEASE, _INDUSTRY_CANCEL,
]
_STUDENT_ENDPOINT = ("get", f"/api/v1/student/internship-workspaces/{_WID}/stipend")


def _body(method, url):
    if url.endswith("/stipend") and method == "post":
        return {"amount": 1000}
    if url.endswith("/stipend") and method == "put":
        return {"amount": 1000}
    if method == "post":
        return {}
    return None


def _call(method, url, **kw):
    body = _body(method, url)
    return getattr(client, method)(url, json=body, **kw) if body is not None else getattr(client, method)(url, **kw)


def test_industry_stipend_endpoints_reject_unauthenticated():
    for method, url in _INDUSTRY_ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_industry_stipend_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in _INDUSTRY_ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer t"})
            assert resp.status_code == 403, (role, method, url)


def test_student_stipend_endpoint_rejects_unauthenticated():
    assert client.get(_STUDENT_ENDPOINT[1]).status_code == 401


def test_student_stipend_endpoint_forbids_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(_STUDENT_ENDPOINT[1], headers={"Authorization": "Bearer t"})
        assert resp.status_code == 403, role


def test_student_has_no_write_route_for_stipend():
    # There is structurally no POST/PUT student stipend endpoint at all.
    for method in ("post", "put"):
        with authenticated_as("STUDENT", user_id=_SID):
            resp = getattr(client, method)(
                _STUDENT_ENDPOINT[1], json={"amount": 1}, headers={"Authorization": "Bearer t"}
            )
        assert resp.status_code in (404, 405), method


# ============================================================
# routes -- behaviour + error mapping
# ============================================================


def test_industry_get_endpoint_returns_a_null_stipend_as_200():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "get_industry_stipend", return_value={"workspace_id": _WID, "stipend": None}),
    ):
        resp = client.get(
            f"/api/v1/internship-workspaces/{_WID}/stipend", headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 200
    assert resp.json()["stipend"] is None


def test_industry_get_endpoint_404s_for_a_foreign_workspace():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "get_industry_stipend", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/internship-workspaces/{_WID}/stipend", headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 404


def test_create_endpoint_is_201():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            svc, "create_stipend",
            return_value={"workspace_id": _WID, "stipend": {
                "id": "s1", "workspace_id": _WID, "amount": 1000.0, "currency": "INR",
                "disbursement_status": "PENDING", "reference": None, "notes": None,
                "released_at": None, "created_at": None, "updated_at": None,
            }},
        ),
    ):
        resp = client.post(
            f"/api/v1/internship-workspaces/{_WID}/stipend",
            json={"amount": 1000},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 201


def test_create_endpoint_rejects_unknown_fields_and_bad_amount():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        bad_field = client.post(
            f"/api/v1/internship-workspaces/{_WID}/stipend",
            json={"amount": 1000, "disbursement_status": "RELEASED"},
            headers={"Authorization": "Bearer t"},
        )
        neg_amount = client.post(
            f"/api/v1/internship-workspaces/{_WID}/stipend",
            json={"amount": -1},
            headers={"Authorization": "Bearer t"},
        )
    assert bad_field.status_code == 422
    assert neg_amount.status_code == 422


def test_create_endpoint_maps_exists_to_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_stipend", side_effect=svc.StipendExistsError(_WID)),
    ):
        resp = client.post(
            f"/api/v1/internship-workspaces/{_WID}/stipend",
            json={"amount": 1000},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 409


def test_update_endpoint_maps_immutable_to_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "update_stipend_details", side_effect=svc.StipendImmutableError("RELEASED")),
    ):
        resp = client.put(
            f"/api/v1/internship-workspaces/{_WID}/stipend",
            json={"amount": 1000},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 409


def test_update_endpoint_rejects_unknown_fields():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        resp = client.put(
            f"/api/v1/internship-workspaces/{_WID}/stipend",
            json={"amount": 1000, "workspace_id": "x"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422


def test_transition_endpoints_map_invalid_transition_to_409():
    for endpoint_fn, service_fn in (
        ("/stipend/approve", "approve_stipend"),
        ("/stipend/release", "release_stipend"),
        ("/stipend/cancel", "cancel_stipend"),
    ):
        with (
            authenticated_as("INDUSTRY", user_id="industry-1"),
            patch.object(svc, service_fn, side_effect=svc.InvalidStipendTransitionError("APPROVED", "APPROVED")),
        ):
            resp = client.post(
                f"/api/v1/internship-workspaces/{_WID}{endpoint_fn}",
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == 409, endpoint_fn


def test_transition_endpoints_map_not_found_to_404():
    for endpoint_fn, service_fn in (
        ("/stipend/approve", "approve_stipend"),
        ("/stipend/release", "release_stipend"),
        ("/stipend/cancel", "cancel_stipend"),
    ):
        with (
            authenticated_as("INDUSTRY", user_id="industry-1"),
            patch.object(svc, service_fn, side_effect=svc.WorkspaceNotFoundError(_WID)),
        ):
            resp = client.post(
                f"/api/v1/internship-workspaces/{_WID}{endpoint_fn}",
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == 404, endpoint_fn


def _stipend_summary(status, **over):
    row = {
        "workspace_id": _WID,
        "stipend": {
            "id": "s1", "workspace_id": _WID, "amount": 1000.0, "currency": "INR",
            "disbursement_status": status, "reference": None, "notes": None,
            "released_at": "2026-09-15T00:00:00Z" if status == "RELEASED" else None,
            "created_at": None, "updated_at": None,
        },
        "_student_id": _SID,
    }
    row.update(over)
    return row


# ============================================================
# notifications
# ============================================================


@pytest.mark.parametrize(
    "endpoint,service_fn,new_status",
    [
        ("/stipend/approve", "approve_stipend", "APPROVED"),
        ("/stipend/release", "release_stipend", "RELEASED"),
        ("/stipend/cancel", "cancel_stipend", "CANCELLED"),
    ],
)
def test_each_transition_emits_exactly_one_notification(endpoint, service_fn, new_status):
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, service_fn, return_value=_stipend_summary(new_status)),
        patch.object(industry_api.notification_producer, "emit_stipend_status_change") as notify,
    ):
        client.post(
            f"/api/v1/internship-workspaces/{_WID}{endpoint}", headers={"Authorization": "Bearer t"}
        )
    notify.assert_called_once_with(student_id=_SID, workspace_id=_WID, new_status=new_status)


def test_create_and_update_never_notify():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_stipend", return_value=_stipend_summary("PENDING")),
        patch.object(industry_api.notification_producer, "emit_stipend_status_change") as notify,
    ):
        client.post(
            f"/api/v1/internship-workspaces/{_WID}/stipend",
            json={"amount": 1000},
            headers={"Authorization": "Bearer t"},
        )
    notify.assert_not_called()


def test_a_rejected_transition_never_notifies():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "approve_stipend", side_effect=svc.InvalidStipendTransitionError("APPROVED", "APPROVED")),
        patch.object(industry_api.notification_producer, "emit_stipend_status_change") as notify,
    ):
        client.post(
            f"/api/v1/internship-workspaces/{_WID}/stipend/approve", headers={"Authorization": "Bearer t"}
        )
    notify.assert_not_called()


def test_a_failed_notification_write_does_not_break_the_transition():
    from unittest.mock import MagicMock

    fake_sb = MagicMock()
    fake_sb.table.side_effect = RuntimeError("db down")
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "approve_stipend", return_value=_stipend_summary("APPROVED")),
        patch.object(notification_producer, "get_supabase", return_value=fake_sb),
    ):
        resp = client.post(
            f"/api/v1/internship-workspaces/{_WID}/stipend/approve", headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 200


def test_stipend_notification_producer_writes_one_internship_workspace_row():
    from unittest.mock import MagicMock

    fake_sb = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake_sb):
        notification_producer.emit_stipend_status_change(
            student_id=_SID, workspace_id=_WID, new_status="RELEASED"
        )
    row = fake_sb.table.return_value.insert.call_args[0][0]
    assert row["type"] == "INTERNSHIP"
    assert row["related_entity_type"] == "INTERNSHIP_WORKSPACE"
    assert row["related_entity_id"] == _WID
    # honest, non-payment wording
    assert "transfer" not in row["body"].lower() and "payment successfully" not in row["body"].lower()


def test_stipend_notification_producer_is_a_noop_for_pending():
    from unittest.mock import MagicMock

    fake_sb = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake_sb):
        notification_producer.emit_stipend_status_change(
            student_id=_SID, workspace_id=_WID, new_status="PENDING"
        )
    fake_sb.table.assert_not_called()


def test_stipend_notification_producer_swallows_its_own_errors():
    from unittest.mock import MagicMock

    fake_sb = MagicMock()
    fake_sb.table.side_effect = RuntimeError("db down")
    with patch.object(notification_producer, "get_supabase", return_value=fake_sb):
        notification_producer.emit_stipend_status_change(
            student_id=_SID, workspace_id=_WID, new_status="APPROVED"
        )  # must not raise
