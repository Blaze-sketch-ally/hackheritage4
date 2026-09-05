"""Live-integration coverage for Phase 2 (Evaluator Assignment + Real
Evaluation Workspace) -- the closure/verification pass. Exercises the
REAL Supabase project + REAL FastAPI server, through the REAL HTTP
endpoints this phase added:

  POST   /admin/evaluator-assignments
  POST   /admin/evaluator-assignments/{id}/revoke
  GET    /admin/evaluator-assignments/eligible-evaluators
  GET    /admin/evaluator-assignments/attempts?assessment_id=
  GET    /faculty/evaluations/{id}/rubrics

-- plus the unmodified F8.3/F8.4.2/F8.4.2.1 evaluator lifecycle
endpoints, proving the whole assign -> evaluate -> save -> submit ->
finalize -> fold-in -> revoke chain end-to-end for the first time
through a real, authorized admin path rather than a direct service-role
RPC call. Self-contained, matching this directory's own convention.

Rubric AUTHORING still has no product path (a known, reported gap, out
of Phase 2's own scope) -- rubrics are seeded directly via the
service-role admin client here, exactly like every prior F8 live test
file already does; this file's own job is to verify VISIBILITY
(051_evaluator_candidate_rubric_visibility.sql), not authoring.
"""

from decimal import Decimal


def _admin(live, tag: str) -> dict:
    admin_id, admin_email = live.create_user(f"tadm{tag}", "ADMIN")
    return {"id": admin_id, "token": live.token_for(admin_email)}


def _evaluator(live, tag: str) -> dict:
    fe_id, fe_email = live.create_user(f"teval{tag}", "FACULTY")
    live.grant_assessment_capabilities(fe_id, "assessment_evaluator")
    return {"id": fe_id, "token": live.token_for(fe_email)}


def _author_reviewer(live, tag: str) -> dict:
    fa_id, fa_email = live.create_user(f"tfa{tag}", "FACULTY")
    fb_id, fb_email = live.create_user(f"tfb{tag}", "FACULTY")
    live.grant_assessment_capabilities(fa_id, "assessment_author")
    live.grant_assessment_capabilities(fb_id, "assessment_reviewer")
    return {"fa_id": fa_id, "fa_token": live.token_for(fa_email), "fb_id": fb_id, "fb_token": live.token_for(fb_email)}


def _completed_ai_evaluated_attempt(live, tag: str, points: str = "10.00") -> dict:
    """One SUBJECTIVE/AI_EVALUATED question, one COMPLETED student
    attempt -- exactly the shape admin_list_attempts_for_assignment()
    is meant to surface."""
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
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    live.api(s_token, "POST", f"/attempts/{attempt_id}/score")

    return {"attempt_id": attempt_id, "aid": aid, "qid": qid, "points": points, "student_id": s_id, "creator_id": people["fa_id"]}


def _seed_rubric(live, question_id: str, max_marks: str) -> str:
    """Rubric AUTHORING has no product path yet (reported gap, out of
    Phase 2 scope) -- direct service-role seed, matching every prior F8
    live test file's own established convention."""
    return live.admin.table("rubrics").insert(
        {"question_id": question_id, "name": "Correctness", "max_marks": max_marks}
    ).execute().data[0]["id"]


def _evaluation_id_for_evaluator(live, evaluator_token: str) -> str:
    rows = live.api(evaluator_token, "GET", "/faculty/evaluations").json()
    assert len(rows) == 1, rows
    return rows[0]["evaluation_id"]


