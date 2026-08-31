"""Live-database regression coverage for Phase 1M (opportunities,
requirements, applications, matching) -- the class of bug mocked tests
structurally cannot prove: RLS correctness on the four new/changed
tables (opportunities, opportunity_skill_requirements, applications, and
the new "Industry can view profiles of their own applicants" policy on
profiles), the prevent_invalid_opportunity_transition and
prevent_unauthorized_application_change triggers, and that matching
reuses the real, unmodified Phase 1L alignment engine against real
assessment evidence. See tests/integration/README.md before adding to
this file -- opt-in only, run with RUN_LIVE_INTEGRATION_TESTS=1.
"""

import httpx


def _rest_insert(live, table: str, token: str, payload: dict) -> httpx.Response:
    url = f"{live._anon_url}/rest/v1/{table}"
    headers = {
        "apikey": live._anon_key,
        "Authorization": f"Bearer {token}",
        "Prefer": "return=representation",
    }
    return httpx.post(url, headers=headers, json=payload)


def _rest_patch(live, table: str, token: str, row_id: str, payload: dict) -> httpx.Response:
    url = f"{live._anon_url}/rest/v1/{table}"
    headers = {
        "apikey": live._anon_key,
        "Authorization": f"Bearer {token}",
        "Prefer": "return=representation",
    }
    return httpx.patch(url, headers=headers, params={"id": f"eq.{row_id}"}, json=payload)


def _complete_one_question_assessment(live, skill_id: str) -> tuple[str, str]:
    """Same shape as the equivalent helper in test_skill_gap_live.py --
    duplicated rather than shared, matching this suite's established
    convention of keeping each live test file self-contained. Returns
    (student_token, achieved_percentage)."""
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
    scored = live.api(s_token, "POST", f"/attempts/{attempt_id}/score").json()
    return s_token, float(scored["percentage"])


def _create_and_publish_opportunity(live, industry_token: str, skill_id: str, required_level: float = 60.0) -> str:
    r = live.api(
        industry_token, "POST", "/opportunities",
        json={"title": "__QA_Test_Role", "opportunity_type": "INTERNSHIP", "location": "Remote"},
    )
    opportunity_id = r.json()["id"]
    live.api(
        industry_token, "PUT", f"/opportunities/{opportunity_id}/requirements",
        json={"requirements": [{"skill_id": skill_id, "required_level": required_level, "weight": "1.0"}]},
    )
    live.api(industry_token, "POST", f"/opportunities/{opportunity_id}/publish")
    return opportunity_id


# Test 1: industry creates opportunity; student cannot.
def test_industry_creates_opportunity_student_cannot(live):
    _i_id, i_email = live.create_user("ind", "INDUSTRY")
    industry_token = live.token_for(i_email)

    r = live.api(
        industry_token, "POST", "/opportunities",
        json={"title": "__QA_Backend Role", "opportunity_type": "JOB"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "DRAFT"

    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)
    r_denied = live.api(
        student_token, "POST", "/opportunities",
        json={"title": "__QA_Fake Role", "opportunity_type": "JOB"},
    )
    assert r_denied.status_code == 403


# Direct RLS: student INSERT into opportunities is denied at the database
# level too, not only by the FastAPI role guard.
def test_direct_rls_student_cannot_insert_opportunity(live):
    industry_id, _i_email = live.create_user("ind", "INDUSTRY")
    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)

    r = _rest_insert(
        live, "opportunities", student_token,
        {"industry_id": industry_id, "title": "Hacked", "opportunity_type": "JOB", "status": "DRAFT"},
    )
    assert r.status_code in (401, 403)


# Test 2: draft invisible to student, published visible.
def test_draft_invisible_published_visible(live):
    _i_id, i_email = live.create_user("ind", "INDUSTRY")
    industry_token = live.token_for(i_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]

    r_draft = live.api(industry_token, "POST", "/opportunities", json={"title": "__QA_Draft Role", "opportunity_type": "JOB"})
    draft_id = r_draft.json()["id"]

    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)

    r_get_draft = live.api(student_token, "GET", f"/opportunities/{draft_id}")
    assert r_get_draft.status_code == 404, "a student must never see another account's DRAFT opportunity"

    published_id = _create_and_publish_opportunity(live, industry_token, skill_id)
    r_get_published = live.api(student_token, "GET", f"/opportunities/{published_id}")
    assert r_get_published.status_code == 200
    assert r_get_published.json()["status"] == "PUBLISHED"


# Test 3: requirements persist correctly.
def test_requirements_persist_correctly(live):
    _i_id, i_email = live.create_user("ind", "INDUSTRY")
    industry_token = live.token_for(i_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]

    r_create = live.api(industry_token, "POST", "/opportunities", json={"title": "__QA_Req Role", "opportunity_type": "JOB"})
    opportunity_id = r_create.json()["id"]

    r_put = live.api(
        industry_token, "PUT", f"/opportunities/{opportunity_id}/requirements",
        json={"requirements": [{"skill_id": skill_id, "required_level": "72.50", "weight": "1.25"}]},
    )
    assert r_put.status_code == 200

    r_get = live.api(industry_token, "GET", f"/opportunities/{opportunity_id}/requirements")
    reqs = r_get.json()["requirements"]
    assert len(reqs) == 1
    assert float(reqs[0]["required_level"]) == 72.50
    assert float(reqs[0]["weight"]) == 1.25


