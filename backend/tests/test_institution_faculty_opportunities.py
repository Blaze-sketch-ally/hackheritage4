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
    """Target=ACCEPTED excluded here as of Phase F4.1 -- see the industry
    test file's identical test for why (routed through accept_via_rpc())."""
    from unittest.mock import MagicMock

    for current_status in ("ACCEPTED", "REJECTED"):
        for target_status in ("UNDER_REVIEW", "REJECTED"):
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
    # faculty_engagements is now legitimately queried too (Phase F4.1
    # engagement enrichment), always scoped to source_kind='INSTITUTION_EOI'.
    assert queried_tables <= {
        "institution_faculty_opportunities",
        "faculty_institution_opportunity_expressions",
        "faculty_engagements",
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


# ============================================================
# Phase F4.1 -- Acceptance -> Engagement
# ============================================================

_ENGAGEMENT_ROW = {
    "id": "eng-1",
    "source_kind": "INSTITUTION_EOI",
    "industry_eoi_id": None,
    "institution_eoi_id": "eoi-1",
    "faculty_id": "faculty-1",
    "organization_id": "institution-1",
    "status": "PLANNED",
    "start_date": None,
    "end_date": None,
    "notes": None,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


def test_accepting_an_eoi_routes_through_the_rpc_not_a_plain_update():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(
            service, "accept_via_rpc", return_value={**_EOI_ROW, "status": "ACCEPTED", "engagement": _ENGAGEMENT_ROW}
        ) as accept_via_rpc,
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACCEPTED"
    assert body["engagement"]["status"] == "PLANNED"
    accept_via_rpc.assert_called_once_with(accept_via_rpc.call_args.args[0], "eoi-1")


def test_institution_can_accept_its_own_eoi_service_level():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value.data = _ENGAGEMENT_ROW
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        **_EOI_ROW,
        "status": "ACCEPTED",
    }

    result = service.accept_via_rpc(mock_client, "eoi-1")

    mock_client.rpc.assert_called_once_with(
        "accept_faculty_institution_expression", {"target_eoi_id": "eoi-1"}
    )
    assert result["status"] == "ACCEPTED"
    assert result["engagement"]["id"] == "eng-1"


@pytest.mark.parametrize(
    ("pg_code", "expected_status"),
    [
        ("P0002", 404),
        ("55000", 409),
        ("23505", 409),
        ("42501", 403),
    ],
)
def test_accept_rpc_errors_map_to_the_correct_http_status(pg_code, expected_status):
    from postgrest.exceptions import APIError

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(
            service,
            "accept_via_rpc",
            side_effect=APIError({"code": pg_code, "message": "boom"}),
        ),
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == expected_status


def test_another_institution_cannot_accept_the_eoi():
    from postgrest.exceptions import APIError

    with (
        authenticated_as("INSTITUTION", user_id="institution-2"),
        patch.object(
            service,
            "accept_via_rpc",
            side_effect=APIError({"code": "42501", "message": "Not authorized to accept this expression of interest."}),
        ),
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


# ---- Engagement listing/lifecycle ----


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None])
def test_non_institution_cannot_list_engagements(role):
    with authenticated_as(role):
        response = client.get(
            "/api/v1/institution/faculty-opportunities/engagements", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None])
def test_non_institution_cannot_update_engagement_status(role):
    with authenticated_as(role):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/engagements/eng-1/status",
            json={"status": "ACTIVE"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_institution_can_list_own_engagements():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(service, "list_own_engagements", return_value=[_ENGAGEMENT_ROW]) as list_engagements,
    ):
        response = client.get(
            "/api/v1/institution/faculty-opportunities/engagements", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["engagements"][0]["status"] == "PLANNED"
    list_engagements.assert_called_once_with(list_engagements.call_args.args[0], "institution-1")


def test_institution_can_activate_own_engagement():
    activated = {**_ENGAGEMENT_ROW, "status": "ACTIVE"}
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(service, "update_engagement_status", return_value=activated) as update,
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/engagements/eng-1/status",
            json={"status": "ACTIVE"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    assert update.call_args.args[1] == "institution-1"


def test_another_institutions_engagement_is_404_not_leaked():
    with (
        authenticated_as("INSTITUTION", user_id="institution-2"),
        patch.object(service, "update_engagement_status", return_value=None) as update,
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/engagements/eng-1/status",
            json={"status": "ACTIVE"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    assert update.call_args.args[1] == "institution-2"


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("PLANNED", "COMPLETED"),
        ("COMPLETED", "ACTIVE"),
        ("COMPLETED", "CANCELLED"),
        ("CANCELLED", "ACTIVE"),
        ("CANCELLED", "COMPLETED"),
    ],
)
def test_invalid_engagement_transitions_are_rejected(current_status, target_status):
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(
            service,
            "update_engagement_status",
            side_effect=service.EngagementInvalidStatusTransitionError(current_status, target_status),
        ),
    ):
        response = client.patch(
            "/api/v1/institution/faculty-opportunities/engagements/eng-1/status",
            json={"status": target_status if target_status in ("ACTIVE", "COMPLETED", "CANCELLED") else "ACTIVE"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


@pytest.mark.parametrize(("current_status", "target_status"), [("PLANNED", "ACTIVE"), ("PLANNED", "CANCELLED"), ("ACTIVE", "COMPLETED"), ("ACTIVE", "CANCELLED")])
def test_valid_engagement_transitions_service_level(current_status, target_status):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        **_ENGAGEMENT_ROW,
        "status": current_status,
    }
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        **_ENGAGEMENT_ROW,
        "status": target_status,
    }

    result = service.update_engagement_status(mock_client, "institution-1", "eng-1", target_status, {})
    assert result["status"] == target_status


def test_engagement_queries_never_touch_the_industry_engagement_scope():
    """Structural isolation: Institution's own-engagement queries are
    always scoped to source_kind='INSTITUTION_EOI' -- Institution can
    never see an Industry-sourced engagement."""
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = (
        []
    )
    service.list_own_engagements(mock_client, "institution-1")

    eq_calls = mock_client.table.return_value.select.return_value.eq.call_args_list
    assert ("organization_id", "institution-1") in [c.args for c in eq_calls]
    second_eq_calls = mock_client.table.return_value.select.return_value.eq.return_value.eq.call_args_list
    assert ("source_kind", "INSTITUTION_EOI") in [c.args for c in second_eq_calls]
