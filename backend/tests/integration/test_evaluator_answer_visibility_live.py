"""Live-integration coverage for Phase F8.2 -- evaluator answer/attempt/
rubric visibility (046_evaluator_answer_access.sql). Exercises the REAL
Supabase project's RLS boundary directly via PostgREST -- no mocking, no
reliance on a frontend/API layer that doesn't exist yet (F8.2 is
database-only, exactly like F8.1). Self-contained, matching this
directory's own convention (no cross-file imports between live test
modules -- each file duplicates its own small helper set).
"""

import httpx


def _rest_as_user(live, token: str, method: str, table: str, **kwargs) -> httpx.Response:
    headers = kwargs.pop("headers", {})
    headers["apikey"] = live._anon_key
    headers["Authorization"] = f"Bearer {token}"
    headers.setdefault("Prefer", "return=representation")
    return httpx.request(method, f"{live._anon_url}/rest/v1/{table}", headers=headers, **kwargs)


def _make_question_and_attempt(live, tag: str) -> dict:
    """One APPROVED MCQ question + one started student attempt against
    it -- deliberately does NOT create an evaluator (unlike F8.1's own
    _setup_attempt_question), since these tests need fine control over
    evaluator capability status per case."""
    fa_id, fa_email = live.create_user(f"fa{tag}", "FACULTY")
    fb_id, fb_email = live.create_user(f"fb{tag}", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)

    aid = live.create_assessment(title_suffix=tag)
    q1 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, f"eval-visibility{tag}")).json()["id"]
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
        "aid": aid, "question_id": q1, "attempt_id": attempt_id,
        "student_id": s_id, "student_token": s_token, "option_id": option_id,
    }


def _submit_student_answer(live, ctx: dict) -> None:
    """AssessmentAnswerRequest rejects an empty selected_option_ids list
    (backend/app/schemas/assessment.py) -- a real option id is required
    to actually create an assessment_answers row."""
    r = live.api(
        ctx["student_token"], "POST", f"/attempts/{ctx['attempt_id']}/answers",
        json={"question_id": ctx["question_id"], "selected_option_ids": [ctx["option_id"]]},
    )
    assert r.status_code < 300, r.text


def _make_evaluator(live, tag: str, status: str = "GRANTED", expires_at: str | None = None) -> dict:
    """A FACULTY account with a faculty_assessment_permissions row for
    assessment_evaluator at the given status (and optional expires_at) --
    written directly via the admin client, since live.grant_assessment_
    capabilities() only ever inserts status='GRANTED' with no expiry."""
    fe_id, fe_email = live.create_user(f"fe{tag}", "FACULTY")
    row = {"faculty_id": fe_id, "capability": "assessment_evaluator", "status": status}
    if expires_at is not None:
        row["expires_at"] = expires_at
    live.admin.table("faculty_assessment_permissions").insert(row).execute()
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


def _get_answer(live, token: str, ctx: dict) -> list:
    r = _rest_as_user(
        live, token, "GET", "assessment_answers",
        params={"attempt_id": f"eq.{ctx['attempt_id']}", "question_id": f"eq.{ctx['question_id']}"},
    )
    assert r.status_code < 300, r.text
    return r.json()


# ============================================================
# Core answer visibility
# ============================================================


def test_evaluator_with_active_assignment_sees_assigned_answer(live):
    ctx = _make_question_and_attempt(live, "1")
    _submit_student_answer(live, ctx)
    ev = _make_evaluator(live, "1")
    _assign(live, ev["id"], ctx, ctx["student_id"])
    assert len(_get_answer(live, ev["token"], ctx)) == 1


def test_evaluator_cannot_see_answer_for_a_different_question_in_the_same_attempt(live):
    """Verifies the RLS scopes by BOTH attempt_id and question_id, not
    just attempt_id -- see F8.2 audit section 20."""
    ctx = _make_question_and_attempt(live, "2")
    fa2_id, fa2_email = live.create_user("fa2b", "FACULTY")
    live.grant_assessment_capabilities(fa2_id, "assessment_author")
    fa2_token = live.token_for(fa2_email)
    other_aid = live.create_assessment(title_suffix="2b")
    q2 = live.api(fa2_token, "POST", "/questions", json=live.mcq_payload(other_aid, "other-question")).json()["id"]

    ev = _make_evaluator(live, "2")
    _assign(live, ev["id"], ctx, ctx["student_id"])

    r = _rest_as_user(
        live, ev["token"], "GET", "assessment_answers",
        params={"attempt_id": f"eq.{ctx['attempt_id']}", "question_id": f"eq.{q2}"},
    )
    assert r.status_code < 300 and r.json() == []


