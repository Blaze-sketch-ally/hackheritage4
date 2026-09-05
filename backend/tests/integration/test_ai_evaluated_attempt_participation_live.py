"""Live-integration coverage for Phase F8.4.0 --
048_ai_evaluated_attempt_participation.sql: letting an AI_EVALUATED
question participate in a real, persisted attempt for the first time in
this project's history, and confirming score_assessment_attempt() defers
it (never auto-scores it) without disturbing the objective-scoring
result for the rest of the attempt. Exercises the REAL Supabase project
+ REAL FastAPI server -- no mocking. Self-contained, matching this
directory's own convention (no cross-file imports between live test
modules).

Deliberately does NOT touch evaluation_status/final_score/reconciliation
-- those are F8.4.1+, per the approved F8.4 architecture audit.
"""

import uuid
from datetime import UTC, datetime

import httpx


def _rest_as_user(live, token: str, method: str, table: str, **kwargs) -> httpx.Response:
    headers = kwargs.pop("headers", {})
    headers["apikey"] = live._anon_key
    headers["Authorization"] = f"Bearer {token}"
    headers.setdefault("Prefer", "return=representation")
    return httpx.request(method, f"{live._anon_url}/rest/v1/{table}", headers=headers, **kwargs)


def _author_reviewer(live, tag: str) -> dict:
    fa_id, fa_email = live.create_user(f"fa{tag}", "FACULTY")
    fb_id, fb_email = live.create_user(f"fb{tag}", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    return {
        "fa_id": fa_id, "fa_token": live.token_for(fa_email),
        "fb_id": fb_id, "fb_token": live.token_for(fb_email),
    }


def _ai_evaluated_payload(aid: str, text: str) -> dict:
    """A SUBJECTIVE + AI_EVALUATED question -- no options, no answer key
    required (043_question_authoring_metadata.sql's F6.3 guard only
    applies when scoring_method = 'OBJECTIVE')."""
    return {
        "assessment_id": aid,
        "question_text": text,
        "question_type": "SUBJECTIVE",
        "scoring_method": "AI_EVALUATED",
        "difficulty": "Intermediate",
        "points": "10.00",
        "display_order": 0,
        "options": [],
    }


def _mixed_assessment(live, tag: str) -> dict:
    """One MCQ (Beginner, 5pts) + one SHORT_ANSWER (Beginner, 5pts) +
    one SUBJECTIVE/AI_EVALUATED (Intermediate, 10pts), each in its own
    blueprint difficulty bucket with question_count exactly matching the
    available pool -- deterministic selection, no randomness in which
    questions land in the attempt."""
    people = _author_reviewer(live, tag)
    aid = live.create_assessment(title_suffix=tag)

    mcq_opt1, mcq_opt2 = str(uuid.uuid4()), str(uuid.uuid4())
    mcq_payload = {
        "assessment_id": aid, "question_text": f"__QA_{tag} mcq", "question_type": "MCQ",
        "scoring_method": "OBJECTIVE", "difficulty": "Beginner", "points": "5.00", "display_order": 0,
        "options": [
            {"id": mcq_opt1, "option_text": "A", "display_order": 0},
            {"id": mcq_opt2, "option_text": "B", "display_order": 1},
        ],
        "answer_key": {"correct_option_ids": [mcq_opt2]},
    }
    mcq_id = live.api(people["fa_token"], "POST", "/questions", json=mcq_payload).json()["id"]

    sa_payload = {
        "assessment_id": aid, "question_text": f"__QA_{tag} short-answer", "question_type": "SHORT_ANSWER",
        "scoring_method": "OBJECTIVE", "difficulty": "Beginner", "points": "5.00", "display_order": 1,
        "options": [], "answer_key": {"correct_answer_text": "closure"},
    }
    sa_id = live.api(people["fa_token"], "POST", "/questions", json=sa_payload).json()["id"]

    ai_id = live.api(
        people["fa_token"], "POST", "/questions", json=_ai_evaluated_payload(aid, f"__QA_{tag} subjective")
    ).json()["id"]

    for qid in (mcq_id, sa_id, ai_id):
        live.api(people["fb_token"], "POST", f"/questions/{qid}/approve")

    live.api(
        people["fa_token"], "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 2}, {"difficulty": "Intermediate", "question_count": 1}]},
    )

    s_id, s_email = live.create_user(f"s{tag}", "STUDENT")
    s_token = live.token_for(s_email)

    return {
        "aid": aid, "mcq_id": mcq_id, "mcq_correct_option": mcq_opt2, "sa_id": sa_id, "ai_id": ai_id,
        "student_id": s_id, "student_token": s_token, "creator_id": people["fa_id"],
    }


# ============================================================
# Selection / persistence
# ============================================================


def test_ai_evaluated_question_is_selected_into_the_attempt(live):
    ctx = _mixed_assessment(live, "1")
    attempt_id = live.api(ctx["student_token"], "POST", f"/assessments/{ctx['aid']}/attempts").json()["id"]
    questions = live.api(ctx["student_token"], "GET", f"/attempts/{attempt_id}/questions").json()
    question_ids = {q["id"] for q in questions}
    assert ctx["ai_id"] in question_ids
    assert ctx["mcq_id"] in question_ids
    assert ctx["sa_id"] in question_ids
    assert len(questions) == 3


def test_ai_evaluated_question_persisted_in_attempt_question_table(live):
    ctx = _mixed_assessment(live, "2")
    attempt_id = live.api(ctx["student_token"], "POST", f"/assessments/{ctx['aid']}/attempts").json()["id"]
    row = (
        live.admin.table("assessment_attempt_questions")
        .select("attempt_id, question_id")
        .eq("attempt_id", attempt_id)
        .eq("question_id", ctx["ai_id"])
        .execute()
        .data
    )
    assert len(row) == 1


def test_objective_only_assessment_is_completely_unaffected(live):
    """Pure regression: an assessment with zero AI_EVALUATED questions
    behaves exactly as before F8.4.0."""
    people = _author_reviewer(live, "3")
    aid = live.create_assessment(title_suffix="3")
    opt1, opt2 = str(uuid.uuid4()), str(uuid.uuid4())
    payload = {
        "assessment_id": aid, "question_text": "__QA_3 obj-only", "question_type": "MCQ",
        "scoring_method": "OBJECTIVE", "difficulty": "Beginner", "points": "1.00", "display_order": 0,
        "options": [{"id": opt1, "option_text": "A", "display_order": 0}, {"id": opt2, "option_text": "B", "display_order": 1}],
        "answer_key": {"correct_option_ids": [opt2]},
    }
    qid = live.api(people["fa_token"], "POST", "/questions", json=payload).json()["id"]
    live.api(people["fb_token"], "POST", f"/questions/{qid}/approve")
    live.api(people["fa_token"], "PUT", f"/assessments/{aid}/blueprint", json={"rules": [{"difficulty": "Beginner", "question_count": 1}]})

    _s_id, s_email = live.create_user("s3", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    live.api(s_token, "POST", f"/attempts/{attempt_id}/answers", json={"question_id": qid, "selected_option_ids": [opt2]})
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    result = live.api(s_token, "POST", f"/attempts/{attempt_id}/score")
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "COMPLETED"
    assert float(body["score"]) == 1.0
    assert float(body["total_marks"]) == 1.0
    assert float(body["percentage"]) == 100.0


# ============================================================
# Scoring behavior
# ============================================================


def test_mixed_assessment_scores_objective_portion_only(live):
    """The task's own worked example: MCQ correct (5), SHORT_ANSWER
    deliberately wrong (0), SUBJECTIVE/AI_EVALUATED excluded entirely --
    total_marks must be 10 (5+5), never 20 (5+5+10)."""
    ctx = _mixed_assessment(live, "4")
    attempt_id = live.api(ctx["student_token"], "POST", f"/assessments/{ctx['aid']}/attempts").json()["id"]

    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["mcq_id"], "selected_option_ids": [ctx["mcq_correct_option"]]})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["sa_id"], "answer_text": "definitely wrong"})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["ai_id"], "answer_text": "My reasoning about closures..."})

    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/submit")
    result = live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/score")
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "COMPLETED"
    assert float(body["total_marks"]) == 10.0, "AI_EVALUATED question's 10 points must be excluded from the denominator"
    assert float(body["score"]) == 5.0, "only the correct MCQ (5) should count -- the wrong SHORT_ANSWER contributes 0"
    assert float(body["percentage"]) == 50.0


