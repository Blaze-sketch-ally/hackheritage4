"""Tests for the cross-module Industry Participant view:
/api/v1/industry/participants (app.api.industry_participants /
app.services.industry_participant_service).

Service-level tests drive list_participants() with each of the four
source services patched (no live project). Route tests confirm role
guards and wiring, mirroring tests/test_applications.py's shape.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    application_service,
    industry_participant_service,
    industry_project_application_service,
    industry_training_application_service,
    industry_workshop_application_service,
)
from tests.conftest import authenticated_as

client = TestClient(app)


def _application_row(**overrides):
    row = {
        "id": "app-1",
        "student_id": "student-1",
        "student_name": "Ada Lovelace",
        "opportunity_type": "JOB",
        "status": "SHORTLISTED",
        "applied_at": "2026-09-03T00:00:00Z",
        "opportunity": {"id": "job-1", "title": "Frontend Developer", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


def _project_row(**overrides):
    row = {
        "id": "papp-1",
        "student_id": "student-1",
        "student_name": "Ada Lovelace",
        "project_id": "project-1",
        "status": "SELECTED",
        "applied_at": "2026-09-02T00:00:00Z",
        "project": {"id": "project-1", "title": "Smart Manufacturing", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


def _workshop_row(**overrides):
    row = {
        "id": "wapp-1",
        "student_id": "student-2",
        "student_name": "Rahul Sen",
        "workshop_id": "workshop-1",
        "status": "ACCEPTED",
        "applied_at": "2026-09-01T00:00:00Z",
        "workshop": {"id": "workshop-1", "title": "React Workshop", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


def _training_row(**overrides):
    row = {
        "id": "tapp-1",
        "student_id": "student-2",
        "student_name": "Rahul Sen",
        "training_id": "training-1",
        "status": "COMPLETED",
        "applied_at": "2026-08-01T00:00:00Z",
        "training": {"id": "training-1", "title": "Python Training", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


def test_role_guard_forbids_non_industry():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.get(
                "/api/v1/industry/participants", headers={"Authorization": "Bearer token"}
            )
        assert resp.status_code == 403, role


def test_route_merges_all_four_sources():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "list_applications", return_value=[_application_row()]),
        patch.object(
            industry_project_application_service, "list_applications", return_value=[_project_row()]
        ),
        patch.object(
            industry_workshop_application_service, "list_applications", return_value=[_workshop_row()]
        ),
        patch.object(
            industry_training_application_service, "list_applications", return_value=[_training_row()]
        ),
    ):
        resp = client.get(
            "/api/v1/industry/participants", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    records = resp.json()["records"]
    assert len(records) == 4
    types = {r["opportunity_type"] for r in records}
    assert types == {"JOB", "PROJECT", "WORKSHOP", "TRAINING"}


def test_service_computes_correct_opportunity_href_per_source():
    client_mock = MagicMock()
    with (
        patch.object(application_service, "list_applications", return_value=[_application_row()]),
        patch.object(
            industry_project_application_service, "list_applications", return_value=[_project_row()]
        ),
        patch.object(
            industry_workshop_application_service, "list_applications", return_value=[_workshop_row()]
        ),
        patch.object(
            industry_training_application_service, "list_applications", return_value=[_training_row()]
        ),
    ):
        records = industry_participant_service.list_participants(client_mock, "industry-1")

    by_type = {r["opportunity_type"]: r for r in records}
    assert by_type["JOB"]["opportunity_href"] == "/industry/applicants/app-1"
    assert by_type["PROJECT"]["opportunity_href"] == "/industry/projects/project-1/applicants"
    assert by_type["WORKSHOP"]["opportunity_href"] == "/industry/workshops/workshop-1/applicants"
    assert by_type["TRAINING"]["opportunity_href"] == "/industry/training/training-1/applicants"


def test_opportunity_type_filter_only_calls_the_matching_source():
    client_mock = MagicMock()
    with (
        patch.object(application_service, "list_applications", return_value=[]) as apps,
        patch.object(
            industry_project_application_service, "list_applications", return_value=[_project_row()]
        ) as projects,
        patch.object(
            industry_workshop_application_service, "list_applications", return_value=[]
        ) as workshops,
        patch.object(
            industry_training_application_service, "list_applications", return_value=[]
        ) as trainings,
    ):
        records = industry_participant_service.list_participants(
            client_mock, "industry-1", opportunity_type="PROJECT"
        )
    apps.assert_not_called()
    workshops.assert_not_called()
    trainings.assert_not_called()
    projects.assert_called_once()
    assert len(records) == 1
    assert records[0]["opportunity_type"] == "PROJECT"


def test_search_filters_by_resolved_student_name_case_insensitively():
    client_mock = MagicMock()
    with (
        patch.object(application_service, "list_applications", return_value=[_application_row()]),
        patch.object(
            industry_project_application_service, "list_applications", return_value=[_project_row()]
        ),
        patch.object(
            industry_workshop_application_service, "list_applications", return_value=[_workshop_row()]
        ),
        patch.object(
            industry_training_application_service, "list_applications", return_value=[_training_row()]
        ),
    ):
        records = industry_participant_service.list_participants(
            client_mock, "industry-1", search="rahul"
        )
    assert len(records) == 2
    assert all(r["student_name"] == "Rahul Sen" for r in records)


def test_student_centric_grouping_shows_all_of_one_students_records():
    """The exact scenario the product spec describes: one student's
    records span multiple opportunity types, all groupable by student_id."""
    client_mock = MagicMock()
    with (
        patch.object(application_service, "list_applications", return_value=[]),
        patch.object(
            industry_project_application_service, "list_applications", return_value=[]
        ),
        patch.object(
            industry_workshop_application_service, "list_applications", return_value=[_workshop_row()]
        ),
        patch.object(
            industry_training_application_service, "list_applications", return_value=[_training_row()]
        ),
    ):
        records = industry_participant_service.list_participants(client_mock, "industry-1")
    student_ids = {r["student_id"] for r in records}
    assert student_ids == {"student-2"}
    assert {r["opportunity_type"] for r in records} == {"WORKSHOP", "TRAINING"}
