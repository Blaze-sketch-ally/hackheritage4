"""Shared fixtures for the live-integration suite (see README.md in this
directory). Every fixture here talks to the REAL Supabase project
configured in backend/.env and the REAL FastAPI server -- there is no
mocking anywhere in this file, by design.

Nothing here runs as part of a plain `pytest -q` / CI run: the
`live_env` fixture is autouse and skips the entire test at collection
time unless RUN_LIVE_INTEGRATION_TESTS=1 is set, in addition to real
Supabase credentials being present.
"""

import os
import time
import uuid

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

API_BASE = os.environ.get("LIVE_TEST_API_BASE", "http://127.0.0.1:8000/api/v1")


@pytest.fixture(autouse=True)
def live_env():
    """Skips every test in this directory unless explicitly opted in.
    Requires BOTH the opt-in flag and real credentials -- either alone is
    not enough, so a stray SUPABASE_* value in the environment can never
    silently turn this suite on."""
    if os.environ.get("RUN_LIVE_INTEGRATION_TESTS") != "1":
        pytest.skip("Live integration tests are opt-in -- set RUN_LIVE_INTEGRATION_TESTS=1")
    missing = [
        name
        for name in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        pytest.skip(f"Live integration tests require {', '.join(missing)} in the environment")
    try:
        httpx.get(f"{API_BASE.rsplit('/api', 1)[0]}/health", timeout=3)
    except httpx.HTTPError:
        pytest.skip(f"No FastAPI server reachable at {API_BASE} -- start the backend first")


@pytest.fixture
def run_id():
    """A unique identifier for this specific test's fixtures -- never
    reuse across tests, never clean up by a bare prefix. See README.md."""
    return f"{uuid.uuid4().hex[:10]}_{int(time.time())}"


class LiveFixtures:
    """Creates and tracks disposable QA data for one test, and cleans up
    EXACTLY what it created -- nothing matched by a broad LIKE pattern.
    """

    def __init__(self, run_id: str):
        from supabase import create_client

        self.run_id = run_id
        self.password = f"QaLive!{run_id}"
        self.admin = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        )
        self._anon_url = os.environ["SUPABASE_URL"]
        self._anon_key = os.environ["SUPABASE_ANON_KEY"]
        self.user_ids: list[str] = []
        self.assessment_ids: list[str] = []
        self.career_role_ids: list[str] = []

    def create_user(self, local: str, role: str) -> tuple[str, str]:
        email = f"__qa_{self.run_id}_{local}@example.com"
        resp = self.admin.auth.admin.create_user(
            {"email": email, "password": self.password, "email_confirm": True}
        )
        user_id = resp.user.id
        self.user_ids.append(user_id)
        self.admin.table("profiles").update(
            {"role": role, "username": f"qa{local}{self.run_id}"[:30], "full_name": f"QA {local}"}
        ).eq("id", user_id).execute()
        return user_id, email

    def token_for(self, email: str) -> str:
        from supabase import create_client

        anon = create_client(self._anon_url, self._anon_key)
        resp = anon.auth.sign_in_with_password({"email": email, "password": self.password})
        return resp.session.access_token

    def create_assessment(self, title_suffix: str = "", skill_id: str | None = None) -> str:
        """skill_id: pass an explicit one when a test needs to know which
        skill this assessment counts toward (e.g. Phase 1L's skill-gap
        tests, which build a matching career_role_skill_requirements row
        for the same skill_id) -- defaults to picking the first active
        catalog skill, unchanged from before Phase 1L, for callers that
        don't care which skill is used."""
        if skill_id is None:
            skill_id = (
                self.admin.table("skills")
                .select("id")
                .eq("is_active", True)
                .limit(1)
                .execute()
                .data[0]["id"]
            )
        row = self.admin.table("assessments").insert(
            {
                "skill_id": skill_id,
                "title": f"__QA_{self.run_id}{title_suffix}",
                "difficulty": "Beginner",
                "is_active": True,
            }
        ).execute().data[0]
        self.assessment_ids.append(row["id"])
        return row["id"]

    def create_career_role_with_requirement(
        self, skill_id: str, required_level: float = 60.0, weight: float = 1.0, title_suffix: str = ""
    ) -> str:
        """Phase 1L: career_roles/career_role_skill_requirements are
        service_role-writable-only reference data (see
        022_career_roles_skill_gap.sql) -- this uses the same admin
        (service-role) client every other fixture method here already
        uses, tags the role's title with this run's unique id (never a
        bare '__QA_' prefix -- see this file's own module docstring), and
        is cleaned up by exact id in cleanup() below, same as every other
        fixture this class creates."""
        role = self.admin.table("career_roles").insert(
            {"title": f"__QA_{self.run_id}{title_suffix}", "category": "Test"}
        ).execute().data[0]
        self.career_role_ids.append(role["id"])
        self.admin.table("career_role_skill_requirements").insert(
            {
                "career_role_id": role["id"],
                "skill_id": skill_id,
                "required_level": required_level,
                "weight": weight,
            }
        ).execute()
        return role["id"]

    def api(self, token: str, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        return httpx.request(method, f"{API_BASE}{path}", headers=headers, timeout=15, **kwargs)

    def mcq_payload(self, assessment_id: str, text: str) -> dict:
        opt1, opt2 = str(uuid.uuid4()), str(uuid.uuid4())
        return {
            "assessment_id": assessment_id,
            "question_text": f"__QA_{self.run_id} {text}",
            "question_type": "MCQ",
            "scoring_method": "OBJECTIVE",
            "difficulty": "Beginner",
            "points": "1.00",
            "display_order": 0,
            "options": [
                {"id": opt1, "option_text": "A", "display_order": 0},
                {"id": opt2, "option_text": "B", "display_order": 1},
            ],
            "answer_key": {"correct_option_ids": [opt2]},
        }

    def cleanup(self) -> None:
        """FK-safe order: attempts before assessments (assessment_attempts
        -> assessments is ON DELETE RESTRICT, not CASCADE). Deletes only
        the exact assessment/user ids this instance created. Best-effort:
        a failure to delete one already-disposable QA user must not mask
        the test's own assertion failures, so errors are reported, not
        raised, but never silently swallowed either.

        Phase 1M: applications.opportunity_id is ON DELETE RESTRICT (a
        historical record must never silently vanish just because its
        opportunity's owner account is deleted), so an industry user
        created by this fixture can't rely on cascade alone if a QA
        student's application to their opportunity still exists --
        deleting the industry user first would leave the opportunity
        (and its requirements) stranded. Delete both explicitly, scoped
        to exactly the user ids this instance created (never a bare
        '__QA_' LIKE match), before deleting any user."""
        if self.user_ids:
            self.admin.table("applications").delete().in_("student_id", self.user_ids).execute()
            owned_opportunities = (
                self.admin.table("opportunities")
                .select("id")
                .in_("industry_id", self.user_ids)
                .execute()
                .data
            )
            owned_opportunity_ids = [row["id"] for row in owned_opportunities]
            if owned_opportunity_ids:
                self.admin.table("applications").delete().in_(
                    "opportunity_id", owned_opportunity_ids
                ).execute()
                self.admin.table("opportunity_skill_requirements").delete().in_(
                    "opportunity_id", owned_opportunity_ids
                ).execute()
                self.admin.table("opportunities").delete().in_("id", owned_opportunity_ids).execute()
        for assessment_id in self.assessment_ids:
            self.admin.table("assessment_attempts").delete().eq("assessment_id", assessment_id).execute()
        for assessment_id in self.assessment_ids:
            self.admin.table("assessments").delete().eq("id", assessment_id).execute()
        # career_role_skill_requirements.career_role_id is ON DELETE CASCADE
        # (022_career_roles_skill_gap.sql) -- deleting the role alone would
        # already remove its requirements, but both are deleted explicitly
        # by exact id anyway, matching every other fixture's cleanup style
        # in this file rather than relying on cascade behavior silently.
        for career_role_id in self.career_role_ids:
            self.admin.table("career_role_skill_requirements").delete().eq(
                "career_role_id", career_role_id
            ).execute()
        for career_role_id in self.career_role_ids:
            self.admin.table("career_roles").delete().eq("id", career_role_id).execute()
        for user_id in self.user_ids:
            try:
                self.admin.auth.admin.delete_user(user_id)
            except Exception as exc:  # noqa: BLE001 -- best-effort cleanup, must not raise
                print(f"tests/integration cleanup: could not delete QA user {user_id}: {exc}")


@pytest.fixture
def live(run_id):
    fixtures = LiveFixtures(run_id)
    yield fixtures
    fixtures.cleanup()
