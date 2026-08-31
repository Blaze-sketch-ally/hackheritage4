"""Live-database regression coverage for Phase 1N (student-owned
portfolio projects/certifications, and the industry applicant-portfolio
read) -- the class of bug mocked tests structurally cannot prove: RLS
correctness on portfolio_projects/portfolio_certifications, the
symmetric USING/WITH CHECK reassignment-blocking design documented in
025_portfolio_projects_and_certifications.sql, the industry
join-through-ownership-chain visibility, and that portfolio never
influences matching or historical records. See
tests/integration/README.md before adding to this file -- opt-in only,
run with RUN_LIVE_INTEGRATION_TESTS=1.

Cleanup note: portfolio_projects/portfolio_certifications both reference
profiles(id) ON DELETE CASCADE with nothing else referencing them (no
RESTRICT chain like applications->opportunities has) -- LiveFixtures'
existing user cleanup already cascades these away with no extra
bookkeeping needed in conftest.py.
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


def _rest_delete(live, table: str, token: str, row_id: str) -> httpx.Response:
    url = f"{live._anon_url}/rest/v1/{table}"
    headers = {
        "apikey": live._anon_key,
        "Authorization": f"Bearer {token}",
        "Prefer": "return=representation",
    }
    return httpx.delete(url, headers=headers, params={"id": f"eq.{row_id}"})


def _create_project(live, token: str, **overrides) -> dict:
    payload = {
        "title": "__QA_Portfolio Project",
        "description": "A project created for live Phase 1N testing.",
        "technologies": ["Python", "FastAPI"],
        "github_url": "https://github.com/example/qa-project",
    }
    payload.update(overrides)
    return live.api(token, "POST", "/portfolio/projects", json=payload).json()


def _apply_student_to_published_opportunity(live, industry_token: str, student_token: str) -> tuple[str, str]:
    """Returns (opportunity_id, application_id)."""
    skill_id = live.admin.table("skills").select("id").eq("is_active", True).limit(1).execute().data[0]["id"]
    opportunity_id = live.api(
        industry_token, "POST", "/opportunities",
        json={"title": "__QA_Portfolio_Test_Role", "opportunity_type": "INTERNSHIP"},
    ).json()["id"]
    live.api(
        industry_token, "PUT", f"/opportunities/{opportunity_id}/requirements",
        json={"requirements": [{"skill_id": skill_id, "required_level": "50", "weight": "1.0"}]},
    )
    live.api(industry_token, "POST", f"/opportunities/{opportunity_id}/publish")
    application_id = live.api(
        student_token, "POST", f"/opportunities/{opportunity_id}/applications", json={}
    ).json()["id"]
    return opportunity_id, application_id


# ============================================================
# Student CRUD -- own projects
# ============================================================


def test_student_can_create_list_update_delete_own_project(live):
    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)

    created = _create_project(live, student_token)
    assert created["title"] == "__QA_Portfolio Project"

    listed = live.api(student_token, "GET", "/portfolio/projects").json()["projects"]
    assert any(p["id"] == created["id"] for p in listed)

    updated = live.api(
        student_token, "PATCH", f"/portfolio/projects/{created['id']}", json={"title": "__QA_Updated Title"}
    ).json()
    assert updated["title"] == "__QA_Updated Title"

    delete_response = live.api(student_token, "DELETE", f"/portfolio/projects/{created['id']}")
    assert delete_response.status_code == 204

    listed_after = live.api(student_token, "GET", "/portfolio/projects").json()["projects"]
    assert not any(p["id"] == created["id"] for p in listed_after)


# ============================================================
# Cross-student authorization (via the real API)
# ============================================================


def test_student_b_cannot_update_or_read_student_a_project(live):
    _sa_id, sa_email = live.create_user("sa", "STUDENT")
    student_a_token = live.token_for(sa_email)
    _sb_id, sb_email = live.create_user("sb", "STUDENT")
    student_b_token = live.token_for(sb_email)

    project = _create_project(live, student_a_token)

    r_read = live.api(student_b_token, "GET", f"/portfolio/projects/{project['id']}")
    assert r_read.status_code == 404, "a student must never see another student's project by id"

    r_update = live.api(
        student_b_token, "PATCH", f"/portfolio/projects/{project['id']}", json={"title": "Hijacked"}
    )
    assert r_update.status_code == 404

    r_delete = live.api(student_b_token, "DELETE", f"/portfolio/projects/{project['id']}")
    assert r_delete.status_code == 404

    unchanged = live.admin.table("portfolio_projects").select("title").eq("id", project["id"]).execute().data[0]
    assert unchanged["title"] == "__QA_Portfolio Project"


# ============================================================
# Direct RLS -- bypassing FastAPI entirely, real REST + real JWTs
# ============================================================


def test_direct_rls_student_a_can_read_own_not_student_b(live):
    student_a_id, sa_email = live.create_user("sa", "STUDENT")
    student_a_token = live.token_for(sa_email)
    _sb_id, sb_email = live.create_user("sb", "STUDENT")
    student_b_token = live.token_for(sb_email)

    project = _create_project(live, student_a_token)

    url = f"{live._anon_url}/rest/v1/portfolio_projects"
    r_own = httpx.get(
        url, headers={"apikey": live._anon_key, "Authorization": f"Bearer {student_a_token}"},
        params={"id": f"eq.{project['id']}"},
    )
    assert len(r_own.json()) == 1

    r_other = httpx.get(
        url, headers={"apikey": live._anon_key, "Authorization": f"Bearer {student_b_token}"},
        params={"id": f"eq.{project['id']}"},
    )
    assert r_other.json() == []
    assert student_a_id  # keep the created id referenced, not dead


def test_direct_rls_student_b_cannot_insert_impersonating_student_a(live):
    student_a_id, _sa_email = live.create_user("sa", "STUDENT")
    _sb_id, sb_email = live.create_user("sb", "STUDENT")
    student_b_token = live.token_for(sb_email)

    r = _rest_insert(
        live, "portfolio_projects", student_b_token,
        {"student_id": student_a_id, "title": "Hacked", "description": "Impersonation attempt."},
    )
    assert r.status_code in (401, 403)


def test_direct_rls_student_b_cannot_update_student_a_project(live):
    _sa_id, sa_email = live.create_user("sa", "STUDENT")
    student_a_token = live.token_for(sa_email)
    _sb_id, sb_email = live.create_user("sb", "STUDENT")
    student_b_token = live.token_for(sb_email)

    project = _create_project(live, student_a_token)

    r = _rest_patch(live, "portfolio_projects", student_b_token, project["id"], {"title": "Hijacked"})
    assert r.status_code == 200
    assert r.json() == [], "RLS must silently match zero rows for a non-owner, never update"

    row = live.admin.table("portfolio_projects").select("title").eq("id", project["id"]).execute().data[0]
    assert row["title"] == "__QA_Portfolio Project"


def test_direct_rls_student_b_cannot_delete_student_a_project(live):
    _sa_id, sa_email = live.create_user("sa", "STUDENT")
    student_a_token = live.token_for(sa_email)
    _sb_id, sb_email = live.create_user("sb", "STUDENT")
    student_b_token = live.token_for(sb_email)

    project = _create_project(live, student_a_token)

    r = _rest_delete(live, "portfolio_projects", student_b_token, project["id"])
    assert r.status_code == 200
    assert r.json() == [], "RLS must silently match zero rows for a non-owner, never delete"

    still_there = live.admin.table("portfolio_projects").select("id").eq("id", project["id"]).execute().data
    assert len(still_there) == 1


def test_direct_rls_student_cannot_reassign_own_project_to_another_student(live):
    """The migration's own design: RLS's symmetric USING/WITH CHECK
    blocks reassignment for free, with no bespoke trigger -- a student
    attempting to move their OWN project onto someone else's student_id
    passes USING (owns the existing row, so PostgREST doesn't silently
    match zero rows the way an unowned-row UPDATE does) but fails WITH
    CHECK against the resulting row (no longer owned by the caller) --
    PostgREST surfaces this as an explicit 403 "row-level security
    policy" violation, not a silent empty-array 200. Confirmed live,
    correcting an initial assumption that this would behave like the
    unowned-row case elsewhere in this file."""
    student_a_id, sa_email = live.create_user("sa", "STUDENT")
    student_a_token = live.token_for(sa_email)
    student_b_id, _sb_email = live.create_user("sb", "STUDENT")

    project = _create_project(live, student_a_token)

    r = _rest_patch(live, "portfolio_projects", student_a_token, project["id"], {"student_id": student_b_id})
    assert r.status_code == 403, "reassigning student_id must be blocked even for the row's own owner"

    row = live.admin.table("portfolio_projects").select("student_id").eq("id", project["id"]).execute().data[0]
    assert row["student_id"] == student_a_id


# ============================================================
# Industry visibility -- the join-through-ownership-chain policy, and
# the GET /applications/{id}/portfolio endpoint built on it
# ============================================================


def test_industry_owner_can_read_applicant_portfolio_unrelated_industry_cannot(live):
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    _ib_id, ib_email = live.create_user("ib", "INDUSTRY")
    industry_b_token = live.token_for(ib_email)
    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)

    _create_project(live, student_token, title="__QA_Visible Project")
    _opportunity_id, application_id = _apply_student_to_published_opportunity(
        live, industry_a_token, student_token
    )

    r_owner = live.api(industry_a_token, "GET", f"/applications/{application_id}/portfolio")
    assert r_owner.status_code == 200
    assert len(r_owner.json()["projects"]) == 1
    assert r_owner.json()["projects"][0]["title"] == "__QA_Visible Project"

    r_unrelated = live.api(industry_b_token, "GET", f"/applications/{application_id}/portfolio")
    assert r_unrelated.status_code == 404, "an unrelated industry must never see this application at all"


def test_direct_rls_industry_a_sees_portfolio_industry_b_does_not(live):
    """Same proof as above, but bypassing FastAPI -- direct REST against
    portfolio_projects itself, confirming the RLS policy (not just the
    route's own 404 translation) is what enforces this."""
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    _ib_id, ib_email = live.create_user("ib", "INDUSTRY")
    industry_b_token = live.token_for(ib_email)
    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)

    project = _create_project(live, student_token)
    _apply_student_to_published_opportunity(live, industry_a_token, student_token)

    url = f"{live._anon_url}/rest/v1/portfolio_projects"
    r_a = httpx.get(
        url, headers={"apikey": live._anon_key, "Authorization": f"Bearer {industry_a_token}"},
        params={"id": f"eq.{project['id']}"},
    )
    assert len(r_a.json()) == 1

    r_b = httpx.get(
        url, headers={"apikey": live._anon_key, "Authorization": f"Bearer {industry_b_token}"},
        params={"id": f"eq.{project['id']}"},
    )
    assert r_b.json() == []


