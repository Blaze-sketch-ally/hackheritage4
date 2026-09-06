"""Live-database regression coverage for Phase 1L (skill gap / career
roles) -- the class of bug mocked tests structurally cannot prove: RLS
correctness on the new career_roles/career_role_skill_requirements
tables, and that the skill-gap endpoint's derived evidence genuinely
comes from real completed assessment history, not something fabricated.
See tests/integration/README.md before adding to this file -- opt-in
only, run with RUN_LIVE_INTEGRATION_TESTS=1.
"""

import httpx


def _complete_one_question_assessment(live, skill_id: str) -> tuple[str, float]:
    """Faculty A creates one question, faculty B approves it, a
    1-question blueprint is set, a fresh student completes and scores an
    attempt answering it correctly. Returns (student_token,
    achieved_percentage) -- the exact same class of setup
    test_question_lifecycle_live.py's _setup_two_question_assessment uses,
    reused rather than duplicated as a new fixture mechanism, just scaled
    to one question so the resulting percentage is deterministic (100 if
    answered correctly, which this helper always does)."""
    _fa_id, fa_email = live.create_user("fa", "FACULTY")
    _fb_id, fb_email = live.create_user("fb", "FACULTY")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)

    aid = live.create_assessment(skill_id=skill_id)
    q1 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "Q1")).json()["id"]
    live.api(fb_token, "POST", f"/questions/{q1}/approve")
    live.api(
        fa_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 1}]},
    )

    _s_id, s_email = live.create_user("s", "STUDENT")
    s_token = live.token_for(s_email)

    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    question = live.api(s_token, "GET", f"/attempts/{attempt_id}/questions").json()[0]
    # mcq_payload's answer_key always marks option_text "B" (opt2) correct
    # -- looked up by text, not list position, since neither
    # get_attempt_questions() nor this endpoint guarantees option order.
    correct_option_id = next(o["id"] for o in question["options"] if o["option_text"] == "B")
    live.api(
        s_token, "POST", f"/attempts/{attempt_id}/answers",
        json={"question_id": question["id"], "selected_option_ids": [correct_option_id]},
    )
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    scored = live.api(s_token, "POST", f"/attempts/{attempt_id}/score").json()

    return s_token, float(scored["percentage"])


def test_career_roles_readable_but_not_writable_by_student(live):
    """RLS: any authenticated student can SELECT career_roles/
    career_role_skill_requirements, but cannot INSERT/UPDATE/DELETE either
    -- these are service_role-seeded reference tables (022_career_roles_
    skill_gap.sql), same precedent as skills/assessments."""
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )
    role_id = live.create_career_role_with_requirement(skill_id, required_level=60.0)

    _s_id, s_email = live.create_user("s", "STUDENT")
    s_token = live.token_for(s_email)

    r_list = live.api(s_token, "GET", "/career-roles")
    assert r_list.status_code == 200
    assert any(row["id"] == role_id for row in r_list.json()["career_roles"])

    r_get = live.api(s_token, "GET", f"/career-roles/{role_id}")
    assert r_get.status_code == 200

    # Direct RLS exploit attempts -- bypass FastAPI entirely, hit
    # PostgREST directly with the student's own token via plain httpx
    # (the same tool live.api() already uses), proving RLS itself -- not
    # application code -- is what blocks these writes.
    rest_url = f"{live._anon_url}/rest/v1/career_roles"
    rest_headers = {"apikey": live._anon_key, "Authorization": f"Bearer {s_token}"}

    # INSERT: no INSERT policy at all means every row fails the implicit
    # (absent) WITH CHECK -- PostgREST surfaces this as a 401/403 policy
    # violation (42501), not a silent no-op.
    r_insert = httpx.post(rest_url, headers=rest_headers, json={"title": "Student-Inserted Role"})
    assert r_insert.status_code in (401, 403), "a student must never be able to INSERT into career_roles"

    # UPDATE/DELETE: no policy for either command means the row is simply
    # never VISIBLE for that operation -- Postgres RLS's default-deny
    # means these match zero rows. PostgREST's actual behavior for that
    # (verified live, not assumed): without a `Prefer: return=representation`
    # header, a zero-row PATCH/DELETE returns 204 No Content with an empty
    # body -- not 200 with `[]` (that shape only appears when
    # return=representation is explicitly requested). Either way, no error
    # status is raised and no row is touched -- the follow-up GET below is
    # what actually confirms the row survived untouched.
    r_update = httpx.patch(
        rest_url, headers=rest_headers, params={"id": f"eq.{role_id}"}, json={"title": "Hacked"}
    )
    assert r_update.status_code == 204, "UPDATE must match zero rows -- no UPDATE policy exists for authenticated"
    assert r_update.content == b""

    r_delete = httpx.delete(rest_url, headers=rest_headers, params={"id": f"eq.{role_id}"})
    assert r_delete.status_code == 204, "DELETE must match zero rows -- no DELETE policy exists for authenticated"
    assert r_delete.content == b""

    # Confirm the row genuinely survived untouched (service-role read,
    # bypassing RLS, so this is a direct check of ground truth).
    still_there = live.admin.table("career_roles").select("title").eq("id", role_id).execute().data[0]
    assert still_there["title"] == f"__QA_{live.run_id}"


