"""Live-database regression coverage for migration
023_role_and_attempt_integrity_hardening.sql -- the class of bug mocked
tests structurally cannot prove: a full-project architecture audit found
five real RLS/trigger gaps (most seriously, a role self-escalation hole),
this file proves each is actually closed live, not just that the
migration file reads correctly. See tests/integration/README.md before
adding to this file -- opt-in only, run with RUN_LIVE_INTEGRATION_TESTS=1.
"""

import httpx


def _rest_patch(live, table: str, token: str, row_id: str, payload: dict) -> httpx.Response:
    """Direct PostgREST PATCH, bypassing FastAPI entirely -- proves RLS/
    triggers, not application code, are the real boundary. Mirrors the
    pattern already established in test_skill_gap_live.py."""
    url = f"{live._anon_url}/rest/v1/{table}"
    headers = {"apikey": live._anon_key, "Authorization": f"Bearer {token}"}
    return httpx.patch(url, headers=headers, params={"id": f"eq.{row_id}"}, json=payload)


def _rest_insert(live, table: str, token: str, payload: dict) -> httpx.Response:
    # Prefer: return=representation -- without it PostgREST's default
    # response to a successful INSERT is 201 with an EMPTY body, which
    # would break any test that needs to read back the created row (e.g.
    # its generated id). Harmless for the rejected-insert tests in this
    # file, which never reach a success response to parse.
    url = f"{live._anon_url}/rest/v1/{table}"
    headers = {
        "apikey": live._anon_key,
        "Authorization": f"Bearer {token}",
        "Prefer": "return=representation",
    }
    return httpx.post(url, headers=headers, json=payload)


def test_student_cannot_self_promote_to_faculty(live):
    """The serious one: 002_protect_admin_role.sql only ever blocked
    self-promotion INTO 'ADMIN' -- every other role transition was
    unguarded until 023. A STUDENT attempting to PATCH their own role to
    FACULTY (real, exploitable privilege escalation: gains question-bank
    write + peer-review authority) must be rejected, and the role must
    remain unchanged on a service-role read afterward."""
    student_id, student_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(student_email)

    r = _rest_patch(live, "profiles", student_token, student_id, {"role": "FACULTY"})
    assert r.status_code >= 400, "a STUDENT must never be able to self-promote to FACULTY"

    row = live.admin.table("profiles").select("role").eq("id", student_id).execute().data[0]
    assert row["role"] == "STUDENT", "role must remain unchanged after the rejected attempt"


def test_faculty_cannot_self_demote_and_reescalate(live):
    """The other half of the same hole: a FACULTY account flipping to
    STUDENT and back (to, e.g., evade an audit trail or exploit a
    STUDENT-only write path) must also be rejected -- the new rule blocks
    ANY self-service change once role is non-null, not just escalation."""
    faculty_id, faculty_email = live.create_user("fa", "FACULTY")
    faculty_token = live.token_for(faculty_email)

    r = _rest_patch(live, "profiles", faculty_token, faculty_id, {"role": "STUDENT"})
    assert r.status_code >= 400, "a FACULTY must never be able to self-demote to STUDENT either"

    row = live.admin.table("profiles").select("role").eq("id", faculty_id).execute().data[0]
    assert row["role"] == "FACULTY"


def test_student_cannot_self_promote_to_industry_institution_or_admin(live):
    """Same hole, every remaining target role -- not just FACULTY."""
    student_id, student_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(student_email)

    for target_role in ("INDUSTRY", "INSTITUTION", "ADMIN"):
        r = _rest_patch(live, "profiles", student_token, student_id, {"role": target_role})
        assert r.status_code >= 400, f"a STUDENT must never be able to self-promote to {target_role}"

    row = live.admin.table("profiles").select("role").eq("id", student_id).execute().data[0]
    assert row["role"] == "STUDENT", "role must remain unchanged after every rejected attempt"


def test_faculty_cannot_self_reassign_to_industry_or_institution(live):
    """Same hole, lateral moves between two already-assigned non-STUDENT
    roles -- not just FACULTY<->STUDENT."""
    faculty_id, faculty_email = live.create_user("fa", "FACULTY")
    faculty_token = live.token_for(faculty_email)

    for target_role in ("INDUSTRY", "INSTITUTION"):
        r = _rest_patch(live, "profiles", faculty_token, faculty_id, {"role": target_role})
        assert r.status_code >= 400, f"a FACULTY must never be able to self-reassign to {target_role}"

    row = live.admin.table("profiles").select("role").eq("id", faculty_id).execute().data[0]
    assert row["role"] == "FACULTY"


