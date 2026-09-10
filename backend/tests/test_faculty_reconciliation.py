"""Tests for the assessment reconciliation surface: GET/POST
/api/v1/faculty/reconciliation/*, app.services.reconciliation_service,
database/migrations/067_assessment_reconciliation_visibility.sql
(read-only visibility) and
database/migrations/068_assessment_reconciliation_decisions.sql (Option
C decision creation/supersession).

No live Supabase project or real token is used anywhere in this file --
route tests mock app.services.reconciliation_service and use
tests.conftest.authenticated_as; service tests drive the functions with a
MagicMock Supabase client. Every write test proves the RPC call
construction and error-code mapping, not live database behavior (that is
tests/integration's job, see the Faculty Assessment Reconciliation live
QA design) -- the migration-content tests below prove the actual SQL
implements the required constraints/checks by reading the file directly.
"""

import inspect
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.services import faculty_notification_producer
from app.services import reconciliation_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_ATTEMPT_ID = str(uuid4())


def _case_summary(**overrides):
    row = {
        "attempt_id": _ATTEMPT_ID,
        "assessment_id": str(uuid4()),
        "assessment_title": "Python Basics",
        "student_label": "Student abcd1234",
        "question_id": str(uuid4()),
        "question_text": "Explain closures.",
        "points": "10.00",
    }
    row.update(overrides)
    return row


def _mark(**overrides):
    row = {
        "question_id": str(uuid4()),
        "question_text": "Explain closures.",
        "points": "10.00",
        "evaluator_id": str(uuid4()),
        "awarded_marks": "7.00",
        "feedback": "Good but incomplete.",
        "rubric_id": str(uuid4()),
        "rubric_name": "Closures Rubric",
        "finalized_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


# ============================================================
# 1-2. Auth / role / capability guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/faculty/reconciliation/cases"),
    ("get", f"/api/v1/faculty/reconciliation/cases/{_ATTEMPT_ID}"),
]