def test_industry_cannot_modify_portfolio(live):
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    student_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)

    project = _create_project(live, student_token)
    _apply_student_to_published_opportunity(live, industry_a_token, student_token)

    r_insert = _rest_insert(
        live, "portfolio_projects", industry_a_token,
        {"student_id": student_id, "title": "Industry Inserted", "description": "Should never work."},
    )
    assert r_insert.status_code in (401, 403)

    r_update = _rest_patch(live, "portfolio_projects", industry_a_token, project["id"], {"title": "Industry Edited"})
    assert r_update.status_code == 200
    assert r_update.json() == [], "industry has SELECT only, never UPDATE, even for a legitimate applicant"

    r_delete = _rest_delete(live, "portfolio_projects", industry_a_token, project["id"])
    assert r_delete.status_code == 200
    assert r_delete.json() == []

    row = live.admin.table("portfolio_projects").select("title").eq("id", project["id"]).execute().data[0]
    assert row["title"] == "__QA_Portfolio Project"


# ============================================================
# Cross-domain: no application => no visibility, regardless of the
# student having a portfolio and the industry having other applicants
# ============================================================


def test_non_applicant_student_portfolio_not_visible_to_industry(live):
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    _s_other_id, s_other_email = live.create_user("s_other", "STUDENT")
    student_other_token = live.token_for(s_other_email)
    # Industry A has at least one real applicant/opportunity, to prove
    # this isn't merely "industry has no data at all".
    _s_applicant_id, s_applicant_email = live.create_user("s_applicant", "STUDENT")
    student_applicant_token = live.token_for(s_applicant_email)
    _opportunity_id, _application_id = _apply_student_to_published_opportunity(
        live, industry_a_token, student_applicant_token
    )

    _create_project(live, student_other_token, title="__QA_Never Applied")

    url = f"{live._anon_url}/rest/v1/portfolio_projects"
    r = httpx.get(
        url, headers={"apikey": live._anon_key, "Authorization": f"Bearer {industry_a_token}"},
        params={"title": "eq.__QA_Never Applied"},
    )
    assert r.json() == [], "a student who never applied anywhere must never be visible to any industry account"


