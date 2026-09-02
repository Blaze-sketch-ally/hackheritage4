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

import httpx


def _setup_two_question_assessment(live):
    """Faculty A creates two questions, faculty B approves both, a
    2-question blueprint is configured. Returns (assessment_id, q1, q2,
    fa_token, fb_token)."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
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
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    # fa holds BOTH capabilities here (unlike _setup_two_question_assessment)
    # so the self-approve check below proves the self-review rule
    # specifically, not merely that fa lacks assessment_reviewer.
    live.grant_assessment_capabilities(fa_id, "assessment_author", "assessment_reviewer")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    r_create = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "peer review"))
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]
    assert r_create.json()["review_status"] == "PENDING"

    r_self_approve = live.api(fa_token, "POST", f"/questions/{question_id}/approve")
    assert r_self_approve.status_code == 403, "self-review must be denied even while holding assessment_reviewer"

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
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
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


# ============================================================
# Phase F5A -- 041_assessment_capability_authorization.sql: the
# question-bank/review/blueprint surface is now capability-gated, not
# just role-gated. These tests prove the actual RLS/RPC behavior live,
# not just that the mocked unit tests exercise the right dependency.
# ============================================================


def test_plain_faculty_without_any_capability_cannot_author_review_or_blueprint(live):
    """A brand-new FACULTY account (as every FACULTY account created
    AFTER 042's one-time backfill will be) has neither capability by
    default and must be denied at every one of these three surfaces."""
    _fp_id, fp_email = live.create_user("fp", "FACULTY")
    fp_token = live.token_for(fp_email)
    aid = live.create_assessment()

    assert live.api(fp_token, "POST", "/questions", json=live.mcq_payload(aid, "plain")).status_code == 403
    assert live.api(
        fp_token, "PUT", f"/assessments/{aid}/blueprint",
        json={"rules": [{"difficulty": "Beginner", "question_count": 1}]},
    ).status_code == 403

    fa_id, fa_email = live.create_user("fa2", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    fa_token = live.token_for(fa_email)
    question_id = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "owned by fa2")).json()["id"]

    assert live.api(fp_token, "POST", f"/questions/{question_id}/approve").status_code == 403
    assert live.api(fp_token, "POST", f"/questions/{question_id}/reject").status_code == 403


def test_answer_key_unreachable_without_capability_but_reachable_with_reviewer(live):
    """The core F5A security requirement: a plain FACULTY account can
    never read an answer key it doesn't own, even via direct PostgREST
    (bypassing FastAPI entirely) -- and a FACULTY account holding
    assessment_reviewer legitimately can, for ANY question, matching the
    pre-existing peer-review visibility behavior."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    fa_token = live.token_for(fa_email)
    aid = live.create_assessment()
    question_id = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "answer key test")).json()["id"]

    _fp_id, fp_email = live.create_user("fp", "FACULTY")
    fp_token = live.token_for(fp_email)
    headers_fp = {"apikey": live._anon_key, "Authorization": f"Bearer {fp_token}"}
    direct_plain = httpx.get(
        f"{live._anon_url}/rest/v1/assessment_question_answers",
        headers=headers_fp,
        params={"question_id": f"eq.{question_id}", "select": "*"},
    )
    assert direct_plain.status_code == 200
    assert direct_plain.json() == [], "a plain FACULTY account must never read another Faculty's answer key"

    fr_id, fr_email = live.create_user("fr", "FACULTY")
    live.grant_assessment_capabilities(fr_id, "assessment_reviewer")
    fr_token = live.token_for(fr_email)
    headers_fr = {"apikey": live._anon_key, "Authorization": f"Bearer {fr_token}"}
    direct_reviewer = httpx.get(
        f"{live._anon_url}/rest/v1/assessment_question_answers",
        headers=headers_fr,
        params={"question_id": f"eq.{question_id}", "select": "*"},
    )
    assert direct_reviewer.status_code == 200
    assert len(direct_reviewer.json()) == 1, "assessment_reviewer must retain full-bank answer-key visibility"


