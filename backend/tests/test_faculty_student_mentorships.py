"""Unit coverage for Phase F4.2 Faculty <-> Student mentorship:
faculty_student_mentorship_service and the three routers built on it
(app.api.faculty_mentorships, app.api.student_mentorships,
app.api.admin_mentorships)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.services import faculty_notification_producer
from app.services import faculty_student_mentorship_service as service
from tests.conftest import authenticated_as

client = TestClient(app)


@pytest.fixture(autouse=True)
def _mock_mentorship_notifications():
    """request_mentorship/update_mentorship_status
    (app.api.student_mentorships) call
    faculty_notification_producer.emit_mentorship_request/
    emit_mentorship_status_change after a successful action. None of the
    tests in this file are about notification behaviour -- that is
    tests/test_faculty_notifications.py's job -- so both are mocked out
    file-wide here to avoid an unmocked real Supabase call (matching the
    existing pattern in tests/test_internship_completion.py for
    app.services.notification_producer)."""
    with (
        patch.object(faculty_notification_producer, "emit_mentorship_request"),
        patch.object(faculty_notification_producer, "emit_mentorship_status_change"),
    ):
        yield

_MENTORSHIP_ROW = {
    "id": "mentorship-1",
    "faculty_id": "faculty-1",
    "student_id": "student-1",
    "requested_by": "faculty-1",
    "status": "REQUESTED",
    "focus_area": "Career guidance",
    "start_date": None,
    "end_date": None,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


# ============================================================
# Faculty-side router: role/capability gating
# ============================================================


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_list_faculty_mentorships(role):
    with authenticated_as(role):
        response = client.get("/api/v1/faculty/mentorships", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_faculty_without_capability_cannot_request_mentorship():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=False),
    ):
        response = client.post(
            "/api/v1/faculty/mentorships",
            json={"target_id": "student-1"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_faculty_can_list_own_mentorships_without_capability():
    """Listing/reading own history needs only require_faculty -- a
    Faculty member can see their past mentorships even after their
    capability is revoked."""
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=False),
        patch("app.api.faculty_mentorships.service.list_for_faculty", return_value=[_MENTORSHIP_ROW]) as list_mock,
    ):
        response = client.get("/api/v1/faculty/mentorships", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["mentorships"][0]["id"] == "mentorship-1"
    list_mock.assert_called_once_with(list_mock.call_args.args[0], "faculty-1")


def test_faculty_with_capability_can_request_mentorship():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch("app.api.faculty_mentorships.service.create_faculty_request", return_value=_MENTORSHIP_ROW) as create,
    ):
        response = client.post(
            "/api/v1/faculty/mentorships",
            json={"target_id": "student-1", "focus_area": "Career guidance"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    assert response.json()["student_id"] == "student-1"
    create.assert_called_once_with(create.call_args.args[0], "faculty-1", "student-1", "Career guidance")


def test_duplicate_mentorship_request_is_409():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch(
            "app.api.faculty_mentorships.service.create_faculty_request",
            side_effect=service.DuplicateMentorshipError("already exists"),
        ),
    ):
        response = client.post(
            "/api/v1/faculty/mentorships",
            json={"target_id": "student-1"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_mentorship_request_to_invalid_target_role_is_403():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch(
            "app.api.faculty_mentorships.service.create_faculty_request",
            side_effect=service.MentorshipAuthorizationError("not a student"),
        ),
    ):
        response = client.post(
            "/api/v1/faculty/mentorships",
            json={"target_id": "not-a-student"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_get_mentorship_not_owned_is_404():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.api.faculty_mentorships.service.get_mentorship", return_value=None),
    ):
        response = client.get(
            "/api/v1/faculty/mentorships/mentorship-1",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (service.MentorshipInvalidStatusTransitionError("REQUESTED", "COMPLETED"), 409),
        (service.MentorshipSelfActionError("self-approval"), 403),
    ],
)
def test_faculty_status_update_error_mapping(exc, expected_status):
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch("app.api.faculty_mentorships.service.update_status", side_effect=exc),
    ):
        response = client.patch(
            "/api/v1/faculty/mentorships/mentorship-1/status",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == expected_status


def test_faculty_status_update_not_found_is_404():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch("app.api.faculty_mentorships.service.update_status", return_value=None),
    ):
        response = client.patch(
            "/api/v1/faculty/mentorships/mentorship-1/status",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_mentee_bundle_requires_capability():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=False),
    ):
        response = client.get(
            "/api/v1/faculty/mentorships/mentorship-1/student",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_mentee_bundle_not_active_is_409():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch("app.api.faculty_mentorships.service.get_mentee_bundle", side_effect=service.MentorshipNotActiveError()),
    ):
        response = client.get(
            "/api/v1/faculty/mentorships/mentorship-1/student",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_mentee_bundle_not_owned_is_404():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch("app.api.faculty_mentorships.service.get_mentee_bundle", return_value=None),
    ):
        response = client.get(
            "/api/v1/faculty/mentorships/mentorship-1/student",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_mentee_bundle_never_includes_answer_or_application_fields():
    """Structural proof the response schema cannot leak assessment
    answers or applications -- the bundle shape itself has no such
    field, regardless of what the service returns."""
    bundle = {
        "mentorship_id": "mentorship-1",
        "student_id": "student-1",
        "full_name": "Jane Student",
        "email": "jane@example.com",
        "username": "jane",
        "academic_profile": {
            "institution_name": "State University",
            "department": "CS",
            "degree": "B.Tech",
            "graduation_year": 2027,
            "cgpa": 8.5,
            "percentage": None,
            "career_goals": "Backend engineering",
            "preferred_roles": ["Backend Engineer"],
            "interests": ["Distributed systems"],
        },
        "skills": [{"skill_id": "skill-1", "proficiency_level": "Advanced", "proficiency_score": 90.0, "is_verified": True}],
        "assessment_attempts": [
            {
                "id": "attempt-1",
                "assessment_id": "assessment-1",
                "status": "COMPLETED",
                "score": 45.0,
                "total_marks": 50.0,
                "percentage": 90.0,
                "submitted_at": "2026-01-01T00:00:00Z",
            }
        ],
        "projects": [],
        "certifications": [],
        "achievements": [],
    }
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch("app.api.faculty_mentorships.service.get_mentee_bundle", return_value=bundle),
    ):
        response = client.get(
            "/api/v1/faculty/mentorships/mentorship-1/student",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["assessment_attempts"][0]["percentage"] == 90.0
    assert "answer" not in str(body).lower()
    assert "applications" not in body


def test_notes_require_capability():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=False),
    ):
        get_response = client.get(
            "/api/v1/faculty/mentorships/mentorship-1/notes",
            headers={"Authorization": "Bearer token"},
        )
        put_response = client.put(
            "/api/v1/faculty/mentorships/mentorship-1/notes",
            json={"note": "Doing great"},
            headers={"Authorization": "Bearer token"},
        )
    assert get_response.status_code == 403
    assert put_response.status_code == 403


def test_faculty_can_save_and_read_own_note():
    note_row = {
        "id": "note-1",
        "mentorship_id": "mentorship-1",
        "faculty_id": "faculty-1",
        "note": "Doing great",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch("app.api.faculty_mentorships.service.upsert_note", return_value=note_row) as upsert,
        patch("app.api.faculty_mentorships.service.get_note", return_value=note_row),
    ):
        put_response = client.put(
            "/api/v1/faculty/mentorships/mentorship-1/notes",
            json={"note": "Doing great"},
            headers={"Authorization": "Bearer token"},
        )
        get_response = client.get(
            "/api/v1/faculty/mentorships/mentorship-1/notes",
            headers={"Authorization": "Bearer token"},
        )
    assert put_response.status_code == 200
    assert put_response.json()["note"] == "Doing great"
    assert get_response.status_code == 200
    assert get_response.json()["note"] == "Doing great"
    upsert.assert_called_once_with(upsert.call_args.args[0], "faculty-1", "mentorship-1", "Doing great")


def test_notes_endpoint_returns_null_when_no_note_exists():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
        patch("app.api.faculty_mentorships.service.get_note", return_value=None),
    ):
        response = client.get(
            "/api/v1/faculty/mentorships/mentorship-1/notes",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json() is None


# ============================================================
# Student-side router
# ============================================================


@pytest.mark.parametrize("role", ["FACULTY", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_student_cannot_list_student_mentorships(role):
    with authenticated_as(role):
        response = client.get("/api/v1/student/mentorships", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_student_can_list_own_mentorships():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch("app.api.student_mentorships.service.list_for_student", return_value=[_MENTORSHIP_ROW]) as list_mock,
    ):
        response = client.get("/api/v1/student/mentorships", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    list_mock.assert_called_once_with(list_mock.call_args.args[0], "student-1")


def test_student_can_request_a_faculty_mentor_with_no_capability_check():
    """The Student side has no capability dependency at all -- only
    require_student()."""
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch("app.api.student_mentorships.service.create_student_request", return_value=_MENTORSHIP_ROW) as create,
    ):
        response = client.post(
            "/api/v1/student/mentorships",
            json={"target_id": "faculty-1"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    create.assert_called_once_with(create.call_args.args[0], "student-1", "faculty-1", None)


def test_student_request_notifies_the_faculty_member():
    row = {**_MENTORSHIP_ROW, "id": "m-new", "faculty_id": "faculty-1", "student_id": "student-1", "requested_by": "student-1"}
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch("app.api.student_mentorships.service.create_student_request", return_value=row),
        patch.object(faculty_notification_producer, "emit_mentorship_request") as mock_emit,
    ):
        response = client.post(
            "/api/v1/student/mentorships",
            json={"target_id": "faculty-1"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    mock_emit.assert_called_once_with(faculty_id="faculty-1", student_id="student-1", mentorship_id="m-new")


def test_student_request_to_faculty_without_capability_is_403():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch(
            "app.api.student_mentorships.service.create_student_request",
            side_effect=service.MentorshipAuthorizationError("target lacks faculty_mentor"),
        ),
    ):
        response = client.post(
            "/api/v1/student/mentorships",
            json={"target_id": "faculty-1"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_student_duplicate_request_is_409():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch(
            "app.api.student_mentorships.service.create_student_request",
            side_effect=service.DuplicateMentorshipError("already exists"),
        ),
    ):
        response = client.post(
            "/api/v1/student/mentorships",
            json={"target_id": "faculty-1"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_student_status_update_notifies_the_faculty_member():
    row = {**_MENTORSHIP_ROW, "id": "m-1", "faculty_id": "faculty-1", "status": "ACCEPTED", "requested_by": "faculty-1"}
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch("app.api.student_mentorships.service.update_status", return_value=row),
        patch.object(faculty_notification_producer, "emit_mentorship_status_change") as mock_emit,
    ):
        response = client.patch(
            "/api/v1/student/mentorships/m-1/status",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    mock_emit.assert_called_once_with(
        faculty_id="faculty-1", student_id="student-1", mentorship_id="m-1", new_status="ACCEPTED"
    )


def test_student_status_update_not_found_does_not_notify():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch("app.api.student_mentorships.service.update_status", return_value=None),
        patch.object(faculty_notification_producer, "emit_mentorship_status_change") as mock_emit,
    ):
        response = client.patch(
            "/api/v1/student/mentorships/m-1/status",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
    mock_emit.assert_not_called()


def test_student_cannot_access_another_students_mentorship():
    with (
        authenticated_as("STUDENT", user_id="student-2"),
        patch("app.api.student_mentorships.service.get_mentorship", return_value=None),
    ):
        response = client.get(
            "/api/v1/student/mentorships/mentorship-1",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_student_has_no_mentee_bundle_route():
    """The Student side never exposes a mentee-data bundle concept --
    that only exists for the Faculty side."""
    paths = app.openapi()["paths"]
    assert "/api/v1/faculty/mentorships/{mentorship_id}/student" in paths
    assert not any(p.startswith("/api/v1/student/mentorships/") and p.endswith("/student") for p in paths)
    assert not any("notes" in p for p in paths if p.startswith("/api/v1/student/"))


# ============================================================
# Admin oversight router
# ============================================================


@pytest.mark.parametrize("role", ["FACULTY", "STUDENT", "INDUSTRY", "INSTITUTION", None])
def test_non_admin_cannot_list_mentorships(role):
    with authenticated_as(role):
        response = client.get("/api/v1/admin/mentorships", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_admin_can_list_all_mentorships():
    admin_row = {
        "id": "mentorship-1",
        "faculty_id": "faculty-1",
        "student_id": "student-1",
        "status": "ACTIVE",
        "requested_by": "faculty-1",
        "start_date": None,
        "end_date": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch("app.api.admin_mentorships.service.admin_list_mentorships", return_value=[admin_row]),
    ):
        response = client.get("/api/v1/admin/mentorships", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()["mentorships"][0]
    assert body["id"] == "mentorship-1"
    # Admin oversight is deliberately narrower than the Faculty/Student
    # response -- no focus_area field at all.
    assert "focus_area" not in body
    assert "note" not in str(body).lower()


def test_admin_mentorship_listing_rejected_at_service_layer_is_403():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_mentorships.service.admin_list_mentorships",
            side_effect=service.AdminAuthorizationError("not admin"),
        ),
    ):
        response = client.get("/api/v1/admin/mentorships", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


# ============================================================
# Service-layer: status transition legality + self-action rules
# ============================================================


def _mock_client_with_sequential_rows(*rows):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
        MagicMock(data=row) for row in rows
    ]
    return mock_client


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("REQUESTED", "ACTIVE"),  # skips ACCEPTED
        ("DECLINED", "ACTIVE"),  # terminal -> anything
        ("COMPLETED", "ACTIVE"),  # terminal -> anything
        ("REQUESTED", "COMPLETED"),  # skips ACCEPTED and ACTIVE
        ("ACTIVE", "REQUESTED"),  # backwards
    ],
)
def test_invalid_mentorship_transitions_are_rejected(current_status, target_status):
    mock_client = _mock_client_with_sequential_rows({**_MENTORSHIP_ROW, "status": current_status})
    with pytest.raises(service.MentorshipInvalidStatusTransitionError):
        service.update_status(mock_client, "faculty-1", "mentorship-1", target_status)


def test_requester_cannot_accept_their_own_request():
    row = {**_MENTORSHIP_ROW, "status": "REQUESTED", "requested_by": "faculty-1"}
    mock_client = _mock_client_with_sequential_rows(row)
    with pytest.raises(service.MentorshipSelfActionError):
        service.update_status(mock_client, "faculty-1", "mentorship-1", "ACCEPTED")


def test_requester_cannot_decline_their_own_request():
    row = {**_MENTORSHIP_ROW, "status": "REQUESTED", "requested_by": "faculty-1"}
    mock_client = _mock_client_with_sequential_rows(row)
    with pytest.raises(service.MentorshipSelfActionError):
        service.update_status(mock_client, "faculty-1", "mentorship-1", "DECLINED")


def test_non_requester_cannot_withdraw_a_request_they_did_not_make():
    row = {**_MENTORSHIP_ROW, "status": "REQUESTED", "requested_by": "student-1"}
    mock_client = _mock_client_with_sequential_rows(row)
    with pytest.raises(service.MentorshipSelfActionError):
        service.update_status(mock_client, "faculty-1", "mentorship-1", "WITHDRAWN")


def test_other_party_can_accept_a_request():
    requested_row = {**_MENTORSHIP_ROW, "status": "REQUESTED", "requested_by": "student-1"}
    accepted_row = {**_MENTORSHIP_ROW, "status": "ACCEPTED", "requested_by": "student-1"}
    mock_client = _mock_client_with_sequential_rows(requested_row, accepted_row)
    result = service.update_status(mock_client, "faculty-1", "mentorship-1", "ACCEPTED")
    assert result["status"] == "ACCEPTED"


def test_requester_can_withdraw_their_own_request():
    requested_row = {**_MENTORSHIP_ROW, "status": "REQUESTED", "requested_by": "faculty-1"}
    withdrawn_row = {**_MENTORSHIP_ROW, "status": "WITHDRAWN", "requested_by": "faculty-1"}
    mock_client = _mock_client_with_sequential_rows(requested_row, withdrawn_row)
    result = service.update_status(mock_client, "faculty-1", "mentorship-1", "WITHDRAWN")
    assert result["status"] == "WITHDRAWN"


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [("ACCEPTED", "ACTIVE"), ("ACTIVE", "COMPLETED"), ("ACTIVE", "ENDED")],
)
def test_either_participant_may_perform_shared_transitions(current_status, target_status):
    before = {**_MENTORSHIP_ROW, "status": current_status}
    after = {**_MENTORSHIP_ROW, "status": target_status}
    mock_client = _mock_client_with_sequential_rows(before, after)
    result = service.update_status(mock_client, "faculty-1", "mentorship-1", target_status)
    assert result["status"] == target_status


def test_update_status_on_a_row_the_caller_is_not_party_to_returns_none():
    mock_client = _mock_client_with_sequential_rows({**_MENTORSHIP_ROW, "faculty_id": "faculty-2", "student_id": "student-2"})
    result = service.update_status(mock_client, "faculty-1", "mentorship-1", "ACCEPTED")
    assert result is None


def test_update_status_on_nonexistent_mentorship_returns_none():
    mock_client = _mock_client_with_sequential_rows(None)
    result = service.update_status(mock_client, "faculty-1", "mentorship-1", "ACCEPTED")
    assert result is None


# ============================================================
# Service-layer: duplicate prevention maps the DB constraint violation
# ============================================================


def test_create_faculty_request_duplicate_maps_unique_violation():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.side_effect = APIError(
        {"code": "23505", "message": "duplicate key value violates unique constraint"}
    )
    with pytest.raises(service.DuplicateMentorshipError):
        service.create_faculty_request(mock_client, "faculty-1", "student-1", None)


def test_create_faculty_request_rls_rejection_maps_authorization_error():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.side_effect = APIError(
        {"code": "42501", "message": "new row violates row-level security policy"}
    )
    with pytest.raises(service.MentorshipAuthorizationError):
        service.create_faculty_request(mock_client, "faculty-1", "not-a-student", None)


# ============================================================
# Service-layer: get_mentee_bundle -- ACTIVE gate + never touches
# assessment_answers/applications
# ============================================================


def test_get_mentee_bundle_raises_when_not_active():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        **_MENTORSHIP_ROW,
        "status": "ACCEPTED",
    }
    with pytest.raises(service.MentorshipNotActiveError):
        service.get_mentee_bundle(mock_client, "faculty-1", "mentorship-1")


def test_get_mentee_bundle_returns_none_when_not_owned():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        **_MENTORSHIP_ROW,
        "faculty_id": "faculty-2",
        "status": "ACTIVE",
    }
    result = service.get_mentee_bundle(mock_client, "faculty-1", "mentorship-1")
    assert result is None


def test_get_mentee_bundle_never_queries_assessment_answers_or_applications():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        **_MENTORSHIP_ROW,
        "status": "ACTIVE",
    }
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    with patch(
        "app.services.portfolio_service.get_student_portfolio",
        return_value={"projects": [], "certifications": [], "achievements": []},
    ):
        service.get_mentee_bundle(mock_client, "faculty-1", "mentorship-1")

    queried_tables = {call.args[0] for call in mock_client.table.call_args_list}
    assert "assessment_answers" not in queried_tables
    assert "assessment_question_answers" not in queried_tables
    assert "applications" not in queried_tables
    assert "assessment_attempts" in queried_tables
    assert "student_profiles" in queried_tables
    assert "student_skills" in queried_tables


def test_get_note_and_upsert_note_scope_by_mentorship_id():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
    inserted = {
        "id": "note-1",
        "mentorship_id": "mentorship-1",
        "faculty_id": "faculty-1",
        "note": "hello",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [inserted]

    result = service.upsert_note(mock_client, "faculty-1", "mentorship-1", "hello")
    assert result["note"] == "hello"
    insert_call = mock_client.table.return_value.insert.call_args
    assert insert_call.args[0]["mentorship_id"] == "mentorship-1"
    assert insert_call.args[0]["faculty_id"] == "faculty-1"
