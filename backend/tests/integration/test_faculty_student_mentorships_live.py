"""Live RLS/RPC coverage for Phase F4.2: faculty_mentor_permissions
(039) and faculty_student_mentorships (040), including the downstream
mentor-visibility policies and the mentor-vs-evaluator boundary. Exercises
the REAL Supabase project + REAL FastAPI server -- no mocking.
"""

import httpx


def _rest_request(live, method: str, table: str, token: str, **kwargs) -> httpx.Response:
    headers = {"apikey": live._anon_key, "Authorization": f"Bearer {token}"}
    return httpx.request(method, f"{live._anon_url}/rest/v1/{table}", headers=headers, **kwargs)


def _grant_mentor_capability(live, faculty_id: str) -> None:
    live.admin.table("faculty_mentor_permissions").insert(
        {"faculty_id": faculty_id, "status": "GRANTED"}
    ).execute()


def test_full_mentorship_lifecycle_and_downstream_visibility(live):
    faculty_id, faculty_email = live.create_user("faculty", "FACULTY")
    student_id, student_email = live.create_user("student", "STUDENT")
    _grant_mentor_capability(live, faculty_id)

    faculty_token = live.token_for(faculty_email)
    student_token = live.token_for(student_email)

    # Faculty requests the student.
    create = live.api(
        faculty_token, "POST", "/faculty/mentorships", json={"target_id": student_id, "focus_area": "Careers"}
    )
    assert create.status_code == 201
    mentorship_id = create.json()["id"]
    assert create.json()["status"] == "REQUESTED"

    # The requesting Faculty cannot accept their own request.
    self_accept = live.api(faculty_token, "PATCH", f"/faculty/mentorships/{mentorship_id}/status", json={"status": "ACCEPTED"})
    assert self_accept.status_code == 403

    # Before activation, Faculty cannot see student data at all.
    pre_active = live.api(faculty_token, "GET", f"/faculty/mentorships/{mentorship_id}/student")
    assert pre_active.status_code == 409

    # Student accepts, then activates.
    accept = live.api(student_token, "PATCH", f"/student/mentorships/{mentorship_id}/status", json={"status": "ACCEPTED"})
    assert accept.status_code == 200
    assert accept.json()["status"] == "ACCEPTED"

    activate = live.api(faculty_token, "PATCH", f"/faculty/mentorships/{mentorship_id}/status", json={"status": "ACTIVE"})
    assert activate.status_code == 200
    assert activate.json()["status"] == "ACTIVE"

    # Now the Faculty mentor can read the authorized student data bundle.
    bundle = live.api(faculty_token, "GET", f"/faculty/mentorships/{mentorship_id}/student")
    assert bundle.status_code == 200
    body = bundle.json()
    assert body["student_id"] == student_id
    assert "skills" in body and "assessment_attempts" in body and "projects" in body

    # Direct REST-level RLS proof (not just the FastAPI layer): the
    # mentor's own token can SELECT student_profiles for this exact
    # student row now that the mentorship is ACTIVE.
    direct_profile = _rest_request(
        live, "GET", "student_profiles", faculty_token, params={"id": f"eq.{student_id}", "select": "id"}
    )
    assert direct_profile.status_code == 200
    assert len(direct_profile.json()) == 1

    # But the SAME mentor token can never read assessment_answers or the
    # answer key for this student -- RLS grants nothing there regardless
    # of the ACTIVE mentorship. PostgREST returns 200 with an empty
    # result set (RLS filters rows, it does not error).
    direct_answers = _rest_request(
        live, "GET", "assessment_answers", faculty_token, params={"select": "id"}
    )
    assert direct_answers.status_code == 200
    assert direct_answers.json() == []

    # Complete the mentorship; visibility is revoked immediately.
    complete = live.api(faculty_token, "PATCH", f"/faculty/mentorships/{mentorship_id}/status", json={"status": "COMPLETED"})
    assert complete.status_code == 200
    after_complete = live.api(faculty_token, "GET", f"/faculty/mentorships/{mentorship_id}/student")
    assert after_complete.status_code == 409

    # The mentorship record itself remains visible to both parties as
    # history.
    still_visible = live.api(faculty_token, "GET", f"/faculty/mentorships/{mentorship_id}")
    assert still_visible.status_code == 200
    assert still_visible.json()["status"] == "COMPLETED"


def test_faculty_without_capability_is_denied(live):
    _faculty_id, faculty_email = live.create_user("faculty", "FACULTY")
    student_id, _student_email = live.create_user("student", "STUDENT")
    faculty_token = live.token_for(faculty_email)

    response = live.api(faculty_token, "POST", "/faculty/mentorships", json={"target_id": student_id})
    assert response.status_code == 403


def test_cross_faculty_isolation(live):
    faculty_a_id, faculty_a_email = live.create_user("facultya", "FACULTY")
    _faculty_b_id, faculty_b_email = live.create_user("facultyb", "FACULTY")
    student_id, _student_email = live.create_user("student", "STUDENT")
    _grant_mentor_capability(live, faculty_a_id)

    faculty_a_token = live.token_for(faculty_a_email)
    faculty_b_token = live.token_for(faculty_b_email)

    create = live.api(faculty_a_token, "POST", "/faculty/mentorships", json={"target_id": student_id})
    assert create.status_code == 201
    mentorship_id = create.json()["id"]

    # Faculty B (not a party to this mentorship) cannot see or act on it.
    get_response = live.api(faculty_b_token, "GET", f"/faculty/mentorships/{mentorship_id}")
    assert get_response.status_code == 404

    status_response = live.api(faculty_b_token, "PATCH", f"/faculty/mentorships/{mentorship_id}/status", json={"status": "DECLINED"})
    assert status_response.status_code in (403, 404)


