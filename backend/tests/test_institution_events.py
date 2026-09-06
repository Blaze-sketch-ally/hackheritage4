"""Tests for the Institution Events module (Phase 10):
/api/v1/institution/events..., database/migrations/
045_institution_events.sql.

Route tests mock institution_event_service and use
tests.conftest.authenticated_as, matching the rest of the institution
test suite. Service tests drive institution_event_service against a
fake Supabase client (table reads + insert/update, same shape as
test_institution_industry_partners.py) -- verifying that
`industry_workshops` stays untouched and read-only, that the directory
union covers both sources without leaking another institution's private
event, that lifecycle transitions are validated server-side, that a
company/department reference must be real and institution-owned, and
that no registration/attendance number is ever fabricated.
"""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_event_service
from tests.conftest import authenticated_as

client = TestClient(app)

BASE = "/api/v1/institution/events"
EVENT_ID = "55555555-5555-5555-5555-555555555555"
COMPANY_ID = "33333333-3333-3333-3333-333333333333"


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    assert client.get(BASE).status_code == 401
    assert client.get(f"{BASE}/overview").status_code == 401
    assert client.get(f"{BASE}/{EVENT_ID}").status_code == 401
    assert client.post(BASE, json={"title": "X"}).status_code == 401
    assert client.put(f"{BASE}/{EVENT_ID}", json={"title": "X"}).status_code == 401
    assert client.patch(f"{BASE}/{EVENT_ID}/status", json={"status": "PUBLISHED"}).status_code == 401


def test_all_endpoints_forbid_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            assert client.get(BASE, headers={"Authorization": "Bearer token"}).status_code == 403
            assert (
                client.post(BASE, json={"title": "X"}, headers={"Authorization": "Bearer token"}).status_code == 403
            )


# ============================================================
# Route wiring
# ============================================================