def test_ai_evaluated_answer_never_receives_automatic_marks(live):
    ctx = _mixed_assessment(live, "5")
    attempt_id = live.api(ctx["student_token"], "POST", f"/assessments/{ctx['aid']}/attempts").json()["id"]
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["mcq_id"], "selected_option_ids": [ctx["mcq_correct_option"]]})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["sa_id"], "answer_text": "closure"})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["ai_id"], "answer_text": "A thoughtful answer."})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/submit")
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/score")

    ai_answer = (
        live.admin.table("assessment_answers")
        .select("awarded_marks, is_correct, answer_text")
        .eq("attempt_id", attempt_id)
        .eq("question_id", ctx["ai_id"])
        .execute()
        .data[0]
    )
    assert ai_answer["awarded_marks"] is None
    assert ai_answer["is_correct"] is None
    assert ai_answer["answer_text"] == "A thoughtful answer.", "the student's actual answer must still be preserved"


def test_objective_scoring_does_not_fail_when_an_ai_evaluated_question_is_present(live):
    """The core F8.4.0 requirement: presence of an AI_EVALUATED question
    must never cause the scoring transaction to fail for the rest of the
    attempt."""
    ctx = _mixed_assessment(live, "6")
    attempt_id = live.api(ctx["student_token"], "POST", f"/assessments/{ctx['aid']}/attempts").json()["id"]
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["mcq_id"], "selected_option_ids": [ctx["mcq_correct_option"]]})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["sa_id"], "answer_text": "closure"})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["ai_id"], "answer_text": "answer"})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/submit")

    result = live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/score")
    assert result.status_code == 200, result.text
    assert float(result.json()["score"]) == 10.0
    assert float(result.json()["total_marks"]) == 10.0


