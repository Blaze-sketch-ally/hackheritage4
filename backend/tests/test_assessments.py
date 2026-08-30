"""Tests for assessments.

Uses fake/mock Supabase clients throughout — this environment's
backend/.env has no real SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY
configured, so these tests exercise the actual auth-dependency and
scoring-service functions against fakes rather than a live database.
That is a deliberate, documented limitation (see the project's own
verification reports), not something these tests try to hide.
"""

import asyncio

import pytest
from fastapi import HTTPException

import app.core.dependencies as deps
from app.services.assessment_service import submit_and_score_attempt

STUDENT_UUID = "11111111-1111-1111-1111-111111111111"


# ============================================================
# Fakes shared by both test groups below
# ============================================================


class FakeUser:
    def __init__(self, id_):
        self.id = id_


class FakeUserResponse:
    def __init__(self, user):
        self.user = user


class FakeAuth:
    def __init__(self, behavior="valid"):
        self.behavior = behavior  # "valid" | "raises"

    def get_user(self, jwt):
        if self.behavior == "raises":
            raise Exception("simulated auth-server failure")
        return FakeUserResponse(user=FakeUser(STUDENT_UUID))


class FakeProfileQuery:
    def __init__(self, role):
        self.role = role

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        class R:
            pass

        r = R()
        r.data = {"role": self.role} if self.role is not None else None
        return r


class FakeAuthSupabase:
    """Fake client used for app.core.dependencies tests (auth.get_user + profiles lookup)."""

    def __init__(self, auth_behavior="valid", role="STUDENT"):
        self.auth = FakeAuth(auth_behavior)
        self._role = role

    def table(self, name):
        assert name == "profiles"
        return FakeProfileQuery(self._role)


# ============================================================
# get_current_student_id — the exact function fixed for the 500->401 bug
# ============================================================


def _run_get_current_student_id(monkeypatch, authorization, auth_behavior="valid", role="STUDENT", supabase_raises=False):
    def fake_get_supabase():
        if supabase_raises:
            raise Exception("supabase_url is required")
        return FakeAuthSupabase(auth_behavior, role)

    monkeypatch.setattr(deps, "get_supabase", fake_get_supabase)
    return asyncio.run(deps.get_current_student_id(authorization=authorization))


def test_missing_header_returns_401_without_touching_supabase(monkeypatch):
    """Regression test for the real bug found during live testing: a
    request with no Authorization header returned 500 instead of 401,
    because get_supabase() was an unconditional sibling dependency.
    Rigging get_supabase() to raise proves it is never even called."""
    with pytest.raises(HTTPException) as exc:
        _run_get_current_student_id(monkeypatch, None, supabase_raises=True)
    assert exc.value.status_code == 401


