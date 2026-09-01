"""Tests for Industry Analytics: GET /api/v1/analytics/industry.

Route tests mock app.services.analytics_service and use
tests.conftest.authenticated_as. Service tests drive
compute_industry_analytics with a MagicMock Supabase client whose
per-table reads return canned rows -- verifying the aggregation math, the
industry_id scoping, the empty-dataset path, and that no fabricated
historical status data is produced.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import analytics_service
from tests.conftest import authenticated_as

client = TestClient(app)

URL = "/api/v1/analytics/industry"


# ============================================================
# Auth / role guards
# ============================================================


def test_unauthenticated_returns_401():
    assert client.get(URL).status_code == 401


def test_forbids_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(URL, headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, role


def test_scopes_to_authenticated_industry():
    captured = {}

    def fake_compute(_client, industry_id):
        captured["industry_id"] = industry_id
        return _empty_payload()

    with (
        authenticated_as("INDUSTRY", user_id="industry-55"),
        patch.object(analytics_service, "compute_industry_analytics", side_effect=fake_compute),
    ):
        resp = client.get(URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-55"


def _empty_payload():
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "kpis": {
            "opportunities_total": 0,
            "opportunities_published": 0,
            "applications_total": 0,
            "shortlisted": 0,
            "interviews_total": 0,
            "interviews_upcoming": 0,
            "selected": 0,
            "collaborations_total": 0,
            "collaborations_active": 0,
        },
        "funnel_counts": {
            s: 0
            for s in (
                "APPLIED",
                "UNDER_REVIEW",
                "SHORTLISTED",
                "INTERVIEW_SCHEDULED",
                "SELECTED",
                "REJECTED",
                "WITHDRAWN",
            )
        },
        "funnel_total": 0,
        "application_status_distribution": [],
        "opportunity_breakdown": [],
        "interview_metrics": {
            "total": 0,
            "scheduled": 0,
            "completed": 0,
            "cancelled": 0,
            "upcoming": 0,
        },
        "top_opportunities": [],
        "timeline": [],
        "historical_note": "note",
        "interviews_available": True,
    }


# ============================================================
# Service aggregation math
# ============================================================


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def execute(self):
        return MagicMock(data=list(self._rows))


class _FakeClient:
    """Returns canned rows per table name."""

    def __init__(self, tables: dict, missing: set | None = None):
        self._tables = tables
        self._missing = missing or set()

    def table(self, name):
        if name in self._missing:
            raise RuntimeError(f"relation {name} does not exist")
        return _FakeQuery(self._tables.get(name, []))


def _month(offset_days=0):
    return datetime.now(UTC).isoformat()


def test_compute_over_a_known_dataset():
    now = datetime.now(UTC).isoformat()
    tables = {
        "applications": [
            {"id": "a1", "status": "APPLIED", "applied_at": now, "opportunity_type": "JOB",
             "internship_id": None, "job_id": "job-1"},
            {"id": "a2", "status": "SHORTLISTED", "applied_at": now, "opportunity_type": "JOB",
             "internship_id": None, "job_id": "job-1"},
            {"id": "a3", "status": "SELECTED", "applied_at": now, "opportunity_type": "INTERNSHIP",
             "internship_id": "int-1", "job_id": None},
            {"id": "a4", "status": "SHORTLISTED", "applied_at": now, "opportunity_type": "JOB",
             "internship_id": None, "job_id": "job-2"},
        ],
        "industry_collaborations": [
            {"status": "ACTIVE"}, {"status": "DRAFT"}, {"status": "COMPLETED"},
        ],
        "interviews": [
            {"status": "SCHEDULED", "scheduled_at": "2099-01-01T10:00:00+00:00"},
            {"status": "COMPLETED", "scheduled_at": "2020-01-01T10:00:00+00:00"},
        ],
        "internships": [
            {"id": "int-1", "title": "SWE Intern", "status": "PUBLISHED", "created_at": now},
        ],
        "jobs": [
            {"id": "job-1", "title": "Backend Engineer", "status": "PUBLISHED", "created_at": now},
            {"id": "job-2", "title": "Frontend Engineer", "status": "DRAFT", "created_at": now},
        ],
        "industry_projects": [],
        "industry_training": [],
        "industry_workshops": [],
        "industry_mentorship": [],
    }
    result = analytics_service.compute_industry_analytics(_FakeClient(tables), "industry-1")

    k = result["kpis"]
    assert k["applications_total"] == 4
    assert k["shortlisted"] == 2
    assert k["selected"] == 1
    assert k["opportunities_total"] == 3
    assert k["opportunities_published"] == 2
    assert k["collaborations_total"] == 3
    assert k["collaborations_active"] == 1
    assert k["interviews_total"] == 2
    assert k["interviews_upcoming"] == 1

    assert result["funnel_counts"]["SHORTLISTED"] == 2
    assert result["funnel_total"] == 4

    breakdown = {b["opportunity_type"]: b for b in result["opportunity_breakdown"]}
    assert breakdown["JOB"]["total"] == 2
    assert breakdown["JOB"]["published"] == 1
    assert breakdown["INTERNSHIP"]["total"] == 1

    assert result["interview_metrics"] == {
        "total": 2, "scheduled": 1, "completed": 1, "cancelled": 0, "upcoming": 1,
    }

    top = {t["id"]: t for t in result["top_opportunities"]}
    assert top["job-1"]["application_count"] == 2
    assert top["job-1"]["title"] == "Backend Engineer"

    assert result["interviews_available"] is True
    # Timeline is present, 6 months, and only ever counts creations.
    assert len(result["timeline"]) == 6
    assert all(set(p) == {"period", "opportunities_created", "applications_received"}
               for p in result["timeline"])


def test_compute_on_empty_account_is_all_zeros_not_error():
    tables = {name: [] for name in (
        "applications", "industry_collaborations", "interviews",
        "internships", "jobs", "industry_projects", "industry_training",
        "industry_workshops", "industry_mentorship",
    )}
    result = analytics_service.compute_industry_analytics(_FakeClient(tables), "industry-1")
    assert result["kpis"]["applications_total"] == 0
    assert result["funnel_total"] == 0
    assert result["top_opportunities"] == []
    assert result["interview_metrics"]["total"] == 0
    assert result["interviews_available"] is True
    assert all(v == 0 for v in result["funnel_counts"].values())


def test_compute_degrades_when_interviews_table_missing():
    tables = {name: [] for name in (
        "applications", "industry_collaborations",
        "internships", "jobs", "industry_projects", "industry_training",
        "industry_workshops", "industry_mentorship",
    )}
    result = analytics_service.compute_industry_analytics(
        _FakeClient(tables, missing={"interviews"}), "industry-1"
    )
    assert result["interviews_available"] is False
    assert result["interview_metrics"]["total"] == 0
    assert "migration 030" in result["historical_note"]


def test_historical_note_disclaims_missing_status_history():
    tables = {name: [] for name in (
        "applications", "industry_collaborations", "interviews",
        "internships", "jobs", "industry_projects", "industry_training",
        "industry_workshops", "industry_mentorship",
    )}
    result = analytics_service.compute_industry_analytics(_FakeClient(tables), "industry-1")
    note = result["historical_note"].lower()
    assert "status" in note and ("history" in note or "changed" in note)


def test_timeline_never_infers_status_transitions():
    """The timeline schema only has creation-based fields -- there is no
    'selected_over_time' / 'shortlisted_over_time' key that would imply
    status history the DB cannot provide."""
    tables = {name: [] for name in (
        "applications", "industry_collaborations", "interviews",
        "internships", "jobs", "industry_projects", "industry_training",
        "industry_workshops", "industry_mentorship",
    )}
    result = analytics_service.compute_industry_analytics(_FakeClient(tables), "industry-1")
    for point in result["timeline"]:
        assert set(point.keys()) == {
            "period", "opportunities_created", "applications_received"
        }