def test_unanswered_ai_evaluated_question_gets_null_not_zero(live):
    """Surgical edge case: even when the student never answers the
    AI_EVALUATED question, score_assessment_attempt() must leave
    awarded_marks/is_correct NULL (pending), never the 0/false an
    unanswered OBJECTIVE question gets. The normal submit flow requires
    every persisted question to be answered first (unmodified,
    pre-existing behavior -- attempts.py's own completeness check), so
    this test bypasses that FastAPI-level gate via the admin client to
    exercise score_assessment_attempt() directly, exactly as it would
    behave for a genuinely partial submission at the database layer."""
    ctx = _mixed_assessment(live, "7")
    attempt_id = live.api(ctx["student_token"], "POST", f"/assessments/{ctx['aid']}/attempts").json()["id"]
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["mcq_id"], "selected_option_ids": [ctx["mcq_correct_option"]]})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["sa_id"], "answer_text": "closure"})
    # Deliberately never answer ctx["ai_id"].

    # Must be >= the attempt's own started_at (a real CHECK constraint,
    # assessment_attempts_submitted_after_started) -- "now" satisfies
    # that regardless of when this test happens to run.
    live.admin.table("assessment_attempts").update(
        {"submitted_at": datetime.now(UTC).isoformat()}
    ).eq("id", attempt_id).execute()
    scored = live.admin.rpc("score_assessment_attempt", {"p_attempt_id": attempt_id, "p_student_id": ctx["student_id"]}).execute().data
    assert scored["status"] == "COMPLETED"
    assert float(scored["total_marks"]) == 10.0
    assert float(scored["score"]) == 10.0

    ai_answer = (
        live.admin.table("assessment_answers")
        .select("awarded_marks, is_correct, selected_option_ids")
        .eq("attempt_id", attempt_id)
        .eq("question_id", ctx["ai_id"])
        .execute()
        .data[0]
    )
    assert ai_answer["awarded_marks"] is None
    assert ai_answer["is_correct"] is None
    assert ai_answer["selected_option_ids"] == []


# ============================================================
# Historical integrity
# ============================================================


def test_deactivating_the_ai_evaluated_question_does_not_remove_it_from_the_attempt(live):
    ctx = _mixed_assessment(live, "8")
    attempt_id = live.api(ctx["student_token"], "POST", f"/assessments/{ctx['aid']}/attempts").json()["id"]

    live.admin.table("assessment_questions").update({"is_active": False}).eq("id", ctx["ai_id"]).execute()

    row = (
        live.admin.table("assessment_attempt_questions")
        .select("question_id")
        .eq("attempt_id", attempt_id)
        .eq("question_id", ctx["ai_id"])
        .execute()
        .data
    )
    assert len(row) == 1, "deactivation after selection must not remove historical attempt membership"

    questions = live.api(ctx["student_token"], "GET", f"/attempts/{attempt_id}/questions").json()
    assert any(q["id"] == ctx["ai_id"] for q in questions), "the student must still see the question they were given"


