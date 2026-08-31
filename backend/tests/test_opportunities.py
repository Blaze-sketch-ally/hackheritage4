"""Tests for the Opportunity API (Phase 1M):
app.services.opportunity_service and the /opportunities routes.

No live Supabase project or real token is used anywhere in this file --
the auth dependency chain is mocked (see conftest.py), and the Supabase
client/service layer is mocked directly, matching the existing pattern in
test_career_roles.py. Cross-account ownership/RLS proofs live in
tests/integration/test_opportunities_live.py -- this file proves the
service/route layer's own logic (role guards, error translation,
identity handling), not RLS itself.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.services import application_service, opportunity_service
from app.services.skill_alignment_service import (
    AlignmentStatus,
    SkillAlignmentResult,
    SkillRequirement,
)
from tests.conftest import authenticated_as

client = TestClient(app)


def _opportunity_row(**overrides):
    row = {
        "id": str(uuid4()),
        "industry_id": str(uuid4()),
        "title": "Backend Developer Internship",
        "description": "Build APIs.",
        "opportunity_type": "INTERNSHIP",
        "location": "Remote",
        "status": "DRAFT",
        "published_at": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


# ============================================================
# Creation: industry can, student cannot
# ============================================================


def test_industry_can_create_opportunity():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(opportunity_service, "create_opportunity", return_value=_opportunity_row()),
    ):
        response = client.post(
            "/api/v1/opportunities",
            json={"title": "Backend Developer Internship", "opportunity_type": "INTERNSHIP"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"


def test_student_cannot_create_opportunity():
    with authenticated_as("STUDENT"):
        response = client.post(
            "/api/v1/opportunities",
            json={"title": "Fake Posting", "opportunity_type": "JOB"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_create_opportunity_never_accepts_client_supplied_status_or_industry_id():
    """OpportunityCreateRequest has no status/industry_id field at all --
    extra="forbid" rejects any attempt to smuggle one in."""
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.post(
            "/api/v1/opportunities",
            json={
                "title": "Backend Developer Internship",
                "opportunity_type": "INTERNSHIP",
                "status": "PUBLISHED",
            },
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_service_create_opportunity_always_forces_draft():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [_opportunity_row()]

    opportunity_service.create_opportunity(mock_client, "industry-1", {"title": "X", "opportunity_type": "JOB"})

    insert_call = mock_client.table.return_value.insert.call_args
    inserted = insert_call.args[0]
    assert inserted["status"] == "DRAFT"
    assert inserted["industry_id"] == "industry-1"


# ============================================================
# Ownership: owner can update, other industry cannot (RLS returns 0 rows)
# ============================================================


def test_owner_can_update_opportunity():
    opportunity_id = uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            opportunity_service, "update_opportunity", return_value=_opportunity_row(id=str(opportunity_id))
        ),
    ):
        response = client.patch(
            f"/api/v1/opportunities/{opportunity_id}",
            json={"title": "Updated Title"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200


def test_unrelated_industry_update_returns_404_not_500():
    """RLS silently matches zero rows for an opportunity the caller
    doesn't own -- update_opportunity() returns None, and the route must
    turn that into a clean 404, never leak whether the row exists."""
    opportunity_id = uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(opportunity_service, "update_opportunity", return_value=None),
    ):
        response = client.patch(
            f"/api/v1/opportunities/{opportunity_id}",
            json={"title": "Hijacked"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_student_cannot_update_opportunity():
    with authenticated_as("STUDENT"):
        response = client.patch(
            f"/api/v1/opportunities/{uuid4()}",
            json={"title": "Hijacked"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_editing_closed_opportunity_returns_409():
    """The trigger raises 42501 for any metadata edit once CLOSED -- the
    route must translate this into 409, not a generic 500."""
    opportunity_id = uuid4()
    error = APIError({"message": "Cannot modify a closed opportunity.", "code": "42501"})
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(opportunity_service, "update_opportunity", side_effect=error),
    ):
        response = client.patch(
            f"/api/v1/opportunities/{opportunity_id}",
            json={"title": "Trying anyway"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


# ============================================================
# Publishing: owner can publish, student cannot
# ============================================================


def test_owner_can_publish_draft_opportunity():
    opportunity_id = uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            opportunity_service,
            "publish_opportunity",
            return_value=_opportunity_row(id=str(opportunity_id), status="PUBLISHED", published_at="2026-01-02T00:00:00Z"),
        ),
    ):
        response = client.post(
            f"/api/v1/opportunities/{opportunity_id}/publish", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"


def test_student_cannot_publish_opportunity():
    with authenticated_as("STUDENT"):
        response = client.post(
            f"/api/v1/opportunities/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_publishing_closed_opportunity_returns_409():
    opportunity_id = uuid4()
    error = APIError({"message": "Invalid opportunity status transition: CLOSED -> PUBLISHED", "code": "42501"})
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(opportunity_service, "publish_opportunity", side_effect=error),
    ):
        response = client.post(
            f"/api/v1/opportunities/{opportunity_id}/publish", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 409


def test_owner_can_close_published_opportunity():
    opportunity_id = uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            opportunity_service, "close_opportunity", return_value=_opportunity_row(id=str(opportunity_id), status="CLOSED")
        ),
    ):
        response = client.post(
            f"/api/v1/opportunities/{opportunity_id}/close", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


# ============================================================
# Student visibility: published visible, draft/closed hidden
# ============================================================


def test_list_opportunities_defaults_to_published_only():
    mock_client = MagicMock()
    query = mock_client.table.return_value.select.return_value
    query.eq.return_value.order.return_value.execute.return_value.data = [_opportunity_row(status="PUBLISHED")]

    opportunity_service.list_opportunities(mock_client, mine_only=False)

    query.eq.assert_any_call("status", "PUBLISHED")


def test_mine_true_requires_industry_role():
    with authenticated_as("STUDENT"):
        response = client.get("/api/v1/opportunities?mine=true", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_get_opportunity_not_found_returns_404():
    """Covers both 'genuinely does not exist' and 'exists but is a DRAFT/
    CLOSED belonging to someone else' -- RLS returns None either way, and
    the route must never distinguish between them (would leak existence)."""
    with (
        authenticated_as("STUDENT"),
        patch.object(opportunity_service, "get_opportunity", return_value=None),
    ):
        response = client.get(f"/api/v1/opportunities/{uuid4()}", headers={"Authorization": "Bearer token"})
    assert response.status_code == 404


# ============================================================
# Requirements: valid accepted, invalid rejected, duplicate rejected
# ============================================================


def test_replace_requirements_accepts_valid_payload():
    opportunity_id = uuid4()
    skill_id = str(uuid4())
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            opportunity_service, "get_opportunity", return_value=_opportunity_row(id=str(opportunity_id), status="DRAFT")
        ),
        patch.object(opportunity_service, "replace_requirements", return_value=[]),
        patch.object(
            opportunity_service,
            "get_requirements",
            return_value=[SkillRequirement(skill_id, "Python", Decimal(70), Decimal("1.0"))],
        ),
    ):
        response = client.put(
            f"/api/v1/opportunities/{opportunity_id}/requirements",
            json={"requirements": [{"skill_id": skill_id, "required_level": "70", "weight": "1.0"}]},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["requirements"][0]["skill_name"] == "Python"


def test_replace_requirements_rejects_required_level_out_of_range():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.put(
            f"/api/v1/opportunities/{uuid4()}/requirements",
            json={"requirements": [{"skill_id": str(uuid4()), "required_level": "150", "weight": "1.0"}]},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_replace_requirements_rejects_negative_weight():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.put(
            f"/api/v1/opportunities/{uuid4()}/requirements",
            json={"requirements": [{"skill_id": str(uuid4()), "required_level": "70", "weight": "-1"}]},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_replace_requirements_rejects_duplicate_skill():
    opportunity_id = uuid4()
    skill_id = str(uuid4())
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            opportunity_service, "get_opportunity", return_value=_opportunity_row(id=str(opportunity_id), status="DRAFT")
        ),
    ):
        response = client.put(
            f"/api/v1/opportunities/{opportunity_id}/requirements",
            json={
                "requirements": [
                    {"skill_id": skill_id, "required_level": "70", "weight": "1.0"},
                    {"skill_id": skill_id, "required_level": "60", "weight": "1.0"},
                ]
            },
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_replace_requirements_rejected_once_opportunity_is_published():
    """The explicit app-layer DRAFT check (see the route's own comment
    for why this isn't left to the RLS-side-effect alone)."""
    opportunity_id = uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            opportunity_service,
            "get_opportunity",
            return_value=_opportunity_row(id=str(opportunity_id), status="PUBLISHED"),
        ),
    ):
        response = client.put(
            f"/api/v1/opportunities/{opportunity_id}/requirements",
            json={"requirements": []},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_student_cannot_replace_requirements():
    with authenticated_as("STUDENT"):
        response = client.put(
            f"/api/v1/opportunities/{uuid4()}/requirements",
            json={"requirements": []},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_get_requirements_skips_deactivated_skill_embed():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [
        {"skill_id": "s1", "required_level": "70.00", "weight": "1.00", "skill": {"name": "Python"}},
        {"skill_id": "s2", "required_level": "60.00", "weight": "1.00", "skill": None},
    ]
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = response

    requirements = opportunity_service.get_requirements(mock_client, uuid4())

    assert len(requirements) == 1
    assert requirements[0].skill_name == "Python"


# ============================================================
# Applicant detail (Phase 1N) -- the "Applicant" step of
# Industry -> My Opportunities -> Applicants -> Applicant -> Portfolio.
# Portfolio itself is tested in test_portfolio.py
# (GET /applications/{id}/portfolio); this covers the candidate
# overview + skill-alignment breakdown only.
# ============================================================


def _applicant_detail(**overrides):
    detail = {
        "id": str(uuid4()),
        "student_id": str(uuid4()),
        "student_name": "Asha Verma",
        "status": "APPLIED",
        "cover_note": None,
        "overall_match_score": Decimal("82.5"),
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "skills": [
            SkillAlignmentResult(
                skill_id=str(uuid4()),
                skill_name="Python",
                required_level=Decimal(70),
                student_score=Decimal(90),
                gap=Decimal(0),
                weight=Decimal("1.0"),
                status=AlignmentStatus.STRONG,
            )
        ],
    }
    detail.update(overrides)
    return detail


def test_industry_owner_can_view_applicant_detail():
    opportunity_id, application_id = uuid4(), uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_applicant_detail", return_value=_applicant_detail()),
    ):
        response = client.get(
            f"/api/v1/opportunities/{opportunity_id}/applicants/{application_id}",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["student_name"] == "Asha Verma"
    assert len(body["skills"]) == 1
    assert body["skills"][0]["status"] == "STRONG"


def test_applicant_detail_never_leaks_answer_keys_or_raw_evidence():
    """The response shape itself (ApplicantDetailResponse) has no field
    that could carry a raw assessment answer or answer key -- confirmed
    structurally rather than by string-matching one response body."""
    opportunity_id, application_id = uuid4(), uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_applicant_detail", return_value=_applicant_detail()),
    ):
        response = client.get(
            f"/api/v1/opportunities/{opportunity_id}/applicants/{application_id}",
            headers={"Authorization": "Bearer token"},
        )
    body = response.json()
    forbidden_fields = {"answer_key", "answer_keys", "selected_option_ids", "correct_option_ids", "raw_score"}
    assert forbidden_fields.isdisjoint(body.keys())
    assert forbidden_fields.isdisjoint(body["skills"][0].keys())


def test_unrelated_industry_gets_404_for_applicant_detail():
    opportunity_id, application_id = uuid4(), uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(application_service, "get_applicant_detail", return_value=None),
    ):
        response = client.get(
            f"/api/v1/opportunities/{opportunity_id}/applicants/{application_id}",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_student_cannot_view_applicant_detail():
    opportunity_id, application_id = uuid4(), uuid4()
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.get(
            f"/api/v1/opportunities/{opportunity_id}/applicants/{application_id}",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403