def test_skill_gap_uses_real_completed_assessment_history(live):
    """The core Phase 1L claim: skill-gap numbers are NOT mocked -- they
    come from a real completed assessment attempt, scored by the real
    Phase 1K scoring RPC, read back through the real skill-gap endpoint."""
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )
    student_token, achieved_percentage = _complete_one_question_assessment(live, skill_id)
    assert achieved_percentage == 100.0  # answered the only question correctly

    role_id = live.create_career_role_with_requirement(skill_id, required_level=70.0, weight=1.0)

    r = live.api(student_token, "GET", f"/career-roles/{role_id}/skill-gap")
    assert r.status_code == 200
    body = r.json()
    assert len(body["skills"]) == 1
    skill_row = body["skills"][0]
    assert skill_row["status"] == "STRONG"
    assert float(skill_row["student_score"]) == achieved_percentage
    assert float(skill_row["gap"]) == 0.0
    assert float(body["overall_score"]) == 100.0


def test_skill_gap_in_progress_attempt_does_not_contribute(live):
    """An IN_PROGRESS attempt (started, not submitted/scored) must not
    make a skill look assessed -- only a COMPLETED attempt counts."""
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )
    _fa_id, fa_email = live.create_user("fa", "FACULTY")
    _fb_id, fb_email = live.create_user("fb", "FACULTY")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)

    aid = live.create_assessment(skill_id=skill_id)
    q1 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "Q1")).json()["id"]
    live.api(fb_token, "POST", f"/questions/{q1}/approve")
    live.api(
        fa_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 1}]},
    )

    _s_id, s_email = live.create_user("s", "STUDENT")
    s_token = live.token_for(s_email)
    live.api(s_token, "POST", f"/assessments/{aid}/attempts")  # started, never submitted/scored

    role_id = live.create_career_role_with_requirement(skill_id, required_level=60.0)
    r = live.api(s_token, "GET", f"/career-roles/{role_id}/skill-gap")
    assert r.status_code == 200
    assert r.json()["skills"][0]["status"] == "NOT_ASSESSED"


def test_skill_gap_cross_student_isolation(live):
    """Student B must never see Student A's skill evidence -- the
    endpoint's identity always comes from the caller's own token."""
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )
    _student_a_token, _percentage = _complete_one_question_assessment(live, skill_id)

    _s_id, s_email = live.create_user("s2", "STUDENT")
    student_b_token = live.token_for(s_email)

    role_id = live.create_career_role_with_requirement(skill_id, required_level=60.0)
    r = live.api(student_b_token, "GET", f"/career-roles/{role_id}/skill-gap")
    assert r.status_code == 200
    assert r.json()["skills"][0]["status"] == "NOT_ASSESSED", (
        "Student B has no completed attempts of their own -- Student A's score must not leak"
    )