def _finalize(live, evaluator_token: str, evaluation_id: str, marks: str, rubric_id: str) -> None:
    r_start = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    assert r_start.status_code == 200, r_start.text
    r_save = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"rubric_id": rubric_id, "awarded_marks": marks})
    assert r_save.status_code == 200, r_save.text
    r_submit = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    assert r_submit.status_code == 200, r_submit.text
    r_final = live.api(evaluator_token, "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_final.status_code == 200, r_final.text


# ============================================================
# 1. Admin discovery + assignment creation (Steps 5, 13)
# ============================================================


def test_admin_can_discover_and_assign_an_evaluator(live):
    ctx = _completed_ai_evaluated_attempt(live, "1")
    ev = _evaluator(live, "1")
    admin = _admin(live, "1")

    r_evaluators = live.api(admin["token"], "GET", "/admin/evaluator-assignments/eligible-evaluators")
    assert r_evaluators.status_code == 200, r_evaluators.text
    evaluator_ids = [e["faculty_id"] for e in r_evaluators.json()]
    assert ev["id"] in evaluator_ids

    r_attempts = live.api(admin["token"], "GET", f"/admin/evaluator-assignments/attempts?assessment_id={ctx['aid']}")
    assert r_attempts.status_code == 200, r_attempts.text
    attempts = r_attempts.json()
    assert len(attempts) == 1
    assert attempts[0]["attempt_id"] == ctx["attempt_id"]
    assert attempts[0]["questions"][0]["question_id"] == ctx["qid"]
    # student_label is a truncated identifier only -- never the real email/name.
    assert ctx["student_id"] not in attempts[0]["student_label"]
    assert "@" not in attempts[0]["student_label"]

    r_create = live.api(
        admin["token"], "POST", "/admin/evaluator-assignments",
        json={"evaluator_id": ev["id"], "attempt_id": ctx["attempt_id"], "question_id": ctx["qid"]},
    )
    assert r_create.status_code == 201, r_create.text
    assert r_create.json()["status"] == "ACTIVE"

    # The evaluator now genuinely sees exactly one assignment.
    r_list = live.api(ev["token"], "GET", "/faculty/evaluations")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1
    assert r_list.json()[0]["attempt_id"] == ctx["attempt_id"]
    assert r_list.json()[0]["assessment_title"]  # non-empty, real title


def test_duplicate_active_assignment_returns_409(live):
    ctx = _completed_ai_evaluated_attempt(live, "2")
    ev = _evaluator(live, "2")
    admin = _admin(live, "2")
    body = {"evaluator_id": ev["id"], "attempt_id": ctx["attempt_id"], "question_id": ctx["qid"]}

    r1 = live.api(admin["token"], "POST", "/admin/evaluator-assignments", json=body)
    assert r1.status_code == 201, r1.text
    r2 = live.api(admin["token"], "POST", "/admin/evaluator-assignments", json=body)
    assert r2.status_code == 409, r2.text


def test_only_admin_can_create_or_revoke_assignments(live):
    ctx = _completed_ai_evaluated_attempt(live, "3")
    ev = _evaluator(live, "3")
    admin = _admin(live, "3")
    body = {"evaluator_id": ev["id"], "attempt_id": ctx["attempt_id"], "question_id": ctx["qid"]}

    # An evaluator (even one holding assessment_evaluator) cannot assign
    # themselves or anyone else.
    r_self_assign = live.api(ev["token"], "POST", "/admin/evaluator-assignments", json=body)
    assert r_self_assign.status_code == 403, r_self_assign.text

    r_create = live.api(admin["token"], "POST", "/admin/evaluator-assignments", json=body)
    assert r_create.status_code == 201, r_create.text
    assignment_id = r_create.json()["assignment_id"]

    r_self_revoke = live.api(ev["token"], "POST", f"/admin/evaluator-assignments/{assignment_id}/revoke")
    assert r_self_revoke.status_code == 403, r_self_revoke.text


def test_ineligible_evaluator_rejected_with_422(live):
    """The target must hold assessment_evaluator right now --
    create_evaluator_assignment() itself only checks FACULTY, so this is
    the Python-layer check Phase 2 added."""
    ctx = _completed_ai_evaluated_attempt(live, "4")
    admin = _admin(live, "4")
    plain_faculty_id, _ = live.create_user("tplain4", "FACULTY")  # no assessment_evaluator

    r = live.api(
        admin["token"], "POST", "/admin/evaluator-assignments",
        json={"evaluator_id": plain_faculty_id, "attempt_id": ctx["attempt_id"], "question_id": ctx["qid"]},
    )
    assert r.status_code == 422, r.text


# ============================================================
# 2. Candidate rubric visibility (051) -- the main verification target
# ============================================================


def test_candidate_rubric_visible_to_assigned_evaluator_only(live):
    ctx = _completed_ai_evaluated_attempt(live, "5", points="10.00")
    ev_assigned = _evaluator(live, "5a")
    ev_unrelated = _evaluator(live, "5b")
    admin = _admin(live, "5")
    rubric_id = _seed_rubric(live, ctx["qid"], "10.00")

    live.api(
        admin["token"], "POST", "/admin/evaluator-assignments",
        json={"evaluator_id": ev_assigned["id"], "attempt_id": ctx["attempt_id"], "question_id": ctx["qid"]},
    )
    evaluation_id = _evaluation_id_for_evaluator(live, ev_assigned["token"])

    r_visible = live.api(ev_assigned["token"], "GET", f"/faculty/evaluations/{evaluation_id}/rubrics")
    assert r_visible.status_code == 200, r_visible.text
    ids = [r["id"] for r in r_visible.json()]
    assert rubric_id in ids

    # An evaluator with the capability but no assignment on this
    # question has no evaluation row to query at all -- confirming the
    # 404 boundary, not a rubric-content leak.
    r_unrelated = live.api(ev_unrelated["token"], "GET", f"/faculty/evaluations/{evaluation_id}/rubrics")
    assert r_unrelated.status_code == 404, r_unrelated.text
    assert "Correctness" not in r_unrelated.text


def test_candidate_rubric_no_longer_visible_after_revocation(live):
    ctx = _completed_ai_evaluated_attempt(live, "6", points="10.00")
    ev = _evaluator(live, "6")
    admin = _admin(live, "6")
    rubric_id = _seed_rubric(live, ctx["qid"], "10.00")

    r_create = live.api(
        admin["token"], "POST", "/admin/evaluator-assignments",
        json={"evaluator_id": ev["id"], "attempt_id": ctx["attempt_id"], "question_id": ctx["qid"]},
    )
    assignment_id = r_create.json()["assignment_id"]
    evaluation_id = _evaluation_id_for_evaluator(live, ev["token"])

    r_before = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}/rubrics")
    assert r_before.status_code == 200
    assert any(r["id"] == rubric_id for r in r_before.json())

    r_revoke = live.api(admin["token"], "POST", f"/admin/evaluator-assignments/{assignment_id}/revoke")
    assert r_revoke.status_code == 200, r_revoke.text
    assert r_revoke.json()["status"] == "REVOKED"

    r_after = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}/rubrics")
    assert r_after.status_code == 404, r_after.text


