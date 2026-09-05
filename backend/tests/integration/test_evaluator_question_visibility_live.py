"""Live-integration coverage for Phase F8.2.1 -- evaluator question/option
visibility (047_evaluator_question_visibility.sql), the RLS gap discovered
during F8.3's own live verification. Exercises the REAL Supabase project
directly via PostgREST -- no mocking. Self-contained, matching this
directory's own convention (no cross-file imports between live test
modules).

Item 23 from the F8.2.1 brief ("evaluator remains able to see the
assigned question if its review_status changes after being selected into
the persisted attempt") is NOT tested here: prevent_unauthorized_
question_review()'s own APPROVED-immutable branch (015/043/044) makes
review_status unconditionally immutable once APPROVED -- there is no
legitimate path to construct that state, and the brief's own instruction
is explicit: "Do not force impossible state transitions merely for
testing."
"""


import httpx


def _rest_as_user(live, token: str, method: str, table: str, **kwargs) -> httpx.Response:
    headers = kwargs.pop("headers", {})
    headers["apikey"] = live._anon_key
    headers["Authorization"] = f"Bearer {token}"
    headers.setdefault("Prefer", "return=representation")
    return httpx.request(method, f"{live._anon_url}/rest/v1/{table}", headers=headers, **kwargs)


def _make_question_and_attempt(live, tag: str) -> dict:
    fa_id, fa_email = live.create_user(f"fa{tag}", "FACULTY")
    fb_id, fb_email = live.create_user(f"fb{tag}", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)

    aid = live.create_assessment(title_suffix=tag)
    q1 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, f"eval-qvis{tag}")).json()["id"]
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

    return {
        "aid": aid, "question_id": q1, "attempt_id": attempt_id, "option_id": option_id,
        "student_id": s_id, "student_token": s_token, "creator_id": fa_id,
    }


def _make_evaluator(live, tag: str, status: str = "GRANTED", expires_at: str | None = None) -> dict:
    fe_id, fe_email = live.create_user(f"fe{tag}", "FACULTY")
    row = {"faculty_id": fe_id, "capability": "assessment_evaluator", "status": status}
    if expires_at is not None:
        row["expires_at"] = expires_at
    live.admin.table("faculty_assessment_permissions").insert(row).execute()
    return {"id": fe_id, "token": live.token_for(fe_email)}


def _assign(live, evaluator_id: str, ctx: dict) -> dict:
    return (
        live.admin.rpc(
            "create_evaluator_assignment",
            {
                "p_evaluator_id": evaluator_id,
                "p_attempt_id": ctx["attempt_id"],
                "p_question_id": ctx["question_id"],
                "p_created_by": ctx["creator_id"],
            },
        )
        .execute()
        .data
    )


# ============================================================
# Positive
# ============================================================


def test_evaluator_with_active_assignment_sees_assigned_question(live):
    ctx = _make_question_and_attempt(live, "1")
    ev = _make_evaluator(live, "1")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and len(r.json()) == 1


def test_evaluator_with_active_assignment_sees_assigned_options(live):
    ctx = _make_question_and_attempt(live, "2")
    ev = _make_evaluator(live, "2")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(
        live, ev["token"], "GET", "assessment_question_options", params={"question_id": f"eq.{ctx['question_id']}"}
    )
    assert r.status_code < 300 and len(r.json()) >= 1


def test_f83_detail_endpoint_now_retrieves_the_question(live):
    ctx = _make_question_and_attempt(live, "3")
    ev = _make_evaluator(live, "3")
    assignment = _assign(live, ev["id"], ctx)
    evaluation_id = live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]

    r = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["question"]["id"] == ctx["question_id"]
    assert "answer_key" not in body["question"]


# ============================================================
# Answer-key boundary
# ============================================================


def test_evaluator_still_sees_zero_answer_key_rows(live):
    ctx = _make_question_and_attempt(live, "4")
    ev = _make_evaluator(live, "4")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(
        live, ev["token"], "GET", "assessment_question_answers", params={"question_id": f"eq.{ctx['question_id']}"}
    )
    assert r.status_code < 300 and r.json() == []


# ============================================================
# Write protection
# ============================================================


def test_evaluator_cannot_update_question(live):
    ctx = _make_question_and_attempt(live, "5")
    ev = _make_evaluator(live, "5")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(
        live, ev["token"], "PATCH", "assessment_questions",
        params={"id": f"eq.{ctx['question_id']}"}, json={"question_text": "hacked"},
    )
    unchanged = live.admin.table("assessment_questions").select("question_text").eq("id", ctx["question_id"]).execute().data[0]
    assert "hacked" not in unchanged["question_text"], f"evaluator must never modify a question, got {r.status_code}"


