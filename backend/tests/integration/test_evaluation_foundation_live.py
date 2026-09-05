"""Live-integration coverage for Phase F8.1 -- the DATABASE-ONLY
evaluation/assignment/rubric foundation (045_evaluation_foundation.sql).

F8.1 ships no FastAPI route and no frontend -- every test here talks to
the RPCs/tables directly, either via the service-role admin client
(live.admin, the only client create_evaluator_assignment()/
revoke_evaluator_assignment() actually grant execute to) or via direct
PostgREST calls with a real user's bearer token (to prove what an
ordinary authenticated caller -- including the assigned evaluator
themselves -- can and cannot do). This mirrors test_question_lifecycle_
live.py's own F7.1 section, written for the identical "DB-only phase,
no API yet" situation.

Regression proof for existing behavior (objective scoring, F6/F7 question
lifecycle, mentor visibility, capability system) is NOT duplicated here --
it comes from the existing test suites (unit + live) passing unmodified,
per this phase's own report. The one regression check that IS new here
(test_faculty_evaluator_with_active_assignment_still_cannot_read_
assessment_answers) is the explicit F8.1-specific guard the phase brief
itself calls for: proving all of this new adjacent infrastructure did NOT
accidentally open the one boundary F8.2 is supposed to build.
"""

import uuid

import httpx
import pytest
from postgrest.exceptions import APIError


def _rpc_as_user(live, token: str, name: str, payload: dict) -> httpx.Response:
    return httpx.post(
        f"{live._anon_url}/rest/v1/rpc/{name}",
        headers={"apikey": live._anon_key, "Authorization": f"Bearer {token}"},
        json=payload,
    )


def _rest_as_user(live, token: str, method: str, table: str, **kwargs) -> httpx.Response:
    headers = kwargs.pop("headers", {})
    headers["apikey"] = live._anon_key
    headers["Authorization"] = f"Bearer {token}"
    headers.setdefault("Prefer", "return=representation")
    return httpx.request(method, f"{live._anon_url}/rest/v1/{table}", headers=headers, **kwargs)


def _setup_attempt_question(live, skill_id: str | None = None, tag: str = "") -> dict:
    """One APPROVED MCQ question, one blueprint rule, one student attempt
    already started against it -- i.e. one real assessment_attempt_
    questions row to assign an evaluator to. Mirrors test_role_and_
    attempt_integrity_live.py's own _complete_one_question_assessment()
    setup shape, but stops right after starting the attempt (no answer/
    submit/score -- F8.1 has nothing to do with objective scoring).
    Also creates one FACULTY evaluator (holding assessment_evaluator)
    ready to be assigned.

    tag: distinguishes the local-part of every QA email this call
    creates -- required whenever a single test calls this helper more
    than once (live.run_id alone is fixed per test, so two calls with
    the same local names would collide on "already registered")."""
    fa_id, fa_email = live.create_user(f"fa{tag}", "FACULTY")
    fb_id, fb_email = live.create_user(f"fb{tag}", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)

    aid = live.create_assessment(skill_id=skill_id, title_suffix=tag)
    q1 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, f"eval-foundation{tag}")).json()["id"]
    live.api(fb_token, "POST", f"/questions/{q1}/approve")
    live.api(
        fa_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 1}]},
    )

    s_id, s_email = live.create_user(f"s{tag}", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]

    fe_id, fe_email = live.create_user(f"fe{tag}", "FACULTY")
    live.grant_assessment_capabilities(fe_id, "assessment_evaluator")
    fe_token = live.token_for(fe_email)

    return {
        "aid": aid,
        "question_id": q1,
        "attempt_id": attempt_id,
        "student_id": s_id,
        "student_token": s_token,
        "evaluator_id": fe_id,
        "evaluator_token": fe_token,
        # any real profile id -- see the migration's own note on why
        # p_created_by is a plain accountability value in F8.1, not yet
        # role-gated (the real governance actor is an open decision).
        "creator_id": fa_id,
    }


