"""Live-database regression coverage for the invariants mocked tests
structurally cannot prove: RLS correctness, SECURITY DEFINER RPC
authorization, cross-user isolation, and the Phase 1K historical-boundary
rule ("current configuration" vs "what an existing attempt actually
recorded"). See tests/integration/README.md before adding to this file --
opt-in only, run with RUN_LIVE_INTEGRATION_TESTS=1.

Each test is independently runnable (its own `live` fixture instance,
cleaned up after) but shares the same setup shape, since most of these
invariants only show up once a real question bank + blueprint + attempt
exists.
"""


def _setup_two_question_assessment(live):
    """Faculty A creates two questions, faculty B approves both, a
    2-question blueprint is configured. Returns (assessment_id, q1, q2,
    fa_token, fb_token)."""
    _fa_id, fa_email = live.create_user("fa", "FACULTY")
    _fb_id, fb_email = live.create_user("fb", "FACULTY")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)

    aid = live.create_assessment()
    q1 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "Q1")).json()["id"]
    live.api(fb_token, "POST", f"/questions/{q1}/approve")
    q2 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "Q2")).json()["id"]
    live.api(fb_token, "POST", f"/questions/{q2}/approve")
    live.api(
        fa_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 2}]},
    )
    return aid, q1, q2, fa_token, fb_token


def test_peer_review_workflow(live):
    """(1) question creation, (2) cross-faculty approval, (3) self-review
    denial, (4) blueprint creation -- items 1-4 of the release-gate smoke
    checklist."""
    _fa_id, fa_email = live.create_user("fa", "FACULTY")
    _fb_id, fb_email = live.create_user("fb", "FACULTY")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    r_create = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "peer review"))
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]
    assert r_create.json()["review_status"] == "PENDING"

    r_self_approve = live.api(fa_token, "POST", f"/questions/{question_id}/approve")
    assert r_self_approve.status_code == 403, "self-review must be denied"

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 200
    assert r_approve.json()["review_status"] == "APPROVED"

    r_blueprint = live.api(
        fa_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 1}]},
    )
    assert r_blueprint.status_code == 200


def test_randomized_attempt_persistence_and_scoring(live):
    """(5) randomized attempt, (6) persisted question set, (9) submission,
    (10) scoring, (11) results, (15) duplicate attempt."""
    aid, q1, q2, _fa_token, _fb_token = _setup_two_question_assessment(live)
    _s_id, s_email = live.create_user("s", "STUDENT")
    s_token = live.token_for(s_email)

    r_attempt = live.api(s_token, "POST", f"/assessments/{aid}/attempts")
    assert r_attempt.status_code == 201
    attempt_id = r_attempt.json()["id"]

    r_dup = live.api(s_token, "POST", f"/assessments/{aid}/attempts")
    assert r_dup.status_code == 409, "duplicate in-progress attempt must be rejected"

    persisted = live.api(s_token, "GET", f"/attempts/{attempt_id}/questions").json()
    persisted_ids = sorted(q["id"] for q in persisted)
    assert persisted_ids == sorted([q1, q2])

    for q in persisted:
        option_id = q["options"][0]["id"]
        r = live.api(
            s_token, "POST", f"/attempts/{attempt_id}/answers",
            json={"question_id": q["id"], "selected_option_ids": [option_id]},
        )
        assert r.status_code == 200

    assert live.api(s_token, "POST", f"/attempts/{attempt_id}/submit").status_code == 200
    assert live.api(s_token, "POST", f"/attempts/{attempt_id}/score").status_code == 200
    r_result = live.api(s_token, "GET", f"/attempts/{attempt_id}/result")
    assert r_result.status_code == 200
    assert sorted(row["question"]["id"] for row in r_result.json()["questions"]) == sorted([q1, q2])