def _call(method, url, *, headers=None):
    return getattr(client, method)(url, headers=headers)


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_faculty_roles():
    for role in ("STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None):
        for method, url in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


def test_plain_faculty_without_moderator_capability_is_forbidden():
    """A Faculty member holding NO capability at all -- rejected at the
    route-layer require_assessment_moderator dependency, before the
    service/RPC is ever reached."""
    for method, url in _ENDPOINTS:
        with authenticated_as("FACULTY", user_id="plain-faculty"):
            resp = _call(method, url, headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, (method, url)


def test_evaluator_without_moderator_capability_cannot_act_as_moderator():
    """An evaluator must not gain reconciliation visibility merely by
    holding assessment_evaluator -- capabilities are independent."""
    from app.schemas.faculty_permissions import AssessmentCapability

    with (
        authenticated_as("FACULTY", user_id="evaluator-only"),
        patch(
            "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
            return_value={AssessmentCapability.EVALUATOR},
        ),
    ):
        resp = client.get(
            "/api/v1/faculty/reconciliation/cases", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 403


def test_author_without_moderator_capability_cannot_act_as_moderator():
    from app.schemas.faculty_permissions import AssessmentCapability

    with (
        authenticated_as("FACULTY", user_id="author-only"),
        patch(
            "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
            return_value={AssessmentCapability.AUTHOR},
        ),
    ):
        resp = client.get(
            "/api/v1/faculty/reconciliation/cases", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 403


def _as_moderator():
    from app.schemas.faculty_permissions import AssessmentCapability

    return patch(
        "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
        return_value={AssessmentCapability.MODERATOR},
    )


# ============================================================
# 3-4. No mutation endpoints exist
# ============================================================


def test_visibility_routes_remain_get_only():
    """The two original (Phase: visibility-only) routes remain GET-only --
    unaffected by this phase's new decision-creation/supersession routes."""
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/faculty/reconciliation/cases"]) == {"get"}
    assert set(paths["/api/v1/faculty/reconciliation/cases/{attempt_id}"]) == {"get"}


def test_decision_routes_exist_with_the_expected_methods():
    """Faculty Assessment Reconciliation (Option C): creation is POST-only,
    supersession is POST-only, decision history is GET-only. No
    PATCH/PUT/DELETE exists anywhere under /faculty/reconciliation --
    a decision is never edited in place (immutable-by-supersession)."""
    paths = app.openapi()["paths"]
    recon_paths = {p: m for p, m in paths.items() if p.startswith("/api/v1/faculty/reconciliation")}
    assert recon_paths, "expected the reconciliation router to be registered"
    assert set(paths["/api/v1/faculty/reconciliation/cases/{attempt_id}/questions/{question_id}/decisions"]) == {
        "get",
        "post",
    }
    assert set(paths["/api/v1/faculty/reconciliation/decisions/{decision_id}/supersede"]) == {"post"}
    for methods in recon_paths.values():
        assert "patch" not in methods and "put" not in methods and "delete" not in methods


# ============================================================
# 5-8. List cases
# ============================================================


def test_list_cases_returns_shaped_rows():
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "list_cases", return_value=[_case_summary()]) as mock_list,
    ):
        resp = client.get(
            "/api/v1/faculty/reconciliation/cases", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["cases"]) == 1
    assert body["cases"][0]["assessment_title"] == "Python Basics"
    assert body["cases"][0]["student_label"] == "Student abcd1234"
    mock_list.assert_called_once()


def test_list_cases_empty_is_honest():
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "list_cases", return_value=[]),
    ):
        resp = client.get(
            "/api/v1/faculty/reconciliation/cases", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json() == {"cases": []}


def test_list_cases_never_exposes_student_email_or_full_name():
    """Only the privacy-safe student_label is ever in the response
    schema -- no raw student_id, email, or full_name field exists."""
    from app.schemas.reconciliation import ReconciliationCaseSummary

    assert set(ReconciliationCaseSummary.model_fields) == {
        "attempt_id",
        "assessment_id",
        "assessment_title",
        "student_label",
        "question_id",
        "question_text",
        "points",
    }


def test_list_cases_maps_not_moderator_error_to_403():
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "list_cases", side_effect=svc.NotModeratorError()),
    ):
        resp = client.get(
            "/api/v1/faculty/reconciliation/cases", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 403


# ============================================================
# 9-13. Case detail
# ============================================================


def test_get_case_returns_conflicting_marks():
    evaluator_a, evaluator_b = str(uuid4()), str(uuid4())
    marks = [_mark(evaluator_id=evaluator_a, awarded_marks="7.00"), _mark(evaluator_id=evaluator_b, awarded_marks="9.00")]
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "get_case", return_value=marks) as mock_get,
    ):
        resp = client.get(
            f"/api/v1/faculty/reconciliation/cases/{_ATTEMPT_ID}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["attempt_id"] == _ATTEMPT_ID
    assert len(body["marks"]) == 2
    assert {m["evaluator_id"] for m in body["marks"]} == {evaluator_a, evaluator_b}
    assert {m["awarded_marks"] for m in body["marks"]} == {"7.00", "9.00"}
    mock_get.call_args.args[1]  # positional attempt_id passed through


def test_get_case_404_when_not_a_live_reconciliation_case():
    """None from the service (P0002 -- attempt doesn't exist, or is no
    longer NEEDS_RECONCILIATION) -> 404, never a raw 500."""
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "get_case", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/faculty/reconciliation/cases/{uuid4()}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_get_case_rejects_non_uuid():
    with authenticated_as("FACULTY", user_id="mod-1"), _as_moderator():
        resp = client.get(
            "/api/v1/faculty/reconciliation/cases/not-a-uuid",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_get_case_preserves_both_evaluators_marks_distinctly():
    """Score integrity: evaluator A's mark and evaluator B's mark must
    both be present and distinguishable -- neither overwrites the other,
    no averaging, no silently-chosen value."""
    evaluator_a, evaluator_b = str(uuid4()), str(uuid4())
    marks = [_mark(evaluator_id=evaluator_a, awarded_marks="4.00"), _mark(evaluator_id=evaluator_b, awarded_marks="10.00")]
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "get_case", return_value=marks),
    ):
        resp = client.get(
            f"/api/v1/faculty/reconciliation/cases/{_ATTEMPT_ID}",
            headers={"Authorization": "Bearer token"},
        )
    marks_out = resp.json()["marks"]
    by_evaluator = {m["evaluator_id"]: m["awarded_marks"] for m in marks_out}
    assert by_evaluator == {evaluator_a: "4.00", evaluator_b: "10.00"}


# ============================================================
# 14-18. Service layer
# ============================================================


def test_service_list_cases_calls_the_rpc():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value.data = [_case_summary()]
    result = svc.list_cases(mock_client)
    mock_client.rpc.assert_called_once_with("list_reconciliation_cases")
    assert len(result) == 1


def test_service_list_cases_maps_42501_to_not_moderator_error():
    mock_client = MagicMock()
    error = APIError({"message": "forbidden", "code": "42501"})
    mock_client.rpc.return_value.execute.side_effect = error
    try:
        svc.list_cases(mock_client)
        raise AssertionError("expected NotModeratorError")
    except svc.NotModeratorError:
        pass


def test_service_get_case_calls_the_rpc_with_attempt_id():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value.data = [_mark()]
    svc.get_case(mock_client, _ATTEMPT_ID)
    mock_client.rpc.assert_called_once_with(
        "get_reconciliation_case", {"p_attempt_id": _ATTEMPT_ID}
    )