def _create_assignment(live, ctx: dict) -> dict:
    return (
        live.admin.rpc(
            "create_evaluator_assignment",
            {
                "p_evaluator_id": ctx["evaluator_id"],
                "p_attempt_id": ctx["attempt_id"],
                "p_question_id": ctx["question_id"],
                "p_created_by": ctx["creator_id"],
            },
        )
        .execute()
        .data
    )


# ============================================================
# Assignment
# ============================================================


def test_create_evaluator_assignment_succeeds_and_auto_creates_evaluation(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)

    assert assignment["evaluator_id"] == ctx["evaluator_id"]
    assert assignment["attempt_id"] == ctx["attempt_id"]
    assert assignment["question_id"] == ctx["question_id"]
    assert assignment["status"] == "ACTIVE"

    evaluation = (
        live.admin.table("evaluations").select("*").eq("assignment_id", assignment["id"]).execute().data[0]
    )
    assert evaluation["evaluator_id"] == ctx["evaluator_id"]
    assert evaluation["status"] == "ASSIGNED"
    assert evaluation["awarded_marks"] is None
    assert evaluation["finalized_at"] is None

    history = (
        live.admin.table("evaluation_history")
        .select("*")
        .eq("evaluation_id", evaluation["id"])
        .execute()
        .data
    )
    assert len(history) == 1
    assert history[0]["previous_status"] is None
    assert history[0]["new_status"] == "ASSIGNED"


def test_create_evaluator_assignment_rejects_non_faculty_evaluator(live):
    ctx = _setup_attempt_question(live)
    with pytest.raises(APIError):
        live.admin.rpc(
            "create_evaluator_assignment",
            {
                "p_evaluator_id": ctx["student_id"],  # a STUDENT, not FACULTY
                "p_attempt_id": ctx["attempt_id"],
                "p_question_id": ctx["question_id"],
                "p_created_by": ctx["creator_id"],
            },
        ).execute()


def test_create_evaluator_assignment_rejects_unknown_attempt_question_scope(live):
    ctx = _setup_attempt_question(live)
    with pytest.raises(APIError):
        live.admin.rpc(
            "create_evaluator_assignment",
            {
                "p_evaluator_id": ctx["evaluator_id"],
                "p_attempt_id": str(uuid.uuid4()),  # no such attempt-question row
                "p_question_id": ctx["question_id"],
                "p_created_by": ctx["creator_id"],
            },
        ).execute()


def test_no_authenticated_user_can_call_create_evaluator_assignment_directly(live):
    """Covers both 'unauthorized evaluator cannot self-assign' and
    'evaluator cannot create an assignment for another evaluator' at
    once: the RPC is revoked from `authenticated` entirely, so no
    authenticated caller -- self-targeting or otherwise -- can reach it,
    regardless of who they try to assign."""
    ctx = _setup_attempt_question(live)
    r = _rpc_as_user(
        live, ctx["evaluator_token"], "create_evaluator_assignment",
        {
            "p_evaluator_id": ctx["evaluator_id"],
            "p_attempt_id": ctx["attempt_id"],
            "p_question_id": ctx["question_id"],
            "p_created_by": ctx["evaluator_id"],
        },
    )
    assert r.status_code >= 400, f"an authenticated user must never be able to self-assign, got {r.status_code}"

    r_other = _rpc_as_user(
        live, ctx["student_token"], "create_evaluator_assignment",
        {
            "p_evaluator_id": ctx["evaluator_id"],
            "p_attempt_id": ctx["attempt_id"],
            "p_question_id": ctx["question_id"],
            "p_created_by": ctx["student_id"],
        },
    )
    assert r_other.status_code >= 400