# ============================================================
# Phase 3A: eligibility fix (get_student_skill_scores now branches on
# evaluation_status/final_percentage instead of trusting raw percentage
# for any COMPLETED row) -- live proof against a real mixed
# OBJECTIVE + AI_EVALUATED attempt, real evaluator assignment, and real
# fold-in, through both existing consumers (career-role skill-gap and
# opportunity skill-matching).
# ============================================================


def _mixed_attempt_pending_evaluation(live, skill_id: str) -> dict:
    """One OBJECTIVE MCQ (answered correctly, so the raw/objective-only
    percentage would be 100 if it were ever wrongly read) plus one
    SUBJECTIVE/AI_EVALUATED question -- a COMPLETED attempt whose
    evaluation_status starts PENDING. Returns everything the rest of the
    test needs to assign an evaluator and finalize."""
    fa_id, fa_email = live.create_user("p3fa", "FACULTY")
    fb_id, fb_email = live.create_user("p3fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)

    aid = live.create_assessment(title_suffix="_p3a", skill_id=skill_id)
    mcq_id = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "Q1")).json()["id"]
    live.api(fb_token, "POST", f"/questions/{mcq_id}/approve")
    subjective_payload = {
        "assessment_id": aid, "question_text": "__QA_p3a subjective", "question_type": "SUBJECTIVE",
        "scoring_method": "AI_EVALUATED", "difficulty": "Beginner", "points": "10.00", "display_order": 1, "options": [],
    }
    subjective_id = live.api(fa_token, "POST", "/questions", json=subjective_payload).json()["id"]
    live.api(fb_token, "POST", f"/questions/{subjective_id}/approve")
    live.api(
        fa_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 2}]},
    )

    _s_id, s_email = live.create_user("p3s", "STUDENT")
    s_token = live.token_for(s_email)
    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    questions = live.api(s_token, "GET", f"/attempts/{attempt_id}/questions").json()
    mcq_q = next(q for q in questions if q["id"] == mcq_id)
    correct_option_id = next(o["id"] for o in mcq_q["options"] if o["option_text"] == "B")
    live.api(
        s_token, "POST", f"/attempts/{attempt_id}/answers",
        json={"question_id": mcq_id, "selected_option_ids": [correct_option_id]},
    )
    live.api(
        s_token, "POST", f"/attempts/{attempt_id}/answers",
        json={"question_id": subjective_id, "answer_text": "My subjective answer."},
    )
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    live.api(s_token, "POST", f"/attempts/{attempt_id}/score")

    return {"attempt_id": attempt_id, "aid": aid, "subjective_qid": subjective_id, "s_token": s_token}


