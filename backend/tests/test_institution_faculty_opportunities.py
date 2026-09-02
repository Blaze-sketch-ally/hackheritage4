"""Unit coverage for Institution-owned Faculty opportunities and their
expression-of-interest review (Phase F3.4,
backend/app/api/institution_faculty_opportunities.py,
backend/app/services/institution_faculty_opportunity_service.py).

Structural twin of test_industry_faculty_opportunities.py."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_faculty_opportunity_service as service
from tests.conftest import authenticated_as

client = TestClient(app)

_OPP_ROW = {
    "id": "opp-1",
    "institution_id": "institution-1",
    "title": "Institution-Faculty Development Opportunity",
    "description": "A joint initiative for Faculty.",
    "location": "Remote",
    "work_mode": "REMOTE",
    "capacity": 5,
    "eligibility_criteria": None,
    "application_deadline": "2026-06-01",
    "start_date": "2026-07-01",
    "status": "DRAFT",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}

_EOI_ROW = {
    "id": "eoi-1",
    "faculty_id": "faculty-1",
    "opportunity_id": "opp-1",
    "status": "SUBMITTED",
    "message": "Interested.",
    "reviewed_by": None,
    "reviewer_note": None,
    "created_at": "2026-01-02T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
}


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None])
def test_non_institution_cannot_create_faculty_opportunity(role):
    with authenticated_as(role):
        response = client.post(
            "/api/v1/institution/faculty-opportunities",
            json={"title": "T", "description": "D"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None])
def test_non_institution_cannot_list_own_faculty_opportunities(role):
    with authenticated_as(role):
        response = client.get(
            "/api/v1/institution/faculty-opportunities", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None])
def test_non_institution_cannot_review_eois(role):
    with authenticated_as(role):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_institution_can_create_own_opportunity():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(service, "create_opportunity", return_value=_OPP_ROW) as create,
    ):
        response = client.post(
            "/api/v1/institution/faculty-opportunities",
            json={"title": "Institution-Faculty Development Opportunity", "description": "desc"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    assert response.json()["owner_id"] == "institution-1"
    create.assert_called_once_with(create.call_args.args[0], "institution-1", create.call_args.args[2])


def test_institution_cannot_create_on_behalf_of_another_institution():
    with authenticated_as("INSTITUTION", user_id="institution-1"):
        response = client.post(
            "/api/v1/institution/faculty-opportunities",
            json={"title": "T", "description": "D", "institution_id": "institution-2"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_institution_cannot_modify_another_institutions_opportunity():
    with (
        authenticated_as("INSTITUTION", user_id="institution-2"),
        patch.object(service, "update_opportunity", return_value=None) as update,
    ):
        response = client.put(
            "/api/v1/institution/faculty-opportunities/opp-1",
            json={"title": "Hijacked"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    assert update.call_args.args[1] == "institution-2"


def test_institution_sees_only_their_own_opportunities_including_drafts():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(service, "list_opportunities", return_value=[_OPP_ROW]) as list_own,
    ):
        response = client.get(
            "/api/v1/institution/faculty-opportunities", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["opportunities"][0]["status"] == "DRAFT"
    list_own.assert_called_once_with(list_own.call_args.args[0], "institution-1")


def test_institution_can_publish_own_opportunity():
    published = {**_OPP_ROW, "status": "PUBLISHED"}
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(service, "publish_opportunity", return_value=published),
    ):
        response = client.post(
            "/api/v1/institution/faculty-opportunities/opp-1/publish",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"


def test_institution_can_close_own_opportunity():
    closed = {**_OPP_ROW, "status": "CLOSED"}
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(service, "close_opportunity", return_value=closed),
    ):
        response = client.post(
            "/api/v1/institution/faculty-opportunities/opp-1/close",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


# ---- IDOR: publish/close scoped to the caller's own opportunity ----


def test_institution_cannot_publish_another_institutions_opportunity():
    with (
        authenticated_as("INSTITUTION", user_id="institution-2"),
        patch.object(service, "publish_opportunity", return_value=None) as publish,
    ):
        response = client.post(
            "/api/v1/institution/faculty-opportunities/opp-1/publish",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    assert publish.call_args.args[1] == "institution-2"


def test_institution_cannot_close_another_institutions_opportunity():
    with (
        authenticated_as("INSTITUTION", user_id="institution-2"),
        patch.object(service, "close_opportunity", return_value=None) as close,
    ):
        response = client.post(
            "/api/v1/institution/faculty-opportunities/opp-1/close",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    assert close.call_args.args[1] == "institution-2"


# ---- ACCEPTED/REJECTED are terminal ----


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("ACCEPTED", "REJECTED"),
        ("ACCEPTED", "UNDER_REVIEW"),
        ("REJECTED", "ACCEPTED"),
        ("REJECTED", "UNDER_REVIEW"),
    ],
)
def test_accepted_and_rejected_eois_are_terminal(current_status, target_status):
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(
            service,
            "review_eoi",
            side_effect=service.EoiInvalidStatusTransitionError(current_status, target_status),
        ),
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": target_status},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_review_eoi_service_rejects_transitions_out_of_terminal_states():
    from unittest.mock import MagicMock

    for current_status in ("ACCEPTED", "REJECTED"):
        for target_status in ("UNDER_REVIEW", "ACCEPTED", "REJECTED"):
            mock_client = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
                **_EOI_ROW,
                "status": current_status,
            }
            with pytest.raises(service.EoiInvalidStatusTransitionError):
                service.review_eoi(mock_client, "institution-1", "eoi-1", target_status, None)


# ---- Message / reviewer-note immutability (schema layer) ----


def test_review_request_cannot_smuggle_a_message_edit():
    with authenticated_as("INSTITUTION", user_id="institution-1"):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW", "message": "rewritten"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_review_request_cannot_smuggle_a_reviewed_by_override():
    with authenticated_as("INSTITUTION", user_id="institution-1"):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW", "reviewed_by": "someone-else"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_institution_can_list_eois_for_own_opportunities():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(service, "list_eois_for_own_opportunities", return_value=[_EOI_ROW]) as list_eois,
    ):
        response = client.get(
            "/api/v1/institution/faculty-opportunities/eoi", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["expressions"][0]["source"] == "INSTITUTION"
    list_eois.assert_called_once_with(list_eois.call_args.args[0], "institution-1")


def test_institution_can_review_an_eoi_for_their_own_opportunity():
    reviewed = {**_EOI_ROW, "status": "UNDER_REVIEW"}
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(service, "review_eoi", return_value=reviewed) as review,
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert review.call_args.args[1] == "institution-1"


def test_reviewing_an_eoi_for_another_institutions_opportunity_is_404():
    with (
        authenticated_as("INSTITUTION", user_id="institution-2"),
        patch.object(service, "review_eoi", return_value=None),
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_institution_eoi_listing_never_queries_the_industry_table():
    """Structural isolation: the Institution service module must never
    touch faculty_industry_opportunity_expressions / industry_faculty_
    opportunities, since Institution must never see Industry EOIs."""
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "opp-1", "title": "T"}
    ]
    mock_client.table.return_value.select.return_value.in_.return_value.order.return_value.execute.return_value.data = []
    service.list_eois_for_own_opportunities(mock_client, "institution-1")
    queried_tables = {call.args[0] for call in mock_client.table.call_args_list if call.args}
    assert queried_tables <= {
        "institution_faculty_opportunities",
        "faculty_institution_opportunity_expressions",
    }
    assert "industry_faculty_opportunities" not in queried_tables
    assert "faculty_industry_opportunity_expressions" not in queried_tables


def test_invalid_eoi_review_transition_is_409():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(
            service,
            "review_eoi",
            side_effect=service.EoiInvalidStatusTransitionError("DRAFT", "ACCEPTED"),
        ),
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409