def test_duplicate_mentorship_pair_is_rejected(live):
    faculty_id, faculty_email = live.create_user("faculty", "FACULTY")
    student_id, _student_email = live.create_user("student", "STUDENT")
    _grant_mentor_capability(live, faculty_id)
    faculty_token = live.token_for(faculty_email)

    first = live.api(faculty_token, "POST", "/faculty/mentorships", json={"target_id": student_id})
    assert first.status_code == 201

    second = live.api(faculty_token, "POST", "/faculty/mentorships", json={"target_id": student_id})
    assert second.status_code == 409


def test_suspended_capability_blocks_lifecycle_actions(live):
    faculty_id, faculty_email = live.create_user("faculty", "FACULTY")
    student_id, student_email = live.create_user("student", "STUDENT")
    _grant_mentor_capability(live, faculty_id)
    faculty_token = live.token_for(faculty_email)
    student_token = live.token_for(student_email)

    create = live.api(faculty_token, "POST", "/faculty/mentorships", json={"target_id": student_id})
    mentorship_id = create.json()["id"]

    accept = live.api(student_token, "PATCH", f"/student/mentorships/{mentorship_id}/status", json={"status": "ACCEPTED"})
    assert accept.status_code == 200

    live.admin.table("faculty_mentor_permissions").update({"status": "SUSPENDED"}).eq("faculty_id", faculty_id).execute()

    activate = live.api(faculty_token, "PATCH", f"/faculty/mentorships/{mentorship_id}/status", json={"status": "ACTIVE"})
    assert activate.status_code == 403


def test_industry_and_institution_cannot_access_mentorships(live):
    faculty_id, faculty_email = live.create_user("faculty", "FACULTY")
    student_id, _student_email = live.create_user("student", "STUDENT")
    _industry_id, industry_email = live.create_user("industry", "INDUSTRY")
    _institution_id, institution_email = live.create_user("institution", "INSTITUTION")
    _grant_mentor_capability(live, faculty_id)
    faculty_token = live.token_for(faculty_email)

    create = live.api(faculty_token, "POST", "/faculty/mentorships", json={"target_id": student_id})
    mentorship_id = create.json()["id"]

    for email in (industry_email, institution_email):
        token = live.token_for(email)
        assert live.api(token, "GET", "/faculty/mentorships").status_code == 403
        assert live.api(token, "GET", "/student/mentorships").status_code == 403
        assert live.api(token, "GET", f"/faculty/mentorships/{mentorship_id}").status_code == 403


def test_admin_oversight_lists_mentorships_without_gaining_student_data_access(live):
    faculty_id, faculty_email = live.create_user("faculty", "FACULTY")
    student_id, _student_email = live.create_user("student", "STUDENT")
    _admin_id, admin_email = live.create_user("admin", "ADMIN")
    _grant_mentor_capability(live, faculty_id)
    faculty_token = live.token_for(faculty_email)
    admin_token = live.token_for(admin_email)

    create = live.api(faculty_token, "POST", "/faculty/mentorships", json={"target_id": student_id})
    mentorship_id = create.json()["id"]

    listing = live.api(admin_token, "GET", "/admin/mentorships")
    assert listing.status_code == 200
    ids = [row["id"] for row in listing.json()["mentorships"]]
    assert mentorship_id in ids
    match = next(row for row in listing.json()["mentorships"] if row["id"] == mentorship_id)
    assert "focus_area" not in match

    # Admin oversight never grants the mentor-only student-data read --
    # direct REST-level proof.
    direct_profile = _rest_request(
        live, "GET", "student_profiles", admin_token, params={"id": f"eq.{student_id}", "select": "id"}
    )
    assert direct_profile.status_code == 200
    assert direct_profile.json() == []


def test_private_notes_are_never_visible_to_the_student(live):
    faculty_id, faculty_email = live.create_user("faculty", "FACULTY")
    student_id, student_email = live.create_user("student", "STUDENT")
    _grant_mentor_capability(live, faculty_id)
    faculty_token = live.token_for(faculty_email)
    student_token = live.token_for(student_email)

    create = live.api(faculty_token, "POST", "/faculty/mentorships", json={"target_id": student_id})
    mentorship_id = create.json()["id"]
    live.api(student_token, "PATCH", f"/student/mentorships/{mentorship_id}/status", json={"status": "ACCEPTED"})
    live.api(faculty_token, "PATCH", f"/faculty/mentorships/{mentorship_id}/status", json={"status": "ACTIVE"})

    note = live.api(faculty_token, "PUT", f"/faculty/mentorships/{mentorship_id}/notes", json={"note": "Doing great"})
    assert note.status_code == 200

    # No student-facing notes endpoint exists at all; independently prove
    # the underlying table denies the student's own token via direct REST.
    direct_notes = _rest_request(
        live, "GET", "faculty_mentorship_notes", student_token, params={"mentorship_id": f"eq.{mentorship_id}"}
    )
    assert direct_notes.status_code == 200
    assert direct_notes.json() == []
