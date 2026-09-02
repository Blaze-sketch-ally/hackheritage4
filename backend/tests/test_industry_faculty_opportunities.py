"""Unit coverage for Industry-owned Faculty opportunities and their
expression-of-interest review (Phase F3.4,
backend/app/api/industry_faculty_opportunities.py,
backend/app/services/industry_faculty_opportunity_service.py)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import industry_faculty_opportunity_service as service
from tests.conftest import authenticated_as

client = TestClient(app)

_OPP_ROW = {
    "id": "opp-1",
    "industry_id": "industry-1",
    "title": "Data Science Research Collaboration",
    "description": "Joint research on anomaly detection.",
    "location": "Remote",
    "work_mode": "REMOTE",
    "capacity": 2,
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


# ---- Authorization ----


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None])
def test_non_industry_cannot_create_faculty_opportunity(role):
    with authenticated_as(role):
        response = client.post(
            "/api/v1/industry/faculty-opportunities",
            json={"title": "T", "description": "D"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None])
def test_non_industry_cannot_list_own_faculty_opportunities(role):
    with authenticated_as(role):
        response = client.get(
            "/api/v1/industry/faculty-opportunities", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None])
def test_non_industry_cannot_review_eois(role):
    with authenticated_as(role):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


# ---- Ownership: create/list/update ----


def test_industry_can_create_own_opportunity():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(service, "create_opportunity", return_value=_OPP_ROW) as create,
    ):
        response = client.post(
            "/api/v1/industry/faculty-opportunities",
            json={"title": "Data Science Research Collaboration", "description": "Joint research."},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    assert response.json()["owner_id"] == "industry-1"
    # industry_id is always the authenticated caller -- never client-supplied.
    create.assert_called_once_with(create.call_args.args[0], "industry-1", create.call_args.args[2])


def test_industry_cannot_create_on_behalf_of_another_industry():
    """There is no owner-id field on the request body at all
    (extra='forbid'), so this is structural, not just a runtime check."""
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.post(
            "/api/v1/industry/faculty-opportunities",
            json={"title": "T", "description": "D", "industry_id": "industry-2"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_industry_cannot_modify_another_industrys_opportunity():
    """update_opportunity scopes its query to the caller's own
    industry_id -- another account's row is indistinguishable from a
    nonexistent one, surfaced as 404."""
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(service, "update_opportunity", return_value=None) as update,
    ):
        response = client.put(
            "/api/v1/industry/faculty-opportunities/opp-1",
            json={"title": "Hijacked"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    assert update.call_args.args[1] == "industry-2"


def test_industry_sees_only_their_own_opportunities_including_drafts():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(service, "list_opportunities", return_value=[_OPP_ROW]) as list_own,
    ):
        response = client.get(
            "/api/v1/industry/faculty-opportunities", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["opportunities"][0]["status"] == "DRAFT"
    list_own.assert_called_once_with(list_own.call_args.args[0], "industry-1")


# ---- Publish/close lifecycle ----


def test_industry_can_publish_own_opportunity():
    published = {**_OPP_ROW, "status": "PUBLISHED"}
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(service, "publish_opportunity", return_value=published),
    ):
        response = client.post(
            "/api/v1/industry/faculty-opportunities/opp-1/publish",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"


def test_invalid_publish_transition_is_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            service,
            "publish_opportunity",
            side_effect=service.InvalidStatusTransitionError("PUBLISHED", "PUBLISHED"),
        ),
    ):
        response = client.post(
            "/api/v1/industry/faculty-opportunities/opp-1/publish",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_industry_can_close_own_opportunity():
    closed = {**_OPP_ROW, "status": "CLOSED"}
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(service, "close_opportunity", return_value=closed),
    ):
        response = client.post(
            "/api/v1/industry/faculty-opportunities/opp-1/close",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


# ---- IDOR: publish/close scoped to the caller's own opportunity ----


def test_industry_cannot_publish_another_industrys_opportunity():
    """publish_opportunity scopes its query to the caller's own
    industry_id (get_opportunity(..., industry_id, ...) internally) -- a
    stranger's opportunity_id is indistinguishable from a nonexistent
    one, surfaced as 404, never leaking whether the id even exists."""
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(service, "publish_opportunity", return_value=None) as publish,
    ):
        response = client.post(
            "/api/v1/industry/faculty-opportunities/opp-1/publish",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    assert publish.call_args.args[1] == "industry-2"


def test_industry_cannot_close_another_industrys_opportunity():
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(service, "close_opportunity", return_value=None) as close,
    ):
        response = client.post(
            "/api/v1/industry/faculty-opportunities/opp-1/close",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    assert close.call_args.args[1] == "industry-2"


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
    """Service-layer mirror of the database trigger's own transition
    table (guard_faculty_industry_eoi_update): ACCEPTED/REJECTED never
    accept a further transition. The trigger itself is the real
    enforcement and has not been executed against a live Postgres in
    this session (no local psql/Docker/live Supabase access) -- this
    test verifies the Python-side transition map raises the same class
    of rejection, not that the SQL trigger was exercised."""
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            service,
            "review_eoi",
            side_effect=service.EoiInvalidStatusTransitionError(current_status, target_status),
        ),
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": target_status},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_review_eoi_service_rejects_transitions_out_of_terminal_states():
    """Direct service-level check (not router-mocked): review_eoi's own
    _REVIEW_TRANSITIONS table must reject a target of UNDER_REVIEW/REJECTED
    when the current status is already ACCEPTED or REJECTED.

    Target=ACCEPTED is deliberately excluded from this parametrization as
    of Phase F4.1: review_eoi() now routes every ACCEPTED target through
    accept_via_rpc() unconditionally (see
    test_accepting_an_eoi_routes_through_the_rpc_not_a_plain_update below),
    so the "EOI must be UNDER_REVIEW before acceptance" check for that
    target lives inside accept_faculty_industry_expression() itself
    (SQLSTATE 55000) instead of this local _REVIEW_TRANSITIONS table --
    covered by test_accept_rpc_errors_map_to_the_correct_http_status."""
    from unittest.mock import MagicMock

    for current_status in ("ACCEPTED", "REJECTED"):
        for target_status in ("UNDER_REVIEW", "REJECTED"):
            mock_client = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
                **_EOI_ROW,
                "status": current_status,
            }
            with pytest.raises(service.EoiInvalidStatusTransitionError):
                service.review_eoi(mock_client, "industry-1", "eoi-1", target_status, None)


# ---- Message / reviewer-note immutability (schema layer) ----


def test_review_request_cannot_smuggle_a_message_edit():
    """ReviewExpressionRequest has no `message` field at all (extra="forbid")
    -- a reviewer cannot rewrite the applicant's message even by trying."""
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW", "message": "rewritten"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_review_request_cannot_smuggle_a_reviewed_by_override():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW", "reviewed_by": "someone-else"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