def test_raw_insert_into_evaluator_assignments_is_blocked_by_rls(live):
    ctx = _setup_attempt_question(live)
    r = _rest_as_user(
        live, ctx["evaluator_token"], "POST", "evaluator_assignments",
        json={
            "evaluator_id": ctx["evaluator_id"],
            "attempt_id": ctx["attempt_id"],
            "question_id": ctx["question_id"],
            "status": "ACTIVE",
        },
    )
    assert r.status_code >= 400, "no INSERT policy exists for authenticated -- a raw insert must fail"


def test_duplicate_active_assignment_is_rejected(live):
    ctx = _setup_attempt_question(live)
    _create_assignment(live, ctx)
    with pytest.raises(APIError):
        _create_assignment(live, ctx)


def test_revoked_assignment_remains_historically_present(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)

    revoked = (
        live.admin.rpc(
            "revoke_evaluator_assignment",
            {"p_assignment_id": assignment["id"], "p_revoked_by": ctx["creator_id"]},
        )
        .execute()
        .data
    )
    assert revoked["status"] == "REVOKED"
    assert revoked["revoked_at"] is not None
    assert revoked["revoked_by"] == ctx["creator_id"]

    still_there = (
        live.admin.table("evaluator_assignments").select("*").eq("id", assignment["id"]).execute().data
    )
    assert len(still_there) == 1, "revocation must not delete the row -- it must remain historically present"
    assert still_there[0]["status"] == "REVOKED"

    # A fresh assignment to the SAME evaluator+scope afterward must still
    # be possible (append-only history, not a permanent lock).
    reassigned = _create_assignment(live, ctx)
    assert reassigned["status"] == "ACTIVE"
    assert reassigned["id"] != assignment["id"]


def test_deleting_an_assignment_is_prevented_for_authenticated_users(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)

    r = _rest_as_user(
        live, ctx["evaluator_token"], "DELETE", "evaluator_assignments",
        params={"id": f"eq.{assignment['id']}"},
    )
    still_there = live.admin.table("evaluator_assignments").select("id").eq("id", assignment["id"]).execute().data
    assert len(still_there) == 1, f"no DELETE policy exists for authenticated -- deletion must be refused, got {r.status_code}"


# ============================================================
# Evaluation
# ============================================================


def test_evaluator_identity_cannot_be_spoofed(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )
    other_evaluator_id = str(uuid.uuid4())

    r = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"},
        json={"evaluator_id": other_evaluator_id},
    )
    assert r.status_code >= 400, f"evaluator_id must be immutable, got {r.status_code}: {r.text}"

    unchanged = live.admin.table("evaluations").select("evaluator_id").eq("id", evaluation_id).execute().data[0]
    assert unchanged["evaluator_id"] == ctx["evaluator_id"]


def test_evaluation_cannot_be_reassigned_to_an_unrelated_assignment(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )

    ctx2 = _setup_attempt_question(live, tag="2")
    other_assignment = _create_assignment(live, ctx2)

    r = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"},
        json={"assignment_id": other_assignment["id"]},
    )
    assert r.status_code >= 400, "assignment_id must be immutable"


def test_only_the_assigned_evaluator_can_update_their_evaluation(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )

    fx_id, fx_email = live.create_user("fx", "FACULTY")
    live.grant_assessment_capabilities(fx_id, "assessment_evaluator")
    fx_token = live.token_for(fx_email)

    r = _rest_as_user(
        live, fx_token, "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"},
        json={"status": "IN_PROGRESS"},
    )
    # RLS excludes the row entirely for a non-owning evaluator -- 200 with
    # zero rows affected, not a 4xx -- the definitive check is the value.
    unchanged = live.admin.table("evaluations").select("status").eq("id", evaluation_id).execute().data[0]
    assert unchanged["status"] == "ASSIGNED", f"only the assigned evaluator may progress this evaluation, got {r.status_code}: {r.text}"


