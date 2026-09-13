"""Tests for the Industry Internship Workspace list view's applicant-name
enrichment (app.services.internship_workspace_service._attach_applicant_names),
added so /industry/internships/{id}/workspaces can show a real name instead
of a raw student_id -- the same public.application_applicant_names RPC
(036) application_service already uses, keyed by each workspace's own
`application_id`.
"""

from unittest.mock import MagicMock

from app.services import internship_workspace_service


def _workspace_row(**overrides):
    row = {
        "id": "ws-1",
        "application_id": "app-1",
        "internship_id": "int-1",
        "student_id": "student-1",
        "industry_id": "industry-1",
        "work_mode": "REMOTE",
        "workspace_status": "IN_PROGRESS",
        "accepted_at": None,
        "started_at": None,
        "completed_at": None,
        "declined_at": None,
        "decline_reason": None,
        "rescinded_at": None,
        "rescind_reason": None,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "internship": {"id": "int-1", "title": "Backend Intern", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


def test_list_industry_workspaces_attaches_resolved_student_name():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        _workspace_row(application_id="app-1"),
        _workspace_row(id="ws-2", application_id="app-2"),
    ]
    supabase.rpc.return_value.execute.return_value.data = [
        {"application_id": "app-1", "student_name": "Ada Lovelace"},
        {"application_id": "app-2", "student_name": None},
    ]
    rows = internship_workspace_service.list_industry_workspaces(supabase, "industry-1")
    assert rows[0]["student_name"] == "Ada Lovelace"
    assert rows[1]["student_name"] is None
    supabase.rpc.assert_called_once_with(
        "application_applicant_names", {"application_ids": ["app-1", "app-2"]}
    )


def test_list_industry_workspaces_tolerates_name_rpc_failure():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        _workspace_row()
    ]
    supabase.rpc.side_effect = Exception("rpc unavailable")
    rows = internship_workspace_service.list_industry_workspaces(supabase, "industry-1")
    assert rows[0]["student_name"] is None


def test_list_industry_workspaces_empty_result_never_calls_rpc():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    rows = internship_workspace_service.list_industry_workspaces(supabase, "industry-1")
    assert rows == []
    supabase.rpc.assert_not_called()