# ============================================================
# 3. Full lifecycle + F8.4 fold-in (Steps 8-9)
# ============================================================


def test_full_lifecycle_and_fold_in_via_the_new_admin_path(live):
    ctx = _completed_ai_evaluated_attempt(live, "7", points="10.00")
    ev = _evaluator(live, "7")
    admin = _admin(live, "7")
    rubric_id = _seed_rubric(live, ctx["qid"], "10.00")

    live.api(
        admin["token"], "POST", "/admin/evaluator-assignments",
        json={"evaluator_id": ev["id"], "attempt_id": ctx["attempt_id"], "question_id": ctx["qid"]},
    )
    evaluation_id = _evaluation_id_for_evaluator(live, ev["token"])

    r_start = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "IN_PROGRESS"})
    assert r_start.status_code == 200
    r_save = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"rubric_id": rubric_id, "awarded_marks": "7.00", "feedback": "Solid answer."})
    assert r_save.status_code == 200, r_save.text

    # Reload via detail -- confirm persistence.
    r_detail = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}")
    assert r_detail.status_code == 200
    body = r_detail.json()
    assert Decimal(str(body["awarded_marks"])) == Decimal("7.00")
    assert body["feedback"] == "Solid answer."
    assert body["rubric"]["id"] == rubric_id
    assert body["assessment_title"]
    assert body["assigned_at"]

    r_submit = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "SUBMITTED"})
    assert r_submit.status_code == 200

    r_finalize = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}/status", json={"status": "FINALIZED"})
    assert r_finalize.status_code == 200
    assert r_finalize.json()["status"] == "FINALIZED"

    # F8.4's own, unmodified fold-in/completion-trigger architecture --
    # a single AI_EVALUATED question, now finalized, on an already-
    # COMPLETED attempt -> immediate COMPLETE fold-in.
    attempt_row = (
        live.admin.table("assessment_attempts")
        .select("evaluation_status, final_score, final_total_marks, final_percentage")
        .eq("id", ctx["attempt_id"])
        .execute()
        .data[0]
    )
    assert attempt_row["evaluation_status"] == "COMPLETE"
    assert Decimal(str(attempt_row["final_score"])) == Decimal("7.00")
    assert Decimal(str(attempt_row["final_total_marks"])) == Decimal("10.00")
    assert Decimal(str(attempt_row["final_percentage"])) == Decimal("70.00")

    # Finalized evaluation is read-only -- the trigger still blocks
    # mutation regardless of this new admin-created-assignment path.
    r_mutate = live.api(ev["token"], "PATCH", f"/faculty/evaluations/{evaluation_id}", json={"awarded_marks": "9.00"})
    assert r_mutate.status_code == 409, r_mutate.text


# ============================================================
# 4. Revocation preserves history (Step 10)
# ============================================================