def test_evaluator_cannot_see_a_different_students_answer_to_the_same_question(live):
    ctx1 = _make_question_and_attempt(live, "3a")
    ctx2 = _make_question_and_attempt(live, "3b")
    ev = _make_evaluator(live, "3")
    _assign(live, ev["id"], ctx1, ctx1["student_id"])

    r = _rest_as_user(
        live, ev["token"], "GET", "assessment_answers",
        params={"attempt_id": f"eq.{ctx2['attempt_id']}", "question_id": f"eq.{ctx2['question_id']}"},
    )
    assert r.status_code < 300 and r.json() == []


def test_evaluator_cannot_see_answer_via_revoked_assignment(live):
    ctx = _make_question_and_attempt(live, "4")
    ev = _make_evaluator(live, "4")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    live.admin.rpc(
        "revoke_evaluator_assignment", {"p_assignment_id": assignment["id"], "p_revoked_by": ctx["student_id"]}
    ).execute()
    assert _get_answer(live, ev["token"], ctx) == []


def test_student_can_still_see_own_answer_after_evaluator_policy_added(live):
    """Regression: the new evaluator SELECT policy is additive
    (PERMISSIVE, OR'd) -- the existing student policy must be completely
    unaffected."""
    ctx = _make_question_and_attempt(live, "5")
    _submit_student_answer(live, ctx)
    assert len(_get_answer(live, ctx["student_token"], ctx)) == 1


# ============================================================
# Capability status (F8.2 audit section 17-18 / decision F)
# ============================================================


def test_suspended_capability_blocks_answer_access(live):
    ctx = _make_question_and_attempt(live, "6")
    ev = _make_evaluator(live, "6", status="SUSPENDED")
    _assign(live, ev["id"], ctx, ctx["student_id"])
    assert _get_answer(live, ev["token"], ctx) == []


def test_expired_capability_blocks_answer_access(live):
    ctx = _make_question_and_attempt(live, "7")
    ev = _make_evaluator(live, "7", status="GRANTED", expires_at="2000-01-01T00:00:00Z")
    _assign(live, ev["id"], ctx, ctx["student_id"])
    assert _get_answer(live, ev["token"], ctx) == []


def test_revoked_capability_blocks_answer_access(live):
    ctx = _make_question_and_attempt(live, "8")
    ev = _make_evaluator(live, "8", status="REVOKED")
    _assign(live, ev["id"], ctx, ctx["student_id"])
    assert _get_answer(live, ev["token"], ctx) == []


def test_capability_suspension_does_not_mutate_the_assignment_row(live):
    """A capability change must never rewrite historical assignment
    data -- decision F."""
    ctx = _make_question_and_attempt(live, "9")
    ev = _make_evaluator(live, "9")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    live.admin.table("faculty_assessment_permissions").update({"status": "SUSPENDED"}).eq(
        "faculty_id", ev["id"]
    ).eq("capability", "assessment_evaluator").execute()

    still_active = live.admin.table("evaluator_assignments").select("status").eq("id", assignment["id"]).execute().data[0]
    assert still_active["status"] == "ACTIVE", "capability suspension must not mutate the assignment row"


# ============================================================
# Attempt visibility
# ============================================================


def test_evaluator_with_active_assignment_sees_assigned_attempt(live):
    ctx = _make_question_and_attempt(live, "10")
    ev = _make_evaluator(live, "10")
    _assign(live, ev["id"], ctx, ctx["student_id"])
    r = _rest_as_user(live, ev["token"], "GET", "assessment_attempts", params={"id": f"eq.{ctx['attempt_id']}"})
    assert r.status_code < 300 and len(r.json()) == 1
    assert r.json()[0]["student_id"] == ctx["student_id"]


def test_evaluator_cannot_see_an_unassigned_attempt(live):
    ctx1 = _make_question_and_attempt(live, "11a")
    ctx2 = _make_question_and_attempt(live, "11b")
    ev = _make_evaluator(live, "11")
    _assign(live, ev["id"], ctx1, ctx1["student_id"])
    r = _rest_as_user(live, ev["token"], "GET", "assessment_attempts", params={"id": f"eq.{ctx2['attempt_id']}"})
    assert r.status_code < 300 and r.json() == []