def test_invalid_lifecycle_transition_is_rejected(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )

    r = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"},
        json={"status": "SUBMITTED"},  # skips IN_PROGRESS
    )
    assert r.status_code >= 400, f"ASSIGNED -> SUBMITTED must be rejected, got {r.status_code}: {r.text}"

    unchanged = live.admin.table("evaluations").select("status").eq("id", evaluation_id).execute().data[0]
    assert unchanged["status"] == "ASSIGNED"


def test_evaluation_progresses_through_full_lifecycle_with_server_forced_timestamps(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )

    r1 = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"}, json={"status": "IN_PROGRESS"},
    )
    assert r1.status_code < 300, r1.text

    r2 = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"},
        json={
            "status": "SUBMITTED",
            "awarded_marks": "1.00",
            "feedback": "Correct reasoning.",
            # a spoofed client-supplied timestamp -- must be ignored/overwritten
            "submitted_at": "2000-01-01T00:00:00Z",
        },
    )
    assert r2.status_code < 300, r2.text
    row = live.admin.table("evaluations").select("*").eq("id", evaluation_id).execute().data[0]
    assert row["status"] == "SUBMITTED"
    assert not row["submitted_at"].startswith("2000-01-01"), "submitted_at must be server-forced, not client-trusted"

    r3 = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"},
        json={"status": "FINALIZED", "finalized_by": str(uuid.uuid4())},  # spoofed finalized_by
    )
    assert r3.status_code < 300, r3.text
    final_row = live.admin.table("evaluations").select("*").eq("id", evaluation_id).execute().data[0]
    assert final_row["status"] == "FINALIZED"
    assert final_row["finalized_by"] == ctx["evaluator_id"], "finalized_by must be server-forced to the acting evaluator, never client-trusted"
    assert final_row["finalized_at"] is not None


def test_finalization_requires_awarded_marks(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )
    _rest_as_user(live, ctx["evaluator_token"], "PATCH", "evaluations", params={"id": f"eq.{evaluation_id}"}, json={"status": "IN_PROGRESS"})
    r = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"}, json={"status": "SUBMITTED"},
    )
    assert r.status_code < 300, r.text  # SUBMITTED alone doesn't require marks

    r_finalize = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"}, json={"status": "FINALIZED"},  # no awarded_marks ever set
    )
    assert r_finalize.status_code >= 400, "cannot finalize without awarded_marks"


def test_finalized_evaluation_is_completely_immutable(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )
    for body in ({"status": "IN_PROGRESS"}, {"status": "SUBMITTED", "awarded_marks": "1.00"}, {"status": "FINALIZED"}):
        resp = _rest_as_user(live, ctx["evaluator_token"], "PATCH", "evaluations", params={"id": f"eq.{evaluation_id}"}, json=body)
        assert resp.status_code < 300, resp.text

    before = live.admin.table("evaluations").select("*").eq("id", evaluation_id).execute().data[0]
    assert before["status"] == "FINALIZED"

    attempts = [
        {"awarded_marks": "0.00"},
        {"feedback": "changed after the fact"},
        {"status": "SUBMITTED"},
    ]
    for body in attempts:
        r = _rest_as_user(live, ctx["evaluator_token"], "PATCH", "evaluations", params={"id": f"eq.{evaluation_id}"}, json=body)
        assert r.status_code >= 400, f"a finalized evaluation must reject {body}, got {r.status_code}: {r.text}"

    after = live.admin.table("evaluations").select("*").eq("id", evaluation_id).execute().data[0]
    assert after["awarded_marks"] == before["awarded_marks"]
    assert after["feedback"] == before["feedback"]
    assert after["status"] == "FINALIZED"


def test_revoking_assignment_blocks_further_evaluator_updates(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )
    live.admin.rpc("revoke_evaluator_assignment", {"p_assignment_id": assignment["id"], "p_revoked_by": ctx["creator_id"]}).execute()

    r = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"}, json={"status": "IN_PROGRESS"},
    )
    unchanged = live.admin.table("evaluations").select("status").eq("id", evaluation_id).execute().data[0]
    assert unchanged["status"] == "ASSIGNED", f"a revoked assignment's evaluator must lose further write access, got {r.status_code}: {r.text}"