# Test 15: student cannot modify opportunity requirements.
def test_student_cannot_modify_requirements(live):
    _i_id, i_email = live.create_user("ind", "INDUSTRY")
    industry_token = live.token_for(i_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    r_create = live.api(industry_token, "POST", "/opportunities", json={"title": "__QA_Locked Role", "opportunity_type": "JOB"})
    opportunity_id = r_create.json()["id"]

    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)
    r = live.api(
        student_token, "PUT", f"/opportunities/{opportunity_id}/requirements",
        json={"requirements": [{"skill_id": skill_id, "required_level": "10", "weight": "1.0"}]},
    )
    assert r.status_code == 403


# Tests 4 & 5: match uses real completed evidence; IN_PROGRESS excluded.
def test_match_uses_real_completed_evidence_and_excludes_in_progress(live):
    _i_id, i_email = live.create_user("ind", "INDUSTRY")
    industry_token = live.token_for(i_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]

    student_token, achieved_percentage = _complete_one_question_assessment(live, skill_id)
    assert achieved_percentage == 100.0

    opportunity_id = _create_and_publish_opportunity(live, industry_token, skill_id, required_level=70.0)

    r_match = live.api(student_token, "GET", f"/opportunities/{opportunity_id}/match")
    assert r_match.status_code == 200
    body = r_match.json()
    assert len(body["skills"]) == 1
    assert body["skills"][0]["status"] == "STRONG"
    assert float(body["skills"][0]["student_score"]) == achieved_percentage
    assert float(body["overall_score"]) == 100.0

    # A second opportunity requiring a DIFFERENT, never-assessed skill --
    # confirms NOT_ASSESSED, not a fabricated/leftover score.
    other_skills = (
        live.admin.table("skills").select("id").eq("is_active", True).neq("id", skill_id).limit(1).execute().data
    )
    if other_skills:
        other_opportunity_id = _create_and_publish_opportunity(live, industry_token, other_skills[0]["id"], required_level=60.0)
        r_other = live.api(student_token, "GET", f"/opportunities/{other_opportunity_id}/match")
        assert r_other.json()["skills"][0]["status"] == "NOT_ASSESSED"


# Tests 6, 7: student can apply; duplicate rejected.
def test_student_applies_duplicate_rejected(live):
    _i_id, i_email = live.create_user("ind", "INDUSTRY")
    industry_token = live.token_for(i_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    opportunity_id = _create_and_publish_opportunity(live, industry_token, skill_id)

    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)

    r1 = live.api(student_token, "POST", f"/opportunities/{opportunity_id}/applications", json={"cover_note": "Excited!"})
    assert r1.status_code == 201
    assert r1.json()["status"] == "APPLIED"

    r2 = live.api(student_token, "POST", f"/opportunities/{opportunity_id}/applications", json={})
    assert r2.status_code == 409