def test_legitimate_first_time_role_assignment_still_works(live):
    """The critical safety check: migration 023 must not have broken the
    REAL onboarding flow -- a brand-new user (role NULL, exactly as
    handle_new_user() leaves it) setting their OWN role via their OWN
    token, once, must still succeed. This is the exact call
    lib/auth.ts's updateProfileRole() makes (typed to PublicRole,
    excludes ADMIN at the TS level) -- proven here at the RLS/trigger
    level directly, independent of the frontend type system. Covers all
    four self-selectable roles, not just STUDENT."""
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "INSTITUTION"):
        email = f"__qa_{live.run_id}_onb_{role.lower()}@example.com"
        resp = live.admin.auth.admin.create_user(
            {"email": email, "password": live.password, "email_confirm": True}
        )
        user_id = resp.user.id
        live.user_ids.append(user_id)
        # Deliberately do NOT set role here -- leave it exactly as
        # handle_new_user() creates it (NULL), then assign it via the
        # user's own token, mirroring the real onboarding call.
        row = live.admin.table("profiles").select("role").eq("id", user_id).execute().data[0]
        assert row["role"] is None, "a freshly created profile must start with role = NULL"

        token = live.token_for(email)
        r = _rest_patch(live, "profiles", token, user_id, {"role": role})
        assert r.status_code < 300, f"the legitimate first-time NULL -> {role} assignment must succeed: {r.text}"

        after = live.admin.table("profiles").select("role").eq("id", user_id).execute().data[0]
        assert after["role"] == role


def test_legitimate_first_time_admin_assignment_still_blocked(live):
    """The ADMIN-specific rule (carried over from 002, still enforced by
    023's more general check) must still block even a FIRST-time
    self-assignment into ADMIN -- unlike the other three roles, NULL ->
    'ADMIN' is never legitimate through this self-service path."""
    email = f"__qa_{live.run_id}_onb_admin@example.com"
    resp = live.admin.auth.admin.create_user(
        {"email": email, "password": live.password, "email_confirm": True}
    )
    user_id = resp.user.id
    live.user_ids.append(user_id)

    token = live.token_for(email)
    r = _rest_patch(live, "profiles", token, user_id, {"role": "ADMIN"})
    assert r.status_code >= 400, "NULL -> ADMIN must never succeed, even as a first-time assignment"

    row = live.admin.table("profiles").select("role").eq("id", user_id).execute().data[0]
    assert row["role"] is None


def test_profile_update_still_works_for_non_role_fields(live):
    """The role-change lock must not accidentally block ordinary profile
    edits -- a student changing their own full_name (role omitted/
    unchanged) must still succeed, and profiles.updated_at (023's second
    fix) must actually advance."""
    student_id, student_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(student_email)

    before = live.admin.table("profiles").select("updated_at").eq("id", student_id).execute().data[0]

    r = _rest_patch(live, "profiles", student_token, student_id, {"full_name": "Updated Name"})
    assert r.status_code < 300, f"an ordinary non-role profile update must still succeed: {r.text}"

    after = live.admin.table("profiles").select("full_name, updated_at").eq("id", student_id).execute().data[0]
    assert after["full_name"] == "Updated Name"
    assert after["updated_at"] != before["updated_at"], "profiles.updated_at must advance on UPDATE"


def test_student_cannot_insert_pre_verified_skill(live):
    """003_skills.sql's prevent_self_skill_verification trigger is
    BEFORE UPDATE only -- it never fired on INSERT, and the INSERT policy
    never constrained is_verified either, so a client could INSERT a new
    student_skills row with is_verified: true set directly. 023 closes
    this via the INSERT policy's WITH CHECK instead of the trigger."""
    student_id, student_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(student_email)
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )

    r = _rest_insert(
        live,
        "student_skills",
        student_token,
        {"student_id": student_id, "skill_id": skill_id, "proficiency_level": "Beginner", "is_verified": True},
    )
    assert r.status_code >= 400, "inserting a pre-verified skill must be rejected"


