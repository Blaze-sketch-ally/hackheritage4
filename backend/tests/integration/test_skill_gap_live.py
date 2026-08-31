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