# Direct RLS: student INSERT own application allowed; for another
# student, denied.
def test_direct_rls_application_insert_identity(live):
    _i_id, i_email = live.create_user("ind", "INDUSTRY")
    industry_token = live.token_for(i_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    opportunity_id = _create_and_publish_opportunity(live, industry_token, skill_id)

    student_a_id, s_email = live.create_user("sa", "STUDENT")
    student_a_token = live.token_for(s_email)
    _student_b_id, s_email_b = live.create_user("sb", "STUDENT")
    student_b_token = live.token_for(s_email_b)

    r_own = _rest_insert(live, "applications", student_a_token, {"opportunity_id": opportunity_id, "student_id": student_a_id})
    assert r_own.status_code in (200, 201)

    r_impersonate = _rest_insert(
        live, "applications", student_b_token, {"opportunity_id": opportunity_id, "student_id": student_a_id}
    )
    assert r_impersonate.status_code in (401, 403), "a student must never be able to apply as another student"


# Test 14: closed opportunity cannot receive new applications.
def test_closed_opportunity_rejects_new_applications(live):
    _i_id, i_email = live.create_user("ind", "INDUSTRY")
    industry_token = live.token_for(i_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    opportunity_id = _create_and_publish_opportunity(live, industry_token, skill_id)
    live.api(industry_token, "POST", f"/opportunities/{opportunity_id}/close")

    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)
    r = live.api(student_token, "POST", f"/opportunities/{opportunity_id}/applications", json={})
    assert r.status_code == 409


# Tests 8, 9: student sees own application; not another student's.
def test_student_sees_own_not_others_applications(live):
    _i_id, i_email = live.create_user("ind", "INDUSTRY")
    industry_token = live.token_for(i_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    opportunity_id = _create_and_publish_opportunity(live, industry_token, skill_id)

    _sa_id, sa_email = live.create_user("sa", "STUDENT")
    student_a_token = live.token_for(sa_email)
    live.api(student_a_token, "POST", f"/opportunities/{opportunity_id}/applications", json={})

    r_own = live.api(student_a_token, "GET", "/applications")
    assert len(r_own.json()["applications"]) == 1

    _sb_id, sb_email = live.create_user("sb", "STUDENT")
    student_b_token = live.token_for(sb_email)
    r_other = live.api(student_b_token, "GET", "/applications")
    assert r_other.json()["applications"] == []


# Tests 10, 11: industry owner sees applicants; unrelated industry does not.
def test_industry_owner_sees_applicants_unrelated_does_not(live):
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    opportunity_id = _create_and_publish_opportunity(live, industry_a_token, skill_id)

    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)
    live.api(student_token, "POST", f"/opportunities/{opportunity_id}/applications", json={})

    r_own = live.api(industry_a_token, "GET", f"/opportunities/{opportunity_id}/applicants")
    assert r_own.status_code == 200
    applicants = r_own.json()["applicants"]
    assert len(applicants) == 1
    assert "student_name" in applicants[0]
    assert "overall_match_score" in applicants[0]

    _ib_id, ib_email = live.create_user("ib", "INDUSTRY")
    industry_b_token = live.token_for(ib_email)
    r_other = live.api(industry_b_token, "GET", f"/opportunities/{opportunity_id}/applicants")
    assert r_other.status_code == 200
    assert r_other.json()["applicants"] == [], "an unrelated industry must never see another's applicants"


# Direct RLS: industry SELECT own applicants allowed; another's denied,
# at the database level (bypassing FastAPI entirely).
def test_direct_rls_applicant_visibility(live):
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    opportunity_id = _create_and_publish_opportunity(live, industry_a_token, skill_id)
    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)
    live.api(student_token, "POST", f"/opportunities/{opportunity_id}/applications", json={})

    _ib_id, ib_email = live.create_user("ib", "INDUSTRY")
    industry_b_token = live.token_for(ib_email)

    rest_url = f"{live._anon_url}/rest/v1/applications"
    r_a = httpx.get(
        rest_url, headers={"apikey": live._anon_key, "Authorization": f"Bearer {industry_a_token}"},
        params={"opportunity_id": f"eq.{opportunity_id}"},
    )
    assert len(r_a.json()) == 1
    r_b = httpx.get(
        rest_url, headers={"apikey": live._anon_key, "Authorization": f"Bearer {industry_b_token}"},
        params={"opportunity_id": f"eq.{opportunity_id}"},
    )
    assert r_b.json() == []


# Tests 12, 13: industry owner can update status; unrelated industry cannot.
def test_owner_updates_status_unrelated_cannot(live):
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    opportunity_id = _create_and_publish_opportunity(live, industry_a_token, skill_id)
    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)
    application_id = live.api(student_token, "POST", f"/opportunities/{opportunity_id}/applications", json={}).json()["id"]

    r_owner = live.api(industry_a_token, "PATCH", f"/applications/{application_id}/status", json={"status": "SHORTLISTED"})
    assert r_owner.status_code == 200
    assert r_owner.json()["status"] == "SHORTLISTED"

    _ib_id, ib_email = live.create_user("ib", "INDUSTRY")
    industry_b_token = live.token_for(ib_email)
    r_unrelated = live.api(industry_b_token, "PATCH", f"/applications/{application_id}/status", json={"status": "REJECTED"})
    assert r_unrelated.status_code == 404

    r_student = live.api(student_token, "PATCH", f"/applications/{application_id}/status", json={"status": "SELECTED"})
    assert r_student.status_code == 403

    unchanged = live.admin.table("applications").select("status").eq("id", application_id).execute().data[0]
    assert unchanged["status"] == "SHORTLISTED"


# Direct RLS: industry UPDATE own opportunity allowed; another's denied.
def test_direct_rls_opportunity_update_ownership(live):
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    r_create = live.api(industry_a_token, "POST", "/opportunities", json={"title": "__QA_Owned Role", "opportunity_type": "JOB"})
    opportunity_id = r_create.json()["id"]

    _ib_id, ib_email = live.create_user("ib", "INDUSTRY")
    industry_b_token = live.token_for(ib_email)

    r_own = _rest_patch(live, "opportunities", industry_a_token, opportunity_id, {"title": "Updated By Owner"})
    assert r_own.status_code == 200
    assert len(r_own.json()) == 1

    r_other = _rest_patch(live, "opportunities", industry_b_token, opportunity_id, {"title": "Hijacked"})
    assert r_other.status_code == 200
    assert r_other.json() == [], "RLS must silently match zero rows for a non-owner, never update"

    row = live.admin.table("opportunities").select("title").eq("id", opportunity_id).execute().data[0]
    assert row["title"] == "Updated By Owner"
