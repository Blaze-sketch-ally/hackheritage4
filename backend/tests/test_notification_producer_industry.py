"""Tests for the Industry-facing notification producers added alongside
the Workshop/Project application pipelines and industry_notifications
(055_industry_notifications.sql): emit_new_application,
emit_application_withdrawn, emit_workshop_status_change,
emit_project_status_change. Same no-live-DB shape as
tests/test_notification_producer.py -- `get_supabase` is mocked.
"""

from unittest.mock import MagicMock, patch

from app.services import notification_producer


def _insert_payload(mock_supabase: MagicMock) -> dict:
    return mock_supabase.table.return_value.insert.call_args.args[0]


def test_emit_new_application_writes_industry_notification_for_workshop():
    fake = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake):
        notification_producer.emit_new_application(
            industry_id="industry-1",
            kind="WORKSHOP",
            related_entity_id="workshop-1",
            opportunity_title="Intro to Git",
            student_name="Ada Lovelace",
        )
    fake.table.assert_called_once_with("industry_notifications")
    payload = _insert_payload(fake)
    assert payload["industry_id"] == "industry-1"
    assert payload["type"] == "NEW_APPLICATION"
    assert payload["related_entity_type"] == "WORKSHOP_APPLICATION"
    assert payload["related_entity_id"] == "workshop-1"
    assert "Ada Lovelace" in payload["body"]


def test_emit_new_application_writes_industry_notification_for_project():
    fake = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake):
        notification_producer.emit_new_application(
            industry_id="industry-1",
            kind="PROJECT",
            related_entity_id="project-1",
            opportunity_title="Recommendation Engine",
            student_name=None,
        )
    payload = _insert_payload(fake)
    assert payload["related_entity_type"] == "PROJECT_APPLICATION"
    assert "A student" in payload["body"]


def test_emit_new_application_writes_internship_application_entity_type():
    """INTERNSHIP/JOB point at the APPLICATION id -- Industry already has a
    per-application detail route (/industry/applicants/{id})."""
    fake = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake):
        notification_producer.emit_new_application(
            industry_id="industry-1",
            kind="INTERNSHIP",
            related_entity_id="app-1",
            opportunity_title="Backend Intern",
            student_name="Ada Lovelace",
        )
    payload = _insert_payload(fake)
    assert payload["related_entity_type"] == "INTERNSHIP_APPLICATION"
    assert payload["related_entity_id"] == "app-1"


def test_emit_new_application_unknown_kind_is_a_noop():
    fake = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake):
        notification_producer.emit_new_application(
            industry_id="industry-1",
            kind="MENTORSHIP",
            related_entity_id="x",
            opportunity_title=None,
            student_name=None,
        )
    fake.table.assert_not_called()


def test_emit_application_withdrawn_writes_withdrawal_notification():
    fake = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake):
        notification_producer.emit_application_withdrawn(
            industry_id="industry-1",
            kind="WORKSHOP",
            related_entity_id="workshop-1",
            opportunity_title="Intro to Git",
            student_name="Ada Lovelace",
        )
    payload = _insert_payload(fake)
    assert payload["type"] == "WITHDRAWAL"
    assert payload["related_entity_type"] == "WORKSHOP_APPLICATION"


def test_emit_workshop_status_change_notifies_on_accept_and_reject_only():
    fake = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake):
        notification_producer.emit_workshop_status_change(
            student_id="student-1", workshop_id="workshop-1", new_status="ACCEPTED", workshop_title="Intro to Git"
        )
    payload = _insert_payload(fake)
    assert payload["type"] == "APPLICATION_STATUS"
    assert payload["related_entity_type"] == "WORKSHOP"
    assert payload["related_entity_id"] == "workshop-1"

    fake2 = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake2):
        notification_producer.emit_workshop_status_change(
            student_id="student-1", workshop_id="workshop-1", new_status="APPLIED", workshop_title=None
        )
    fake2.table.assert_not_called()


def test_emit_project_status_change_notifies_on_shortlist_select_reject():
    for status in ("SHORTLISTED", "SELECTED", "REJECTED", "COMPLETED"):
        fake = MagicMock()
        with patch.object(notification_producer, "get_supabase", return_value=fake):
            notification_producer.emit_project_status_change(
                student_id="student-1", project_id="project-1", new_status=status, project_title="Rec Engine"
            )
        payload = _insert_payload(fake)
        assert payload["related_entity_type"] == "PROJECT"

    fake_noop = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake_noop):
        notification_producer.emit_project_status_change(
            student_id="student-1", project_id="project-1", new_status="ACTIVE", project_title=None
        )
    fake_noop.table.assert_not_called()