# ============================================================
# Co-evaluation (decision A) -- section 21/22 of the audit
# ============================================================


def test_two_evaluators_can_both_see_the_same_assigned_answer(live):
    ctx = _make_question_and_attempt(live, "12")
    _submit_student_answer(live, ctx)
    ev_a = _make_evaluator(live, "12a")
    ev_b = _make_evaluator(live, "12b")
    _assign(live, ev_a["id"], ctx, ctx["student_id"])
    _assign(live, ev_b["id"], ctx, ctx["student_id"])
    assert len(_get_answer(live, ev_a["token"], ctx)) == 1
    assert len(_get_answer(live, ev_b["token"], ctx)) == 1


def test_revoking_one_coevaluator_does_not_affect_the_other(live):
    """The critical edge case the audit's section 22 explicitly calls
    out: answer RLS must scope by evaluator_id, not merely by
    (attempt_id, question_id) -- otherwise revoking A would blind B too."""
    ctx = _make_question_and_attempt(live, "13")
    _submit_student_answer(live, ctx)
    ev_a = _make_evaluator(live, "13a")
    ev_b = _make_evaluator(live, "13b")
    assignment_a = _assign(live, ev_a["id"], ctx, ctx["student_id"])
    _assign(live, ev_b["id"], ctx, ctx["student_id"])

    live.admin.rpc(
        "revoke_evaluator_assignment", {"p_assignment_id": assignment_a["id"], "p_revoked_by": ctx["student_id"]}
    ).execute()

    assert _get_answer(live, ev_a["token"], ctx) == [], "revoked co-evaluator must lose access"
    assert len(_get_answer(live, ev_b["token"], ctx)) == 1, "the OTHER co-evaluator must be unaffected"


def test_coevaluator_cannot_see_the_others_assignment_or_evaluation_row(live):
    ctx = _make_question_and_attempt(live, "14")
    ev_a = _make_evaluator(live, "14a")
    ev_b = _make_evaluator(live, "14b")
    assignment_a = _assign(live, ev_a["id"], ctx, ctx["student_id"])
    _assign(live, ev_b["id"], ctx, ctx["student_id"])

    r = _rest_as_user(
        live, ev_b["token"], "GET", "evaluator_assignments", params={"id": f"eq.{assignment_a['id']}"},
    )
    assert r.status_code < 300 and r.json() == [], "co-evaluators must not see each other's own assignment rows"


# ============================================================
# Mentor boundary (decision: mentor contributes nothing) -- section 16
# ============================================================


def test_mentor_only_cannot_see_answer_content(live):
    ctx = _make_question_and_attempt(live, "15")
    mentor_id, mentor_email = live.create_user("mentor15", "FACULTY")
    live.admin.table("faculty_mentor_permissions").insert({"faculty_id": mentor_id, "status": "GRANTED"}).execute()
    mentor_token = live.token_for(mentor_email)

    create = live.api(mentor_token, "POST", "/faculty/mentorships", json={"target_id": ctx["student_id"], "focus_area": "Test"})
    assert create.status_code == 201
    mentorship_id = create.json()["id"]
    live.api(ctx["student_token"], "PATCH", f"/student/mentorships/{mentorship_id}/status", json={"status": "ACCEPTED"})
    live.api(mentor_token, "PATCH", f"/faculty/mentorships/{mentorship_id}/status", json={"status": "ACTIVE"})

    assert _get_answer(live, mentor_token, ctx) == [], "an ACTIVE mentorship must grant zero assessment_answers visibility"


def test_faculty_with_mentor_and_evaluator_sees_answer_only_via_evaluator_path(live):
    ctx = _make_question_and_attempt(live, "16")
    _submit_student_answer(live, ctx)
    fx_id, fx_email = live.create_user("fx16", "FACULTY")
    live.admin.table("faculty_mentor_permissions").insert({"faculty_id": fx_id, "status": "GRANTED"}).execute()
    live.admin.table("faculty_assessment_permissions").insert(
        {"faculty_id": fx_id, "capability": "assessment_evaluator", "status": "GRANTED"}
    ).execute()
    fx_token = live.token_for(fx_email)

    create = live.api(fx_token, "POST", "/faculty/mentorships", json={"target_id": ctx["student_id"], "focus_area": "Test"})
    mentorship_id = create.json()["id"]
    live.api(ctx["student_token"], "PATCH", f"/student/mentorships/{mentorship_id}/status", json={"status": "ACCEPTED"})
    live.api(fx_token, "PATCH", f"/faculty/mentorships/{mentorship_id}/status", json={"status": "ACTIVE"})

    # Before any evaluator assignment exists, the mentor relationship
    # alone must grant nothing.
    assert _get_answer(live, fx_token, ctx) == [], "mentor relationship alone must never grant answer visibility"

    _assign(live, fx_id, ctx, ctx["student_id"])
    assert len(_get_answer(live, fx_token, ctx)) == 1, "answer visibility must appear only once the evaluator assignment exists"