def test_mixed_attempt_excluded_while_pending_then_contributes_final_percentage_after_finalization(live):
    """The core Phase 3A live proof: a COMPLETED mixed attempt does NOT
    contribute to skill-gap while its AI_EVALUATED question is
    unresolved, then contributes final_percentage (not the raw,
    objective-only percentage) once an admin-assigned evaluator finalizes
    it through the real Phase 2 evaluator workflow.

    This only exercises the career-role skill-gap consumer live.
    Opportunity skill-matching reads the exact same
    get_student_skill_scores() function (see app/services/
    application_service.py) with no eligibility logic of its own, so a
    live proof through that second consumer would be redundant; it is
    instead verified at the unit level (tests/test_applications.py,
    unchanged and still passing after this fix). A live opportunity-
    match test was deliberately NOT added here: doing so would require
    creating an opportunity via a fixture-created INDUSTRY account, which
    triggers a PRE-EXISTING, unrelated bug in this directory's own
    conftest.py LiveFixtures.cleanup() -- it deletes from
    applications.opportunity_id, a column that does not exist on the
    real live `applications` table (whose actual columns are id,
    student_id, industry_id, opportunity_type, internship_id, job_id,
    status, cover_note, match_score, applied_at, created_at, updated_at
    -- confirmed directly against the live project). This appears to
    predate this task entirely (migration 024's `applications` schema
    does not match the live table at all) and affects every live test in
    this suite that creates an opportunity through a fixture-owned
    industry account, including the pre-existing
    test_opportunities_live.py -- it is a live-test-infrastructure/schema
    issue, not an eligibility-logic issue, and is out of Phase 3A's
    scope to fix. Reported as a known limitation, not fixed here."""
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )
    ctx = _mixed_attempt_pending_evaluation(live, skill_id)

    role_id = live.create_career_role_with_requirement(skill_id, required_level=50.0)

    # 1. Pending: excluded, despite the objective MCQ having been
    #    answered correctly (raw percentage would show a misleadingly
    #    high number if this function still read it).
    r_gap_pending = live.api(ctx["s_token"], "GET", f"/career-roles/{role_id}/skill-gap")
    assert r_gap_pending.status_code == 200
    assert r_gap_pending.json()["skills"][0]["status"] == "NOT_ASSESSED"

    # 2. Admin assigns an evaluator and the evaluator finalizes with a
    #    known awarded_marks -- exactly the real Phase 2 workflow.
    _admin_id, admin_email = live.create_user("p3adm", "ADMIN")
    admin_token = live.token_for(admin_email)
    evaluator_id, evaluator_email = live.create_user("p3eval", "FACULTY")
    live.grant_assessment_capabilities(evaluator_id, "assessment_evaluator")
    evaluator_token = live.token_for(evaluator_email)

    r_assign = live.api(
        admin_token, "POST", "/admin/evaluator-assignments",
        json={"evaluator_id": evaluator_id, "attempt_id": ctx["attempt_id"], "question_id": ctx["subjective_qid"]},
    )
    assert r_assign.status_code == 201, r_assign.text

    rubric_id = live.admin.table("rubrics").insert(
        {"question_id": ctx["subjective_qid"], "name": "Correctness", "max_marks": "10.00"}
    ).execute().data[0]["id"]

    evaluation_id = live.api(evaluator_token, "GET", "/faculty/evaluations").json()[0]["evaluation_id"]
    live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    live.api(
        evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}",
        json={"rubric_id": rubric_id, "awarded_marks": "6.00"},
    )
    live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    r_finalize = live.api(
        evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"}
    )
    assert r_finalize.status_code == 200, r_finalize.text

    # 3. Confirm the attempt itself is now COMPLETE with a real
    #    final_percentage (ground truth via the service-role admin
    #    client, independent of either consumer endpoint).
    attempt_row = (
        live.admin.table("assessment_attempts")
        .select("evaluation_status, percentage, final_percentage")
        .eq("id", ctx["attempt_id"])
        .execute()
        .data[0]
    )
    assert attempt_row["evaluation_status"] == "COMPLETE"
    final_percentage = float(attempt_row["final_percentage"])
    # MCQ (1 pt, correct -> 1) + subjective (10 pts, awarded 6) =
    # 7/11 = 63.64%, not the objective-only percentage (100%, since the
    # MCQ alone was answered correctly) that this function used to
    # (wrongly) treat as final.
    assert final_percentage == 63.64
    assert float(attempt_row["percentage"]) == 100.0
    assert final_percentage != float(attempt_row["percentage"])

    # 4. The consumer now reflects final_percentage, not the
    #    stale/objective-only percentage.
    r_gap_final = live.api(ctx["s_token"], "GET", f"/career-roles/{role_id}/skill-gap")
    assert r_gap_final.status_code == 200
    gap_skill = r_gap_final.json()["skills"][0]
    assert gap_skill["status"] == "STRONG"
    assert float(gap_skill["student_score"]) == final_percentage