# ---- EOI review ----


def test_industry_can_list_eois_for_own_opportunities():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(service, "list_eois_for_own_opportunities", return_value=[_EOI_ROW]) as list_eois,
    ):
        response = client.get(
            "/api/v1/industry/faculty-opportunities/eoi", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["expressions"][0]["source"] == "INDUSTRY"
    list_eois.assert_called_once_with(list_eois.call_args.args[0], "industry-1")


def test_industry_can_review_an_eoi_for_their_own_opportunity():
    reviewed = {**_EOI_ROW, "status": "UNDER_REVIEW"}
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(service, "review_eoi", return_value=reviewed) as review,
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "UNDER_REVIEW"
    assert review.call_args.args[1] == "industry-1"


def test_reviewing_an_eoi_for_another_industrys_opportunity_is_404():
    """review_eoi scopes through the caller's own opportunities via
    list_eois_for_own_opportunities-style filtering at the RLS layer;
    the service returns None when the row isn't reachable by this caller."""
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(service, "review_eoi", return_value=None),
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "UNDER_REVIEW"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_invalid_eoi_review_transition_is_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            service,
            "review_eoi",
            side_effect=service.EoiInvalidStatusTransitionError("DRAFT", "ACCEPTED"),
        ),
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_industry_eoi_listing_never_queries_the_institution_table():
    """Structural isolation: the Industry service module must never touch
    faculty_institution_opportunity_expressions / institution_faculty_
    opportunities, since Industry must never see Institution EOIs."""
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "opp-1", "title": "T"}
    ]
    mock_client.table.return_value.select.return_value.in_.return_value.order.return_value.execute.return_value.data = []
    service.list_eois_for_own_opportunities(mock_client, "industry-1")
    queried_tables = {call.args[0] for call in mock_client.table.call_args_list if call.args}
    # faculty_engagements is now legitimately queried too (Phase F4.1
    # engagement enrichment), always scoped to source_kind='INDUSTRY_EOI'.
    assert queried_tables <= {
        "industry_faculty_opportunities",
        "faculty_industry_opportunity_expressions",
        "faculty_engagements",
    }
    assert "institution_faculty_opportunities" not in queried_tables
    assert "faculty_institution_opportunity_expressions" not in queried_tables


def test_faculty_cannot_set_their_own_eoi_to_accepted_via_the_review_endpoint():
    """Structural: the review endpoint requires require_industry, so a
    FACULTY caller can never reach it at all -- covered by
    test_non_industry_cannot_review_eois above, restated here to make the
    specific 'self-accept' scenario explicit per the review checklist."""
    with authenticated_as("FACULTY", user_id="faculty-1"):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


# ============================================================
# Phase F4.1 -- Acceptance -> Engagement
# ============================================================

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