def test_list_scopes_to_authenticated_institution_and_forwards_params():
    captured = {}

    def fake_list(_client, institution_id, **kwargs):
        captured["institution_id"] = institution_id
        captured.update(kwargs)
        return {"events": []}

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_event_service, "list_events", side_effect=fake_list),
    ):
        resp = client.get(
            f"{BASE}?search=acme&event_type=SEMINAR&status=PUBLISHED&mode=ONSITE",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-1"
    assert captured["search"] == "acme"
    assert captured["event_type"] == "SEMINAR"
    assert captured["status"] == "PUBLISHED"
    assert captured["mode"] == "ONSITE"


def test_create_derives_institution_from_token_not_body():
    captured = {}

    def fake_create(_client, institution_id, fields):
        captured["institution_id"] = institution_id
        captured["fields"] = fields
        return _event_row()

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_event_service, "create_event", side_effect=fake_create),
    ):
        resp = client.post(
            BASE, json={"title": "Placement Orientation"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 201
    assert captured["institution_id"] == "institution-1"
    assert captured["fields"]["title"] == "Placement Orientation"


def test_create_rejects_client_supplied_status():
    with authenticated_as("INSTITUTION"):
        resp = client.post(
            BASE, json={"title": "X", "status": "PUBLISHED"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_rejects_unknown_company():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_event_service,
            "create_event",
            side_effect=institution_event_service.IndustryProfileNotFoundError("not found"),
        ),
    ):
        resp = client.post(
            BASE, json={"title": "X", "industry_id": COMPANY_ID}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_without_targeting_sends_json_safe_datetimes_to_the_service():
    """Regression: POST /institution/events used to call body.model_dump()
    (no mode="json") in create_institution_event, so start_at/end_at/
    registration_deadline reached institution_event_service.create_event
    as raw datetime objects -- values postgrest-py's httpx transport
    cannot JSON-encode, which crashed the INSERT with a TypeError that
    the route's own `except Exception` turned into a 500 for every event
    that had a start time, with or without department/batch targeting.
    The sibling PUT route (update_institution_event) already used
    model_dump(mode="json") and never had this bug -- this test locks in
    the same fix for POST."""
    captured = {}

    def fake_create(_client, institution_id, fields):
        captured["fields"] = fields
        return _event_row(start_at="2026-11-01T09:00:00", end_at="2026-11-01T11:00:00")

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_event_service, "create_event", side_effect=fake_create),
    ):
        resp = client.post(
            BASE,
            json={
                "title": "Placement Orientation 2026",
                "start_at": "2026-11-01T09:00:00",
                "end_at": "2026-11-01T11:00:00",
                "registration_deadline": "2026-10-25T00:00:00",
            },
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    # The exact regression: these must be JSON-safe strings, never raw
    # datetime objects -- json.dumps would raise TypeError otherwise.
    json.dumps(captured["fields"])
    assert captured["fields"]["start_at"] == "2026-11-01T09:00:00"
    assert captured["fields"]["end_at"] == "2026-11-01T11:00:00"
    assert captured["fields"]["registration_deadline"] == "2026-10-25T00:00:00"
    assert captured["fields"]["target_department_ids"] is None
    assert captured["fields"]["target_batches"] is None


def test_create_with_department_targeting_sends_json_safe_datetimes():
    captured = {}

    def fake_create(_client, institution_id, fields):
        captured["fields"] = fields
        return _event_row(target_department_ids=[COMPANY_ID], target_department_names=["CSE"])

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_event_service, "create_event", side_effect=fake_create),
    ):
        resp = client.post(
            BASE,
            json={
                "title": "CSE Placement Drive Briefing",
                "start_at": "2026-11-01T09:00:00",
                "target_department_ids": [COMPANY_ID],
            },
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    json.dumps(captured["fields"])
    assert captured["fields"]["start_at"] == "2026-11-01T09:00:00"
    assert captured["fields"]["target_department_ids"] == [COMPANY_ID]


def test_create_with_batch_targeting_sends_json_safe_datetimes():
    captured = {}

    def fake_create(_client, institution_id, fields):
        captured["fields"] = fields
        return _event_row(target_batches=[2026])

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_event_service, "create_event", side_effect=fake_create),
    ):
        resp = client.post(
            BASE,
            json={
                "title": "Batch 2026 Orientation",
                "start_at": "2026-11-01T09:00:00",
                "target_batches": [2026],
            },
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    json.dumps(captured["fields"])
    assert captured["fields"]["start_at"] == "2026-11-01T09:00:00"
    assert captured["fields"]["target_batches"] == [2026]


def test_create_with_department_and_batch_targeting_together():
    captured = {}

    def fake_create(_client, institution_id, fields):
        captured["fields"] = fields
        return _event_row(target_department_ids=[COMPANY_ID], target_batches=[2026])

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_event_service, "create_event", side_effect=fake_create),
    ):
        resp = client.post(
            BASE,
            json={
                "title": "CSE Batch 2026 Briefing",
                "start_at": "2026-11-01T09:00:00",
                "end_at": "2026-11-01T11:00:00",
                "target_department_ids": [COMPANY_ID],
                "target_batches": [2026],
            },
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    json.dumps(captured["fields"])
    assert captured["fields"]["target_department_ids"] == [COMPANY_ID]
    assert captured["fields"]["target_batches"] == [2026]


def test_detail_404_for_event_outside_union():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_event_service, "get_event_detail", return_value=None),
    ):
        resp = client.get(f"{BASE}/{EVENT_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_status_update_rejects_invalid_transition():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_event_service,
            "update_event_status",
            side_effect=institution_event_service.InvalidStatusTransitionError("COMPLETED", "PUBLISHED"),
        ),
    ):
        resp = client.patch(
            f"{BASE}/{EVENT_ID}/status", json={"status": "PUBLISHED"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def _event_row(**overrides):
    row = {
        "id": EVENT_ID,
        "source": "INSTITUTION",
        "title": "Placement Orientation",
        "event_type": "PLACEMENT_ORIENTATION",
        "status": "DRAFT",
        "industry_id": None,
        "company_name": None,
        "mode": None,
        "venue": None,
        "start_at": None,
        "end_at": None,
        "registration_deadline": None,
        "target_department_ids": [],
        "target_department_names": [],
        "target_batches": [],
        "includes_faculty": False,
        "platform_wide": False,
        "description": None,
        "instructions": None,
        "created_at": None,
        "updated_at": None,
    }
    row.update(overrides)
    return row


# ============================================================
# Service-level tests -- fake Supabase client
# ============================================================


class _FakeQuery:
    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name
        self._rows = list(store.get(name, []))
        self._single = False

    def select(self, *_a, **_kw):
        return self

    def eq(self, field, value):
        self._rows = [r for r in self._rows if r.get(field) == value]
        return self

    def in_(self, field, values):
        values = set(values)
        self._rows = [r for r in self._rows if r.get(field) in values]
        return self

    def order(self, field, desc=False):
        self._rows = sorted(self._rows, key=lambda r: r.get(field) or "", reverse=desc)
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload):
        row = {"id": "new-event", **payload}
        self._store.setdefault(self._name, []).append(row)
        self._rows = [row]
        return self

    def update(self, payload):
        for row in self._rows:
            row.update(payload)
        return self

    def execute(self):
        data = self._rows[0] if self._single and self._rows else (None if self._single else self._rows)
        return MagicMock(data=data)


class _FakeClient:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables, name)