def test_application_to_industry_a_not_visible_to_industry_b(live):
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    _ib_id, ib_email = live.create_user("ib", "INDUSTRY")
    industry_b_token = live.token_for(ib_email)
    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)

    _create_project(live, student_token)
    _opportunity_id, application_id = _apply_student_to_published_opportunity(
        live, industry_a_token, student_token
    )

    r = live.api(industry_b_token, "GET", f"/applications/{application_id}/portfolio")
    assert r.status_code == 404


# ============================================================
# Historical integrity: portfolio changes never mutate match scores,
# applications, or assessment-derived evidence
# ============================================================


def test_portfolio_changes_never_affect_match_or_application(live):
    _ia_id, ia_email = live.create_user("ia", "INDUSTRY")
    industry_a_token = live.token_for(ia_email)
    _s_id, s_email = live.create_user("s", "STUDENT")
    student_token = live.token_for(s_email)

    opportunity_id, application_id = _apply_student_to_published_opportunity(
        live, industry_a_token, student_token
    )

    match_before = live.api(student_token, "GET", f"/opportunities/{opportunity_id}/match").json()
    application_before = live.api(student_token, "GET", "/applications").json()["applications"]
    application_before_row = next(a for a in application_before if a["id"] == application_id)

    project = _create_project(live, student_token, title="__QA_Historical Integrity Project")

    match_after_add = live.api(student_token, "GET", f"/opportunities/{opportunity_id}/match").json()
    assert match_after_add["overall_score"] == match_before["overall_score"]
    assert match_after_add["skills"] == match_before["skills"]

    application_after_add = live.api(student_token, "GET", "/applications").json()["applications"]
    application_after_add_row = next(a for a in application_after_add if a["id"] == application_id)
    assert application_after_add_row["status"] == application_before_row["status"]
    assert application_after_add_row["updated_at"] == application_before_row["updated_at"]

    live.api(student_token, "DELETE", f"/portfolio/projects/{project['id']}")

    match_after_delete = live.api(student_token, "GET", f"/opportunities/{opportunity_id}/match").json()
    assert match_after_delete["overall_score"] == match_before["overall_score"]
    assert match_after_delete["skills"] == match_before["skills"]