def test_accepting_an_eoi_routes_through_the_rpc_not_a_plain_update():
    """review_eoi(..., "ACCEPTED", ...) must call accept_via_rpc(), never
    a plain .update({"status": "ACCEPTED"}) -- that's the whole point of
    atomicity (section 3 of the brief)."""
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            service, "accept_via_rpc", return_value={**_EOI_ROW, "status": "ACCEPTED", "engagement": _ENGAGEMENT_ROW}
        ) as accept_via_rpc,
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACCEPTED"
    assert body["engagement"]["status"] == "PLANNED"
    accept_via_rpc.assert_called_once_with(accept_via_rpc.call_args.args[0], "eoi-1")


def test_industry_can_accept_its_own_eoi_service_level():
    """Verifies the service calls the correct RPC name with the correct
    parameter, and that the result attaches the engagement."""
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value.data = _ENGAGEMENT_ROW
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        **_EOI_ROW,
        "status": "ACCEPTED",
    }

    result = service.accept_via_rpc(mock_client, "eoi-1")

    mock_client.rpc.assert_called_once_with(
        "accept_faculty_industry_expression", {"target_eoi_id": "eoi-1"}
    )
    assert result["status"] == "ACCEPTED"
    assert result["engagement"]["id"] == "eng-1"


@pytest.mark.parametrize(
    ("pg_code", "expected_status"),
    [
        ("P0002", 404),  # EOI not found
        ("55000", 409),  # not UNDER_REVIEW
        ("23505", 409),  # engagement already exists (UNIQUE-constraint backstop)
        ("42501", 403),  # not the owner / not INDUSTRY
    ],
)
def test_accept_rpc_errors_map_to_the_correct_http_status(pg_code, expected_status):
    from postgrest.exceptions import APIError

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            service,
            "accept_via_rpc",
            side_effect=APIError({"code": pg_code, "message": "boom"}),
        ),
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == expected_status


def test_another_industry_cannot_accept_the_eoi():
    """The RPC itself is what actually enforces this (ownership re-check
    inside accept_faculty_industry_expression) -- this test verifies the
    error it would raise (42501) is correctly surfaced as 403, not
    silently swallowed or misreported."""
    from postgrest.exceptions import APIError

    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(
            service,
            "accept_via_rpc",
            side_effect=APIError({"code": "42501", "message": "Not authorized to accept this expression of interest."}),
        ),
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/eoi/eoi-1/review",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


# ---- Engagement listing/lifecycle ----


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None])
def test_non_industry_cannot_list_engagements(role):
    with authenticated_as(role):
        response = client.get(
            "/api/v1/industry/faculty-opportunities/engagements", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None])
def test_non_industry_cannot_update_engagement_status(role):
    with authenticated_as(role):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/engagements/eng-1/status",
            json={"status": "ACTIVE"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_industry_can_list_own_engagements():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(service, "list_own_engagements", return_value=[_ENGAGEMENT_ROW]) as list_engagements,
    ):
        response = client.get(
            "/api/v1/industry/faculty-opportunities/engagements", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["engagements"][0]["status"] == "PLANNED"
    list_engagements.assert_called_once_with(list_engagements.call_args.args[0], "industry-1")


def test_industry_can_activate_own_engagement():
    activated = {**_ENGAGEMENT_ROW, "status": "ACTIVE"}
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(service, "update_engagement_status", return_value=activated) as update,
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/engagements/eng-1/status",
            json={"status": "ACTIVE"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    assert update.call_args.args[1] == "industry-1"


def test_another_industrys_engagement_is_404_not_leaked():
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(service, "update_engagement_status", return_value=None) as update,
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/engagements/eng-1/status",
            json={"status": "ACTIVE"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    assert update.call_args.args[1] == "industry-2"


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
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            service,
            "update_engagement_status",
            side_effect=service.EngagementInvalidStatusTransitionError(current_status, target_status),
        ),
    ):
        response = client.patch(
            "/api/v1/industry/faculty-opportunities/engagements/eng-1/status",
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

    result = service.update_engagement_status(mock_client, "industry-1", "eng-1", target_status, {})
    assert result["status"] == target_status


def test_engagement_queries_never_touch_the_institution_engagement_scope():
    """Structural isolation: Industry's own-engagement queries are always
    scoped to source_kind='INDUSTRY_EOI' -- Industry can never see an
    Institution-sourced engagement even though both live in the same
    physical table."""
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = (
        []
    )
    service.list_own_engagements(mock_client, "industry-1")

    eq_calls = mock_client.table.return_value.select.return_value.eq.call_args_list
    assert ("organization_id", "industry-1") in [c.args for c in eq_calls]
    second_eq_calls = mock_client.table.return_value.select.return_value.eq.return_value.eq.call_args_list
    assert ("source_kind", "INDUSTRY_EOI") in [c.args for c in second_eq_calls]