def _base_tables(**overrides):
    tables = {
        "institution_events": [],
        "industry_workshops": [],
        "industry_profiles": [],
        "departments": [],
    }
    tables.update(overrides)
    return tables


def _institution_event_row(**overrides):
    row = {
        "id": EVENT_ID,
        "institution_id": "inst-1",
        "industry_id": None,
        "title": "Placement Orientation 2026",
        "description": "Kickoff session.",
        "event_type": "PLACEMENT_ORIENTATION",
        "status": "DRAFT",
        "mode": "ONSITE",
        "venue": "Main Auditorium",
        "start_at": "2026-09-10T09:00:00+00:00",
        "end_at": "2026-09-10T11:00:00+00:00",
        "registration_deadline": None,
        "target_department_ids": [],
        "target_batches": [],
        "includes_faculty": False,
        "instructions": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


# ---- directory union ----


def test_empty_institution_has_no_events():
    result = institution_event_service.list_events(_FakeClient(_base_tables()), "inst-1")
    assert result["events"] == []


def test_institution_event_visible_only_to_owning_institution():
    tables = _base_tables(institution_events=[_institution_event_row(institution_id="inst-A")])
    result_a = institution_event_service.list_events(_FakeClient(tables), "inst-A")
    result_b = institution_event_service.list_events(_FakeClient(tables), "inst-B")
    assert len(result_a["events"]) == 1
    assert result_b["events"] == []


def test_published_workshop_visible_platform_wide_and_marked_read_only():
    tables = _base_tables(
        industry_workshops=[
            {
                "id": "workshop-1",
                "industry_id": "co-1",
                "title": "React Bootcamp",
                "description": "3-day hands-on workshop.",
                "location": "Remote",
                "work_mode": "REMOTE",
                "application_deadline": "2026-09-01",
                "start_date": "2026-09-15",
                "status": "PUBLISHED",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result_a = institution_event_service.list_events(_FakeClient(tables), "inst-A")
    result_b = institution_event_service.list_events(_FakeClient(tables), "inst-B")
    assert len(result_a["events"]) == 1
    assert len(result_b["events"]) == 1
    row = result_a["events"][0]
    assert row["source"] == "INDUSTRY_WORKSHOP"
    assert row["platform_wide"] is True
    assert row["company_name"] == "Acme Corp"
    assert row["event_type"] == "WORKSHOP"


def test_draft_and_closed_workshops_never_leak_platform_wide():
    tables = _base_tables(
        industry_workshops=[
            {"id": "w1", "industry_id": "co-1", "title": "Draft Workshop", "description": "d",
             "location": None, "work_mode": None, "application_deadline": None, "start_date": None,
             "status": "DRAFT", "created_at": None},
        ],
    )
    result = institution_event_service.list_events(_FakeClient(tables), "inst-1")
    assert result["events"] == []


def test_search_filters_across_title_and_company():
    tables = _base_tables(
        institution_events=[
            _institution_event_row(id="e1", institution_id="inst-1", title="Career Fair"),
            _institution_event_row(id="e2", institution_id="inst-1", title="Guest Lecture"),
        ],
    )
    result = institution_event_service.list_events(_FakeClient(tables), "inst-1", search="career")
    assert [e["title"] for e in result["events"]] == ["Career Fair"]


def test_type_status_mode_filters():
    tables = _base_tables(
        institution_events=[
            _institution_event_row(id="e1", institution_id="inst-1", event_type="SEMINAR", status="PUBLISHED", mode="ONSITE"),
            _institution_event_row(id="e2", institution_id="inst-1", event_type="WORKSHOP", status="DRAFT", mode="REMOTE"),
        ],
    )
    result = institution_event_service.list_events(_FakeClient(tables), "inst-1", event_type="SEMINAR")
    assert [e["id"] for e in result["events"]] == ["e1"]

    result = institution_event_service.list_events(_FakeClient(tables), "inst-1", status="DRAFT")
    assert [e["id"] for e in result["events"]] == ["e2"]

    result = institution_event_service.list_events(_FakeClient(tables), "inst-1", mode="REMOTE")
    assert [e["id"] for e in result["events"]] == ["e2"]


# ---- detail ----


def test_detail_returns_none_for_other_institutions_event():
    tables = _base_tables(institution_events=[_institution_event_row(institution_id="inst-B")])
    result = institution_event_service.get_event_detail(_FakeClient(tables), "inst-A", EVENT_ID)
    assert result is None


def test_detail_resolves_department_names_from_real_departments_entity():
    tables = _base_tables(
        institution_events=[_institution_event_row(target_department_ids=["dept-1"])],
        departments=[{"id": "dept-1", "institution_id": "inst-1", "name": "CSE"}],
    )
    result = institution_event_service.get_event_detail(_FakeClient(tables), "inst-1", EVENT_ID)
    assert result["target_department_names"] == ["CSE"]


def test_detail_never_exposes_registration_or_attendance_fields():
    tables = _base_tables(institution_events=[_institution_event_row()])
    result = institution_event_service.get_event_detail(_FakeClient(tables), "inst-1", EVENT_ID)
    assert "registration_count" not in result
    assert "attendance" not in result
    assert "attended_count" not in result


# ---- create / update ----


def test_create_requires_real_company_when_industry_id_set():
    tables = _base_tables()
    raised = False
    try:
        institution_event_service.create_event(
            _FakeClient(tables), "inst-1", {"title": "Industry Talk", "industry_id": "co-missing"}
        )
    except institution_event_service.IndustryProfileNotFoundError:
        raised = True
    assert raised


def test_create_succeeds_with_real_company_and_own_department():
    tables = _base_tables(
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
        departments=[{"id": "dept-1", "institution_id": "inst-1", "name": "CSE"}],
    )
    row = institution_event_service.create_event(
        _FakeClient(tables),
        "inst-1",
        {"title": "Industry Talk", "industry_id": "co-1", "target_department_ids": ["dept-1"]},
    )
    assert row["status"] == "DRAFT"
    assert row["company_name"] == "Acme Corp"
    assert row["target_department_names"] == ["CSE"]


def test_create_rejects_another_institutions_department():
    tables = _base_tables(departments=[{"id": "dept-1", "institution_id": "inst-B", "name": "CSE"}])
    from app.services.institution_placement_service import CrossInstitutionEligibilityError

    raised = False
    try:
        institution_event_service.create_event(
            _FakeClient(tables), "inst-1", {"title": "X", "target_department_ids": ["dept-1"]}
        )
    except CrossInstitutionEligibilityError:
        raised = True
    assert raised


def test_create_succeeds_with_batch_targeting_and_a_start_time():
    tables = _base_tables()
    row = institution_event_service.create_event(
        _FakeClient(tables),
        "inst-1",
        {"title": "Batch 2026 Orientation", "start_at": "2026-11-01T09:00:00", "target_batches": [2026]},
    )
    assert row["status"] == "DRAFT"
    assert row["target_batches"] == [2026]
    assert row["start_at"] == "2026-11-01T09:00:00"


def test_create_isolated_between_institutions_even_with_targeting():
    """Institution tenancy: creating under inst-1 must never be visible to
    inst-2, regardless of department/batch targeting or a start time."""
    tables = _base_tables(departments=[{"id": "dept-1", "institution_id": "inst-1", "name": "CSE"}])
    institution_event_service.create_event(
        _FakeClient(tables),
        "inst-1",
        {
            "title": "Inst-1 Only Session",
            "start_at": "2026-11-01T09:00:00",
            "target_department_ids": ["dept-1"],
            "target_batches": [2026],
        },
    )
    own_view = institution_event_service.list_events(_FakeClient(tables), "inst-1")
    other_view = institution_event_service.list_events(_FakeClient(tables), "inst-2")
    assert len(own_view["events"]) == 1
    assert other_view["events"] == []


def test_update_cannot_touch_a_platform_wide_workshop():
    tables = _base_tables(
        industry_workshops=[
            {"id": "workshop-1", "industry_id": "co-1", "title": "React Bootcamp", "description": "d",
             "location": None, "work_mode": None, "application_deadline": None, "start_date": None,
             "status": "PUBLISHED", "created_at": None},
        ],
    )
    result = institution_event_service.update_event(_FakeClient(tables), "inst-1", "workshop-1", {"title": "Hacked"})
    assert result is None


def test_update_only_changes_sent_fields():
    tables = _base_tables(institution_events=[_institution_event_row(description="Old description")])
    row = institution_event_service.update_event(_FakeClient(tables), "inst-1", EVENT_ID, {"venue": "New Hall"})
    assert row["venue"] == "New Hall"
    assert row["description"] == "Old description"


def test_update_isolated_between_institutions():
    tables = _base_tables(institution_events=[_institution_event_row(institution_id="inst-B")])
    result = institution_event_service.update_event(_FakeClient(tables), "inst-A", EVENT_ID, {"venue": "X"})
    assert result is None


# ---- status lifecycle ----


def test_status_transition_draft_to_published_allowed():
    tables = _base_tables(institution_events=[_institution_event_row(status="DRAFT")])
    row = institution_event_service.update_event_status(_FakeClient(tables), "inst-1", EVENT_ID, "PUBLISHED")
    assert row["status"] == "PUBLISHED"


def test_status_transition_draft_to_ongoing_rejected():
    tables = _base_tables(institution_events=[_institution_event_row(status="DRAFT")])
    raised = False
    try:
        institution_event_service.update_event_status(_FakeClient(tables), "inst-1", EVENT_ID, "ONGOING")
    except institution_event_service.InvalidStatusTransitionError:
        raised = True
    assert raised


def test_status_transition_from_completed_rejected():
    tables = _base_tables(institution_events=[_institution_event_row(status="COMPLETED")])
    raised = False
    try:
        institution_event_service.update_event_status(_FakeClient(tables), "inst-1", EVENT_ID, "PUBLISHED")
    except institution_event_service.InvalidStatusTransitionError:
        raised = True
    assert raised


def test_status_transition_cancel_from_any_non_terminal_state():
    for status in ("DRAFT", "PUBLISHED", "ONGOING"):
        tables = _base_tables(institution_events=[_institution_event_row(status=status)])
        row = institution_event_service.update_event_status(_FakeClient(tables), "inst-1", EVENT_ID, "CANCELLED")
        assert row["status"] == "CANCELLED"


def test_status_update_404_for_other_institutions_event():
    tables = _base_tables(institution_events=[_institution_event_row(institution_id="inst-B", status="DRAFT")])
    result = institution_event_service.update_event_status(_FakeClient(tables), "inst-A", EVENT_ID, "PUBLISHED")
    assert result is None


# ---- overview / KPIs ----


def test_overview_empty_institution_is_all_zeros():
    result = institution_event_service.compute_event_overview(_FakeClient(_base_tables()), "inst-1")
    assert result["kpis"] == {
        "total_events": 0,
        "upcoming_events": 0,
        "ongoing_events": 0,
        "completed_events": 0,
        "industry_events": 0,
        "institution_organized_events": 0,
        "platform_workshops": 0,
    }


def test_overview_counts_institution_events_and_workshops_together():
    tables = _base_tables(
        institution_events=[
            _institution_event_row(id="e1", institution_id="inst-1", status="PUBLISHED", industry_id="co-1"),
            _institution_event_row(id="e2", institution_id="inst-1", status="COMPLETED"),
        ],
        industry_workshops=[
            {"id": "w1", "industry_id": "co-1", "title": "React Bootcamp", "description": "d",
             "location": None, "work_mode": None, "application_deadline": None, "start_date": None,
             "status": "PUBLISHED", "created_at": None},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = institution_event_service.compute_event_overview(_FakeClient(tables), "inst-1")
    kpis = result["kpis"]
    assert kpis["total_events"] == 3
    assert kpis["upcoming_events"] == 2  # e1 (PUBLISHED) + w1 (workshop, always upcoming bucket)
    assert kpis["completed_events"] == 1
    assert kpis["industry_events"] == 2  # e1 has industry_id, w1 always does
    assert kpis["institution_organized_events"] == 2
    assert kpis["platform_workshops"] == 1