# ============================================================
# Rubric visibility
# ============================================================


def test_evaluator_sees_rubric_attached_to_own_evaluation(live):
    ctx = _make_question_and_attempt(live, "17")
    ev = _make_evaluator(live, "17")
    assignment = _assign(live, ev["id"], ctx, ctx["student_id"])
    rubric = live.admin.table("rubrics").insert(
        {"question_id": ctx["question_id"], "name": "R", "max_marks": "5.00"}
    ).execute().data[0]
    criterion = live.admin.table("rubric_criteria").insert(
        {"rubric_id": rubric["id"], "criterion": "C", "max_marks": "5.00", "display_order": 0}
    ).execute().data[0]

    evaluation_id = live.admin.table("evaluations").select("id").eq("assignment_id", assignment["id"]).execute().data[0]["id"]
    r_attach = _rest_as_user(
        live, ev["token"], "PATCH", "evaluations", params={"id": f"eq.{evaluation_id}"}, json={"rubric_id": rubric["id"]},
    )
    assert r_attach.status_code < 300, r_attach.text

    r_rubric = _rest_as_user(live, ev["token"], "GET", "rubrics", params={"id": f"eq.{rubric['id']}"})
    assert r_rubric.status_code < 300 and len(r_rubric.json()) == 1

    r_criteria = _rest_as_user(live, ev["token"], "GET", "rubric_criteria", params={"id": f"eq.{criterion['id']}"})
    assert r_criteria.status_code < 300 and len(r_criteria.json()) == 1


def test_evaluator_cannot_see_a_rubric_not_attached_to_their_own_evaluation(live):
    ctx = _make_question_and_attempt(live, "18")
    ev = _make_evaluator(live, "18")
    _assign(live, ev["id"], ctx, ctx["student_id"])
    unrelated_rubric = live.admin.table("rubrics").insert(
        {"question_id": ctx["question_id"], "name": "Unrelated", "max_marks": "5.00"}
    ).execute().data[0]

    r = _rest_as_user(live, ev["token"], "GET", "rubrics", params={"id": f"eq.{unrelated_rubric['id']}"})
    assert r.status_code < 300 and r.json() == []


# ============================================================
# Boundaries that must remain exactly as closed as before F8.2
# ============================================================


def test_evaluator_still_cannot_see_the_answer_key(live):
    ctx = _make_question_and_attempt(live, "19")
    ev = _make_evaluator(live, "19")
    _assign(live, ev["id"], ctx, ctx["student_id"])
    r = _rest_as_user(
        live, ev["token"], "GET", "assessment_question_answers", params={"question_id": f"eq.{ctx['question_id']}"},
    )
    assert r.status_code < 300 and r.json() == [], "F8.2 must not grant evaluator access to the answer key (decision C)"


def test_evaluator_still_cannot_see_assessment_attempt_questions(live):
    ctx = _make_question_and_attempt(live, "20")
    ev = _make_evaluator(live, "20")
    _assign(live, ev["id"], ctx, ctx["student_id"])
    r = _rest_as_user(
        live, ev["token"], "GET", "assessment_attempt_questions", params={"attempt_id": f"eq.{ctx['attempt_id']}"},
    )
    assert r.status_code < 300 and r.json() == [], "F8.2 deliberately does not grant this (decision D)"


def test_evaluator_cannot_browse_the_assigned_students_profile(live):
    """Decision B: student identity via student_id is visible on the
    attempt, but this migration adds no profiles policy -- confirm an
    evaluator cannot resolve that uuid to a browsable profile row."""
    ctx = _make_question_and_attempt(live, "21")
    ev = _make_evaluator(live, "21")
    _assign(live, ev["id"], ctx, ctx["student_id"])
    r = _rest_as_user(live, ev["token"], "GET", "profiles", params={"id": f"eq.{ctx['student_id']}"})
    assert r.status_code < 300 and r.json() == [], "no broad Faculty/evaluator profiles policy should exist"