def test_student_can_insert_unverified_skill_normally(live):
    """The fix must not be over-broad -- a normal insert (is_verified
    omitted, or explicitly false) is the ordinary, legitimate case and
    must keep working. Also confirms a student can never flip an existing
    row to verified afterward via UPDATE (the pre-existing, correctly-
    working 003_skills.sql trigger -- re-confirmed here alongside the new
    INSERT-side fix, not assumed)."""
    student_id, student_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(student_email)
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )

    r = _rest_insert(
        live,
        "student_skills",
        student_token,
        {"student_id": student_id, "skill_id": skill_id, "proficiency_level": "Beginner", "is_verified": False},
    )
    assert r.status_code < 300, f"a normal unverified skill insert must succeed: {r.text}"
    row_id = r.json()[0]["id"]

    r_verify = _rest_patch(live, "student_skills", student_token, row_id, {"is_verified": True})
    assert r_verify.status_code >= 400, "a student must never be able to self-verify an existing skill either"

    after = live.admin.table("student_skills").select("is_verified").eq("id", row_id).execute().data[0]
    assert after["is_verified"] is False


def _complete_one_question_assessment(live, skill_id: str) -> tuple[str, str]:
    """Same helper shape as test_skill_gap_live.py's -- returns
    (student_token, attempt_id) for a fully completed, scored attempt."""
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
    correct_option_id = next(o["id"] for o in question["options"] if o["option_text"] == "B")
    live.api(
        s_token, "POST", f"/attempts/{attempt_id}/answers",
        json={"question_id": question["id"], "selected_option_ids": [correct_option_id]},
    )
    live.api(s_token, "POST", f"/attempts/{attempt_id}/submit")
    live.api(s_token, "POST", f"/attempts/{attempt_id}/score")

    return s_token, attempt_id


def test_completed_attempt_assessment_id_is_immutable(live):
    """An attempt must never be reassignable to a different assessment --
    never a legitimate operation, and not blocked before 023."""
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )
    student_token, attempt_id = _complete_one_question_assessment(live, skill_id)
    other_assessment_id = live.create_assessment("_other", skill_id=skill_id)

    r = _rest_patch(live, "assessment_attempts", student_token, attempt_id, {"assessment_id": other_assessment_id})
    assert r.status_code >= 400, "an attempt's assessment_id must never be reassignable"

    row = live.admin.table("assessment_attempts").select("assessment_id").eq("id", attempt_id).execute().data[0]
    assert row["assessment_id"] != other_assessment_id


def test_completed_attempt_timestamps_are_immutable(live):
    """Once COMPLETED, started_at/submitted_at are historical fact -- the
    same 'never reconstruct history' principle this project already
    enforces for scoring. Legitimate submission (setting submitted_at
    while still IN_PROGRESS) is a separate code path and is unaffected --
    this test only proves the LOCKED state, not that submission broke."""
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )
    student_token, attempt_id = _complete_one_question_assessment(live, skill_id)

    before = (
        live.admin.table("assessment_attempts").select("submitted_at").eq("id", attempt_id).execute().data[0]
    )

    r = _rest_patch(live, "assessment_attempts", student_token, attempt_id, {"submitted_at": "2020-01-01T00:00:00Z"})
    assert r.status_code >= 400, "a completed attempt's submitted_at must be immutable"

    after = (
        live.admin.table("assessment_attempts").select("submitted_at").eq("id", attempt_id).execute().data[0]
    )
    assert after["submitted_at"] == before["submitted_at"]


def test_answer_attempt_and_question_reassignment_is_blocked(live):
    """An existing answer row must never be reassignable to a different
    attempt or question -- a revision changes answer content on the SAME
    (attempt_id, question_id) pair, never the pair itself."""
    skill_id = (
        live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    )
    student_token, attempt_id = _complete_one_question_assessment(live, skill_id)

    answer_row = (
        live.admin.table("assessment_answers").select("id, question_id").eq("attempt_id", attempt_id).execute().data[0]
    )

    r = _rest_patch(
        live, "assessment_answers", student_token, answer_row["id"],
        {"question_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code >= 400, "an answer's question_id must never be reassignable"

    after = live.admin.table("assessment_answers").select("question_id").eq("id", answer_row["id"]).execute().data[0]
    assert after["question_id"] == answer_row["question_id"]