def test_deactivation_before_and_after_answering(live):
    """(7) question deactivation, (8) answer after deactivation -- the
    exact Phase 1K final-hardening regression. Covers both orderings:
    deactivated before the student answers it, and after."""
    aid, q1, q2, fa_token, _fb_token = _setup_two_question_assessment(live)
    _s_id, s_email = live.create_user("s", "STUDENT")
    s_token = live.token_for(s_email)

    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    persisted = live.api(s_token, "GET", f"/attempts/{attempt_id}/questions").json()
    options_by_question = {q["id"]: q["options"][0]["id"] for q in persisted}

    # Deactivate q1 BEFORE it's answered.
    live.api(fa_token, "PATCH", f"/questions/{q1}", json={"is_active": False})

    r_reload = live.api(s_token, "GET", f"/attempts/{attempt_id}/questions")
    assert r_reload.status_code == 200, "a deactivated-but-persisted question must still be readable"
    assert sorted(q["id"] for q in r_reload.json()) == sorted([q1, q2])

    for qid, option_id in options_by_question.items():
        r = live.api(
            s_token, "POST", f"/attempts/{attempt_id}/answers",
            json={"question_id": qid, "selected_option_ids": [option_id]},
        )
        assert r.status_code == 200, f"answering {qid} (deactivated={qid == q1}) must succeed"

    assert live.api(s_token, "POST", f"/attempts/{attempt_id}/submit").status_code == 200
    assert live.api(s_token, "POST", f"/attempts/{attempt_id}/score").status_code == 200
    assert live.api(s_token, "GET", f"/attempts/{attempt_id}/result").status_code == 200


def test_new_attempt_excludes_deactivated_question(live):
    """(12) new attempt excludes inactive question -- proves the fix is
    membership-based for EXISTING attempts, not a blanket eligibility
    relaxation for NEW ones."""
    aid, q1, q2, fa_token, fb_token = _setup_two_question_assessment(live)
    q3 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "Q3")).json()["id"]
    live.api(fb_token, "POST", f"/questions/{q3}/approve")

    live.api(fa_token, "PATCH", f"/questions/{q1}", json={"is_active": False})
    live.api(
        fa_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 2}]},
    )

    _s_id, s_email = live.create_user("s", "STUDENT")
    s_token = live.token_for(s_email)
    r = live.api(s_token, "POST", f"/assessments/{aid}/attempts")
    assert r.status_code == 201
    new_set = {q["id"] for q in live.api(s_token, "GET", f"/attempts/{r.json()['id']}/questions").json()}
    assert q1 not in new_set, "a deactivated question must never enter a NEW attempt"
    assert new_set == {q2, q3}


def test_cross_student_isolation(live):
    """(13) cross-student isolation -- IDOR on read, answer, and submit."""
    aid, q1, _q2, _fa_token, _fb_token = _setup_two_question_assessment(live)
    _s1_id, s1_email = live.create_user("s1", "STUDENT")
    _s2_id, s2_email = live.create_user("s2", "STUDENT")
    s1_token, s2_token = live.token_for(s1_email), live.token_for(s2_email)

    attempt1 = live.api(s1_token, "POST", f"/assessments/{aid}/attempts").json()["id"]

    assert live.api(s2_token, "GET", f"/attempts/{attempt1}/questions").status_code == 404
    assert live.api(
        s2_token, "POST", f"/attempts/{attempt1}/answers",
        json={"question_id": q1, "selected_option_ids": [q1]},
    ).status_code == 404
    assert live.api(s2_token, "POST", f"/attempts/{attempt1}/submit").status_code == 404


def test_answer_key_never_exposed_before_completion(live):
    """(14) answer-key protection."""
    aid, _q1, _q2, _fa_token, _fb_token = _setup_two_question_assessment(live)
    _s_id, s_email = live.create_user("s", "STUDENT")
    s_token = live.token_for(s_email)

    attempt_id = live.api(s_token, "POST", f"/assessments/{aid}/attempts").json()["id"]
    r = live.api(s_token, "GET", f"/attempts/{attempt_id}/questions")
    body_text = r.text
    for forbidden in ("correct_option_ids", "correct_answer_text", "explanation"):
        assert forbidden not in body_text


def test_insufficient_pool_rolls_back_cleanly(live):
    """(16) insufficient pool rollback -- no orphaned attempt left behind."""
    aid = live.create_assessment("_insufficient")
    _fa_id, fa_email = live.create_user("fa", "FACULTY")
    fa_token = live.token_for(fa_email)
    live.api(
        fa_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 999}]},
    )
    _s_id, s_email = live.create_user("s", "STUDENT")
    s_token = live.token_for(s_email)

    before = len(live.admin.table("assessment_attempts").select("id").eq("assessment_id", aid).execute().data)
    r = live.api(s_token, "POST", f"/assessments/{aid}/attempts")
    assert r.status_code == 409
    after = len(live.admin.table("assessment_attempts").select("id").eq("assessment_id", aid).execute().data)
    assert before == after == 0, "a failed attempt-creation RPC must leave zero orphaned rows"
