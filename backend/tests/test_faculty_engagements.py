"""Unit coverage for Faculty-side Engagement access (Phase F4.1,
backend/app/api/faculty_engagements.py,
backend/app/services/faculty_engagement_service.py)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import faculty_engagement_service
from tests.conftest import authenticated_as

client = TestClient(app)

_ENGAGEMENT_ROW = {
    "id": "eng-1",
    "source_kind": "INDUSTRY_EOI",
    "industry_eoi_id": "eoi-1",
    "institution_eoi_id": None,
    "faculty_id": "faculty-1",
    "organization_id": "industry-1",
    "status": "PLANNED",
    "start_date": None,
    "end_date": None,
    "notes": None,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_list_engagements(role):
    with authenticated_as(role):
        response = client.get("/api/v1/faculty/engagements", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_faculty_can_list_own_engagements():
    from unittest.mock import patch

    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_engagements.faculty_engagement_service.list_own_engagements",
            return_value=[_ENGAGEMENT_ROW],
        ) as list_engagements,
    ):
        response = client.get("/api/v1/faculty/engagements", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["engagements"][0]["status"] == "PLANNED"
    assert list_engagements.call_args.args[1] == "faculty-1"


def test_service_scopes_engagement_listing_to_the_callers_own_faculty_id():
    """Faculty A cannot see Faculty B's engagements: the service always
    filters by the caller's own faculty_id."""
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = (
        []
    )
    faculty_engagement_service.list_own_engagements(mock_client, "faculty-A")

    eq_call = mock_client.table.return_value.select.return_value.eq.call_args
    assert eq_call.args == ("faculty_id", "faculty-A")


def test_faculty_has_no_write_path_to_engagements():
    """Structural: there is no PATCH/PUT/POST route under
    /faculty/engagements at all -- Faculty is view-only in this phase.
    Checked via the actual exposed OpenAPI schema rather than internal
    route objects, which are less stable across FastAPI versions."""
    paths = app.openapi()["paths"]
    assert "/api/v1/faculty/engagements" in paths
    assert set(paths["/api/v1/faculty/engagements"].keys()) == {"get"}