def test_evaluation_history_records_every_transition(live):
    ctx = _setup_attempt_question(live)
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )
    for body in ({"status": "IN_PROGRESS"}, {"status": "SUBMITTED", "awarded_marks": "1.00", "feedback": "ok"}, {"status": "FINALIZED"}):
        _rest_as_user(live, ctx["evaluator_token"], "PATCH", "evaluations", params={"id": f"eq.{evaluation_id}"}, json=body)

    history = (
        live.admin.table("evaluation_history")
        .select("*")
        .eq("evaluation_id", evaluation_id)
        .order("occurred_at")
        .execute()
        .data
    )
    statuses = [row["new_status"] for row in history]
    assert statuses == ["ASSIGNED", "IN_PROGRESS", "SUBMITTED", "FINALIZED"]
    assert history[-1]["awarded_marks"] == 1.0  # postgrest-py deserializes numeric as a JSON number
    assert history[-1]["feedback"] == "ok"


# ============================================================
# Rubric
# ============================================================


def test_rubric_and_criteria_can_be_created_via_service_role(live):
    ctx = _setup_attempt_question(live)
    rubric = live.admin.table("rubrics").insert(
        {"question_id": ctx["question_id"], "name": "Correctness", "max_marks": "5.00", "created_by": ctx["creator_id"]}
    ).execute().data[0]
    c1 = live.admin.table("rubric_criteria").insert(
        {"rubric_id": rubric["id"], "criterion": "Accuracy", "max_marks": "3.00", "display_order": 0}
    ).execute().data[0]
    c2 = live.admin.table("rubric_criteria").insert(
        {"rubric_id": rubric["id"], "criterion": "Clarity", "max_marks": "2.00", "display_order": 1}
    ).execute().data[0]
    assert c1["rubric_id"] == rubric["id"]
    assert c2["display_order"] == 1


def test_criterion_requires_a_valid_rubric(live):
    with pytest.raises(APIError):
        live.admin.table("rubric_criteria").insert(
            {"rubric_id": str(uuid.uuid4()), "criterion": "Orphan", "max_marks": "1.00", "display_order": 0}
        ).execute()


def test_duplicate_criterion_display_order_is_rejected(live):
    ctx = _setup_attempt_question(live)
    rubric = live.admin.table("rubrics").insert(
        {"question_id": ctx["question_id"], "name": "R", "max_marks": "5.00"}
    ).execute().data[0]
    live.admin.table("rubric_criteria").insert(
        {"rubric_id": rubric["id"], "criterion": "A", "max_marks": "1.00", "display_order": 0}
    ).execute()
    with pytest.raises(APIError):
        live.admin.table("rubric_criteria").insert(
            {"rubric_id": rubric["id"], "criterion": "B", "max_marks": "1.00", "display_order": 0}
        ).execute()


def test_invalid_criterion_and_rubric_marks_are_rejected(live):
    ctx = _setup_attempt_question(live)
    with pytest.raises(APIError):
        live.admin.table("rubrics").insert(
            {"question_id": ctx["question_id"], "name": "Bad", "max_marks": "0.00"}
        ).execute()

    rubric = live.admin.table("rubrics").insert(
        {"question_id": ctx["question_id"], "name": "R2", "max_marks": "5.00"}
    ).execute().data[0]
    with pytest.raises(APIError):
        live.admin.table("rubric_criteria").insert(
            {"rubric_id": rubric["id"], "criterion": "Bad", "max_marks": "-1.00", "display_order": 0}
        ).execute()


