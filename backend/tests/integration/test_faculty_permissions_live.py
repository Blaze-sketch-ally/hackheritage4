"""Live RLS/RPC coverage for Phase F2 capability infrastructure, including
the ADMIN control surface added by
035_admin_faculty_permission_management.sql."""

import httpx


def _rest_request(live, method: str, table: str, token: str, **kwargs) -> httpx.Response:
    headers = {"apikey": live._anon_key, "Authorization": f"Bearer {token}"}
    return httpx.request(method, f"{live._anon_url}/rest/v1/{table}", headers=headers, **kwargs)


def _rest_rpc(live, function: str, token: str, params: dict) -> httpx.Response:
    headers = {"apikey": live._anon_key, "Authorization": f"Bearer {token}"}
    return httpx.post(f"{live._anon_url}/rest/v1/rpc/{function}", headers=headers, json=params)


def _grant(live, faculty_id: str, capability: str, **overrides) -> str:
    row = (
        live.admin.table("faculty_assessment_permissions")
        .insert({"faculty_id": faculty_id, "capability": capability, **overrides})
        .execute()
        .data[0]
    )
    return row["id"]


def test_effective_capabilities_are_self_only_role_gated_and_lifecycle_aware(live):
    faculty_id, faculty_email = live.create_user("faculty", "FACULTY")
    student_id, student_email = live.create_user("student", "STUDENT")
    _industry_id, industry_email = live.create_user("industry", "INDUSTRY")
    _institution_id, institution_email = live.create_user("institution", "INSTITUTION")
    _admin_id, admin_email = live.create_user("admin", "ADMIN")
    faculty_token = live.token_for(faculty_email)

    for capability in (
        "assessment_author",
        "assessment_reviewer",
        "assessment_evaluator",
        "assessment_moderator",
        "assessment_lead",
    ):
        _grant(live, faculty_id, capability)

    # A malformed/legacy permission row cannot bypass the top-level role.
    _grant(live, student_id, "assessment_author")

    response = live.api(faculty_token, "GET", "/faculty/me/assessment-capabilities")
    assert response.status_code == 200
    assert response.json()["capabilities"] == [
        "assessment_author",
        "assessment_evaluator",
        "assessment_lead",
        "assessment_moderator",
        "assessment_reviewer",
    ]

    for email in (student_email, industry_email, institution_email, admin_email):
        denied = live.api(live.token_for(email), "GET", "/faculty/me/assessment-capabilities")
        assert denied.status_code == 403

    lifecycle_cases = (
        ("assessment_author", "SUSPENDED", None),
        ("assessment_reviewer", "REVOKED", None),
        ("assessment_evaluator", "EXPIRED", None),
        ("assessment_moderator", "GRANTED", "2000-01-01T00:00:00Z"),
    )
    for capability, status, expires_at in lifecycle_cases:
        payload = {"status": status, "status_changed_by": faculty_id}
        if expires_at is not None:
            payload["expires_at"] = expires_at
        live.admin.table("faculty_assessment_permissions").update(payload).eq(
            "faculty_id", faculty_id
        ).eq("capability", capability).execute()

    after = live.api(faculty_token, "GET", "/faculty/me/assessment-capabilities")
    assert after.status_code == 200
    assert after.json()["capabilities"] == ["assessment_lead"]


def test_permission_rows_are_not_directly_readable_or_writable_by_faculty(live):
    faculty_a_id, faculty_a_email = live.create_user("faculty_a", "FACULTY")
    faculty_b_id, _faculty_b_email = live.create_user("faculty_b", "FACULTY")
    faculty_a_token = live.token_for(faculty_a_email)
    permission_id = _grant(live, faculty_b_id, "assessment_author")

    # No SELECT policy exists: Faculty cannot inspect their own or another
    # Faculty member's raw grant metadata.
    read = _rest_request(
        live,
        "GET",
        "faculty_assessment_permissions",
        faculty_a_token,
        params={"select": "*"},
    )
    assert read.status_code < 300
    assert read.json() == []

    self_grant = _rest_request(
        live,
        "POST",
        "faculty_assessment_permissions",
        faculty_a_token,
        json={"faculty_id": faculty_a_id, "capability": "assessment_lead"},
    )
    assert self_grant.status_code >= 400

    cross_user_change = _rest_request(
        live,
        "PATCH",
        "faculty_assessment_permissions",
        faculty_a_token,
        params={"id": f"eq.{permission_id}"},
        json={"status": "REVOKED", "status_changed_by": faculty_a_id},
    )
    assert cross_user_change.status_code < 300
    unchanged = (
        live.admin.table("faculty_assessment_permissions")
        .select("status, status_changed_by")
        .eq("id", permission_id)
        .execute()
        .data[0]
    )
    assert unchanged == {"status": "GRANTED", "status_changed_by": None}