# ============================================================
# Evaluator workflow end-to-end (first real exercise of F8.1-F8.3
# against a question that actually exists inside an attempt)
# ============================================================


def test_evaluator_can_resolve_a_real_persisted_ai_evaluated_question(live):
    ctx = _mixed_assessment(live, "9")
    attempt_id = live.api(ctx["student_token"], "POST", f"/assessments/{ctx['aid']}/attempts").json()["id"]
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["mcq_id"], "selected_option_ids": [ctx["mcq_correct_option"]]})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["sa_id"], "answer_text": "closure"})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/answers", json={"question_id": ctx["ai_id"], "answer_text": "My real answer."})
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/submit")
    live.api(ctx["student_token"], "POST", f"/attempts/{attempt_id}/score")

    fe_id, fe_email = live.create_user("fe9", "FACULTY")
    live.grant_assessment_capabilities(fe_id, "assessment_evaluator")
    fe_token = live.token_for(fe_email)

    assignment = (
        live.admin.rpc(
            "create_evaluator_assignment",
            {"p_evaluator_id": fe_id, "p_attempt_id": attempt_id, "p_question_id": ctx["ai_id"], "p_created_by": ctx["creator_id"]},
        )
        .execute()
        .data
    )
    evaluation_id = live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]

    detail = live.api(fe_token, "GET", f"/faculty/evaluations/{evaluation_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["question"]["id"] == ctx["ai_id"]
    assert body["student_answer"]["answer_text"] == "My real answer."
    assert "answer_key" not in body["question"]

    live.api(fe_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    live.api(fe_token, "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "8.00", "feedback": "Solid reasoning."})
    live.api(fe_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    r_finalize = live.api(fe_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_finalize.status_code == 200
    assert r_finalize.json()["status"] == "FINALIZED"

    # The underlying assessment_answers row (objective-scoring's own
    # table) must still show NULL for this question -- F8.4.0
    # deliberately does not fold the finalized evaluation back into it
    # (that is F8.4.1+ work).
    ai_answer = (
        live.admin.table("assessment_answers")
        .select("awarded_marks, is_correct")
        .eq("attempt_id", attempt_id)
        .eq("question_id", ctx["ai_id"])
        .execute()
        .data[0]
    )
    assert ai_answer["awarded_marks"] is None
    assert ai_answer["is_correct"] is None


def test_answer_key_access_remains_denied_for_the_evaluator(live):
    ctx = _mixed_assessment(live, "10")
    attempt_id = live.api(ctx["student_token"], "POST", f"/assessments/{ctx['aid']}/attempts").json()["id"]
    fe_id, fe_email = live.create_user("fe10", "FACULTY")
    live.grant_assessment_capabilities(fe_id, "assessment_evaluator")
    fe_token = live.token_for(fe_email)
    live.admin.rpc(
        "create_evaluator_assignment",
        {"p_evaluator_id": fe_id, "p_attempt_id": attempt_id, "p_question_id": ctx["ai_id"], "p_created_by": ctx["creator_id"]},
    ).execute()

    r = _rest_as_user(live, fe_token, "GET", "assessment_question_answers", params={"question_id": f"eq.{ctx['ai_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_student_cannot_see_another_students_ai_evaluated_answer(live):
    ctx1 = _mixed_assessment(live, "11a")
    ctx2 = _mixed_assessment(live, "11b")
    attempt1 = live.api(ctx1["student_token"], "POST", f"/assessments/{ctx1['aid']}/attempts").json()["id"]
    live.api(ctx1["student_token"], "POST", f"/attempts/{attempt1}/answers", json={"question_id": ctx1["ai_id"], "answer_text": "private answer"})

    r = _rest_as_user(
        live, ctx2["student_token"], "GET", "assessment_answers",
        params={"attempt_id": f"eq.{attempt1}", "question_id": f"eq.{ctx1['ai_id']}"},
    )
    assert r.status_code < 300 and r.json() == []