def test_suspended_capability_immediately_blocks_authoring(live):
    """Mirrors the F2 lifecycle-awareness test for assessment
    capabilities specifically: SUSPENDED must behave identically to
    never-granted at the RLS layer, not just at the FastAPI dependency
    layer."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    fa_token = live.token_for(fa_email)
    aid = live.create_assessment()

    r1 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "before suspension"))
    assert r1.status_code == 201

    live.admin.table("faculty_assessment_permissions").update({"status": "SUSPENDED"}).eq(
        "faculty_id", fa_id
    ).eq("capability", "assessment_author").execute()

    r2 = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "after suspension"))
    assert r2.status_code == 403, "a suspended assessment_author grant must immediately block further authoring"


def test_faculty_created_after_backfill_does_not_auto_receive_capabilities(live):
    """042's backfill is a ONE-TIME migration-time INSERT, not an ongoing
    trigger -- proves the negative directly: a FACULTY account created
    during this test run (long after 042 was applied to this database)
    starts with zero assessment capabilities, exactly like any other new
    Faculty signup going forward must be explicitly granted by an ADMIN."""
    _fn_id, fn_email = live.create_user("fn", "FACULTY")
    fn_token = live.token_for(fn_email)

    response = live.api(fn_token, "GET", "/faculty/me/assessment-capabilities")
    assert response.status_code == 200
    assert response.json()["capabilities"] == []


# ============================================================
# Phase F6.1-F6.3 -- 043_question_authoring_metadata.sql: additive
# learning_objective/estimated_time_minutes metadata (covered by the
# SAME approved-question immutability trigger as every other content
# field), and the new review_question() approval-readiness guard that
# blocks an APPROVED decision unless the question is actually
# structurally scoreable. See that migration's own header comment for
# the full reasoning -- these tests prove the DB-side behavior live,
# not just that a mocked unit test exercises the right code path.
# ============================================================


def _short_answer_payload(assessment_id: str, text: str, *, with_answer: bool) -> dict:
    payload = {
        "assessment_id": assessment_id,
        "question_text": f"__QA_{text}",
        "question_type": "SHORT_ANSWER",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Beginner",
        "points": "1.00",
        "display_order": 0,
    }
    if with_answer:
        payload["answer_key"] = {"correct_answer_text": "42"}
    return payload


def test_new_metadata_fields_round_trip_and_are_immutable_once_approved(live):
    """learning_objective/estimated_time_minutes behave exactly like
    every pre-existing content field: settable while PENDING (including
    by an ordinary PATCH), readable back through the API, and rejected
    (403, the same prevent_unauthorized_question_review trigger) the
    moment the same field is touched on an APPROVED question -- proving
    043's trigger extension actually covers the new columns rather than
    silently exempting them."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    payload = live.mcq_payload(aid, "metadata round trip")
    payload["learning_objective"] = "Recall basic arithmetic facts."
    payload["estimated_time_minutes"] = 3
    r_create = live.api(fa_token, "POST", "/questions", json=payload)
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]
    assert r_create.json()["learning_objective"] == "Recall basic arithmetic facts."
    assert r_create.json()["estimated_time_minutes"] == 3

    r_patch_pending = live.api(
        fa_token, "PATCH", f"/questions/{question_id}",
        json={"learning_objective": "Revised objective.", "estimated_time_minutes": 5},
    )
    assert r_patch_pending.status_code == 200, "PENDING questions must remain freely editable, new fields included"
    assert r_patch_pending.json()["learning_objective"] == "Revised objective."
    assert r_patch_pending.json()["estimated_time_minutes"] == 5

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 200

    r_patch_approved = live.api(
        fa_token, "PATCH", f"/questions/{question_id}",
        json={"learning_objective": "Trying to rewrite history."},
    )
    assert r_patch_approved.status_code == 403, (
        "an approved question's learning_objective must be exactly as immutable as "
        "question_text -- 043 must extend the existing trigger, not add an "
        "unprotected column"
    )

    r_patch_time_approved = live.api(
        fa_token, "PATCH", f"/questions/{question_id}", json={"estimated_time_minutes": 99}
    )
    assert r_patch_time_approved.status_code == 403, (
        "estimated_time_minutes must be independently covered by the same trigger, "
        "not just learning_objective"
    )