def test_revocation_after_finalization_preserves_history_and_final_score(live):
    ctx = _completed_ai_evaluated_attempt(live, "8", points="10.00")
    ev = _evaluator(live, "8")
    admin = _admin(live, "8")
    rubric_id = _seed_rubric(live, ctx["qid"], "10.00")

    r_create = live.api(
        admin["token"], "POST", "/admin/evaluator-assignments",
        json={"evaluator_id": ev["id"], "attempt_id": ctx["attempt_id"], "question_id": ctx["qid"]},
    )
    assignment_id = r_create.json()["assignment_id"]
    evaluation_id = _evaluation_id_for_evaluator(live, ev["token"])
    _finalize(live, ev["token"], evaluation_id, "6.00", rubric_id)

    before = live.admin.table("assessment_attempts").select("final_score, evaluation_status").eq("id", ctx["attempt_id"]).execute().data[0]
    assert before["evaluation_status"] == "COMPLETE"

    r_revoke = live.api(admin["token"], "POST", f"/admin/evaluator-assignments/{assignment_id}/revoke")
    assert r_revoke.status_code == 200, r_revoke.text

    # Evaluator immediately loses live access to the (now historical) evaluation...
    r_detail_after = live.api(ev["token"], "GET", f"/faculty/evaluations/{evaluation_id}")
    assert r_detail_after.status_code == 404, r_detail_after.text
    assert "Solid" not in r_detail_after.text and "closure" not in r_detail_after.text.lower()

    # ...but the FINALIZED evaluation row, its history, and the folded-in
    # final score all remain completely intact.
    eval_row = live.admin.table("evaluations").select("status, awarded_marks").eq("id", evaluation_id).execute().data[0]
    assert eval_row["status"] == "FINALIZED"
    assert Decimal(str(eval_row["awarded_marks"])) == Decimal("6.00")

    history_rows = live.admin.table("evaluation_history").select("new_status").eq("evaluation_id", evaluation_id).execute().data
    assert any(h["new_status"] == "FINALIZED" for h in history_rows)

    after = live.admin.table("assessment_attempts").select("final_score, evaluation_status").eq("id", ctx["attempt_id"]).execute().data[0]
    assert after["evaluation_status"] == "COMPLETE"
    assert Decimal(str(after["final_score"])) == Decimal("6.00")


# ============================================================
# 5. Expired capability (Step 11)
# ============================================================


def test_expired_capability_rejects_evaluator_actions_without_touching_assignment(live):
    ctx = _completed_ai_evaluated_attempt(live, "9", points="10.00")
    ev = _evaluator(live, "9")
    admin = _admin(live, "9")

    live.api(
        admin["token"], "POST", "/admin/evaluator-assignments",
        json={"evaluator_id": ev["id"], "attempt_id": ctx["attempt_id"], "question_id": ctx["qid"]},
    )

    live.admin.table("faculty_assessment_permissions").update({"expires_at": "2000-01-01T00:00:00Z"}).eq("faculty_id", ev["id"]).eq("capability", "assessment_evaluator").execute()

    r_list = live.api(ev["token"], "GET", "/faculty/evaluations")
    assert r_list.status_code == 403, r_list.text

    # The assignment itself is untouched by capability expiry -- purely
    # an app-layer rejection, no data mutated.
    assignments = live.admin.table("evaluator_assignments").select("status").eq("evaluator_id", ev["id"]).execute().data
    assert all(a["status"] == "ACTIVE" for a in assignments)


# ============================================================
# 6. Cross-evaluator / cross-attempt isolation (Step 12)
# ============================================================


def test_cross_evaluator_isolation_list_and_detail_and_rubrics(live):
    ctx_a = _completed_ai_evaluated_attempt(live, "10a", points="10.00")
    ctx_b = _completed_ai_evaluated_attempt(live, "10b", points="10.00")
    ev_a = _evaluator(live, "10a")
    ev_b = _evaluator(live, "10b")
    admin = _admin(live, "10")
    rubric_a = _seed_rubric(live, ctx_a["qid"], "10.00")
    _seed_rubric(live, ctx_b["qid"], "10.00")

    live.api(admin["token"], "POST", "/admin/evaluator-assignments", json={"evaluator_id": ev_a["id"], "attempt_id": ctx_a["attempt_id"], "question_id": ctx_a["qid"]})
    live.api(admin["token"], "POST", "/admin/evaluator-assignments", json={"evaluator_id": ev_b["id"], "attempt_id": ctx_b["attempt_id"], "question_id": ctx_b["qid"]})

    evaluation_a = _evaluation_id_for_evaluator(live, ev_a["token"])
    evaluation_b = _evaluation_id_for_evaluator(live, ev_b["token"])
    assert evaluation_a != evaluation_b

    # A's own list contains only A's work.
    list_a = live.api(ev_a["token"], "GET", "/faculty/evaluations").json()
    assert [row["evaluation_id"] for row in list_a] == [evaluation_a]

    # Direct-ID access to B's evaluation, detail, and rubrics -- all 404,
    # never a leak of B's student/question/rubric content.
    r_detail = live.api(ev_a["token"], "GET", f"/faculty/evaluations/{evaluation_b}")
    assert r_detail.status_code == 404, r_detail.text

    r_rubrics = live.api(ev_a["token"], "GET", f"/faculty/evaluations/{evaluation_b}/rubrics")
    assert r_rubrics.status_code == 404, r_rubrics.text

    r_mutate = live.api(ev_a["token"], "PATCH", f"/faculty/evaluations/{evaluation_b}", json={"rubric_id": rubric_a})
    assert r_mutate.status_code == 404, r_mutate.text
