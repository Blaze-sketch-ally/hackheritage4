"""Unit coverage for Faculty opportunity discovery (Phase F3.2, corrected
in Phase F3.4 to source from industry_faculty_opportunities /
institution_faculty_opportunities instead of the Student-facing
industry_projects/training/workshops/mentorship tables) and expressions
of interest (Phase F3.4,
backend/app/api/faculty_opportunities.py,
backend/app/services/faculty_opportunity_service.py,
backend/app/services/faculty_opportunity_expression_service.py)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import faculty_opportunity_service
from tests.conftest import authenticated_as

client = TestClient(app)

_SAMPLE = [
    {
        "id": "opp-1",
        "source": "INDUSTRY",
        "owner_id": "industry-1",
        "owner_name": "Acme Corp",
        "title": "Industry-Academia Data Science Collaboration",
        "description": "Collaborate on a joint dataset.",
        "location": "Remote",
        "work_mode": "REMOTE",
        "capacity": 2,
        "eligibility_criteria": None,
        "application_deadline": "2026-06-01",
        "start_date": "2026-07-01",
        "status": "PUBLISHED",
        "created_at": "2026-02-01T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
    }
]

_EOI_ROW = {
    "id": "eoi-1",
    "source": "INDUSTRY",
    "opportunity_id": "opp-1",
    "faculty_id": "faculty-1",
    "status": "SUBMITTED",
    "message": "I would love to collaborate.",
    "reviewed_by": None,
    "reviewer_note": None,
    "created_at": "2026-02-02T00:00:00Z",
    "updated_at": "2026-02-02T00:00:00Z",
}


# ---- Discovery: authorization ----


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_list_opportunities(role):
    with authenticated_as(role):
        response = client.get("/api/v1/faculty/opportunities", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_faculty_can_list_opportunities():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_service.list_published_opportunities",
            return_value=_SAMPLE,
        ) as list_opportunities,
    ):
        response = client.get("/api/v1/faculty/opportunities", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()
    assert body["opportunities"][0]["source"] == "INDUSTRY"
    assert body["opportunities"][0]["owner_name"] == "Acme Corp"
    list_opportunities.assert_called_once()
    assert list_opportunities.call_args.args[1] is None


@pytest.mark.parametrize("source", ["INDUSTRY", "INSTITUTION"])
def test_faculty_can_filter_by_source(source):
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_service.list_published_opportunities",
            return_value=_SAMPLE,
        ) as list_opportunities,
    ):
        response = client.get(
            f"/api/v1/faculty/opportunities?source={source}",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    list_opportunities.assert_called_once_with(list_opportunities.call_args.args[0], [source])


def test_invalid_source_is_rejected_before_touching_the_service():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_service.list_published_opportunities"
        ) as list_opportunities,
    ):
        response = client.get(
            "/api/v1/faculty/opportunities?source=NOT_A_REAL_SOURCE",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422
    list_opportunities.assert_not_called()


# ---- Discovery service: only PUBLISHED rows from the correct (Faculty) tables ----


def _mock_client_returning(rows_by_table: dict[str, list[dict]]) -> MagicMock:
    client_mock = MagicMock()
    table_mocks: dict[str, MagicMock] = {}

    def table_side_effect(name: str) -> MagicMock:
        if name not in table_mocks:
            table_mock = MagicMock()
            table_mock.select.return_value.eq.return_value.execute.return_value.data = rows_by_table.get(
                name, []
            )
            table_mock.select.return_value.in_.return_value.execute.return_value.data = rows_by_table.get(
                "industry_profiles", []
            )
            table_mocks[name] = table_mock
        return table_mocks[name]

    client_mock.table.side_effect = table_side_effect
    return client_mock


def test_service_reads_from_the_correct_faculty_tables_only():
    """The whole point of the F3.4 correction: discovery must never touch
    industry_projects/training/workshops/mentorship again."""
    mock_client = _mock_client_returning(
        {
            "industry_faculty_opportunities": [
                {
                    "id": "opp-1",
                    "industry_id": "industry-1",
                    "title": "Title",
                    "description": "desc",
                    "location": None,
                    "work_mode": None,
                    "capacity": 2,
                    "eligibility_criteria": None,
                    "application_deadline": None,
                    "start_date": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
    )

    results = faculty_opportunity_service.list_published_opportunities(mock_client, ["INDUSTRY"])

    assert len(results) == 1
    assert results[0]["source"] == "INDUSTRY"
    queried_tables = {call.args[0] for call in mock_client.table.call_args_list if call.args}
    assert "industry_faculty_opportunities" in queried_tables
    assert "industry_projects" not in queried_tables
    assert "industry_training" not in queried_tables
    assert "industry_workshops" not in queried_tables
    assert "industry_mentorship" not in queried_tables
    table_mock = mock_client.table("industry_faculty_opportunities")
    table_mock.select.return_value.eq.assert_any_call("status", "PUBLISHED")


def test_service_covers_both_sources_when_none_requested():
    mock_client = _mock_client_returning({})
    faculty_opportunity_service.list_published_opportunities(mock_client, None)
    queried_tables = {call.args[0] for call in mock_client.table.call_args_list if call.args}
    assert {"industry_faculty_opportunities", "institution_faculty_opportunities"} <= queried_tables


def test_institution_owner_name_is_not_fabricated():
    """No institution identity table with a public-read policy exists --
    owner_name must stay None for INSTITUTION sources, never guessed."""
    mock_client = _mock_client_returning(
        {
            "institution_faculty_opportunities": [
                {
                    "id": "opp-2",
                    "institution_id": "institution-1",
                    "title": "Title",
                    "description": "desc",
                    "location": None,
                    "work_mode": None,
                    "capacity": None,
                    "eligibility_criteria": None,
                    "application_deadline": None,
                    "start_date": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
    )
    results = faculty_opportunity_service.list_published_opportunities(mock_client, ["INSTITUTION"])
    assert results[0]["owner_name"] is None


# ---- Expressions of interest (Faculty side) ----


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_list_own_eois(role):
    with authenticated_as(role):
        response = client.get("/api/v1/faculty/opportunities/eoi/mine", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_faculty_can_list_own_eois():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_expression_service.list_own_expressions",
            return_value=[_EOI_ROW],
        ),
    ):
        response = client.get("/api/v1/faculty/opportunities/eoi/mine", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["expressions"][0]["status"] == "SUBMITTED"


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_express_interest(role):
    with authenticated_as(role):
        response = client.post(
            "/api/v1/faculty/opportunities/INDUSTRY/opp-1/express-interest",
            json={"message": "hi"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_faculty_can_express_interest_in_a_published_opportunity():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_service.get_published_opportunity",
            return_value=_SAMPLE[0],
        ),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_expression_service.express_interest",
            return_value=_EOI_ROW,
        ) as express_interest,
    ):
        response = client.post(
            "/api/v1/faculty/opportunities/INDUSTRY/opp-1/express-interest",
            json={"message": "I would love to collaborate."},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "SUBMITTED"
    express_interest.assert_called_once()
    assert express_interest.call_args.args[1:] == ("INDUSTRY", "faculty-1", "opp-1", "I would love to collaborate.")


def test_cannot_express_interest_in_a_non_published_opportunity():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_service.get_published_opportunity",
            return_value=None,
        ),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_expression_service.express_interest"
        ) as express_interest,
    ):
        response = client.post(
            "/api/v1/faculty/opportunities/INDUSTRY/does-not-exist/express-interest",
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    express_interest.assert_not_called()


def test_duplicate_expression_of_interest_is_rejected():
    from postgrest.exceptions import APIError

    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_service.get_published_opportunity",
            return_value=_SAMPLE[0],
        ),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_expression_service.express_interest",
            side_effect=APIError({"code": "23505", "message": "duplicate"}),
        ),
    ):
        response = client.post(
            "/api/v1/faculty/opportunities/INDUSTRY/opp-1/express-interest",
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_faculty_can_withdraw_own_eoi():
    withdrawn = {**_EOI_ROW, "status": "WITHDRAWN"}
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_expression_service.withdraw_expression",
            return_value=withdrawn,
        ) as withdraw,
    ):
        response = client.post(
            "/api/v1/faculty/opportunities/eoi/INDUSTRY/eoi-1/withdraw",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "WITHDRAWN"
    withdraw.assert_called_once_with(withdraw.call_args.args[0], "INDUSTRY", "faculty-1", "eoi-1")


def test_express_interest_service_scopes_insert_to_the_caller_and_target():
    from app.services import faculty_opportunity_expression_service

    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "eoi-1"}]
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = (
        _EOI_ROW
    )

    faculty_opportunity_expression_service.express_interest(
        mock_client, "INDUSTRY", "faculty-1", "opp-1", "hello"
    )

    insert_call = mock_client.table.return_value.insert.call_args
    payload = insert_call.args[0]
    assert payload["faculty_id"] == "faculty-1"
    assert payload["opportunity_id"] == "opp-1"
    assert payload["status"] == "DRAFT"  # INSERT is always a fresh draft; SUBMITTED is a separate UPDATE


def test_duplicate_expression_of_interest_raises_the_real_unique_violation():
    """The service does not swallow or reinterpret the DB's own
    (faculty_id, opportunity_id) unique constraint -- it propagates
    unchanged so the route layer's APIError(23505) -> 409 mapping applies."""
    from postgrest.exceptions import APIError

    from app.services import faculty_opportunity_expression_service

    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.side_effect = APIError(
        {"code": "23505", "message": "duplicate key value violates unique constraint"}
    )

    with pytest.raises(APIError) as exc_info:
        faculty_opportunity_expression_service.express_interest(
            mock_client, "INDUSTRY", "faculty-1", "opp-1", None
        )
    assert exc_info.value.code == "23505"


def test_list_own_expressions_is_scoped_to_the_caller_faculty_id():
    """Faculty A cannot see Faculty B's EOIs: the service always filters
    by the caller's own faculty_id on both source tables."""
    from app.services import faculty_opportunity_expression_service

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = (
        []
    )

    faculty_opportunity_expression_service.list_own_expressions(mock_client, "faculty-A")

    eq_calls = mock_client.table.return_value.select.return_value.eq.call_args_list
    assert all(call.args == ("faculty_id", "faculty-A") for call in eq_calls)
    assert len(eq_calls) == 2  # once per source table (industry + institution)


def test_withdraw_of_someone_elses_or_nonexistent_eoi_is_404():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty_opportunities.faculty_opportunity_expression_service.withdraw_expression",
            return_value=None,
        ),
    ):
        response = client.post(
            "/api/v1/faculty/opportunities/eoi/INDUSTRY/not-mine/withdraw",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
