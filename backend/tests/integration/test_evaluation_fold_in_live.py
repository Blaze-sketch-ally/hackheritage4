"""Live-integration coverage for Phase F8.4.1 --
049_evaluation_status_and_final_score.sql: the new evaluation_status/
final_score/final_total_marks/final_percentage columns on
assessment_attempts, and the fold_in_attempt_evaluation() trusted RPC.
Exercises the REAL Supabase project + REAL FastAPI server (for the
existing student/evaluator APIs, all untouched) plus direct RPC calls
via the service-role admin client (since fold_in_attempt_evaluation() is
deliberately not reachable through any FastAPI route yet -- F8.4.2's
job). Self-contained, matching this directory's own convention.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import httpx


def _rest_as_user(live, token: str, method: str, table: str, **kwargs) -> httpx.Response:
    headers = kwargs.pop("headers", {})
    headers["apikey"] = live._anon_key
    headers["Authorization"] = f"Bearer {token}"
    headers.setdefault("Prefer", "return=representation")
    return httpx.request(method, f"{live._anon_url}/rest/v1/{table}", headers=headers, **kwargs)


def _fold_in(live, attempt_id: str) -> dict:
    return live.admin.rpc("fold_in_attempt_evaluation", {"p_attempt_id": attempt_id}).execute().data


def _author_reviewer(live, tag: str) -> dict:
    fa_id, fa_email = live.create_user(f"fa{tag}", "FACULTY")
    fb_id, fb_email = live.create_user(f"fb{tag}", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    return {"fa_id": fa_id, "fa_token": live.token_for(fa_email), "fb_id": fb_id, "fb_token": live.token_for(fb_email)}


def _make_evaluator(live, tag: str, status: str = "GRANTED", expires_at: str | None = None) -> dict:
    fe_id, fe_email = live.create_user(f"fe{tag}", "FACULTY")
    row = {"faculty_id": fe_id, "capability": "assessment_evaluator", "status": status}
    if expires_at is not None:
        row["expires_at"] = expires_at
    live.admin.table("faculty_assessment_permissions").insert(row).execute()
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


def _finalize(live, evaluator_token: str, evaluation_id: str, marks: str, rubric_id: str) -> None:
    r_start = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    assert r_start.status_code == 200, r_start.text
    r_save = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"rubric_id": rubric_id, "awarded_marks": marks})
    assert r_save.status_code == 200, r_save.text
    r_submit = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    assert r_submit.status_code == 200, r_submit.text
    r_final = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_final.status_code == 200, r_final.text


def _objective_only_attempt(live, tag: str) -> dict:
    people = _author_reviewer(live, tag)
    aid = live.create_assessment(title_suffix=tag)
    opt1, opt2 = str(uuid.uuid4()), str(uuid.uuid4())
    payload = {
        "assessment_id": aid, "question_text": f"__QA_{tag} obj", "question_type": "MCQ",
        "scoring_method": "OBJECTIVE", "difficulty": "Beginner", "points": "1.00", "display_order": 0,
        "options": [{"id": opt1, "option_text": "A", "display_order": 0}, {"id": opt2, "option_text": "B", "display_order": 1}],
        "answer_key": {"correct_option_ids": [opt2]},
    }
    qid = live.api(people["fa_token"], "POST", "/questions", json=payload).json()["id"]
    live.api(people["fb_token"], "POST", f"/questions/{qid}/approve")
    live.api(people["fa_token"], "PUT", f"/assessments/{aid}/blueprint", json={"rules": [{"difficulty": "Beginner", "question_count": 1}]})

    s_id, s_email = live.create_user(f"s{tag}", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": qid, "selected_option_ids": [opt2]})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    live.api(s_token, "POST", f"/attempts/{attempt_id}/score")

    return {"attempt_id": attempt_id, "aid": aid, "qid": qid, "student_id": s_id, "creator_id": people["fa_id"]}


def _single_ai_evaluated_attempt(live, tag: str, points: str = "10.00") -> dict:
    """One SUBJECTIVE/AI_EVALUATED question, no objective questions at
    all -- objective score/total_marks come out 0/0 (score_assessment_
    attempt()'s own pre-existing zero-questions fallback), scored and
    COMPLETED, ready for fold-in."""
    people = _author_reviewer(live, tag)
    aid = live.create_assessment(title_suffix=tag)
    payload = {
        "assessment_id": aid, "question_text": f"__QA_{tag} subjective", "question_type": "SUBJECTIVE",
        "scoring_method": "AI_EVALUATED", "difficulty": "Intermediate", "points": points, "display_order": 0, "options": [],
    }
    qid = live.api(people["fa_token"], "POST", "/questions", json=payload).json()["id"]
    live.api(people["fb_token"], "POST", f"/questions/{qid}/approve")
    live.api(people["fa_token"], "PUT", f"/assessments/{aid}/blueprint", json={"rules": [{"difficulty": "Intermediate", "question_count": 1}]})

    s_id, s_email = live.create_user(f"s{tag}", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": qid, "answer_text": "My answer."})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    live.api(s_token, "POST", f"/attempts/{attempt_id}/score")

    return {"attempt_id": attempt_id, "aid": aid, "qid": qid, "points": points, "student_id": s_id, "creator_id": people["fa_id"]}


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

    s_id, s_email = live.create_user(f"s{tag}", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": mcq_id, "selected_option_ids": [opt2]})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ai_id, "answer_text": "answer"})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    live.api(s_token, "POST", f"/attempts/{attempt_id}/score")

    return {"attempt_id": attempt_id, "aid": aid, "mcq_id": mcq_id, "ai_id": ai_id, "student_id": s_id, "creator_id": people["fa_id"]}


# ============================================================
# 1. Objective-only
# ============================================================


def test_objective_only_attempt_gets_not_required(live):
    ctx = _objective_only_attempt(live, "1")
    before = live.admin.table("assessment_attempts").select("score, total_marks, percentage").eq("id", ctx["attempt_id"]).execute().data[0]

    result = _fold_in(live, ctx["attempt_id"])

    assert result["evaluation_status"] == "NOT_REQUIRED"
    assert result["final_score"] is None
    assert result["final_total_marks"] is None
    assert result["final_percentage"] is None
    assert result["score"] == before["score"]
    assert result["total_marks"] == before["total_marks"]
    assert result["percentage"] == before["percentage"]


# ============================================================
# 2. Single AI_EVALUATED question
# ============================================================


def test_pending_before_any_finalized_evaluation(live):
    ctx = _single_ai_evaluated_attempt(live, "2")
    result = _fold_in(live, ctx["attempt_id"])
    assert result["evaluation_status"] == "PENDING"
    assert result["final_score"] is None


def test_finalized_evaluation_folds_in_correctly(live):
    ctx = _single_ai_evaluated_attempt(live, "3", points="10.00")
    ev = _make_evaluator(live, "3")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    evaluation_id = _evaluation_id_for(live, assignment["id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    _finalize(live, ev["token"], evaluation_id, "7.00", rubric_id)

    result = _fold_in(live, ctx["attempt_id"])
    assert result["evaluation_status"] == "COMPLETE"
    assert Decimal(str(result["final_score"])) == Decimal("7.00")
    assert Decimal(str(result["final_total_marks"])) == Decimal("10.00")
    assert Decimal(str(result["final_percentage"])) == Decimal("70.00")


# ============================================================
# 3. Mixed assessment
# ============================================================


def test_mixed_assessment_combines_objective_and_human_score(live):
    ctx = _mixed_attempt(live, "4")
    objective = live.admin.table("assessment_attempts").select("score, total_marks").eq("id", ctx["attempt_id"]).execute().data[0]
    assert Decimal(str(objective["score"])) == Decimal("6.00")  # MCQ correct
    assert Decimal(str(objective["total_marks"])) == Decimal("6.00")

    ev = _make_evaluator(live, "4")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["ai_id"], ctx["creator_id"])
    evaluation_id = _evaluation_id_for(live, assignment["id"])
    rubric_id = _make_rubric(live, ctx["ai_id"], "4.00")
    _finalize(live, ev["token"], evaluation_id, "3.00", rubric_id)

    result = _fold_in(live, ctx["attempt_id"])
    assert result["evaluation_status"] == "COMPLETE"
    assert Decimal(str(result["final_score"])) == Decimal("9.00")  # 6 + 3
    assert Decimal(str(result["final_total_marks"])) == Decimal("10.00")  # 6 + 4
    assert Decimal(str(result["final_percentage"])) == Decimal("90.00")


# ============================================================
# 4/5. Co-evaluation
# ============================================================


def test_multiple_evaluators_agreeing_produces_final_score(live):
    ctx = _single_ai_evaluated_attempt(live, "5", points="10.00")
    ev_a = _make_evaluator(live, "5a")
    ev_b = _make_evaluator(live, "5b")
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")

    assignment_a = _assign(live, ev_a["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    assignment_b = _assign(live, ev_b["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    _finalize(live, ev_a["token"], _evaluation_id_for(live, assignment_a["id"]), "8.00", rubric_id)
    _finalize(live, ev_b["token"], _evaluation_id_for(live, assignment_b["id"]), "8.00", rubric_id)

    result = _fold_in(live, ctx["attempt_id"])
    assert result["evaluation_status"] == "COMPLETE"
    assert Decimal(str(result["final_score"])) == Decimal("8.00")


def test_multiple_evaluators_disagreeing_needs_reconciliation(live):
    ctx = _single_ai_evaluated_attempt(live, "6", points="10.00")
    ev_a = _make_evaluator(live, "6a")
    ev_b = _make_evaluator(live, "6b")
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")

    assignment_a = _assign(live, ev_a["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    assignment_b = _assign(live, ev_b["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    _finalize(live, ev_a["token"], _evaluation_id_for(live, assignment_a["id"]), "7.00", rubric_id)
    _finalize(live, ev_b["token"], _evaluation_id_for(live, assignment_b["id"]), "9.00", rubric_id)

    result = _fold_in(live, ctx["attempt_id"])
    assert result["evaluation_status"] == "NEEDS_RECONCILIATION"
    assert result["final_score"] is None
    assert result["final_total_marks"] is None
    assert result["final_percentage"] is None

    # Both finalized evaluations must remain intact -- nothing deleted,
    # nothing mutated, no evaluator marked authoritative.
    marks = (
        live.admin.table("evaluations")
        .select("awarded_marks")
        .in_("assignment_id", [assignment_a["id"], assignment_b["id"]])
        .execute()
        .data
    )
    assert sorted(Decimal(str(m["awarded_marks"])) for m in marks) == [Decimal("7.00"), Decimal("9.00")]


# ============================================================
# 6. Partial (multi-question, one resolved one not)
# ============================================================


def test_partial_when_some_but_not_all_required_questions_are_resolved(live):
    people = _author_reviewer(live, "7")
    aid = live.create_assessment(title_suffix="7")
    ai1_payload = {"assessment_id": aid, "question_text": "__QA_7 q1", "question_type": "SUBJECTIVE", "scoring_method": "AI_EVALUATED", "difficulty": "Beginner", "points": "5.00", "display_order": 0, "options": []}
    ai2_payload = {"assessment_id": aid, "question_text": "__QA_7 q2", "question_type": "SUBJECTIVE", "scoring_method": "AI_EVALUATED", "difficulty": "Intermediate", "points": "5.00", "display_order": 1, "options": []}
    ai1_id = live.api(people["fa_token"], "POST", "/questions", json=ai1_payload).json()["id"]
    ai2_id = live.api(people["fa_token"], "POST", "/questions", json=ai2_payload).json()["id"]
    for qid in (ai1_id, ai2_id):
        live.api(people["fb_token"], "POST", f"/questions/{qid}/approve")
    live.api(
        people["fa_token"], "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 1}, {"difficulty": "Intermediate", "question_count": 1}]},
    )
    _s_id, s_email = live.create_user("s7", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ai1_id, "answer_text": "a1"})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ai2_id, "answer_text": "a2"})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    live.api(s_token, "POST", f"/attempts/{attempt_id}/score")

    ev = _make_evaluator(live, "7")
    assignment = _assign(live, ev["id"], attempt_id, ai1_id, people["fa_id"])
    rubric_id = _make_rubric(live, ai1_id, "5.00")
    _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "4.00", rubric_id)
    # ai2_id is never assigned/evaluated at all.

    result = _fold_in(live, attempt_id)
    assert result["evaluation_status"] == "PARTIAL"
    assert result["final_score"] is None


# ============================================================
# 7/8. Rubric / points enforcement
# ============================================================


def test_matching_rubric_max_marks_is_accepted(live):
    ctx = _single_ai_evaluated_attempt(live, "8", points="10.00")
    ev = _make_evaluator(live, "8")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")  # matches points exactly
    _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "6.00", rubric_id)

    result = _fold_in(live, ctx["attempt_id"])
    assert result["evaluation_status"] == "COMPLETE"


def test_mismatched_rubric_max_marks_is_excluded_from_fold_in(live):
    ctx = _single_ai_evaluated_attempt(live, "9", points="10.00")
    ev = _make_evaluator(live, "9")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "20.00")  # deliberately mismatched
    _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "15.00", rubric_id)

    result = _fold_in(live, ctx["attempt_id"])
    assert result["evaluation_status"] == "PENDING", "a finalized evaluation with a mismatched rubric must not resolve the question"
    assert result["final_score"] is None


# ============================================================
# 9/11. Immutability regressions (F8.1) unaffected by fold-in
# ============================================================


def test_finalized_evaluation_stays_immutable_after_fold_in(live):
    ctx = _single_ai_evaluated_attempt(live, "10", points="10.00")
    ev = _make_evaluator(live, "10")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    evaluation_id = _evaluation_id_for(live, assignment["id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    _finalize(live, ev["token"], evaluation_id, "5.00", rubric_id)
    _fold_in(live, ctx["attempt_id"])

    r_mutate = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "9.00"})
    assert r_mutate.status_code == 409


def test_rubric_content_still_locked_after_use_and_fold_in_unaffected(live):
    ctx = _single_ai_evaluated_attempt(live, "11", points="10.00")
    ev = _make_evaluator(live, "11")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "6.00", rubric_id)

    r_rubric_mutate = _rest_as_user(live, ev["token"], "PATCH", "rubrics", params={"id": f"eq.{rubric_id}"}, json={"max_marks": "999.00"})
    unchanged = live.admin.table("rubrics").select("max_marks").eq("id", rubric_id).execute().data[0]
    assert Decimal(str(unchanged["max_marks"])) == Decimal("10.00"), f"got {r_rubric_mutate.status_code}"

    result = _fold_in(live, ctx["attempt_id"])
    assert result["evaluation_status"] == "COMPLETE"
    assert Decimal(str(result["final_score"])) == Decimal("6.00")


# ============================================================
# 10/12/13. Historical stability of an already-COMPLETE result
# ============================================================


def test_question_deactivated_after_fold_in_result_still_reproducible(live):
    ctx = _single_ai_evaluated_attempt(live, "12", points="10.00")
    ev = _make_evaluator(live, "12")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "8.00", rubric_id)
    first = _fold_in(live, ctx["attempt_id"])

    live.admin.table("assessment_questions").update({"is_active": False}).eq("id", ctx["qid"]).execute()

    second = _fold_in(live, ctx["attempt_id"])
    assert second["evaluation_status"] == "COMPLETE"
    assert second["final_score"] == first["final_score"]
    assert second["final_total_marks"] == first["final_total_marks"]
    assert second["final_percentage"] == first["final_percentage"]


def test_evaluator_revoked_after_finalization_final_result_unchanged(live):
    ctx = _single_ai_evaluated_attempt(live, "13", points="10.00")
    ev = _make_evaluator(live, "13")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "4.00", rubric_id)
    first = _fold_in(live, ctx["attempt_id"])

    live.admin.rpc("revoke_evaluator_assignment", {"p_assignment_id": assignment["id"], "p_revoked_by": ctx["creator_id"]}).execute()

    second = _fold_in(live, ctx["attempt_id"])
    assert second["evaluation_status"] == "COMPLETE"
    assert Decimal(str(second["final_score"])) == Decimal(str(first["final_score"])) == Decimal("4.00")


def test_evaluator_capability_expired_after_finalization_final_result_unchanged(live):
    ctx = _single_ai_evaluated_attempt(live, "14", points="10.00")
    ev = _make_evaluator(live, "14")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "3.00", rubric_id)
    first = _fold_in(live, ctx["attempt_id"])

    live.admin.table("faculty_assessment_permissions").update({"expires_at": "2000-01-01T00:00:00Z"}).eq("faculty_id", ev["id"]).eq("capability", "assessment_evaluator").execute()

    second = _fold_in(live, ctx["attempt_id"])
    assert second["evaluation_status"] == "COMPLETE"
    assert Decimal(str(second["final_score"])) == Decimal(str(first["final_score"])) == Decimal("3.00")


# ============================================================
# 14/15. Idempotency and concurrency
# ============================================================


def test_repeated_fold_in_is_idempotent(live):
    ctx = _single_ai_evaluated_attempt(live, "15", points="10.00")
    ev = _make_evaluator(live, "15")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "6.00", rubric_id)

    first = _fold_in(live, ctx["attempt_id"])
    second = _fold_in(live, ctx["attempt_id"])
    third = _fold_in(live, ctx["attempt_id"])
    assert first["final_score"] == second["final_score"] == third["final_score"]
    assert first["evaluation_status"] == second["evaluation_status"] == third["evaluation_status"] == "COMPLETE"


def test_concurrent_fold_in_serializes_safely(live):
    ctx = _single_ai_evaluated_attempt(live, "16", points="10.00")
    ev = _make_evaluator(live, "16")
    assignment = _assign(live, ev["id"], ctx["attempt_id"], ctx["qid"], ctx["creator_id"])
    rubric_id = _make_rubric(live, ctx["qid"], "10.00")
    _finalize(live, ev["token"], _evaluation_id_for(live, assignment["id"]), "5.00", rubric_id)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: _fold_in(live, ctx["attempt_id"]), range(4)))

    for r in results:
        assert r["evaluation_status"] == "COMPLETE"
        assert Decimal(str(r["final_score"])) == Decimal("5.00")
        assert Decimal(str(r["final_total_marks"])) == Decimal("10.00")

    final_row = live.admin.table("assessment_attempts").select("evaluation_status, final_score").eq("id", ctx["attempt_id"]).execute().data[0]
    assert final_row["evaluation_status"] == "COMPLETE"
    assert Decimal(str(final_row["final_score"])) == Decimal("5.00")