def test_evaluator_cannot_update_options(live):
    ctx = _make_question_and_attempt(live, "6")
    ev = _make_evaluator(live, "6")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(
        live, ev["token"], "PATCH", "assessment_question_options",
        params={"id": f"eq.{ctx['option_id']}"}, json={"option_text": "hacked"},
    )
    unchanged = live.admin.table("assessment_question_options").select("option_text").eq("id", ctx["option_id"]).execute().data[0]
    assert unchanged["option_text"] != "hacked", f"evaluator must never modify an option, got {r.status_code}"


def test_evaluator_cannot_insert_question(live):
    ctx = _make_question_and_attempt(live, "7")
    ev = _make_evaluator(live, "7")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(
        live, ev["token"], "POST", "assessment_questions",
        json={
            "assessment_id": ctx["aid"], "question_text": "injected", "question_type": "MCQ",
            "scoring_method": "OBJECTIVE", "difficulty": "Beginner", "points": "1.00",
        },
    )
    assert r.status_code >= 400, "no INSERT policy exists for evaluators"


def test_evaluator_cannot_delete_question_or_options(live):
    ctx = _make_question_and_attempt(live, "8")
    ev = _make_evaluator(live, "8")
    _assign(live, ev["id"], ctx)
    r_q = _rest_as_user(live, ev["token"], "DELETE", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    r_o = _rest_as_user(live, ev["token"], "DELETE", "assessment_question_options", params={"id": f"eq.{ctx['option_id']}"})
    still_there_q = live.admin.table("assessment_questions").select("id").eq("id", ctx["question_id"]).execute().data
    still_there_o = live.admin.table("assessment_question_options").select("id").eq("id", ctx["option_id"]).execute().data
    assert len(still_there_q) == 1, f"got {r_q.status_code}"
    assert len(still_there_o) == 1, f"got {r_o.status_code}"


# ============================================================
# Authorization
# ============================================================


def test_faculty_without_evaluator_capability_cannot_see_question(live):
    ctx = _make_question_and_attempt(live, "9")
    _fx_id, fx_email = live.create_user("fx9", "FACULTY")
    fx_token = live.token_for(fx_email)
    r = _rest_as_user(live, fx_token, "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_mentor_only_cannot_see_question_through_this_policy(live):
    ctx = _make_question_and_attempt(live, "10")
    mentor_id, mentor_email = live.create_user("mentor10", "FACULTY")
    live.admin.table("faculty_mentor_permissions").insert({"faculty_id": mentor_id, "status": "GRANTED"}).execute()
    mentor_token = live.token_for(mentor_email)
    r = _rest_as_user(live, mentor_token, "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_evaluator_with_no_assignment_cannot_see_the_question(live):
    ctx = _make_question_and_attempt(live, "11")
    ev = _make_evaluator(live, "11")
    r = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_evaluator_assigned_to_another_question_cannot_see_this_one(live):
    ctx1 = _make_question_and_attempt(live, "12a")
    ctx2 = _make_question_and_attempt(live, "12b")
    ev = _make_evaluator(live, "12")
    _assign(live, ev["id"], ctx1)
    r = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx2['question_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_evaluator_a_cannot_use_evaluator_bs_assignment(live):
    ctx = _make_question_and_attempt(live, "13")
    ev_a = _make_evaluator(live, "13a")
    ev_b = _make_evaluator(live, "13b")
    _assign(live, ev_b["id"], ctx)  # only B is assigned
    r = _rest_as_user(live, ev_a["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_industry_cannot_see(live):
    ctx = _make_question_and_attempt(live, "14")
    _, email = live.create_user("ind14", "INDUSTRY")
    r = _rest_as_user(live, live.token_for(email), "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_institution_cannot_see(live):
    ctx = _make_question_and_attempt(live, "15")
    _, email = live.create_user("inst15", "INSTITUTION")
    r = _rest_as_user(live, live.token_for(email), "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_unauthenticated_cannot_see(live):
    ctx = _make_question_and_attempt(live, "16")
    r = httpx.get(
        f"{live._anon_url}/rest/v1/assessment_questions",
        headers={"apikey": live._anon_key},
        params={"id": f"eq.{ctx['question_id']}"},
    )
    assert r.status_code in (401, 403) or r.json() == []


# ============================================================
# Capability lifecycle
# ============================================================


def test_suspended_capability_blocks_question_access(live):
    ctx = _make_question_and_attempt(live, "17")
    ev = _make_evaluator(live, "17", status="SUSPENDED")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_expired_capability_blocks_question_access(live):
    ctx = _make_question_and_attempt(live, "18")
    ev = _make_evaluator(live, "18", status="GRANTED", expires_at="2000-01-01T00:00:00Z")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


def test_revoked_capability_blocks_question_access(live):
    ctx = _make_question_and_attempt(live, "19")
    ev = _make_evaluator(live, "19", status="REVOKED")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


# ============================================================
# Assignment lifecycle
# ============================================================


def test_active_assignment_visible(live):
    ctx = _make_question_and_attempt(live, "20")
    ev = _make_evaluator(live, "20")
    _assign(live, ev["id"], ctx)
    r = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and len(r.json()) == 1


def test_revoked_assignment_invisible(live):
    ctx = _make_question_and_attempt(live, "21")
    ev = _make_evaluator(live, "21")
    assignment = _assign(live, ev["id"], ctx)
    live.admin.rpc(
        "revoke_evaluator_assignment", {"p_assignment_id": assignment["id"], "p_revoked_by": ctx["creator_id"]}
    ).execute()
    r = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and r.json() == []


# ============================================================
# Historical behavior
# ============================================================


def test_evaluator_still_sees_question_after_later_deactivation(live):
    """The core historical-integrity claim this migration's own header
    makes: a question deactivated AFTER being selected into a persisted
    attempt and assigned to an evaluator must remain visible to that
    evaluator -- mirrors 020_student_view_own_attempt_questions.sql's
    identical guarantee for students."""
    ctx = _make_question_and_attempt(live, "22")
    ev = _make_evaluator(live, "22")
    _assign(live, ev["id"], ctx)

    live.admin.table("assessment_questions").update({"is_active": False}).eq("id", ctx["question_id"]).execute()

    r = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and len(r.json()) == 1, "deactivation must not hide the question from its assigned evaluator"


# ============================================================
# Cross-student isolation (F8.2's own answer RLS must be unaffected)
# ============================================================


def test_question_content_visibility_does_not_leak_unrelated_attempt_answers(live):
    ctx1 = _make_question_and_attempt(live, "23a")
    ctx2 = _make_question_and_attempt(live, "23b")
    ev = _make_evaluator(live, "23")
    _assign(live, ev["id"], ctx1)

    # Can see ctx1's question content (assigned).
    r_question = _rest_as_user(live, ev["token"], "GET", "assessment_questions", params={"id": f"eq.{ctx1['question_id']}"})
    assert r_question.status_code < 300 and len(r_question.json()) == 1

    # Still zero rows for an unrelated attempt's answers (F8.2, untouched).
    r_answers = _rest_as_user(
        live, ev["token"], "GET", "assessment_answers",
        params={"attempt_id": f"eq.{ctx2['attempt_id']}", "question_id": f"eq.{ctx2['question_id']}"},
    )
    assert r_answers.status_code < 300 and r_answers.json() == []


# ============================================================
# Existing roles unchanged
# ============================================================


def test_student_question_visibility_unchanged(live):
    ctx = _make_question_and_attempt(live, "24")
    r = _rest_as_user(live, ctx["student_token"], "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and len(r.json()) == 1


def test_reviewer_visibility_unchanged(live):
    ctx = _make_question_and_attempt(live, "25")
    # The reviewer who approved ctx's question (fb) should still see it
    # via 041's own unchanged policy, regardless of any evaluator
    # assignment existing or not.
    fb_id, fb_email = live.create_user("fb25b", "FACULTY")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fb_token = live.token_for(fb_email)
    r = _rest_as_user(live, fb_token, "GET", "assessment_questions", params={"id": f"eq.{ctx['question_id']}"})
    assert r.status_code < 300 and len(r.json()) == 1


def test_question_author_visibility_unchanged(live):
    # 041's author-visibility clause (created_by = auth.uid()) is
    # untouched by this migration -- confirmed by a fresh author seeing
    # their own newly-created question via the normal /questions API,
    # matching pre-F8.2.1 behavior exactly.
    fa2_id, fa2_email = live.create_user("fa26", "FACULTY")
    live.grant_assessment_capabilities(fa2_id, "assessment_author")
    fa2_token = live.token_for(fa2_email)
    aid2 = live.create_assessment(title_suffix="26b")
    q2 = live.api(fa2_token, "POST", "/questions", json=live.mcq_payload(aid2, "author-owns-this")).json()["id"]
    r = _rest_as_user(live, fa2_token, "GET", "assessment_questions", params={"id": f"eq.{q2}"})
    assert r.status_code < 300 and len(r.json()) == 1