def test_rubric_content_is_unreachable_by_any_authenticated_caller(live):
    """F8.1 leaves rubrics/rubric_criteria fully closed to `authenticated`
    (zero policies) -- who may author them is an explicit F8.3 decision,
    not made here. Today, this closure is itself the guarantee that
    'finalized evaluation cannot be silently changed by rubric mutation'
    (no authenticated path to rubrics exists at all); the usage-triggered
    immutability trigger (prevent_rubric_modification_after_use) is
    additive protection for once F8.3 opens a real write path."""
    ctx = _setup_attempt_question(live)
    rubric = live.admin.table("rubrics").insert(
        {"question_id": ctx["question_id"], "name": "Locked", "max_marks": "5.00"}
    ).execute().data[0]

    r_read = _rest_as_user(live, ctx["evaluator_token"], "GET", "rubrics", params={"id": f"eq.{rubric['id']}"})
    assert r_read.status_code < 300 and r_read.json() == [], "no SELECT policy -- must return zero rows, not an error"

    r_write = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "rubrics",
        params={"id": f"eq.{rubric['id']}"}, json={"max_marks": "999.00"},
    )
    unchanged = live.admin.table("rubrics").select("max_marks").eq("id", rubric["id"]).execute().data[0]
    assert unchanged["max_marks"] == 5.0, f"no UPDATE policy -- must be refused, got {r_write.status_code}"


def test_rubric_must_belong_to_the_assignments_own_question(live):
    ctx = _setup_attempt_question(live)
    other_ctx = _setup_attempt_question(live, tag="2")  # a DIFFERENT question
    unrelated_rubric = live.admin.table("rubrics").insert(
        {"question_id": other_ctx["question_id"], "name": "Wrong question", "max_marks": "5.00"}
    ).execute().data[0]

    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )
    r = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"}, json={"rubric_id": unrelated_rubric["id"]},
    )
    assert r.status_code >= 400, f"a rubric for a different question must be rejected, got {r.status_code}: {r.text}"


def test_awarded_marks_cannot_exceed_rubric_max_marks(live):
    ctx = _setup_attempt_question(live)
    rubric = live.admin.table("rubrics").insert(
        {"question_id": ctx["question_id"], "name": "Small", "max_marks": "2.00"}
    ).execute().data[0]
    assignment = _create_assignment(live, ctx)
    evaluation_id = (
        live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    )
    _rest_as_user(live, ctx["evaluator_token"], "PATCH", "evaluations", params={"id": f"eq.{evaluation_id}"}, json={"rubric_id": rubric["id"]})

    r = _rest_as_user(
        live, ctx["evaluator_token"], "PATCH", "evaluations",
        params={"id": f"eq.{evaluation_id}"}, json={"awarded_marks": "10.00"},
    )
    assert r.status_code >= 400, f"awarded_marks exceeding the rubric's max must be rejected, got {r.status_code}: {r.text}"


# ============================================================
# Isolation / regression -- the F8.1-specific guard the phase brief
# explicitly asks for (see the module docstring for why the rest of
# items 23-30 are proven by the EXISTING suites, not duplicated here).
# ============================================================


def test_faculty_evaluator_with_active_assignment_still_cannot_read_assessment_answers(live):
    """The single most important check in this file: even a FACULTY
    member who holds assessment_evaluator AND has a real, ACTIVE
    assignment to this EXACT (attempt, question) still cannot read the
    answer content directly -- F8.1 built the assignment/evaluation
    scaffolding but deliberately did not touch assessment_answers' RLS at
    all (that's F8.2). If this test ever fails, F8.1 accidentally
    widened Faculty answer access, which is the one thing it must never
    do."""
    ctx = _setup_attempt_question(live)
    _create_assignment(live, ctx)

    r = _rest_as_user(
        live, ctx["evaluator_token"], "GET", "assessment_answers",
        params={"attempt_id": f"eq.{ctx['attempt_id']}", "question_id": f"eq.{ctx['question_id']}"},
    )
    assert r.status_code < 300 and r.json() == [], (
        f"an evaluator must still see zero rows on assessment_answers in F8.1, got {r.status_code}: {r.text}"
    )