def test_admin_can_grant_and_change_status_and_faculty_sees_the_effect(live):
    """The API-level path (require_admin -> admin_grant_assessment_capability
    / admin_set_assessment_permission_status), end to end: an ADMIN grants
    a capability through the FastAPI admin router, the Faculty member's
    own self-only endpoint immediately reflects it, the admin suspends it
    through the same router, and the Faculty member immediately loses it
    -- all without either side ever touching
    faculty_assessment_permissions directly."""
    admin_id, admin_email = live.create_user("admin_grant", "ADMIN")
    faculty_id, faculty_email = live.create_user("faculty_grant", "FACULTY")
    admin_token = live.token_for(admin_email)
    faculty_token = live.token_for(faculty_email)

    granted = live.api(
        admin_token,
        "POST",
        f"/admin/faculty/{faculty_id}/assessment-permissions",
        json={"capability": "assessment_reviewer"},
    )
    assert granted.status_code == 200
    permission_id = granted.json()["permission_id"]
    assert granted.json()["status"] == "GRANTED"

    reflected = live.api(faculty_token, "GET", "/faculty/me/assessment-capabilities")
    assert reflected.status_code == 200
    assert reflected.json()["capabilities"] == ["assessment_reviewer"]

    suspended = live.api(
        admin_token,
        "PATCH",
        f"/admin/faculty/assessment-permissions/{permission_id}/status",
        json={"status": "SUSPENDED"},
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "SUSPENDED"

    after_suspend = live.api(faculty_token, "GET", "/faculty/me/assessment-capabilities")
    assert after_suspend.status_code == 200
    assert after_suspend.json()["capabilities"] == []

    listing = live.api(admin_token, "GET", "/admin/faculty/assessment-permissions")
    assert listing.status_code == 200
    listed_faculty = {entry["faculty_id"]: entry for entry in listing.json()["faculty"]}
    assert admin_id not in listed_faculty
    assert listed_faculty[faculty_id]["permissions"][0]["status"] == "SUSPENDED"


def test_only_admin_can_manage_faculty_assessment_permissions(live):
    """FACULTY (targeting themselves or another Faculty member),
    STUDENT, INDUSTRY, and INSTITUTION must all be denied by the admin
    API -- and, independently, by the underlying RPCs directly (bypassing
    FastAPI's require_admin() entirely), since both admin_* functions are
    granted to `authenticated` and reachable via plain PostgREST."""
    _admin_id, admin_email = live.create_user("admin_deny", "ADMIN")
    faculty_a_id, faculty_a_email = live.create_user("faculty_deny_a", "FACULTY")
    faculty_b_id, faculty_b_email = live.create_user("faculty_deny_b", "FACULTY")
    _student_id, student_email = live.create_user("student_deny", "STUDENT")
    _industry_id, industry_email = live.create_user("industry_deny", "INDUSTRY")
    _institution_id, institution_email = live.create_user("institution_deny", "INSTITUTION")
    admin_token = live.token_for(admin_email)

    non_admin_emails = {
        "faculty_self": faculty_a_email,
        "faculty_cross": faculty_b_email,
        "student": student_email,
        "industry": industry_email,
        "institution": institution_email,
    }
    targets = {
        "faculty_self": faculty_a_id,
        "faculty_cross": faculty_a_id,
        "student": faculty_a_id,
        "industry": faculty_a_id,
        "institution": faculty_a_id,
    }

    for case, email in non_admin_emails.items():
        token = live.token_for(email)
        target_id = targets[case]

        api_grant = live.api(
            token,
            "POST",
            f"/admin/faculty/{target_id}/assessment-permissions",
            json={"capability": "assessment_lead"},
        )
        assert api_grant.status_code == 403, f"{case}: API grant should be denied"

        rpc_grant = _rest_rpc(
            live,
            "admin_grant_assessment_capability",
            token,
            {
                "target_faculty_id": target_id,
                "requested_capability": "assessment_lead",
                "capability_expires_at": None,
            },
        )
        assert rpc_grant.status_code >= 400, f"{case}: direct RPC grant should be denied"

    unaffected = (
        live.admin.table("faculty_assessment_permissions")
        .select("id")
        .in_("faculty_id", [faculty_a_id, faculty_b_id])
        .eq("capability", "assessment_lead")
        .execute()
        .data
    )
    assert unaffected == []

    # An ADMIN acting on a non-FACULTY target is rejected too -- capabilities
    # are Faculty-only regardless of who is asking.
    _student2_id, _student2_email = live.create_user("student_target", "STUDENT")
    admin_on_student = live.api(
        admin_token,
        "POST",
        f"/admin/faculty/{_student2_id}/assessment-permissions",
        json={"capability": "assessment_lead"},
    )
    assert admin_on_student.status_code == 403
