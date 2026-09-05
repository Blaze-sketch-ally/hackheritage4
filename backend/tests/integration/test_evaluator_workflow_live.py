"""Live-integration coverage for Phase F8.3 -- the evaluator workflow API
(app.api.faculty_evaluations), exercised through the REAL FastAPI server
against the REAL Supabase project. F8.1 (045) and F8.2 (046) already
proved the underlying RLS/trigger boundaries directly via PostgREST
(test_evaluation_foundation_live.py, test_evaluator_answer_visibility_
live.py) -- this file deliberately does not re-prove those guarantees
one-for-one; it tests the NEW surface: route wiring, status-code mapping,
and the API-observable lifecycle/concurrency behavior.

Self-contained, matching this directory's own convention (no cross-file
imports between live test modules).
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import httpx


def _marks(value) -> Decimal:
    """awarded_marks round-trips through Postgres numeric -> PostgREST
    JSON -> Python float -> Pydantic Decimal -> JSON string, which loses
    trailing-zero display precision along the way ("4.50" comes back as
    "4.5") without losing numeric value -- compare via Decimal, never an
    exact string, matching the same lesson already applied in
    test_evaluation_foundation_live.py."""
    return Decimal(str(value))


def _make_question_and_attempt(live, tag: str) -> dict:
    fa_id, fa_email = live.create_user(f"fa{tag}", "FACULTY")
    fb_id, fb_email = live.create_user(f"fb{tag}", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)

    aid = live.create_assessment(title_suffix=tag)
    q1 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, f"eval-workflow{tag}")).json()["id"]
    live.api(fb_token, "POST", f"/questions/{q1}/approve")
    live.api(
        fa_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 1}]},
    )

    s_id, s_email = live.create_user(f"s{tag}", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    question = live.api(s_token, "GET", f"/attempts/{attempt_id}/questions").json()[0]
    option_id = question["options"][0]["id"]
    live.api(
        s_token, "POST", f"/attempts/{attempt_id}/answers",
        json={"question_id": q1, "selected_option_ids": [option_id]},
    )

    return {
        "aid": aid, "question_id": q1, "attempt_id": attempt_id,
        "student_id": s_id, "student_token": s_token,
    }


def _make_evaluator(live, tag: str) -> dict:
    fe_id, fe_email = live.create_user(f"fe{tag}", "FACULTY")
    live.grant_assessment_capabilities(fe_id, "assessment_evaluator")
    return {"id": fe_id, "token": live.token_for(fe_email)}


def _assign(live, evaluator_id: str, ctx: dict, creator_id: str) -> dict:
    return (
        live.admin.rpc(
            "create_evaluator_assignment",
            {
                "p_evaluator_id": evaluator_id,
                "p_attempt_id": ctx["attempt_id"],
                "p_question_id": ctx["question_id"],
                "p_created_by": creator_id,
            },
        )
        .execute()
        .data
    )


def _evaluation_id_for(live, assignment: dict) -> str:
    return live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]


# ============================================================
# Happy path
# ============================================================


def test_full_evaluator_lifecycle(live):
    ctx = _make_question_and_attempt(live, "1")
    ev = _make_evaluator(live, "1")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)

    listing = live.api(ev["token"], "GET", "/faculty/evaluations")
    assert listing.status_code == 200
    assert any(row["evaluation_id"] == evaluation_id for row in listing.json())

    detail = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "ASSIGNED"
    assert body["question"]["id"] == ctx["question_id"]
    assert body["student_answer"] is not None
    assert "answer_key" not in body["question"]

    r_start = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    assert r_start.status_code == 200
    assert r_start.json()["status"] == "IN_PROGRESS"

    r_marks = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "4.50"})
    assert r_marks.status_code == 200
    assert _marks(r_marks.json()["awarded_marks"]) == Decimal("4.50")

    r_feedback = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"feedback": "Well reasoned."})
    assert r_feedback.status_code == 200

    r_submit = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    assert r_submit.status_code == 200
    assert r_submit.json()["status"] == "SUBMITTED"

    r_finalize = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_finalize.status_code == 200
    assert r_finalize.json()["status"] == "FINALIZED"

    detail_after = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}")
    assert _marks(detail_after.json()["awarded_marks"]) == Decimal("4.50")
    assert detail_after.json()["feedback"] == "Well reasoned."


def test_save_rubric_selection(live):
    ctx = _make_question_and_attempt(live, "2")
    ev = _make_evaluator(live, "2")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    rubric = live.admin.table("rubrics").insert(
        {"question_id": ctx["question_id"], "name": "R", "max_marks": "5.00"}
    ).execute().data[0]

    r = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"rubric_id": rubric["id"]})
    assert r.status_code == 200

    detail = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}").json()
    assert detail["rubric"]["id"] == rubric["id"]


def test_list_filters_by_status(live):
    ctx = _make_question_and_attempt(live, "3")
    ev = _make_evaluator(live, "3")
    _assign(live, ev["id"], ctx, ctx["student_id"])

    r_assigned = live.api(ev["token"], "GET", "/faculty/evaluations?status_filter=ASSIGNED")
    assert r_assigned.status_code == 200 and len(r_assigned.json()) == 1

    r_finalized = live.api(ev["token"], "GET", "/faculty/evaluations?status_filter=FINALIZED")
    assert r_finalized.status_code == 200 and r_finalized.json() == []


# ============================================================
# Security -- API-level mapping only; the underlying RLS boundary is
# already proven by test_evaluator_answer_visibility_live.py.
# ============================================================


def test_non_faculty_rejected(live):
    ctx = _make_question_and_attempt(live, "4")
    r = live.api(ctx["student_token"], "GET", "/faculty/evaluations")
    assert r.status_code == 403


def test_faculty_without_evaluator_capability_rejected(live):
    _fx_id, fx_email = live.create_user("fx5", "FACULTY")
    fx_token = live.token_for(fx_email)
    r = live.api(fx_token, "GET", "/faculty/evaluations")
    assert r.status_code == 403


def test_evaluator_a_cannot_access_evaluator_bs_evaluation(live):
    ctx = _make_question_and_attempt(live, "6")
    ev_a = _make_evaluator(live, "6a")
    ev_b = _make_evaluator(live, "6b")
    assignment = _assign(live, ev_a["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)

    r_get = live.api(ev_b["token"], "GET", f"/faculty/evaluations/{evaluation_id}")
    assert r_get.status_code == 404

    r_patch = live.api(ev_b["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"feedback": "hijack"})
    assert r_patch.status_code == 404

    r_status = live.api(ev_b["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    assert r_status.status_code == 404


def test_revoked_assignment_returns_404_via_api(live):
    ctx = _make_question_and_attempt(live, "7")
    ev = _make_evaluator(live, "7")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)

    live.admin.rpc(
        "revoke_evaluator_assignment", {"p_assignment_id": assignment["id"], "p_revoked_by": ctx["student_id"]}
    ).execute()

    r = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}")
    assert r.status_code == 404


def test_unknown_evaluation_id_returns_404(live):
    ev = _make_evaluator(live, "8")
    r = live.api(ev["token"], "GET", f"/faculty/evaluations/{uuid.uuid4()}")
    assert r.status_code == 404


# ============================================================
# Lifecycle
# ============================================================


def test_invalid_transition_returns_409(live):
    ctx = _make_question_and_attempt(live, "9")
    ev = _make_evaluator(live, "9")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)

    r = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    assert r.status_code == 409


def test_duplicate_start_is_idempotent(live):
    ctx = _make_question_and_attempt(live, "10")
    ev = _make_evaluator(live, "10")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)

    r1 = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    r2 = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json()["status"] == "IN_PROGRESS"


def test_finalize_before_submit_returns_409(live):
    ctx = _make_question_and_attempt(live, "11")
    ev = _make_evaluator(live, "11")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "1.00"})

    r = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r.status_code == 409


def test_mutate_finalized_evaluation_returns_409(live):
    ctx = _make_question_and_attempt(live, "12")
    ev = _make_evaluator(live, "12")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "1.00"})
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    r_finalize = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_finalize.status_code == 200

    r_mutate = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"feedback": "too late"})
    assert r_mutate.status_code == 409

    r_status = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    assert r_status.status_code == 409


def test_duplicate_finalize_is_idempotent(live):
    ctx = _make_question_and_attempt(live, "13")
    ev = _make_evaluator(live, "13")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "1.00"})
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    r1 = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    r2 = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r1.status_code == 200 and r2.status_code == 200


# ============================================================
# Validation
# ============================================================


def test_marks_above_rubric_maximum_returns_422(live):
    ctx = _make_question_and_attempt(live, "14")
    ev = _make_evaluator(live, "14")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    rubric = live.admin.table("rubrics").insert(
        {"question_id": ctx["question_id"], "name": "Small", "max_marks": "2.00"}
    ).execute().data[0]
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"rubric_id": rubric["id"]})

    r = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "10.00"})
    assert r.status_code == 422


def test_rubric_for_a_different_question_returns_422(live):
    ctx = _make_question_and_attempt(live, "15")
    other_ctx = _make_question_and_attempt(live, "15b")
    ev = _make_evaluator(live, "15")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    unrelated_rubric = live.admin.table("rubrics").insert(
        {"question_id": other_ctx["question_id"], "name": "Wrong", "max_marks": "5.00"}
    ).execute().data[0]

    r = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"rubric_id": unrelated_rubric["id"]})
    assert r.status_code == 422


def test_malformed_evaluation_id_returns_422(live):
    ev = _make_evaluator(live, "16")
    r = live.api(ev["token"], "GET", "/faculty/evaluations/not-a-uuid")
    assert r.status_code == 422


def test_missing_marks_at_finalization_returns_422(live):
    ctx = _make_question_and_attempt(live, "17")
    ev = _make_evaluator(live, "17")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})

    r = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r.status_code == 422


def test_negative_marks_rejected_at_the_api(live):
    ctx = _make_question_and_attempt(live, "18")
    ev = _make_evaluator(live, "18")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    r = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "-1.00"})
    assert r.status_code == 422


# ============================================================
# Co-evaluation
# ============================================================


def test_coevaluators_work_independently_through_the_api(live):
    ctx = _make_question_and_attempt(live, "19")
    ev_a = _make_evaluator(live, "19a")
    ev_b = _make_evaluator(live, "19b")
    assignment_a = _assign(live, ev_a["id"], ctx, ctx["student_id"])
    assignment_b = _assign(live, ev_b["id"], ctx, ctx["student_id"])
    eval_a = _evaluation_id_for(live, assignment_a)
    eval_b = _evaluation_id_for(live, assignment_b)

    live.api(ev_a["token"], "PATCH", f"/faculty/evaluations/{eval_a}", json={"awarded_marks": "3.00"})
    live.api(ev_b["token"], "PATCH", f"/faculty/evaluations/{eval_b}", json={"awarded_marks": "4.00"})

    detail_a = live.api(ev_a["token"], "GET", f"/faculty/evaluations/{eval_a}").json()
    detail_b = live.api(ev_b["token"], "GET", f"/faculty/evaluations/{eval_b}").json()
    assert _marks(detail_a["awarded_marks"]) == Decimal("3.00")
    assert _marks(detail_b["awarded_marks"]) == Decimal("4.00")

    # Neither can mutate the other's, through the API.
    r_a_on_b = live.api(ev_a["token"], "PATCH", f"/faculty/evaluations/{eval_b}", json={"awarded_marks": "0.00"})
    r_b_on_a = live.api(ev_b["token"], "PATCH", f"/faculty/evaluations/{eval_a}", json={"awarded_marks": "0.00"})
    assert r_a_on_b.status_code == 404
    assert r_b_on_a.status_code == 404

    unchanged_a = live.api(ev_a["token"], "GET", f"/faculty/evaluations/{eval_a}").json()
    unchanged_b = live.api(ev_b["token"], "GET", f"/faculty/evaluations/{eval_b}").json()
    assert _marks(unchanged_a["awarded_marks"]) == Decimal("3.00")
    assert _marks(unchanged_b["awarded_marks"]) == Decimal("4.00")


# ============================================================
# Concurrency -- real parallel HTTP requests against the live server
# ============================================================


def test_concurrent_start_requests_both_succeed_idempotently(live):
    ctx = _make_question_and_attempt(live, "20")
    ev = _make_evaluator(live, "20")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)

    def start() -> httpx.Response:
        return live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: start(), range(2)))

    assert all(r.status_code == 200 for r in results), [r.status_code for r in results]
    final = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}").json()
    assert final["status"] == "IN_PROGRESS"


def test_concurrent_saves_leave_a_consistent_last_writer(live):
    ctx = _make_question_and_attempt(live, "21")
    ev = _make_evaluator(live, "21")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)

    def save(marks: str) -> httpx.Response:
        return live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": marks})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["1.00", "2.00"]))

    assert all(r.status_code == 200 for r in results)
    final = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}").json()
    assert _marks(final["awarded_marks"]) in (Decimal("1.00"), Decimal("2.00")), "one of the two concurrent saves must have won, cleanly"


def test_save_vs_submit_race_leaves_no_corruption(live):
    ctx = _make_question_and_attempt(live, "22")
    ev = _make_evaluator(live, "22")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})

    def save() -> httpx.Response:
        return live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "3.00"})

    def submit() -> httpx.Response:
        return live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        r_save = pool.submit(save)
        r_submit = pool.submit(submit)
        results = [r_save.result(), r_submit.result()]

    assert all(r.status_code == 200 for r in results), [r.status_code for r in results]
    final = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}").json()
    assert final["status"] == "SUBMITTED"


def test_submit_vs_finalize_race_leaves_no_corruption(live):
    """A finalize attempt concurrent with (or immediately following) a
    submit must either succeed cleanly once submit has landed, or be
    rejected as an invalid transition -- never leave a torn/ambiguous
    state."""
    ctx = _make_question_and_attempt(live, "23")
    ev = _make_evaluator(live, "23")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "5.00"})

    def submit() -> httpx.Response:
        return live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})

    def finalize() -> httpx.Response:
        return live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        r_submit = pool.submit(submit)
        r_finalize = pool.submit(finalize)
        results = [r_submit.result(), r_finalize.result()]

    for r in results:
        assert r.status_code in (200, 409), r.status_code

    final = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}").json()
    assert final["status"] in ("SUBMITTED", "FINALIZED")


def test_assignment_revoked_mid_session_blocks_the_next_request(live):
    ctx = _make_question_and_attempt(live, "24")
    ev = _make_evaluator(live, "24")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    evaluation_id = _evaluation_id_for(live, assignment)

    r_start = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    assert r_start.status_code == 200

    live.admin.rpc(
        "revoke_evaluator_assignment", {"p_assignment_id": assignment["id"], "p_revoked_by": ctx["student_id"]}
    ).execute()

    r_after = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"feedback": "too late now"})
    assert r_after.status_code == 404
