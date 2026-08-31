"""Tests for the Portfolio API (Phase 1N):
app.services.portfolio_service and the /portfolio routes.

No live Supabase project or real token is used anywhere in this file --
the auth dependency chain is mocked (see conftest.py), and the Supabase
client/service layer is mocked directly, matching the existing pattern in
test_opportunities.py. Cross-account ownership/RLS proofs (including the
industry applicant-portfolio join-through-ownership-chain) live in
tests/integration/test_portfolio_live.py -- this file proves the
service/route layer's own logic (role guards, identity handling,
validation), not RLS itself.
"""

from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import application_service, portfolio_service
from tests.conftest import authenticated_as

client = TestClient(app)


def _project_row(**overrides):
    row = {
        "id": str(uuid4()),
        "student_id": str(uuid4()),
        "title": "Campus Event Finder",
        "description": "A React + FastAPI app for discovering campus events.",
        "technologies": ["React", "FastAPI", "PostgreSQL"],
        "project_url": "https://events.example.com",
        "github_url": "https://github.com/example/events",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _certification_row(**overrides):
    row = {
        "id": str(uuid4()),
        "student_id": str(uuid4()),
        "name": "AWS Certified Cloud Practitioner",
        "issuer": "Amazon Web Services",
        "issue_date": "2025-06-01",
        "credential_url": "https://aws.amazon.com/verification/abc123",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


# ============================================================
# Projects: student can create/list/update/delete own
# ============================================================


def test_student_can_create_project():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "create_project", return_value=_project_row()),
    ):
        response = client.post(
            "/api/v1/portfolio/projects",
            json={
                "title": "Campus Event Finder",
                "description": "A React + FastAPI app for discovering campus events.",
                "technologies": ["React", "FastAPI"],
                "project_url": "https://events.example.com",
                "github_url": "https://github.com/example/events",
            },
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    assert response.json()["title"] == "Campus Event Finder"


def test_industry_cannot_create_project():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.post(
            "/api/v1/portfolio/projects",
            json={"title": "Fake", "description": "Fake project."},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_student_can_list_own_projects():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "list_projects", return_value=[_project_row()]),
    ):
        response = client.get("/api/v1/portfolio/projects", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert len(response.json()["projects"]) == 1


def test_student_can_update_own_project():
    project_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "update_project", return_value=_project_row(title="Updated Title")),
    ):
        response = client.patch(
            f"/api/v1/portfolio/projects/{project_id}",
            json={"title": "Updated Title"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


def test_updating_another_students_project_returns_404_not_403():
    """update_project returns None when RLS matches zero rows -- the
    route must not leak whether the row exists at all, same
    non-existence-leaking shape as every other ownership check in this
    project (e.g. opportunity_service.update_opportunity)."""
    project_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "update_project", return_value=None),
    ):
        response = client.patch(
            f"/api/v1/portfolio/projects/{project_id}",
            json={"title": "Hijacked"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_student_can_delete_own_project():
    project_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "delete_project", return_value=True),
    ):
        response = client.delete(
            f"/api/v1/portfolio/projects/{project_id}", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 204


def test_deleting_another_students_project_returns_404():
    project_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "delete_project", return_value=False),
    ):
        response = client.delete(
            f"/api/v1/portfolio/projects/{project_id}", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_project_update_never_accepts_client_supplied_student_id():
    """ProjectUpdateRequest has no student_id field at all --
    extra="forbid" rejects any attempt to smuggle one in."""
    project_id = uuid4()
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.patch(
            f"/api/v1/portfolio/projects/{project_id}",
            json={"title": "X", "student_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


# ============================================================
# Certifications: same authorization matrix
# ============================================================


def test_student_can_create_certification():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "create_certification", return_value=_certification_row()),
    ):
        response = client.post(
            "/api/v1/portfolio/certifications",
            json={"name": "AWS Certified Cloud Practitioner", "issuer": "Amazon Web Services"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201


def test_industry_cannot_create_certification():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.post(
            "/api/v1/portfolio/certifications",
            json={"name": "Fake", "issuer": "Fake Org"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_student_can_update_own_certification():
    certification_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(
            portfolio_service, "update_certification", return_value=_certification_row(name="Updated")
        ),
    ):
        response = client.patch(
            f"/api/v1/portfolio/certifications/{certification_id}",
            json={"name": "Updated"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200


def test_updating_another_students_certification_returns_404():
    certification_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "update_certification", return_value=None),
    ):
        response = client.patch(
            f"/api/v1/portfolio/certifications/{certification_id}",
            json={"name": "Hijacked"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_student_can_delete_own_certification():
    certification_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "delete_certification", return_value=True),
    ):
        response = client.delete(
            f"/api/v1/portfolio/certifications/{certification_id}", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 204


# ============================================================
# GET /portfolio -- combined view
# ============================================================


def test_get_my_portfolio_combines_projects_and_certifications():
    student_id = str(uuid4())
    with (
        authenticated_as("STUDENT", user_id=student_id),
        patch.object(
            portfolio_service,
            "get_student_portfolio",
            return_value={
                "student_id": student_id,
                "projects": [_project_row(student_id=student_id)],
                "certifications": [_certification_row(student_id=student_id)],
            },
        ) as mock_get,
    ):
        response = client.get("/api/v1/portfolio", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["projects"]) == 1
    assert len(body["certifications"]) == 1
    # Identity always from the token, never a client-supplied student_id
    # -- there is no request body/query param this endpoint could even
    # accept one through.
    mock_get.assert_called_once()
    assert mock_get.call_args[0][1] == student_id


def test_faculty_cannot_access_portfolio():
    with authenticated_as("FACULTY", user_id="faculty-1"):
        response = client.get("/api/v1/portfolio", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


# ============================================================
# Validation
# ============================================================


def test_create_project_rejects_missing_title():
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.post(
            "/api/v1/portfolio/projects",
            json={"description": "Missing a title."},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_project_rejects_empty_description():
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.post(
            "/api/v1/portfolio/projects",
            json={"title": "X", "description": ""},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_project_rejects_invalid_github_url():
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.post(
            "/api/v1/portfolio/projects",
            json={"title": "X", "description": "Y", "github_url": "not-a-url"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_project_accepts_valid_https_url():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(portfolio_service, "create_project", return_value=_project_row()),
    ):
        response = client.post(
            "/api/v1/portfolio/projects",
            json={"title": "X", "description": "Y", "github_url": "https://github.com/example/repo"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201


def test_create_certification_rejects_missing_issuer():
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.post(
            "/api/v1/portfolio/certifications",
            json={"name": "X"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_certification_rejects_invalid_date():
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.post(
            "/api/v1/portfolio/certifications",
            json={"name": "X", "issuer": "Y", "issue_date": "not-a-date"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_certification_rejects_invalid_credential_url():
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.post(
            "/api/v1/portfolio/certifications",
            json={"name": "X", "issuer": "Y", "credential_url": "ftp://not-http"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_project_rejects_malformed_payload():
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.post(
            "/api/v1/portfolio/projects",
            json={"title": "X", "description": "Y", "technologies": "not-a-list"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


# ============================================================
# Industry read of an applicant's portfolio
# (GET /applications/{id}/portfolio -- app/api/applications.py)
# ============================================================


def test_industry_owner_can_read_applicant_portfolio():
    application_id = uuid4()
    student_id = str(uuid4())
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            application_service,
            "get_application",
            return_value={"id": str(application_id), "student_id": student_id, "opportunity_id": str(uuid4())},
        ),
        patch.object(
            portfolio_service,
            "get_student_portfolio",
            return_value={"student_id": student_id, "projects": [_project_row(student_id=student_id)], "certifications": []},
        ),
    ):
        response = client.get(
            f"/api/v1/applications/{application_id}/portfolio", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert len(response.json()["projects"]) == 1


def test_unrelated_industry_gets_404_for_applicant_portfolio():
    """get_application() returns None when RLS's own "Industry can view
    applications for their own opportunities" policy matches zero rows
    -- this route must turn that into a 404, never reach
    get_student_portfolio at all (proven by portfolio_service never
    being patched/called here)."""
    application_id = uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(application_service, "get_application", return_value=None),
        patch.object(portfolio_service, "get_student_portfolio") as mock_portfolio,
    ):
        response = client.get(
            f"/api/v1/applications/{application_id}/portfolio", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404
    mock_portfolio.assert_not_called()


def test_student_cannot_access_applicant_portfolio_endpoint():
    application_id = uuid4()
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.get(
            f"/api/v1/applications/{application_id}/portfolio", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_industry_cannot_modify_portfolio_no_write_routes_exist():
    """There is no POST/PATCH/DELETE route anywhere under
    /applications/{id}/portfolio or accepting an industry-authenticated
    write to portfolio_projects/portfolio_certifications -- confirmed
    structurally via the OpenAPI schema rather than probing one guessed
    URL."""
    schema = app.openapi()
    portfolio_paths = {
        path: methods
        for path, methods in schema["paths"].items()
        if "portfolio" in path
    }
    for path, methods in portfolio_paths.items():
        if path.startswith("/api/v1/applications/"):
            assert set(methods.keys()) == {"get"}, f"{path} must be read-only for industry"