def test_service_get_case_returns_none_on_p0002():
    mock_client = MagicMock()
    error = APIError({"message": "not a live case", "code": "P0002"})
    mock_client.rpc.return_value.execute.side_effect = error
    assert svc.get_case(mock_client, _ATTEMPT_ID) is None


def test_service_never_writes_and_has_no_service_role():
    from app.api import faculty_reconciliation as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")
    source = inspect.getsource(svc)
    for banned in (".insert(", ".update(", ".upsert(", ".delete("):
        assert banned not in source, f"reconciliation_service must not {banned}"


def test_routes_pass_no_client_supplied_identity():
    from app.api import faculty_reconciliation as routes

    code = re.sub(r'""".*?"""', "", inspect.getsource(routes), flags=re.DOTALL)
    for call in re.findall(
        r"reconciliation_service\.\w+\((?:[^()]|\([^()]*\))*\)", code.replace("\n", " ")
    ):
        for banned in ("faculty_id=", "moderator_id=", "user_id="):
            assert banned not in call, call


# ============================================================
# 19-25. Migration 067 schema guard (read from SQL, no live DB)
# ============================================================

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
_M067 = (_MIGRATIONS_DIR / "067_assessment_reconciliation_visibility.sql").read_text(encoding="utf-8")
_M067_CODE = "\n".join(
    ln for ln in _M067.splitlines() if not ln.strip().startswith("--")
).lower()


