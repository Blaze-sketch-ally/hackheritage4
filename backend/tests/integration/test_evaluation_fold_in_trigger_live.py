"""Live-integration coverage for Phase F8.4.2 -- wiring the F8.3
evaluation lifecycle so a successful FINALIZED transition automatically
triggers the F8.4.1 fold-in RPC (fold_in_attempt_evaluation), via
app.api.faculty_evaluations.update_evaluation_status /
app.services.evaluation_service.fold_in_attempt.

Unlike test_evaluation_fold_in_live.py (F8.4.1), this file deliberately
does NOT call fold_in_attempt_evaluation() directly via the admin RPC
client except where explicitly noted (the retry-after-fix flow) --
every "did fold-in happen" assertion here is driven purely by hitting
the real PATCH /faculty/evaluations/{id}/status FINALIZED endpoint and
reading back assessment_attempts afterward, proving the automatic wiring
itself, not just the underlying RPC (already proven by F8.4.1's own
suite). Self-contained, matching this directory's own convention.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import httpx


def _attempt_row(live, attempt_id: str) -> dict:
    return (
        live.admin.table("assessment_attempts")
        .select("evaluation_status, final_score, final_total_marks, final_percentage")
        .eq("id", attempt_id)
        .execute()
        .data[0]
    )


def _author_reviewer(live, tag: str) -> dict:
    fa_id, fa_email = live.create_user(f"tfa{tag}", "FACULTY")
    fb_id, fb_email = live.create_user(f"tfb{tag}", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    return {"fa_id": fa_id, "fa_token": live.token_for(fa_email), "fb_id": fb_id, "fb_token": live.token_for(fb_email)}


def _make_evaluator(live, tag: str) -> dict:
    fe_id, fe_email = live.create_user(f"tfe{tag}", "FACULTY")
    live.admin.table("faculty_assessment_permissions").insert(
        {"faculty_id": fe_id, "capability": "assessment_evaluator", "status": "GRANTED"}
    ).execute()
    return {"id": fe_id, "token": live.token_for(fe_email)}


def _assign(live, evaluator_id: str, attempt_id: str, question_id: str, creator_id: str) -> dict:
    return (
        live.admin.rpc(
            "create_evaluator_assignment",
            {"p_evaluator_id": evaluator_id, "p_attempt_id": attempt_id, "p_question_id": question_id, "p_created_by": creator_id},
        )
        .execute()
        .data
    )


def _evaluation_id_for(live, assignment_id: str) -> str:
    return live.admin.table("evaluations").select("id").eq("assignment_id", assignment_id).execute().data[0]["id"]


def _make_rubric(live, question_id: str, max_marks: str) -> str:
    return live.admin.table("rubrics").insert({"question_id": question_id, "name": "R", "max_marks": max_marks}).execute().data[0]["id"]


def _finalize(live, evaluator_token: str, evaluation_id: str, marks: str, rubric_id: str) -> httpx.Response:
    """Drives IN_PROGRESS -> save -> SUBMITTED -> FINALIZED. Unlike
    F8.4.1's own _finalize helper, this deliberately does NOT assert 200
    on the final FINALIZED transition -- some tests here expect it to
    come back as a genuine 500 (the fold-in-failure test) -- callers that
    expect success must assert that themselves."""
    r_start = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    assert r_start.status_code == 200, r_start.text
    r_save = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"rubric_id": rubric_id, "awarded_marks": marks})
    assert r_save.status_code == 200, r_save.text
    r_submit = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    assert r_submit.status_code == 200, r_submit.text
    return live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})


def _single_ai_evaluated_attempt(live, tag: str, points: str = "10.00", complete: bool = True) -> dict:
    """One SUBJECTIVE/AI_EVALUATED question. When complete=True (the
    default), the student submits and the attempt is scored to
    COMPLETED, exactly like F8.4.1's own fixture. When complete=False,
    the attempt is deliberately left IN_PROGRESS -- used only by the
    genuine-fold-in-failure test below."""
    people = _author_reviewer(live, tag)
    aid = live.create_assessment(title_suffix=tag)
    payload = {
        "assessment_id": aid, "question_text": f"__QA_{tag} subjective", "question_type": "SUBJECTIVE",
        "scoring_method": "AI_EVALUATED", "difficulty": "Intermediate", "points": points, "display_order": 0, "options": [],
    }
    qid = live.api(people["fa_token"], "POST", "/questions", json=payload).json()["id"]
    live.api(people["fb_token"], "POST", f"/questions/{qid}/approve")
    live.api(people["fa_token"], "PUT", f"/assessments/{aid}/blueprint", json={"rules": [{"difficulty": "Intermediate", "question_count": 1}]})

    s_id, s_email = live.create_user(f"ts{tag}", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": qid, "answer_text": "My answer."})
    if complete:
        live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
        live.api(s_token, "POST", f"/attempts/{attempt_id}/score")

    return {
        "attempt_id": attempt_id, "aid": aid, "qid": qid, "points": points,
        "student_id": s_id, "s_token": s_token, "creator_id": people["fa_id"],
    }


def _two_ai_question_attempt(live, tag: str, complete: bool = True) -> dict:
    """Two independent AI_EVALUATED questions in one attempt -- used for
    the non-last-vs-last-required-evaluation tests, and (complete=False)
    for the deferred-fold-in-then-completed ordering tests."""
    people = _author_reviewer(live, tag)
    aid = live.create_assessment(title_suffix=tag)
    q1 = {"assessment_id": aid, "question_text": f"__QA_{tag} q1", "question_type": "SUBJECTIVE", "scoring_method": "AI_EVALUATED", "difficulty": "Beginner", "points": "5.00", "display_order": 0, "options": []}
    q2 = {"assessment_id": aid, "question_text": f"__QA_{tag} q2", "question_type": "SUBJECTIVE", "scoring_method": "AI_EVALUATED", "difficulty": "Intermediate", "points": "5.00", "display_order": 1, "options": []}
    q1_id = live.api(people["fa_token"], "POST", "/questions", json=q1).json()["id"]
    q2_id = live.api(people["fa_token"], "POST", "/questions", json=q2).json()["id"]
    for qid in (q1_id, q2_id):
        live.api(people["fb_token"], "POST", f"/questions/{qid}/approve")
    live.api(
        people["fa_token"], "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 1}, {"difficulty": "Intermediate", "question_count": 1}]},
    )
    s_id, s_email = live.create_user(f"ts{tag}", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": q1_id, "answer_text": "a1"})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": q2_id, "answer_text": "a2"})
    if complete:
        live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
        live.api(s_token, "POST", f"/attempts/{attempt_id}/score")
    return {
        "attempt_id": attempt_id, "aid": aid, "q1_id": q1_id, "q2_id": q2_id,
        "student_id": s_id, "s_token": s_token, "creator_id": people["fa_id"],
    }


def _mixed_attempt(live, tag: str) -> dict:
    people = _author_reviewer(live, tag)
    aid = live.create_assessment(title_suffix=tag)
    opt1, opt2 = str(uuid.uuid4()), str(uuid.uuid4())
    mcq_payload = {
        "assessment_id": aid, "question_text": f"__QA_{tag} mcq", "question_type": "MCQ",
        "scoring_method": "OBJECTIVE", "difficulty": "Beginner", "points": "6.00", "display_order": 0,
        "options": [{"id": opt1, "option_text": "A", "display_order": 0}, {"id": opt2, "option_text": "B", "display_order": 1}],
        "answer_key": {"correct_option_ids": [opt2]},
    }
    mcq_id = live.api(people["fa_token"], "POST", "/questions", json=mcq_payload).json()["id"]
    ai_payload = {
        "assessment_id": aid, "question_text": f"__QA_{tag} subjective", "question_type": "SUBJECTIVE",
        "scoring_method": "AI_EVALUATED", "difficulty": "Intermediate", "points": "4.00", "display_order": 1, "options": [],
    }
    ai_id = live.api(people["fa_token"], "POST", "/questions", json=ai_payload).json()["id"]
    for qid in (mcq_id, ai_id):
        live.api(people["fb_token"], "POST", f"/questions/{qid}/approve")
    live.api(
        people["fa_token"], "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 1}, {"difficulty": "Intermediate", "question_count": 1}]},
    )
    s_id, s_email = live.create_user(f"ts{tag}", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": mcq_id, "selected_option_ids": [opt2]})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ai_id, "answer_text": "answer"})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    live.api(s_token, "POST", f"/attempts/{attempt_id}/score")
    return {"attempt_id": attempt_id, "aid": aid, "mcq_id": mcq_id, "ai_id": ai_id, "student_id": s_id, "creator_id": people["fa_id"]}


# ============================================================
# 1. Basic trigger
# ============================================================


def test_finalizing_the_only_required_evaluation_auto_triggers_fold_in(live):
    ctx = _single_ai_evaluated_attempt(live, "t1", points="10.00")
    ev = _make_evaluator(live, "t1")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")

    before = _attempt_row(live, ctx["attempt_id"])
    # As of F8.4.2.1's Fix A, _single_ai_evaluated_attempt's own submit+
    # score already auto-triggered fold-in (050_fold_in_after_attempt_
    # completed.sql) before this assignment/rubric even existed -- one
    # AI_EVALUATED question, zero evaluations yet, so PENDING, not the
    # column's raw NOT_REQUIRED default (that default is only ever
    # observed for an attempt that has never yet reached COMPLETED at
    # all -- see test_finalize_before_attempt_completed_defers_gracefully).
    assert before["evaluation_status"] == "PENDING"

    r_final = _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "7.00", rubric_id)
    assert r_final.status_code == 200, r_final.text

    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after["final_score"])) == Decimal("7.00")
    assert Decimal(str(after["final_total_marks"])) == Decimal("10.00")
    assert Decimal(str(after["final_percentage"])) == Decimal("70.00")


# ============================================================
# 2/3. Non-last vs last required evaluation
# ============================================================


def test_finalizing_a_non_last_required_evaluation_leaves_attempt_pending_or_partial(live):
    ctx = _two_ai_question_attempt(live, "t2")
    ev = _make_evaluator(live, "t2")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["q1_id"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["q1_id"], "5.00")

    r_final = _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "4.00", rubric_id)
    assert r_final.status_code == 200, r_final.text

    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "PARTIAL"
    assert after["final_score"] is None


def test_finalizing_the_last_required_evaluation_produces_complete(live):
    ctx = _two_ai_question_attempt(live, "t3")
    ev1 = _make_evaluator(live, "t3a")
    ev2 = _make_evaluator(live, "t3b")
    a1 = _assign(live, ev1["id"], ctx["attempt_id"], ctx["q1_id"], ctx["creator_id"])
    a2 = _assign(live, ev2["id"], ctx["attempt_id"], ctx["q2_id"], ctx["creator_id"])
    r1 = _make_rubric(live, ctx["q1_id"], "5.00")
    r2 = _make_rubric(live, ctx["q2_id"], "5.00")

    r_first = _finalize(live, ev1["token"], _evaluation_id_for(live, a1["id"]), "4.00", r1)
    assert r_first.status_code == 200, r_first.text
    mid = _attempt_row(live, ctx["attempt_id"])
    assert mid["evaluation_status"] == "PARTIAL"

    r_second = _finalize(live, ev2["token"], _evaluation_id_for(live, a2["id"]), "3.00", r2)
    assert r_second.status_code == 200, r_second.text

    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after["final_score"])) == Decimal("7.00")  # 4 + 3
    assert Decimal(str(after["final_total_marks"])) == Decimal("10.00")


# ============================================================
# 4. Mixed objective + AI_EVALUATED
# ============================================================


def test_mixed_assessment_final_score_correct_after_auto_fold_in(live):
    ctx = _mixed_attempt(live, "t4")
    ev = _make_evaluator(live, "t4")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["ai_id"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["ai_id"], "4.00")

    r_final = _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "3.00", rubric_id)
    assert r_final.status_code == 200, r_final.text

    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after["final_score"])) == Decimal("9.00")  # 6 (MCQ) + 3
    assert Decimal(str(after["final_total_marks"])) == Decimal("10.00")


# ============================================================
# 5/6/7. Co-evaluation via automatic triggering
# ============================================================


def test_two_agreeing_evaluators_auto_trigger_to_complete(live):
    ctx = _single_ai_evaluated_attempt(live, "t5", points="10.00")
    ev_a = _make_evaluator(live, "t5a")
    ev_b = _make_evaluator(live, "t5b")
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    assignment_a = _assign(live, ev_a["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    assignment_b = _assign(live, ev_b["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])

    r_a = _finalize(live, ev_a["token"], _evaluation_id_for(live, assignment_a["id"]), "7.00", rubric_id)
    assert r_a.status_code == 200, r_a.text
    after_a = _attempt_row(live, ctx["attempt_id"])
    assert after_a["evaluation_status"] == "COMPLETE"  # correct with one evaluator so far

    r_b = _finalize(live, ev_b["token"], _evaluation_id_for(live, assignment_b["id"]), "7.00", rubric_id)
    assert r_b.status_code == 200, r_b.text
    after_b = _attempt_row(live, ctx["attempt_id"])
    assert after_b["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after_b["final_score"])) == Decimal("7.00")


def test_two_disagreeing_evaluators_auto_trigger_to_needs_reconciliation(live):
    ctx = _single_ai_evaluated_attempt(live, "t6", points="10.00")
    ev_a = _make_evaluator(live, "t6a")
    ev_b = _make_evaluator(live, "t6b")
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    assignment_a = _assign(live, ev_a["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    assignment_b = _assign(live, ev_b["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])

    r_a = _finalize(live, ev_a["token"], _evaluation_id_for(live, assignment_a["id"]), "7.00", rubric_id)
    assert r_a.status_code == 200, r_a.text
    after_a = _attempt_row(live, ctx["attempt_id"])
    assert after_a["evaluation_status"] == "COMPLETE"  # provisionally correct with only A so far

    r_b = _finalize(live, ev_b["token"], _evaluation_id_for(live, assignment_b["id"]), "9.00", rubric_id)
    assert r_b.status_code == 200, r_b.text  # the evaluation itself still finalizes successfully

    after_b = _attempt_row(live, ctx["attempt_id"])
    assert after_b["evaluation_status"] == "NEEDS_RECONCILIATION"
    assert after_b["final_score"] is None
    assert after_b["final_total_marks"] is None
    assert after_b["final_percentage"] is None

    # No averaging, no latest-wins: both finalized marks remain intact.
    marks = (
        live.admin.table("evaluations")
        .select("awarded_marks")
        .in_("assignment_id", [assignment_a["id"], assignment_b["id"]])
        .execute()
        .data
    )
    assert sorted(Decimal(str(m["awarded_marks"])) for m in marks) == [Decimal("7.00"), Decimal("9.00")]


# ============================================================
# 8. Duplicate FINALIZED request is safe/idempotent
# ============================================================


def test_duplicate_finalized_request_is_safe_and_idempotent(live):
    ctx = _single_ai_evaluated_attempt(live, "t7", points="10.00")
    ev = _make_evaluator(live, "t7")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    r1 = _finalize(live, ev["token"], evaluation_id, "6.00", rubric_id)
    assert r1.status_code == 200, r1.text
    after_first = _attempt_row(live, ctx["attempt_id"])

    # Re-send the identical FINALIZED transition -- hits the idempotent
    # short-circuit in evaluation_service.update_evaluation_status, no
    # second write to the evaluation row, but still re-triggers fold-in.
    r2 = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r2.status_code == 200, r2.text
    after_second = _attempt_row(live, ctx["attempt_id"])

    assert after_second == after_first
    assert after_second["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after_second["final_score"])) == Decimal("6.00")


# ============================================================
# 9. Invalid transition never triggers fold-in
# ============================================================


def test_invalid_transition_does_not_trigger_fold_in(live):
    ctx = _single_ai_evaluated_attempt(live, "t8", points="10.00")
    ev = _make_evaluator(live, "t8")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    # ASSIGNED -> FINALIZED directly is not a legal one-hop transition.
    before = _attempt_row(live, ctx["attempt_id"])  # PENDING already, from Fix A's completion-time auto fold-in
    r = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r.status_code == 409, r.text

    after = _attempt_row(live, ctx["attempt_id"])
    assert after == before  # untouched by the rejected transition -- fold-in never ran again


# ============================================================
# 10. Unauthorized evaluator cannot trigger fold-in
# ============================================================


def test_unauthorized_evaluator_cannot_trigger_fold_in(live):
    ctx = _single_ai_evaluated_attempt(live, "t9", points="10.00")
    ev_owner = _make_evaluator(live, "t9owner")
    ev_stranger = _make_evaluator(live, "t9stranger")
    assignment = _assign(live, ev_owner["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    # The stranger was never assigned this evaluation -- 046/047's own
    # RLS makes it invisible to them, regardless of the fact that they
    # independently hold the assessment_evaluator capability.
    before = _attempt_row(live, ctx["attempt_id"])  # PENDING already, from Fix A's completion-time auto fold-in
    r = live.api(ev_stranger["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    assert r.status_code == 404, r.text

    after = _attempt_row(live, ctx["attempt_id"])
    assert after == before  # untouched -- fold-in never ran again


# ============================================================
# 11/12/13. Revocation / capability / question mutation after
# auto-fold-in -- historical result must not erase.
# ============================================================


def test_evaluator_revoked_after_auto_fold_in_result_unchanged(live):
    """Deliberately does NOT resend the FINALIZED PATCH after revocation
    -- that specific combination (idempotent-resend + a since-revoked
    assignment) hits a separate, pre-existing bug in evaluation_service.
    update_evaluation_status's own idempotent short-circuit (_to_summary
    -> _student_id_for_attempt returns None once 046's ACTIVE-assignment-
    scoped policy stops resolving the attempt, violating
    EvaluationSummaryResponse's non-nullable student_id) -- unrelated to
    F8.4.2's own fold-in trigger, out of this phase's scope (evaluation_
    service.py must not be modified unless absolutely required), and
    reported separately. This test instead verifies exactly what F8.4.2
    requires: revocation must not erase the already-folded-in historical
    result, without needing any second live request."""
    ctx = _single_ai_evaluated_attempt(live, "t10", points="10.00")
    ev = _make_evaluator(live, "t10")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    r_final = _finalize(live, ev["token"], evaluation_id, "4.00", rubric_id)
    assert r_final.status_code == 200, r_final.text
    first = _attempt_row(live, ctx["attempt_id"])
    assert first["evaluation_status"] == "COMPLETE"

    live.admin.rpc("revoke_evaluator_assignment", {"p_assignment_id": assignment["id"], "p_revoked_by": ctx["creator_id"]}).execute()

    second = _attempt_row(live, ctx["attempt_id"])
    assert second == first
    assert Decimal(str(second["final_score"])) == Decimal("4.00")


def test_duplicate_finalize_resend_after_revocation_returns_404(live):
    """Phase F8.4.2.1, Fix B: previously (F8.4.2) this exact scenario
    500'd -- see the git history of this test, formerly named
    test_KNOWN_ISSUE_duplicate_finalize_resend_after_revocation_500s.

    Root cause was in evaluation_service.update_evaluation_status's
    idempotent short-circuit: resending the SAME already-FINALIZED
    status for an evaluation whose assignment has since been revoked
    fell through to _to_summary() -> _student_id_for_attempt(), which
    silently resolved to None once 046's ACTIVE-only assessment_attempts
    policy stopped matching -- failing EvaluationSummaryResponse's
    non-nullable student_id at response-model validation time (500).

    Fix B added an explicit evaluator_assignments.status == 'ACTIVE'
    check to that same idempotent branch (mirroring get_evaluation_
    detail's own F8.2.1 precedent exactly) -- "assignment no longer
    active" now returns None -> 404, before _to_summary() is ever
    called, matching every other revocation behavior in this codebase.
    No RLS change, no schema change, no broadened access: the historical
    evaluation and its already-folded-in contribution to the attempt
    remain completely untouched by this request.
    """
    ctx = _single_ai_evaluated_attempt(live, "t10x", points="10.00")
    ev = _make_evaluator(live, "t10x")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    r_final = _finalize(live, ev["token"], evaluation_id, "4.00", rubric_id)
    assert r_final.status_code == 200, r_final.text

    live.admin.rpc("revoke_evaluator_assignment", {"p_assignment_id": assignment["id"], "p_revoked_by": ctx["creator_id"]}).execute()

    r_retry = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_retry.status_code == 404, r_retry.text

    # No question/answer/rubric/student content in the 404 body.
    body_text = r_retry.text.lower()
    for leaked in ("question", "answer", "rubric", "student_id", ctx["student_id"].lower()):
        assert leaked not in body_text, f"{leaked!r} unexpectedly present in 404 body: {r_retry.text}"

    # The already-folded-in historical result was completely untouched.
    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after["final_score"])) == Decimal("4.00")


def test_duplicate_finalize_resend_after_capability_expiry_returns_403(live):
    """Verifies (does not newly fix -- this path was already correct
    before F8.4.2.1, and corrects the audit's own predicted status code)
    that capability expiry, unlike assignment revocation, already
    produces a clean, non-500 rejection on an idempotent resend -- but
    at an EARLIER point than the audit assumed: app.core.dependencies.
    require_assessment_capability (the FastAPI dependency EVERY route in
    faculty_evaluations.py requires) checks the caller's CURRENT
    capabilities before the route body -- and therefore before
    evaluation_service.update_evaluation_status -- ever runs, rejecting
    with 403 ("This action requires the assessment_evaluator
    capability."), not 404. evaluations' own SELECT policy (045) being
    capability-gated (has_assessment_capability) would ALSO have
    produced a clean outcome (current_row is None, mapped to 404) had
    the request ever reached that far -- it simply never does, since the
    app-layer dependency rejects first. Either way, never a 500, and
    Fix B's new ACTIVE check in the idempotent branch is unreached here.
    """
    ctx = _single_ai_evaluated_attempt(live, "t10y", points="10.00")
    ev = _make_evaluator(live, "t10y")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    r_final = _finalize(live, ev["token"], evaluation_id, "6.00", rubric_id)
    assert r_final.status_code == 200, r_final.text

    live.admin.table("faculty_assessment_permissions").update({"expires_at": "2000-01-01T00:00:00Z"}).eq("faculty_id", ev["id"]).eq("capability", "assessment_evaluator").execute()

    r_retry = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_retry.status_code == 403, r_retry.text

    body_text = r_retry.text.lower()
    for leaked in ("question", "answer", "rubric", "student_id", ctx["student_id"].lower()):
        assert leaked not in body_text, f"{leaked!r} unexpectedly present in 403 body: {r_retry.text}"

    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after["final_score"])) == Decimal("6.00")


def test_active_idempotent_finalized_resend_still_succeeds(live):
    """Regression guard for Fix B: an ACTIVE assignment + valid
    capability + an idempotent FINALIZED resend must remain a normal
    200 with the existing response shape -- Fix B's new ACTIVE check
    must never turn a legitimate, still-active idempotent resend into a
    404."""
    ctx = _single_ai_evaluated_attempt(live, "t10z", points="10.00")
    ev = _make_evaluator(live, "t10z")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    r_final = _finalize(live, ev["token"], evaluation_id, "5.00", rubric_id)
    assert r_final.status_code == 200, r_final.text

    r_retry = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_retry.status_code == 200, r_retry.text
    body = r_retry.json()
    assert body["status"] == "FINALIZED"
    assert body["evaluation_id"] == evaluation_id
    assert Decimal(str(body["awarded_marks"])) == Decimal("5.00")


def test_capability_expired_after_auto_fold_in_result_unchanged(live):
    ctx = _single_ai_evaluated_attempt(live, "t11", points="10.00")
    ev = _make_evaluator(live, "t11")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    r_final = _finalize(live, ev["token"], evaluation_id, "3.00", rubric_id)
    assert r_final.status_code == 200, r_final.text
    first = _attempt_row(live, ctx["attempt_id"])

    live.admin.table("faculty_assessment_permissions").update({"expires_at": "2000-01-01T00:00:00Z"}).eq("faculty_id", ev["id"]).eq("capability", "assessment_evaluator").execute()

    second = _attempt_row(live, ctx["attempt_id"])
    assert second == first  # nothing re-triggered fold-in, and nothing needed to


def test_question_deactivated_after_auto_fold_in_result_still_reproducible(live):
    ctx = _single_ai_evaluated_attempt(live, "t12", points="10.00")
    ev = _make_evaluator(live, "t12")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    r_final = _finalize(live, ev["token"], evaluation_id, "8.00", rubric_id)
    assert r_final.status_code == 200, r_final.text
    first = _attempt_row(live, ctx["attempt_id"])

    live.admin.table("assessment_questions").update({"is_active": False}).eq("id", ctx["qid"]).execute()

    r_retry = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_retry.status_code == 200, r_retry.text
    second = _attempt_row(live, ctx["attempt_id"])
    assert second["evaluation_status"] == "COMPLETE"
    assert second["final_score"] == first["final_score"]
    assert second["final_total_marks"] == first["final_total_marks"]


# ============================================================
# 14. Correction evaluation creates disagreement
# ============================================================


def test_new_correction_evaluation_auto_triggers_needs_reconciliation(live):
    ctx = _single_ai_evaluated_attempt(live, "t13", points="10.00")
    ev_original = _make_evaluator(live, "t13orig")
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    assignment_original = _assign(live, ev_original["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    evaluation_original_id = _evaluation_id_for(live, assignment_original["id"])

    r_first = _finalize(live, ev_original["token"], evaluation_original_id, "6.00", rubric_id)
    assert r_first.status_code == 200, r_first.text
    first = _attempt_row(live, ctx["attempt_id"])
    assert first["evaluation_status"] == "COMPLETE"

    # A correction: a NEW assignment/evaluation for a different
    # evaluator, on the same attempt/question -- the original FINALIZED
    # evaluation is never mutated (immutable, F8.1).
    ev_correction = _make_evaluator(live, "t13correction")
    assignment_correction = _assign(live, ev_correction["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    r_second = _finalize(live, ev_correction["token"], _evaluation_id_for(live, assignment_correction["id"]), "9.00", rubric_id)
    assert r_second.status_code == 200, r_second.text

    second = _attempt_row(live, ctx["attempt_id"])
    assert second["evaluation_status"] == "NEEDS_RECONCILIATION"
    assert second["final_score"] is None

    original_still = live.admin.table("evaluations").select("status, awarded_marks").eq("id", evaluation_original_id).execute().data[0]
    assert original_still["status"] == "FINALIZED"
    assert Decimal(str(original_still["awarded_marks"])) == Decimal("6.00")


# ============================================================
# 15. Concurrency
# ============================================================


def test_concurrent_agreeing_finalizations_converge_to_complete(live):
    ctx = _single_ai_evaluated_attempt(live, "t14", points="10.00")
    ev_a = _make_evaluator(live, "t14a")
    ev_b = _make_evaluator(live, "t14b")
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    assignment_a = _assign(live, ev_a["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    assignment_b = _assign(live, ev_b["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    evaluation_a = _evaluation_id_for(live, assignment_a["id"])
    evaluation_b = _evaluation_id_for(live, assignment_b["id"])
    # Bring both to SUBMITTED first so only the final FINALIZED PATCH
    # (the one that triggers fold-in) races.
    for token, eval_id in ((ev_a["token"], evaluation_a), (ev_b["token"], evaluation_b)):
        live.api(token, "PATCH", f"/faculty/evaluations/{eval_id}/status", json={"status": "IN_PROGRESS"})
        live.api(token, "PATCH", f"/faculty/evaluations/{eval_id}", json={"rubric_id": rubric_id, "awarded_marks": "6.00"})
        live.api(token, "PATCH", f"/faculty/evaluations/{eval_id}/status", json={"status": "SUBMITTED"})

    def _do_finalize(args):
        token, eval_id = args
        return live.api(token, "PATCH", f"/faculty/evaluations/{eval_id}/status", json={"status": "FINALIZED"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_do_finalize, [(ev_a["token"], evaluation_a), (ev_b["token"], evaluation_b)]))

    for r in results:
        assert r.status_code == 200, r.text

    final_row = _attempt_row(live, ctx["attempt_id"])
    assert final_row["evaluation_status"] == "COMPLETE"
    assert Decimal(str(final_row["final_score"])) == Decimal("6.00")


def test_concurrent_disagreeing_finalizations_converge_to_needs_reconciliation(live):
    ctx = _single_ai_evaluated_attempt(live, "t15", points="10.00")
    ev_a = _make_evaluator(live, "t15a")
    ev_b = _make_evaluator(live, "t15b")
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    assignment_a = _assign(live, ev_a["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    assignment_b = _assign(live, ev_b["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    evaluation_a = _evaluation_id_for(live, assignment_a["id"])
    evaluation_b = _evaluation_id_for(live, assignment_b["id"])
    for token, eval_id, marks in ((ev_a["token"], evaluation_a, "6.00"), (ev_b["token"], evaluation_b, "8.00")):
        live.api(token, "PATCH", f"/faculty/evaluations/{eval_id}/status", json={"status": "IN_PROGRESS"})
        live.api(token, "PATCH", f"/faculty/evaluations/{eval_id}", json={"rubric_id": rubric_id, "awarded_marks": marks})
        live.api(token, "PATCH", f"/faculty/evaluations/{eval_id}/status", json={"status": "SUBMITTED"})

    def _do_finalize(args):
        token, eval_id = args
        return live.api(token, "PATCH", f"/faculty/evaluations/{eval_id}/status", json={"status": "FINALIZED"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_do_finalize, [(ev_a["token"], evaluation_a), (ev_b["token"], evaluation_b)]))

    for r in results:
        assert r.status_code == 200, r.text  # both evaluations finalize successfully regardless of the attempt-level outcome

    final_row = _attempt_row(live, ctx["attempt_id"])
    assert final_row["evaluation_status"] == "NEEDS_RECONCILIATION"
    assert final_row["final_score"] is None


# ============================================================
# Error/retry: a genuine, unfaked fold-in failure.
# ============================================================


def test_finalize_before_attempt_completed_defers_gracefully(live):
    """Constructs a REAL, unmocked fold_in_attempt_evaluation() rejection
    (SQLSTATE 55000, "Attempt is not eligible for evaluation fold-in") by
    finalizing an evaluation whose ATTEMPT was deliberately never
    submitted/scored (create_evaluator_assignment,
    045_evaluation_foundation.sql, has no attempt-status precondition --
    an evaluator can legally be assigned, and can legally finalize their
    own evaluation, against an attempt that is still IN_PROGRESS; F8.3's
    own established workflow has always allowed this ordering). This is
    not a mocked/weakened RPC -- the real trusted RPC genuinely rejects
    this attempt's status.

    Per app.services.evaluation_service.EvaluationFoldInNotEligibleError's
    own docstring, this is treated as benign, not a failure: the
    evaluation's FINALIZED transition still returns 200 (it IS genuinely
    finalized), fold-in is silently deferred, and no corrupted/partial
    final_* values are ever written.

    Renamed from F8.4.2's own test_finalize_before_attempt_completed_
    defers_gracefully_and_later_resend_recovers -- as of F8.4.2.1 Fix A,
    completing the attempt alone (no second evaluator FINALIZED request
    of any kind) now automatically recovers this -- see
    test_deferred_finalize_auto_folds_in_when_attempt_later_completes
    below for that dedicated proof. This test now stops at the deferral
    itself, plus a manual resend as a still-valid, still-safe fallback
    path (F8.4.2's original recovery contract, kept working
    unconditionally).

    (The separate "genuinely unexpected fold-in failure -> 500, logged,
    evaluation stays finalized, safe retry" contract is proven at the
    unit level in test_evaluations.py -- constructing a truly unexpected
    live DB failure without weakening the real RPC is not practical.)
    """
    ctx = _single_ai_evaluated_attempt(live, "t16", points="10.00", complete=False)
    ev = _make_evaluator(live, "t16")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    attempt_before = live.admin.table("assessment_attempts").select("status").eq("id", ctx["attempt_id"]).execute().data[0]
    assert attempt_before["status"] == "IN_PROGRESS"  # the precondition this test relies on

    r_final = _finalize(live, ev["token"], evaluation_id, "8.00", rubric_id)
    assert r_final.status_code == 200, r_final.text  # the evaluation itself genuinely finalizes

    eval_row = live.admin.table("evaluations").select("status, awarded_marks").eq("id", evaluation_id).execute().data[0]
    assert eval_row["status"] == "FINALIZED"
    assert Decimal(str(eval_row["awarded_marks"])) == Decimal("8.00")

    # No corrupted/partial final_* values were ever written -- fold-in
    # was silently deferred, not partially applied.
    after_deferral = _attempt_row(live, ctx["attempt_id"])
    assert after_deferral["evaluation_status"] == "NOT_REQUIRED"  # unchanged column default -- fold-in never wrote anything
    assert after_deferral["final_score"] is None
    assert after_deferral["final_total_marks"] is None
    assert after_deferral["final_percentage"] is None

    # Fix the underlying condition (submit + score the attempt), then a
    # manual resend remains a valid, safe fallback recovery path
    # (F8.4.2's original contract) even though F8.4.2.1's Fix A now also
    # recovers this automatically without any resend at all -- see
    # test_deferred_finalize_auto_folds_in_when_attempt_later_completes
    # below for that dedicated, resend-free proof.
    live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/submit")
    live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/score")

    r_retry = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_retry.status_code == 200, r_retry.text

    after_retry = _attempt_row(live, ctx["attempt_id"])
    assert after_retry["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after_retry["final_score"])) == Decimal("8.00")
    assert Decimal(str(after_retry["final_total_marks"])) == Decimal("10.00")


# ============================================================
# Phase F8.4.2.1, Fix A -- automatic fold-in when the attempt
# LATER becomes COMPLETED, with no second evaluator FINALIZED
# request of any kind (database trigger, 050_fold_in_after_
# attempt_completed.sql).
# ============================================================


def test_deferred_finalize_auto_folds_in_when_attempt_later_completes(live):
    """THE key F8.4.2.1 test. Sequence, exactly per the approved audit's
    own required test 2:
      1. create an AI_EVALUATED attempt (left IN_PROGRESS)
      2. create an evaluator assignment
      3. finalize the evaluation while the attempt is still IN_PROGRESS
         (fold-in defers, per test_finalize_before_attempt_completed_
         defers_gracefully above)
      4. do NOT send a second FINALIZED PATCH of any kind
      5. submit the attempt
      6. score the attempt
      7. query assessment_attempts directly

    Asserts the NEW 050 trigger alone -- fired purely as a side effect
    of POST /attempts/{id}/score setting status = 'COMPLETED' -- already
    produced the correct evaluation_status/final_* with zero further
    evaluator interaction.
    """
    ctx = _single_ai_evaluated_attempt(live, "t17", points="10.00", complete=False)
    ev = _make_evaluator(live, "t17")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    r_final = _finalize(live, ev["token"], evaluation_id, "7.00", rubric_id)
    assert r_final.status_code == 200, r_final.text

    before_completion = _attempt_row(live, ctx["attempt_id"])
    assert before_completion["evaluation_status"] == "NOT_REQUIRED"  # deferred, nothing computed yet

    # No second FINALIZED request anywhere below -- only the student's
    # own submit + score.
    r_submit = live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/submit")
    assert r_submit.status_code == 200, r_submit.text
    r_score = live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/score")
    assert r_score.status_code == 200, r_score.text

    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after["final_score"])) == Decimal("7.00")
    assert Decimal(str(after["final_total_marks"])) == Decimal("10.00")
    assert Decimal(str(after["final_percentage"])) == Decimal("70.00")

    # The evaluation itself is untouched by the trigger.
    eval_row = live.admin.table("evaluations").select("status, awarded_marks").eq("id", evaluation_id).execute().data[0]
    assert eval_row["status"] == "FINALIZED"
    assert Decimal(str(eval_row["awarded_marks"])) == Decimal("7.00")


def test_multi_question_finalize_first_then_complete_produces_correct_final_state(live):
    """Ordering: both AI_EVALUATED evaluations finalized while the
    attempt is still IN_PROGRESS, THEN the attempt completes. No second
    FINALIZED request after completion -- the 050 trigger alone must
    fold in both already-finalized evaluations."""
    ctx = _two_ai_question_attempt(live, "t18", complete=False)
    ev1 = _make_evaluator(live, "t18a")
    ev2 = _make_evaluator(live, "t18b")
    a1 = _assign(live, ev1["id"], ctx["attempt_id"], ctx["q1_id"], ctx["creator_id"])
    a2 = _assign(live, ev2["id"], ctx["attempt_id"], ctx["q2_id"], ctx["creator_id"])
    r1 = _make_rubric(live, ctx["q1_id"], "5.00")
    r2 = _make_rubric(live, ctx["q2_id"], "5.00")

    assert _finalize(live, ev1["token"], _evaluation_id_for(live, a1["id"]), "4.00", r1).status_code == 200
    assert _finalize(live, ev2["token"], _evaluation_id_for(live, a2["id"]), "3.00", r2).status_code == 200

    assert _attempt_row(live, ctx["attempt_id"])["evaluation_status"] == "NOT_REQUIRED"  # still deferred

    live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/submit")
    live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/score")

    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after["final_score"])) == Decimal("7.00")  # 4 + 3
    assert Decimal(str(after["final_total_marks"])) == Decimal("10.00")


def test_multi_question_complete_first_then_finalize_produces_same_final_state(live):
    """The opposite ordering of the test above, using the SAME marks:
    the attempt completes first, then both evaluations are finalized
    (F8.4.2's own route-level trigger, unchanged). The final result must
    be identical regardless of which direction happened first --
    exactly the ordering-independence invariant this phase exists to
    guarantee."""
    ctx = _two_ai_question_attempt(live, "t19", complete=True)
    ev1 = _make_evaluator(live, "t19a")
    ev2 = _make_evaluator(live, "t19b")
    a1 = _assign(live, ev1["id"], ctx["attempt_id"], ctx["q1_id"], ctx["creator_id"])
    a2 = _assign(live, ev2["id"], ctx["attempt_id"], ctx["q2_id"], ctx["creator_id"])
    r1 = _make_rubric(live, ctx["q1_id"], "5.00")
    r2 = _make_rubric(live, ctx["q2_id"], "5.00")

    assert _finalize(live, ev1["token"], _evaluation_id_for(live, a1["id"]), "4.00", r1).status_code == 200
    assert _finalize(live, ev2["token"], _evaluation_id_for(live, a2["id"]), "3.00", r2).status_code == 200

    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after["final_score"])) == Decimal("7.00")
    assert Decimal(str(after["final_total_marks"])) == Decimal("10.00")


def test_multi_question_disagreement_after_deferred_completion_is_needs_reconciliation(live):
    """Both evaluations finalized pre-completion, but disagreeing on the
    SAME question (two evaluators on q1, none on q2 is required here --
    reuse the single-question co-evaluation shape but with the deferred
    ordering) -- the 050 trigger alone must correctly surface
    NEEDS_RECONCILIATION with no final_* populated, exactly like
    F8.4.2's own already-completed-attempt disagreement test."""
    ctx = _single_ai_evaluated_attempt(live, "t20", points="10.00", complete=False)
    ev_a = _make_evaluator(live, "t20a")
    ev_b = _make_evaluator(live, "t20b")
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    assignment_a = _assign(live, ev_a["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    assignment_b = _assign(live, ev_b["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])

    assert _finalize(live, ev_a["token"], _evaluation_id_for(live, assignment_a["id"]), "6.00", rubric_id).status_code == 200
    assert _finalize(live, ev_b["token"], _evaluation_id_for(live, assignment_b["id"]), "9.00", rubric_id).status_code == 200

    live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/submit")
    live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/score")

    after = _attempt_row(live, ctx["attempt_id"])
    assert after["evaluation_status"] == "NEEDS_RECONCILIATION"
    assert after["final_score"] is None
    assert after["final_total_marks"] is None
    assert after["final_percentage"] is None


def test_objective_only_attempt_completion_unaffected_by_new_trigger(live):
    """The 050 trigger fires unconditionally on every COMPLETED
    transition, including an attempt with zero AI_EVALUATED questions --
    must remain a pure, cheap no-op: evaluation_status stays NOT_REQUIRED
    (already the default), and the objective score/total_marks/
    percentage response is completely unchanged."""
    people = _author_reviewer(live, "t21")
    aid = live.create_assessment(title_suffix="t21")
    opt1, opt2 = str(uuid.uuid4()), str(uuid.uuid4())
    mcq_payload = {
        "assessment_id": aid, "question_text": "__QA_t21 mcq", "question_type": "MCQ",
        "scoring_method": "OBJECTIVE", "difficulty": "Beginner", "points": "5.00", "display_order": 0,
        "options": [{"id": opt1, "option_text": "A", "display_order": 0}, {"id": opt2, "option_text": "B", "display_order": 1}],
        "answer_key": {"correct_option_ids": [opt2]},
    }
    qid = live.api(people["fa_token"], "POST", "/questions", json=mcq_payload).json()["id"]
    live.api(people["fb_token"], "POST", f"/questions/{qid}/approve")
    live.api(people["fa_token"], "PUT", f"/assessments/{aid}/blueprint", json={"rules": [{"difficulty": "Beginner", "question_count": 1}]})

    _s_id, s_email = live.create_user("ts21", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": qid, "selected_option_ids": [opt2]})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")

    r_score = live.api(s_token, "POST", f"/attempts/{attempt_id}/score")
    assert r_score.status_code == 200, r_score.text
    body = r_score.json()
    assert Decimal(str(body["score"])) == Decimal("5.00")
    assert Decimal(str(body["total_marks"])) == Decimal("5.00")

    after = _attempt_row(live, attempt_id)
    assert after["evaluation_status"] == "NOT_REQUIRED"
    assert after["final_score"] is None
    assert after["final_total_marks"] is None
    assert after["final_percentage"] is None


def test_repeated_score_call_still_returns_409_trigger_does_not_change_that(live):
    """The 050 trigger must not make /score retryable -- the existing
    409-on-repeat behavior (assessment_service.AttemptNotEligibleForScoringError)
    is completely unrelated to and unaffected by this trigger."""
    ctx = _single_ai_evaluated_attempt(live, "t22", points="10.00")  # complete=True default
    r_second = live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/score")
    assert r_second.status_code == 409, r_second.text


def test_concurrent_finalize_and_complete_converges_correctly(live):
    """Required concurrency test: Thread A finalizes the evaluator's
    evaluation while Thread B independently submits+scores the SAME
    attempt, racing F8.4.2's own route-level fold-in trigger against
    this phase's new 050 completion trigger for the same attempt_id.
    Both ultimately serialize through fold_in_attempt_evaluation()'s own
    `select ... for update` (identical mechanism F8.4.2's own two-
    evaluator concurrency tests already proved safe) -- no Redis, no
    application locks, no sleeps, no polling loops; only the existing
    database row lock is relied upon.

    The exact interleaving is not predetermined -- what's asserted is
    the END state after both threads complete: no exception from either
    thread, attempt COMPLETED, evaluation FINALIZED, and the fold-in
    result converges to the single correct value with no duplicate/
    corrupted final_* left behind.
    """
    ctx = _single_ai_evaluated_attempt(live, "t23", points="10.00", complete=False)
    ev = _make_evaluator(live, "t23")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    evaluation_id = _evaluation_id_for(live, assignment["id"])

    # Bring the evaluation to SUBMITTED first so only the final
    # FINALIZED PATCH (the one that triggers fold-in) races against
    # attempt completion.
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"rubric_id": rubric_id, "awarded_marks": "9.00"})
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/submit")

    def _do_finalize(_):
        return live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})

    def _do_complete(_):
        return live.api(ctx["s_token"], "POST", f"/attempts/{ctx['attempt_id']}/score")

    with ThreadPoolExecutor(max_workers=2) as pool:
        finalize_future = pool.submit(_do_finalize, None)
        complete_future = pool.submit(_do_complete, None)
        r_finalize = finalize_future.result()
        r_complete = complete_future.result()

    assert r_finalize.status_code == 200, r_finalize.text
    assert r_complete.status_code == 200, r_complete.text

    eval_row = live.admin.table("evaluations").select("status, awarded_marks").eq("id", evaluation_id).execute().data[0]
    assert eval_row["status"] == "FINALIZED"

    attempt_status_row = live.admin.table("assessment_attempts").select("status").eq("id", ctx["attempt_id"]).execute().data[0]
    assert attempt_status_row["status"] == "COMPLETED"

    final_row = _attempt_row(live, ctx["attempt_id"])
    assert final_row["evaluation_status"] == "COMPLETE"
    assert Decimal(str(final_row["final_score"])) == Decimal("9.00")
    assert Decimal(str(final_row["final_total_marks"])) == Decimal("10.00")