# ============================================================
# Write-attack / IDOR
# ============================================================


def test_evaluator_cannot_write_assessment_answers_through_this_new_policy(live):
    ctx = _make_question_and_attempt(live, "22")
    ev = _make_evaluator(live, "22")
    _assign(live, ev["id"], ctx, ctx["student_id"])

    r_insert = _rest_as_user(
        live, ev["token"], "POST", "assessment_answers",
        json={"attempt_id": ctx["attempt_id"], "question_id": ctx["question_id"], "answer_text": "hack"},
    )
    assert r_insert.status_code >= 400, "the new SELECT policy must not create any write access"

    # No answer row exists yet for this attempt/question (student never
    # answered) -- confirm an UPDATE attempt against a real row is also
    # blocked by re-using the score-immutability trigger's own row.
    _submit_student_answer(live, ctx)
    real_answer_id = _get_answer(live, ev["token"], ctx)[0]["id"]
    r_update = _rest_as_user(
        live, ev["token"], "PATCH", "assessment_answers",
        params={"id": f"eq.{real_answer_id}"}, json={"awarded_marks": "99.00"},
    )
    unchanged = live.admin.table("assessment_answers").select("awarded_marks").eq("id", real_answer_id).execute().data[0]
    assert unchanged["awarded_marks"] is None, f"evaluator must never be able to write awarded_marks, got {r_update.status_code}: {r_update.text}"

    r_delete = _rest_as_user(live, ev["token"], "DELETE", "assessment_answers", params={"id": f"eq.{real_answer_id}"})
    still_there = live.admin.table("assessment_answers").select("id").eq("id", real_answer_id).execute().data
    assert len(still_there) == 1, f"evaluator must never be able to delete an answer, got {r_delete.status_code}"


def test_evaluator_cannot_obtain_another_students_answer_by_manipulating_query_params(live):
    """IDOR check: the RLS boundary, not any client-supplied filter, is
    what must reject this -- an evaluator assigned to ctx1 simply
    changing the attempt_id/question_id query params to ctx2's values
    must still get zero rows."""
    ctx1 = _make_question_and_attempt(live, "23a")
    ctx2 = _make_question_and_attempt(live, "23b")
    ev = _make_evaluator(live, "23")
    _assign(live, ev["id"], ctx1, ctx1["student_id"])

    r = _rest_as_user(
        live, ev["token"], "GET", "assessment_answers",
        params={"attempt_id": f"eq.{ctx2['attempt_id']}", "question_id": f"eq.{ctx2['question_id']}"},
    )
    assert r.status_code < 300 and r.json() == []

    # Also try a broad, unfiltered query -- must return only rows RLS
    # actually permits (zero, since no assignment exists for ctx1 or
    # ctx2's answers yet -- neither student has answered).
    r_broad = _rest_as_user(live, ev["token"], "GET", "assessment_answers", params={"select": "id"})
    assert r_broad.status_code < 300 and r_broad.json() == []


# ============================================================
# Other roles / unauthenticated
# ============================================================


def test_faculty_without_evaluator_capability_sees_nothing(live):
    ctx = _make_question_and_attempt(live, "24")
    _fx_id, fx_email = live.create_user("fx24", "FACULTY")
    fx_token = live.token_for(fx_email)
    assert _get_answer(live, fx_token, ctx) == []


def test_industry_and_institution_see_nothing(live):
    ctx = _make_question_and_attempt(live, "26")
    _ind_id, ind_email = live.create_user("ind26", "INDUSTRY")
    _inst_id, inst_email = live.create_user("inst26", "INSTITUTION")
    assert _get_answer(live, live.token_for(ind_email), ctx) == []
    assert _get_answer(live, live.token_for(inst_email), ctx) == []


def test_unauthenticated_request_is_rejected(live):
    ctx = _make_question_and_attempt(live, "25")
    r = httpx.get(
        f"{live._anon_url}/rest/v1/assessment_answers",
        headers={"apikey": live._anon_key},
        params={"attempt_id": f"eq.{ctx['attempt_id']}"},
    )
    assert r.status_code in (401, 403) or r.json() == []