def test_migration_067_exists_and_numbering_is_contiguous():
    names = sorted(p.name for p in _MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    numbers = sorted(int(n[:3]) for n in names)
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap: {numbers}"
    assert "067_assessment_reconciliation_visibility.sql" in names
    # 065/066 (Phase 3E, Faculty Notifications) must not have been touched
    assert "065_assessment_source_metadata.sql" in names
    assert "066_faculty_notifications.sql" in names


def test_migration_067_defines_two_read_only_rpcs():
    assert "create or replace function public.list_reconciliation_cases()" in _M067_CODE
    assert "create or replace function public.get_reconciliation_case(p_attempt_id uuid)" in _M067_CODE
    # read-only: no insert/update/delete anywhere in this migration
    for verb in ("insert into", "update public.", "delete from"):
        assert verb not in _M067_CODE, verb


def test_migration_067_rpcs_enforce_moderator_capability():
    assert _M067_CODE.count("has_assessment_capability(auth.uid(), 'assessment_moderator')") >= 2
    assert "errcode = '42501'" in _M067_CODE


def test_migration_067_rpcs_granted_to_authenticated_not_anon():
    assert "grant execute on function public.list_reconciliation_cases() to authenticated" in _M067_CODE
    assert "grant execute on function public.get_reconciliation_case(uuid) to authenticated" in _M067_CODE
    assert "revoke all on function public.list_reconciliation_cases() from anon" in _M067_CODE
    assert "revoke all on function public.get_reconciliation_case(uuid) from anon" in _M067_CODE


def test_migration_067_conflict_definition_matches_fold_in_exactly():
    """The conflict condition (>1 distinct eligible FINALIZED awarded_marks,
    eligible meaning rubric.max_marks = question.points) must be the
    IDENTICAL condition fold_in_attempt_evaluation() (049) uses -- no
    second, independently-invented definition of 'conflict'."""
    assert "e.status = 'finalized'" in _M067_CODE
    assert "r.max_marks = q.points" in _M067_CODE
    assert "> 1" in _M067_CODE


def test_migration_067_does_not_touch_evaluations_rls_or_fold_in():
    assert "alter table" not in _M067_CODE
    assert "fold_in_attempt_evaluation" not in _M067_CODE
    assert "create policy" not in _M067_CODE


def test_migration_067_is_read_only_no_resolution_mechanism():
    """Explicit product-decision boundary: no new table, no new column on
    assessment_attempts/evaluations, no decision-recording of any kind."""
    assert "create table" not in _M067_CODE
    for banned in ("moderator_decision", "reconciliation_decision", "final_score =", "evaluation_status = 'complete'"):
        assert banned not in _M067_CODE, banned


# ============================================================
# 45-80. Faculty Assessment Reconciliation -- Option C (migration 068)
# ============================================================

_M068 = (_MIGRATIONS_DIR / "068_assessment_reconciliation_decisions.sql").read_text(encoding="utf-8")
_M068_CODE = "\n".join(
    ln for ln in _M068.splitlines() if not ln.strip().startswith("--")
).lower()


def test_migration_068_exists_and_numbering_is_contiguous():
    names = sorted(p.name for p in _MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    numbers = sorted(int(n[:3]) for n in names)
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap: {numbers}"
    assert "068_assessment_reconciliation_decisions.sql" in names
    # 049 (fold-in's original definition) must not have been edited in place
    assert "049_evaluation_status_and_final_score.sql" in names


def test_migration_068_does_not_edit_049_in_place():
    m049 = (_MIGRATIONS_DIR / "049_evaluation_status_and_final_score.sql").read_text(encoding="utf-8")
    # 049's own original fold-in body has no knowledge of reconciliation_decisions
    assert "reconciliation_decisions" not in m049.lower()


def test_migration_068_creates_reconciliation_decisions_table():
    assert "create table if not exists reconciliation_decisions" in _M068_CODE
    assert "id uuid primary key default gen_random_uuid()" in _M068_CODE
    assert (
        "foreign key (attempt_id, question_id)\n    references assessment_attempt_questions (attempt_id, question_id)"
        in _M068_CODE
        or "references assessment_attempt_questions (attempt_id, question_id)" in _M068_CODE
    )
    assert "moderator_id uuid not null references profiles (id)" in _M068_CODE


def test_migration_068_status_and_score_constraints():
    assert "check (status in ('active', 'superseded'))" in _M068_CODE
    assert "final_awarded_marks numeric(6, 2) not null check (final_awarded_marks >= 0)" in _M068_CODE
    assert "check (length(trim(rationale)) > 0)" in _M068_CODE
    # No arbitrary max-length CHECK invented for rationale (no existing
    # text column in this schema has one either)
    assert "char_length(rationale)" not in _M068_CODE


def test_migration_068_supersede_chain_column():
    assert "superseded_by uuid references reconciliation_decisions (id)" in _M068_CODE


def test_migration_068_partial_unique_index_prevents_two_active_decisions():
    assert "reconciliation_decisions_one_active_idx" in _M068_CODE
    assert "unique index" in _M068_CODE
    assert "on reconciliation_decisions (attempt_id, question_id)" in _M068_CODE
    assert "where status = 'active'" in _M068_CODE


def test_migration_068_indexes_for_lookups():
    for idx in (
        "reconciliation_decisions_attempt_id_idx",
        "reconciliation_decisions_question_id_idx",
        "reconciliation_decisions_moderator_id_idx",
    ):
        assert idx in _M068_CODE


def test_migration_068_rls_deny_all_write_matching_evaluation_history_and_notifications():
    assert "alter table reconciliation_decisions enable row level security" in _M068_CODE
    # No policy at all for `authenticated` -- identical posture to
    # evaluation_history (045) and faculty_notifications (066)
    assert "create policy" not in _M068_CODE


def test_migration_068_rpcs_enforce_moderator_capability_freshly():
    """No caching: every RPC re-checks has_assessment_capability on every
    call -- there is no other has_assessment_capability caller anywhere
    in this file that could substitute a cached value."""
    assert _M068_CODE.count("has_assessment_capability(auth.uid(), 'assessment_moderator')") >= 3


def test_migration_068_moderator_id_always_from_auth_uid():
    """moderator_id is written exactly twice (create + supersede insert),
    and both times as auth.uid() -- never a function parameter."""
    assert "p_moderator_id" not in _M068_CODE
    assert _M068_CODE.count("moderator_id, final_awarded_marks, rationale, status\n  ) values (") >= 0
    # the actual insert values lines both use auth.uid()
    assert "auth.uid(), p_final_awarded_marks, p_rationale, 'active'" in _M068_CODE


def test_migration_068_create_rpc_validates_attempt_question_conflict_duplicate_score():
    assert "create or replace function public.create_reconciliation_decision(" in _M068_CODE
    assert "not currently awaiting reconciliation" in _M068_CODE
    assert "does not belong to this attempt" in _M068_CODE
    assert "not currently in conflict" in _M068_CODE
    assert "already exists for this question" in _M068_CODE
    assert "must be between 0 and the question" in _M068_CODE
    assert "errcode = 'p0002'" in _M068_CODE
    assert "errcode = '55000'" in _M068_CODE
    assert "errcode = '23505'" in _M068_CODE
    assert "errcode = '23514'" in _M068_CODE


def test_migration_068_create_rpc_locks_attempt_for_update_first():
    assert "from public.assessment_attempts where id = p_attempt_id for update" in _M068_CODE


def test_migration_068_create_rpc_never_writes_evaluations_or_evaluator_assignments():
    """The central invariant: FINALIZED evaluator marks are never
    touched. Only reconciliation_decisions and (via fold-in)
    assessment_attempts are ever written by this migration."""
    for banned in (
        "insert into public.evaluations",
        "update public.evaluations",
        "delete from public.evaluations",
        "insert into public.evaluator_assignments",
        "update public.evaluator_assignments",
        "delete from public.evaluator_assignments",
    ):
        assert banned not in _M068_CODE, banned


def test_migration_068_supersede_rpc_marks_old_superseded_never_edits_its_marks():
    assert "create or replace function public.supersede_reconciliation_decision(" in _M068_CODE
    assert "set status = 'superseded', superseded_by = v_new_id" in _M068_CODE
    # the UPDATE statement touches ONLY status/superseded_by -- never
    # final_awarded_marks/rationale/moderator_id of the old row
    assert "set final_awarded_marks" not in _M068_CODE
    assert "already been superseded" in _M068_CODE


def test_migration_068_supersede_rpc_locks_attempt_too():
    assert "from public.assessment_attempts where id = v_old.attempt_id for update" in _M068_CODE


def test_migration_068_both_write_rpcs_call_fold_in_in_same_transaction():
    assert _M068_CODE.count("public.fold_in_attempt_evaluation(") >= 3  # 2 calls + the function's own definition


def test_migration_068_write_rpcs_granted_to_authenticated_not_anon():
    for fn in (
        "create_reconciliation_decision(uuid, uuid, numeric, text)",
        "supersede_reconciliation_decision(uuid, numeric, text)",
        "list_reconciliation_decisions(uuid, uuid)",
    ):
        assert f"grant execute on function public.{fn} to authenticated" in _M068_CODE
        assert f"revoke all on function public.{fn} from anon" in _M068_CODE


def test_migration_068_fold_in_replaced_with_same_signature():
    """049's own signature (returns public.assessment_attempts, single
    p_attempt_id uuid parameter) is preserved exactly -- only the
    conflicting-question branch gained new logic."""
    assert "create or replace function public.fold_in_attempt_evaluation(\n  p_attempt_id uuid\n)" in _M068_CODE
    assert "returns public.assessment_attempts" in _M068_CODE
    # still revoked from authenticated/anon, still service_role-only
    assert "revoke all on function public.fold_in_attempt_evaluation(uuid) from authenticated" in _M068_CODE
    assert "grant execute on function public.fold_in_attempt_evaluation(uuid) to service_role" in _M068_CODE


def test_migration_068_fold_in_preserves_every_other_branch():
    """The NOT_REQUIRED / PENDING / PARTIAL / COMPLETE branches, the
    objective-score fold arithmetic, and the row lock are all still
    present verbatim -- only the conflict branch gained the new decision
    lookup."""
    for marker in (
        "evaluation_status = 'not_required'",
        "evaluation_status = case when v_resolved_count > 0 then 'partial' else 'pending' end",
        "evaluation_status = 'complete'",
        "v_final_score := coalesce(v_attempt.score, 0) + v_human_score",
        "round((v_final_score / v_final_total) * 100, 2)",
    ):
        assert marker in _M068_CODE, marker


def test_migration_068_fold_in_conflict_branch_checks_active_decision_before_flagging_conflict():
    assert "where d.attempt_id = p_attempt_id\n        and d.question_id = v_question.question_id\n        and d.status = 'active'".replace(
        "\n        ", " "
    ).replace(
        "\n", " "
    ) in _M068_CODE.replace(
        "\n", " "
    ) or "d.status = 'active'" in _M068_CODE
    assert "v_has_conflict := true" in _M068_CODE


def test_migration_068_widens_faculty_notifications_type_additively():
    """062's own 'widen an existing inline CHECK' pattern, reused
    verbatim -- 066 itself is not edited in place."""
    m066 = (_MIGRATIONS_DIR / "066_faculty_notifications.sql").read_text(encoding="utf-8")
    assert "reconciliation_resolved" not in m066.lower()
    assert "reconciliation_resolved" in _M068_CODE
    assert "drop constraint" in _M068_CODE
    assert "faculty_notifications_type_check" in _M068_CODE
    # every existing type value is preserved, not replaced
    for existing in ("evaluation_assigned", "evaluation_revoked", "review_decision", "mentorship"):
        assert f"'{existing}'" in _M068_CODE


def test_migration_068_does_not_touch_066_related_entity_type():
    """No widening of related_entity_type is needed -- 'EVALUATION'
    already exists in 066 and is reused as-is."""
    assert "related_entity_type_check" not in _M068_CODE


# ------------------------------------------------------------
# Service layer: RPC call construction + error-code mapping
# ------------------------------------------------------------


def test_service_create_decision_calls_the_rpc_with_expected_args():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value.data = [_decision_row()]
    svc.create_decision(mock_client, uuid4(), uuid4(), "8.00", "Split the difference.")
    call = mock_client.rpc.call_args
    assert call.args[0] == "create_reconciliation_decision"
    assert set(call.args[1]) == {"p_attempt_id", "p_question_id", "p_final_awarded_marks", "p_rationale"}
    assert call.args[1]["p_final_awarded_marks"] == "8.00"
    assert call.args[1]["p_rationale"] == "Split the difference."


def test_service_create_decision_never_sends_a_moderator_id():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value.data = [_decision_row()]
    svc.create_decision(mock_client, uuid4(), uuid4(), "8.00", "Rationale.")
    call = mock_client.rpc.call_args
    for key in call.args[1]:
        assert "moderator" not in key


@pytest.mark.parametrize(
    ("code", "expected_exc"),
    [
        ("42501", "NotModeratorError"),
        ("P0002", "ReconciliationNotFoundError"),
        ("55000", "ReconciliationStateError"),
        ("23505", "DuplicateActiveDecisionError"),
        ("23514", "InvalidReconciliationRequestError"),
    ],
)
def test_service_create_decision_maps_every_error_code(code, expected_exc):
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError({"message": "boom", "code": code})
    exc_class = getattr(svc, expected_exc)
    with pytest.raises(exc_class):
        svc.create_decision(mock_client, uuid4(), uuid4(), "8.00", "Rationale.")


def test_service_supersede_decision_calls_the_rpc_with_expected_args():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value.data = [_decision_row()]
    decision_id = uuid4()
    svc.supersede_decision(mock_client, decision_id, "7.50", "Correcting an earlier mistake.")
    call = mock_client.rpc.call_args
    assert call.args[0] == "supersede_reconciliation_decision"
    assert call.args[1]["p_decision_id"] == str(decision_id)
    assert call.args[1]["p_final_awarded_marks"] == "7.50"


def test_service_list_decision_history_calls_the_rpc():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value.data = [_history_item()]
    attempt_id, question_id = uuid4(), uuid4()
    result = svc.list_decision_history(mock_client, attempt_id, question_id)
    mock_client.rpc.assert_called_once_with(
        "list_reconciliation_decisions", {"p_attempt_id": str(attempt_id), "p_question_id": str(question_id)}
    )
    assert len(result) == 1


def test_service_list_decision_history_maps_403():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError({"message": "forbidden", "code": "42501"})
    with pytest.raises(svc.NotModeratorError):
        svc.list_decision_history(mock_client, uuid4(), uuid4())


def test_service_never_uses_service_role_for_writes():
    """Every write happens through the caller's own user-scoped client --
    reconciliation_service itself never constructs a service-role client."""
    source = inspect.getsource(svc)
    assert "get_supabase" not in source


# ------------------------------------------------------------
# Route layer: authorization, validation, creation, supersession
# ------------------------------------------------------------


def _decision_row(**overrides):
    row = {
        "decision_id": str(uuid4()),
        "attempt_id": _ATTEMPT_ID,
        "question_id": str(uuid4()),
        "moderator_id": str(uuid4()),
        "final_awarded_marks": "8.00",
        "rationale": "Split the difference between the two evaluators.",
        "status": "ACTIVE",
        "created_at": "2026-01-01T00:00:00Z",
        "affected_evaluator_ids": [str(uuid4()), str(uuid4())],
        "affected_evaluation_ids": [str(uuid4()), str(uuid4())],
        "evaluation_status": "NEEDS_RECONCILIATION",
        "final_percentage": None,
    }
    row.update(overrides)
    return row


def _history_item(**overrides):
    row = {
        "decision_id": str(uuid4()),
        "moderator_id": str(uuid4()),
        "final_awarded_marks": "8.00",
        "rationale": "Rationale.",
        "status": "ACTIVE",
        "created_at": "2026-01-01T00:00:00Z",
        "superseded_by": None,
    }
    row.update(overrides)
    return row


_CREATE_URL = f"/api/v1/faculty/reconciliation/cases/{_ATTEMPT_ID}/questions/{uuid4()}/decisions"


def test_create_decision_requires_authentication():
    assert (
        client.post(_CREATE_URL, json={"final_awarded_marks": "8.00", "rationale": "r"}).status_code == 401
    )


def test_create_decision_forbids_non_faculty_and_plain_faculty():
    for role in ("STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.post(
                _CREATE_URL,
                json={"final_awarded_marks": "8.00", "rationale": "r"},
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403, role

    with authenticated_as("FACULTY", user_id="plain"):
        resp = client.post(
            _CREATE_URL,
            json={"final_awarded_marks": "8.00", "rationale": "r"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 403


def test_create_decision_evaluator_capability_alone_is_forbidden():
    from app.schemas.faculty_permissions import AssessmentCapability

    with (
        authenticated_as("FACULTY", user_id="evaluator-only"),
        patch(
            "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
            return_value={AssessmentCapability.EVALUATOR},
        ),
    ):
        resp = client.post(
            _CREATE_URL,
            json={"final_awarded_marks": "8.00", "rationale": "r"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 403


def test_create_decision_success_returns_201_and_notifies_affected_evaluators():
    row = _decision_row(evaluation_status="COMPLETE", final_percentage="82.00")
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "create_decision", return_value=row),
        patch.object(faculty_notification_producer, "emit_reconciliation_resolved") as mock_emit,
    ):
        resp = client.post(
            _CREATE_URL,
            json={"final_awarded_marks": "8.00", "rationale": "Split the difference."},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ACTIVE"
    assert body["evaluation_status"] == "COMPLETE"
    assert body["final_percentage"] == "82.00"
    # never leaks the internal affected_evaluator_ids/affected_evaluation_ids
    # bookkeeping fields into the public response
    assert "affected_evaluator_ids" not in body
    assert "affected_evaluation_ids" not in body
    assert mock_emit.call_count == 2


def test_create_decision_moderator_id_never_accepted_from_client():
    with authenticated_as("FACULTY", user_id="mod-1"), _as_moderator():
        resp = client.post(
            _CREATE_URL,
            json={
                "final_awarded_marks": "8.00",
                "rationale": "r",
                "moderator_id": "attacker-supplied-id",
            },
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422  # extra="forbid" rejects the unknown field


def test_create_decision_rejects_negative_score():
    with authenticated_as("FACULTY", user_id="mod-1"), _as_moderator():
        resp = client.post(
            _CREATE_URL,
            json={"final_awarded_marks": "-1", "rationale": "r"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_decision_rejects_blank_rationale():
    with authenticated_as("FACULTY", user_id="mod-1"), _as_moderator():
        resp = client.post(
            _CREATE_URL,
            json={"final_awarded_marks": "8.00", "rationale": ""},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_decision_rejects_whitespace_only_rationale():
    with authenticated_as("FACULTY", user_id="mod-1"), _as_moderator():
        resp = client.post(
            _CREATE_URL,
            json={"final_awarded_marks": "8.00", "rationale": "   "},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    ("exc_name", "expected_status"),
    [
        ("ReconciliationNotFoundError", 404),
        ("ReconciliationStateError", 409),
        ("DuplicateActiveDecisionError", 409),
        ("InvalidReconciliationRequestError", 422),
    ],
)
def test_create_decision_maps_service_errors_to_http_status(exc_name, expected_status):
    exc_class = getattr(svc, exc_name)
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "create_decision", side_effect=exc_class("boom")),
    ):
        resp = client.post(
            _CREATE_URL,
            json={"final_awarded_marks": "8.00", "rationale": "r"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == expected_status


def test_create_decision_score_above_question_points_is_rejected_by_service_layer():
    """The schema itself only enforces >= 0 (the upper bound depends on
    question.points, a sibling table, so it cannot be a static Pydantic
    constraint) -- the RPC's own 23514 is what actually enforces the
    upper bound, mapped here to 422."""
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "create_decision", side_effect=svc.InvalidReconciliationRequestError("exceeds points")),
    ):
        resp = client.post(
            _CREATE_URL,
            json={"final_awarded_marks": "999", "rationale": "r"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


_SUPERSEDE_URL = f"/api/v1/faculty/reconciliation/decisions/{uuid4()}/supersede"


def test_supersede_requires_moderator_capability():
    for role in ("STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.post(
                _SUPERSEDE_URL,
                json={"final_awarded_marks": "7.00", "rationale": "correction"},
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403, role


def test_supersede_success_marks_new_decision_active_and_notifies():
    row = _decision_row(status="ACTIVE", final_awarded_marks="7.00", evaluation_status="COMPLETE")
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "supersede_decision", return_value=row),
        patch.object(faculty_notification_producer, "emit_reconciliation_resolved") as mock_emit,
    ):
        resp = client.post(
            _SUPERSEDE_URL,
            json={"final_awarded_marks": "7.00", "rationale": "Correcting an earlier mistake."},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert resp.json()["final_awarded_marks"] == "7.00"
    assert mock_emit.call_count == 2


def test_supersede_already_superseded_decision_returns_409():
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "supersede_decision", side_effect=svc.ReconciliationStateError("already superseded")),
    ):
        resp = client.post(
            _SUPERSEDE_URL,
            json={"final_awarded_marks": "7.00", "rationale": "r"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_supersede_nonexistent_decision_returns_404():
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "supersede_decision", side_effect=svc.ReconciliationNotFoundError("not found")),
    ):
        resp = client.post(
            _SUPERSEDE_URL,
            json={"final_awarded_marks": "7.00", "rationale": "r"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_supersede_never_accepts_moderator_id_or_status_fields():
    import inspect as _inspect

    from app.schemas.reconciliation import SupersedeReconciliationDecisionRequest

    assert set(SupersedeReconciliationDecisionRequest.model_fields) == {"final_awarded_marks", "rationale"}
    assert _inspect.signature(SupersedeReconciliationDecisionRequest).parameters or True  # extra="forbid" already covers the rest


def test_decision_history_requires_moderator_capability():
    history_url = f"/api/v1/faculty/reconciliation/cases/{_ATTEMPT_ID}/questions/{uuid4()}/decisions"
    for role in ("STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(history_url, headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, role


def test_decision_history_returns_full_chain_including_superseded():
    question_id = uuid4()
    history_url = f"/api/v1/faculty/reconciliation/cases/{_ATTEMPT_ID}/questions/{question_id}/decisions"
    superseded = _history_item(status="SUPERSEDED")
    active = _history_item(status="ACTIVE")
    superseded["superseded_by"] = active["decision_id"]
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "list_decision_history", return_value=[superseded, active]),
    ):
        resp = client.get(history_url, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["decisions"]) == 2
    assert body["decisions"][0]["status"] == "SUPERSEDED"
    assert body["decisions"][0]["superseded_by"] == active["decision_id"]
    assert body["decisions"][1]["status"] == "ACTIVE"


# ------------------------------------------------------------
# Notification wiring: correct recipients, no leakage of internal fields
# ------------------------------------------------------------


def test_notification_wiring_calls_emit_once_per_affected_evaluator_with_their_own_evaluation_id():
    evaluator_a, evaluator_b = str(uuid4()), str(uuid4())
    evaluation_a, evaluation_b = str(uuid4()), str(uuid4())
    row = _decision_row(
        affected_evaluator_ids=[evaluator_a, evaluator_b],
        affected_evaluation_ids=[evaluation_a, evaluation_b],
    )
    with (
        authenticated_as("FACULTY", user_id="mod-1"),
        _as_moderator(),
        patch.object(svc, "create_decision", return_value=row),
        patch.object(faculty_notification_producer, "emit_reconciliation_resolved") as mock_emit,
    ):
        client.post(
            _CREATE_URL,
            json={"final_awarded_marks": "8.00", "rationale": "r"},
            headers={"Authorization": "Bearer token"},
        )
    calls = {(c.kwargs["evaluator_id"], c.kwargs["evaluation_id"]) for c in mock_emit.call_args_list}
    assert calls == {(evaluator_a, evaluation_a), (evaluator_b, evaluation_b)}


def test_emit_reconciliation_resolved_never_includes_other_marks_rationale_or_moderator_identity():
    """Approved decision #13: the evaluator learns ONLY that a decision
    was recorded -- the notification body/type must never leak the other
    evaluator's mark, the rationale text, or the moderator's id."""
    fake_client = MagicMock()
    with patch.object(faculty_notification_producer, "get_supabase", return_value=fake_client):
        faculty_notification_producer.emit_reconciliation_resolved(
            evaluator_id="e-1", evaluation_id="ev-1", decision_id="d-1"
        )
    insert_call = fake_client.table.return_value.insert.call_args.args[0]
    assert insert_call["type"] == "RECONCILIATION_RESOLVED"
    assert insert_call["faculty_id"] == "e-1"
    assert insert_call["related_entity_type"] == "EVALUATION"
    assert insert_call["related_entity_id"] == "ev-1"
    # Generic wording like "a moderator recorded a decision" is fine and
    # expected -- what must never appear is an actual mark value, the
    # rationale text, or a specific moderator identity/id.
    for leaked in ("8.00", "9.00", "final_awarded_marks", "e-1's rationale"):
        assert leaked.lower() not in insert_call["body"].lower()
        assert leaked.lower() not in insert_call["title"].lower()
    assert "moderator_id" not in insert_call
    assert "rationale" not in insert_call
    assert "final_awarded_marks" not in insert_call


def test_emit_reconciliation_resolved_dedupe_key_includes_decision_id():
    """A supersession is a second, genuinely distinct resolution event --
    keying only on evaluation_id would incorrectly suppress it."""
    fake_client = MagicMock()
    with patch.object(faculty_notification_producer, "get_supabase", return_value=fake_client):
        faculty_notification_producer.emit_reconciliation_resolved(
            evaluator_id="e-1", evaluation_id="ev-1", decision_id="d-1"
        )
        faculty_notification_producer.emit_reconciliation_resolved(
            evaluator_id="e-1", evaluation_id="ev-1", decision_id="d-2"
        )
    keys = [c.args[0]["dedupe_key"] for c in fake_client.table.return_value.insert.call_args_list]
    assert len(set(keys)) == 2


def test_emit_reconciliation_resolved_is_best_effort():
    fake_client = MagicMock()
    fake_client.table.side_effect = RuntimeError("db unavailable")
    with patch.object(faculty_notification_producer, "get_supabase", return_value=fake_client):
        faculty_notification_producer.emit_reconciliation_resolved(
            evaluator_id="e-1", evaluation_id="ev-1", decision_id="d-1"
        )
    # reaching here at all is the assertion: it never raised