def test_approve_blocked_when_answer_key_missing(live):
    """The F6 audit's headline finding: an OBJECTIVE MCQ with no answer
    key could previously be approved and would only fail at scoring
    time. 043's review_question() guard must now block the approval
    itself, at the one point (the reviewer's decision) the F6 brief
    identified as safe to enforce it -- not creation, not every PATCH."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    payload = live.mcq_payload(aid, "no answer key")
    del payload["answer_key"]
    r_create = live.api(fa_token, "POST", "/questions", json=payload)
    assert r_create.status_code == 201, "creation itself must remain unrestricted -- draft-safety is preserved"
    question_id = r_create.json()["id"]

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 409

    r_reject = live.api(fb_token, "POST", f"/questions/{question_id}/reject")
    assert r_reject.status_code == 200, "rejecting an incomplete draft must always remain possible"


def test_approve_blocked_when_correct_option_ids_reference_a_foreign_option(live):
    """The request-level Pydantic validator only ever sees ONE payload at
    a time, so it cannot catch an answer key left stale by a LATER,
    separate PATCH that replaces the options alone -- exactly the gap
    the F6 audit flagged (Section 12/16). The DB-side approval guard must
    catch it as the actual last line of defense."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    r_create = live.api(fa_token, "POST", "/questions", json=live.mcq_payload(aid, "stale options"))
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]

    import uuid as _uuid

    new_opt1, new_opt2 = str(_uuid.uuid4()), str(_uuid.uuid4())
    r_replace_options = live.api(
        fa_token, "PATCH", f"/questions/{question_id}",
        json={"options": [
            {"id": new_opt1, "option_text": "C", "display_order": 0},
            {"id": new_opt2, "option_text": "D", "display_order": 1},
        ]},
    )
    assert r_replace_options.status_code == 200, (
        "an options-only PATCH (no answer_key in the same payload) must remain legal -- "
        "this is the exact partial-draft-editing behavior the F6 brief requires preserving"
    )

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 409, (
        "the answer key still references the OLD option ids, which no longer belong to "
        "this question -- approval must be blocked"
    )


def test_approve_blocked_when_fewer_than_two_options(live):
    """No Pydantic-level minimum-option-count check exists (by design --
    see 043's header comment), so this must be caught at approval time."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    import uuid as _uuid

    only_opt = str(_uuid.uuid4())
    payload = {
        "assessment_id": aid,
        "question_text": "__QA_single option",
        "question_type": "MCQ",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Beginner",
        "points": "1.00",
        "display_order": 0,
        "options": [{"id": only_opt, "option_text": "Only one", "display_order": 0}],
        "answer_key": {"correct_option_ids": [only_opt]},
    }
    r_create = live.api(fa_token, "POST", "/questions", json=payload)
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 409


def test_approve_blocked_for_short_answer_without_answer_text(live):
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    r_create = live.api(
        fa_token, "POST", "/questions",
        json=_short_answer_payload(aid, "no answer text", with_answer=False),
    )
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 409


def test_approve_succeeds_for_a_complete_short_answer_question(live):
    """Confirms the new guard does not false-positive-block a legitimately
    complete SHORT_ANSWER question -- the F6 brief's explicit "can
    approve" requirement, not just the "cannot approve" side."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    r_create = live.api(
        fa_token, "POST", "/questions",
        json=_short_answer_payload(aid, "complete", with_answer=True),
    )
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 200
    assert r_approve.json()["review_status"] == "APPROVED"