def test_malformed_scheme_returns_401_without_touching_supabase(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _run_get_current_student_id(monkeypatch, "Basic something", supabase_raises=True)
    assert exc.value.status_code == 401


def test_bearer_with_empty_token_returns_401_without_touching_supabase(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _run_get_current_student_id(monkeypatch, "Bearer   ", supabase_raises=True)
    assert exc.value.status_code == 401


def test_invalid_token_returns_401_when_supabase_is_reachable(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _run_get_current_student_id(monkeypatch, "Bearer invalid-token", auth_behavior="raises")
    assert exc.value.status_code == 401


def test_unreachable_supabase_returns_503_not_401_or_500(monkeypatch):
    """A genuine backend misconfiguration must not masquerade as the
    caller's fault (401) or crash unhandled (500)."""
    with pytest.raises(HTTPException) as exc:
        _run_get_current_student_id(monkeypatch, "Bearer some-token", supabase_raises=True)
    assert exc.value.status_code == 503


@pytest.mark.parametrize("role", ["FACULTY", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_student_role_returns_403(monkeypatch, role):
    with pytest.raises(HTTPException) as exc:
        _run_get_current_student_id(monkeypatch, "Bearer valid-token", role=role)
    assert exc.value.status_code == 403


def test_student_role_succeeds(monkeypatch):
    user_id = _run_get_current_student_id(monkeypatch, "Bearer valid-token", role="STUDENT")
    assert user_id == STUDENT_UUID


# ============================================================
# submit_and_score_attempt — deterministic scoring
# ============================================================


ATTEMPT_ID = "attempt-1"
STUDENT_ID = "student-1"
ASSESSMENT_ID = "assessment-1"

QUESTIONS = [
    {"id": "q1", "question_type": "MCQ", "points": 5},
    {"id": "q2", "question_type": "MCQ", "points": 5},
    {"id": "q3", "question_type": "MULTIPLE_SELECT", "points": 10},
    {"id": "q4", "question_type": "MULTIPLE_SELECT", "points": 10},
    {"id": "q5", "question_type": "MCQ", "points": 5},
]
ANSWER_KEYS = {"q1": ["A"], "q2": ["B"], "q3": ["A", "B"], "q4": ["A", "B"], "q5": ["A"]}
STUDENT_ANSWERS = [
    {"id": "ans1", "question_id": "q1", "selected_option_ids": ["A"]},  # correct
    {"id": "ans2", "question_id": "q2", "selected_option_ids": ["C"]},  # wrong
    {"id": "ans3", "question_id": "q3", "selected_option_ids": ["A", "B"]},  # correct
    {"id": "ans4", "question_id": "q4", "selected_option_ids": ["A"]},  # partial -> wrong, no partial credit
    # q5 deliberately unanswered
]


class Result:
    def __init__(self, data):
        self.data = data


class FakeScoringQuery:
    def __init__(self, table, attempt_row, updates_log):
        self.table = table
        self.attempt_row = attempt_row
        self.updates_log = updates_log
        self._filters = {}
        self._update_payload = None
        self._in_vals = None

    def select(self, *_):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def in_(self, col, vals):
        self._in_vals = vals
        return self

    def maybe_single(self):
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    def execute(self):
        if self._update_payload is not None:
            self.updates_log.append((self.table, dict(self._filters), dict(self._update_payload)))
            if self.table == "assessment_attempts":
                self.attempt_row.update(self._update_payload)
                return Result([dict(self.attempt_row)])
            return Result([{"id": self._filters.get("id")}])

        if self.table == "assessment_attempts":
            if self._filters.get("id") == ATTEMPT_ID:
                return Result(dict(self.attempt_row))
            return Result(None)
        if self.table == "assessment_questions":
            return Result(list(QUESTIONS))
        if self.table == "assessment_answers":
            if self._filters.get("attempt_id") == ATTEMPT_ID:
                return Result(list(STUDENT_ANSWERS))
            return Result([])
        if self.table == "assessment_question_answers":
            ids = self._in_vals or []
            return Result([{"question_id": qid, "correct_option_ids": ANSWER_KEYS[qid]} for qid in ids])
        raise AssertionError(f"unexpected table {self.table}")


class FakeScoringSupabase:
    def __init__(self, attempt_row):
        self.attempt_row = attempt_row
        self.updates_log = []

    def table(self, name):
        return FakeScoringQuery(name, self.attempt_row, self.updates_log)


def _fresh_attempt_row():
    return {
        "id": ATTEMPT_ID,
        "student_id": STUDENT_ID,
        "assessment_id": ASSESSMENT_ID,
        "status": "IN_PROGRESS",
        "started_at": "2026-01-01T00:00:00Z",
        "submitted_at": None,
        "score": None,
        "total_marks": None,
        "percentage": None,
    }


def test_scoring_exact_set_match_no_partial_credit():
    supabase = FakeScoringSupabase(_fresh_attempt_row())
    result = submit_and_score_attempt(supabase, ATTEMPT_ID, STUDENT_ID)

    assert result.total_marks == 35  # 5+5+10+10+5, every question counted regardless of answer
    assert result.score == 15  # q1 (5) + q3 (10); q2 wrong, q4 partial-selected (no credit), q5 unanswered
    assert result.percentage == pytest.approx(42.86, abs=0.01)
    assert result.correct_count == 2
    assert result.incorrect_count == 3
    assert result.status == "COMPLETED"


def test_scoring_rejects_cross_student_submission():
    supabase = FakeScoringSupabase(_fresh_attempt_row())
    with pytest.raises(HTTPException) as exc:
        submit_and_score_attempt(supabase, ATTEMPT_ID, "a-different-student")
    assert exc.value.status_code == 403


def test_scoring_is_idempotent_on_resubmit():
    supabase = FakeScoringSupabase(_fresh_attempt_row())
    first = submit_and_score_attempt(supabase, ATTEMPT_ID, STUDENT_ID)
    updates_after_first = len(supabase.updates_log)

    second = submit_and_score_attempt(supabase, ATTEMPT_ID, STUDENT_ID)

    assert second.score == first.score
    assert second.status == "COMPLETED"
    # No new writes on the idempotent path — it only reads.
    assert len(supabase.updates_log) == updates_after_first


def test_scoring_rejects_abandoned_attempt():
    row = _fresh_attempt_row()
    row["status"] = "ABANDONED"
    supabase = FakeScoringSupabase(row)
    with pytest.raises(HTTPException) as exc:
        submit_and_score_attempt(supabase, ATTEMPT_ID, STUDENT_ID)
    assert exc.value.status_code == 409


def test_scoring_missing_attempt_returns_404():
    supabase = FakeScoringSupabase(_fresh_attempt_row())
    with pytest.raises(HTTPException) as exc:
        submit_and_score_attempt(supabase, "does-not-exist", STUDENT_ID)
    assert exc.value.status_code == 404