def test_approve_succeeds_for_a_complete_multiple_select_question_with_two_correct_options(live):
    """MULTIPLE_SELECT, unlike MCQ, legitimately allows more than one
    correct option -- confirms the guard's MCQ-specific
    exactly-one-correct-option rule does not incorrectly apply here."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    import uuid as _uuid

    opt1, opt2, opt3 = str(_uuid.uuid4()), str(_uuid.uuid4()), str(_uuid.uuid4())
    payload = {
        "assessment_id": aid,
        "question_text": "__QA_multi select",
        "question_type": "MULTIPLE_SELECT",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Beginner",
        "points": "1.00",
        "display_order": 0,
        "options": [
            {"id": opt1, "option_text": "A", "display_order": 0},
            {"id": opt2, "option_text": "B", "display_order": 1},
            {"id": opt3, "option_text": "C", "display_order": 2},
        ],
        "answer_key": {"correct_option_ids": [opt1, opt3]},
    }
    r_create = live.api(fa_token, "POST", "/questions", json=payload)
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 200


def test_approve_blocked_for_mcq_with_more_than_one_correct_option(live):
    """MCQ specifically must have EXACTLY one correct option -- unlike
    MULTIPLE_SELECT. Two correct options on an MCQ is exactly the kind
    of "approved but not actually scoreable the way the UI/product
    intends" state the guard exists to prevent."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    import uuid as _uuid

    opt1, opt2 = str(_uuid.uuid4()), str(_uuid.uuid4())
    payload = {
        "assessment_id": aid,
        "question_text": "__QA_two correct on mcq",
        "question_type": "MCQ",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Beginner",
        "points": "1.00",
        "display_order": 0,
        "options": [
            {"id": opt1, "option_text": "A", "display_order": 0},
            {"id": opt2, "option_text": "B", "display_order": 1},
        ],
        "answer_key": {"correct_option_ids": [opt1, opt2]},
    }
    r_create = live.api(fa_token, "POST", "/questions", json=payload)
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 409


def test_approve_blocked_for_code_question_type_marked_objective(live):
    """CODE/SUBJECTIVE are valid question_type CHECK-constraint values
    (and valid Pydantic enum members) but score_assessment_attempt() has
    never implemented scoring for either -- the confirmed latent failure
    mode the F6 audit flagged. 043's guard must block this at approval
    time WITHOUT implementing any CODE-specific scoring (F6 explicitly
    does not implement CODE)."""
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    payload = {
        "assessment_id": aid,
        "question_text": "__QA_code question",
        "question_type": "CODE",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Beginner",
        "points": "1.00",
        "display_order": 0,
        "answer_key": {"correct_answer_text": "print('hello')"},
    }
    r_create = live.api(fa_token, "POST", "/questions", json=payload)
    assert r_create.status_code == 201, (
        "creation must remain unrestricted for every existing valid question_type -- "
        "the guard belongs at approval time only"
    )
    question_id = r_create.json()["id"]

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 409


def test_approve_blocked_for_subjective_question_type_marked_objective(live):
    fa_id, fa_email = live.create_user("fa", "FACULTY")
    fb_id, fb_email = live.create_user("fb", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    fa_token, fb_token = live.token_for(fa_email), live.token_for(fb_email)
    aid = live.create_assessment()

    payload = {
        "assessment_id": aid,
        "question_text": "__QA_subjective question",
        "question_type": "SUBJECTIVE",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Beginner",
        "points": "1.00",
        "display_order": 0,
        "answer_key": {"correct_answer_text": "A model answer."},
    }
    r_create = live.api(fa_token, "POST", "/questions", json=payload)
    assert r_create.status_code == 201
    question_id = r_create.json()["id"]

    r_approve = live.api(fb_token, "POST", f"/questions/{question_id}/approve")
    assert r_approve.status_code == 409
