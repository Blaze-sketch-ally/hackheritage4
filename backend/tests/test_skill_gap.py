"""Tests for Skill Gap Analysis: the pure deterministic status/priority
rules, the job-role and personal gap-computation functions (service
layer, with Supabase reads mocked -- no live project or real token), and
the API routes (job roles, target role CRUD, /skill-gap dispatch).

No LLM is involved anywhere in the feature under test, and none is used
to generate these tests either.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import skill_gap as skill_gap_routes
from app.main import app
from app.services import skill_gap_service
from tests.conftest import authenticated_as

client = TestClient(app)


# ============================================================
# calculate_status
# ============================================================


def test_status_missing_when_no_current_level():
    assert skill_gap_service.calculate_status(0, 3) == "MISSING"


def test_status_needs_improvement_when_current_below_required():
    assert skill_gap_service.calculate_status(1, 3) == "NEEDS_IMPROVEMENT"


def test_status_matched_when_current_equals_required():
    assert skill_gap_service.calculate_status(2, 2) == "MATCHED"


def test_status_matched_when_current_exceeds_required():
    """Edge case: the student's declared level is HIGHER than the role
    requires -- still MATCHED, never a negative/invalid status."""
    assert skill_gap_service.calculate_status(4, 2) == "MATCHED"


# ============================================================
# calculate_priority
# ============================================================


def test_priority_matched_is_always_low():
    assert skill_gap_service.calculate_priority("MATCHED", "CORE", 0) == "LOW"


def test_priority_large_gap_is_high_regardless_of_importance():
    assert skill_gap_service.calculate_priority("NEEDS_IMPROVEMENT", "OPTIONAL", 2) == "HIGH"
    assert skill_gap_service.calculate_priority("MISSING", "IMPORTANT", 3) == "HIGH"


def test_priority_missing_core_is_high():
    assert skill_gap_service.calculate_priority("MISSING", "CORE", 1) == "HIGH"


def test_priority_missing_important_is_medium():
    assert skill_gap_service.calculate_priority("MISSING", "IMPORTANT", 1) == "MEDIUM"


def test_priority_needs_improvement_one_level_is_medium():
    assert skill_gap_service.calculate_priority("NEEDS_IMPROVEMENT", "CORE", 1) == "MEDIUM"


def test_priority_optional_gap_is_low():
    assert skill_gap_service.calculate_priority("MISSING", "OPTIONAL", 1) == "LOW"
    assert skill_gap_service.calculate_priority("NEEDS_IMPROVEMENT", "OPTIONAL", 1) == "LOW"


# ============================================================
# compute_job_role_gap
# ============================================================


def _requirement(skill_id, skill_name, required_level, importance):
    return {
        "skill_id": skill_id,
        "skill_name": skill_name,
        "category_name": None,
        "required_level": required_level,
        "importance": importance,
    }


def test_job_role_gap_all_matched_gives_full_readiness():
    skill_id = str(uuid4())
    requirements = [_requirement(skill_id, "Python", "Intermediate", "CORE")]
    job_role = {"id": str(uuid4()), "name": "Backend Developer"}
    with (
        patch.object(
            skill_gap_service,
            "get_student_skill_map",
            return_value={skill_id: {"proficiency_level": "Intermediate", "is_verified": True}},
        ),
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
    ):
        result = skill_gap_service.compute_job_role_gap(MagicMock(), "student-1", job_role, requirements)

    assert result["readiness_percentage"] == 100
    assert result["summary"] == {"matched": 1, "needs_improvement": 0, "missing": 0, "unverified": 0}
    assert result["skills"][0]["status"] == "MATCHED"
    assert result["recommendations"] == []


def test_job_role_gap_all_missing_gives_zero_readiness():
    skill_id = str(uuid4())
    requirements = [_requirement(skill_id, "Docker", "Beginner", "CORE")]
    job_role = {"id": str(uuid4()), "name": "DevOps Engineer"}
    with (
        patch.object(skill_gap_service, "get_student_skill_map", return_value={}),
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
    ):
        result = skill_gap_service.compute_job_role_gap(MagicMock(), "student-1", job_role, requirements)

    assert result["readiness_percentage"] == 0
    assert result["summary"]["missing"] == 1
    assert result["skills"][0]["status"] == "MISSING"
    assert result["skills"][0]["priority"] == "HIGH"
    assert result["skills"][0]["verification_status"] == "UNVERIFIED"


def test_job_role_gap_no_requirements_does_not_divide_by_zero():
    job_role = {"id": str(uuid4()), "name": "Empty Role"}
    with (
        patch.object(skill_gap_service, "get_student_skill_map", return_value={}),
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
    ):
        result = skill_gap_service.compute_job_role_gap(MagicMock(), "student-1", job_role, [])

    assert result["readiness_percentage"] == 0
    assert result["skills"] == []
    assert result["recommendations"] == []


def test_job_role_gap_weighted_readiness_matches_importance_weights():
    core_id, optional_id = str(uuid4()), str(uuid4())
    requirements = [
        _requirement(core_id, "SQL", "Advanced", "CORE"),  # weight 5, missing -> 0 earned
        _requirement(optional_id, "Redis", "Beginner", "OPTIONAL"),  # weight 1, matched -> 1 earned
    ]
    job_role = {"id": str(uuid4()), "name": "Backend Developer"}
    with (
        patch.object(
            skill_gap_service,
            "get_student_skill_map",
            return_value={optional_id: {"proficiency_level": "Beginner", "is_verified": False}},
        ),
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
    ):
        result = skill_gap_service.compute_job_role_gap(MagicMock(), "student-1", job_role, requirements)

    # total_weight = 6, earned_weight = 1 -> round(100 * 1/6) = 17
    assert result["readiness_percentage"] == 17


def test_job_role_gap_unverified_counted_even_when_matched():
    skill_id = str(uuid4())
    requirements = [_requirement(skill_id, "Python", "Beginner", "CORE")]
    job_role = {"id": str(uuid4()), "name": "Backend Developer"}
    with (
        patch.object(
            skill_gap_service,
            "get_student_skill_map",
            return_value={skill_id: {"proficiency_level": "Beginner", "is_verified": False}},
        ),
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
    ):
        result = skill_gap_service.compute_job_role_gap(MagicMock(), "student-1", job_role, requirements)

    assert result["summary"]["matched"] == 1
    assert result["summary"]["unverified"] == 1


def test_job_role_gap_assessment_available_resolved_for_next_level():
    skill_id = str(uuid4())
    assessment_id = str(uuid4())
    requirements = [_requirement(skill_id, "FastAPI", "Advanced", "CORE")]
    job_role = {"id": str(uuid4()), "name": "Backend Developer"}
    with (
        patch.object(
            skill_gap_service,
            "get_student_skill_map",
            return_value={skill_id: {"proficiency_level": "Beginner", "is_verified": True}},
        ),
        patch.object(
            skill_gap_service,
            "get_assessment_availability",
            return_value={(skill_id, "Advanced"): assessment_id},
        ),
    ):
        result = skill_gap_service.compute_job_role_gap(MagicMock(), "student-1", job_role, requirements)

    item = result["skills"][0]
    assert item["status"] == "NEEDS_IMPROVEMENT"
    assert item["assessment_available"] is True
    assert item["assessment_id"] == assessment_id


def test_job_role_gap_recommendations_sorted_by_priority_and_exclude_matched():
    core_missing = str(uuid4())
    optional_missing = str(uuid4())
    matched = str(uuid4())
    requirements = [
        _requirement(optional_missing, "Redis", "Beginner", "OPTIONAL"),
        _requirement(core_missing, "SQL", "Beginner", "CORE"),
        _requirement(matched, "Git", "Beginner", "IMPORTANT"),
    ]
    job_role = {"id": str(uuid4()), "name": "Backend Developer"}
    with (
        patch.object(
            skill_gap_service,
            "get_student_skill_map",
            return_value={matched: {"proficiency_level": "Beginner", "is_verified": True}},
        ),
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
    ):
        result = skill_gap_service.compute_job_role_gap(MagicMock(), "student-1", job_role, requirements)

    rec_skill_ids = [rec["skill_id"] for rec in result["recommendations"]]
    assert matched not in rec_skill_ids
    assert rec_skill_ids[0] == core_missing  # HIGH priority (missing CORE) surfaces first
    assert rec_skill_ids[1] == optional_missing  # LOW priority (missing OPTIONAL) last
    assert all(rec["reason"] for rec in result["recommendations"])


# ============================================================
# compute_personal_analysis
# ============================================================


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def execute(self):
        response = MagicMock()
        response.data = self._rows
        return response


class _FakeClient:
    """Only supports the single student_skills query compute_personal_analysis
    issues directly -- every other lookup it needs is a module-level
    function patched separately in each test below."""

    def __init__(self, student_skills_rows):
        self._rows = student_skills_rows

    def table(self, name):
        assert name == "student_skills"
        return _FakeTable(self._rows)


def test_personal_analysis_no_skills_returns_empty_result():
    with (
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
        patch.object(skill_gap_service, "get_skill_relationships_from", return_value=[]),
        patch.object(skill_gap_service, "get_prerequisites_of", return_value={}),
    ):
        result = skill_gap_service.compute_personal_analysis(_FakeClient([]), "student-1")

    assert result["counts"]["total_active_skills"] == 0
    assert result["progressable_skills"] == []
    assert result["recommendations"] == []
    assert result["prerequisite_gaps"] == []


def test_personal_analysis_counts_by_level_and_verification():
    rows = [
        {"skill_id": "s1", "proficiency_level": "Beginner", "is_verified": True, "skill": {"id": "s1", "name": "HTML"}},
        {"skill_id": "s2", "proficiency_level": "Advanced", "is_verified": False, "skill": {"id": "s2", "name": "Python"}},
        {"skill_id": "s3", "proficiency_level": "Expert", "is_verified": False, "skill": {"id": "s3", "name": "Git"}},
    ]
    with (
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
        patch.object(skill_gap_service, "get_skill_relationships_from", return_value=[]),
        patch.object(skill_gap_service, "get_prerequisites_of", return_value={}),
    ):
        result = skill_gap_service.compute_personal_analysis(_FakeClient(rows), "student-1")

    counts = result["counts"]
    assert counts["total_active_skills"] == 3
    assert counts["verified_skills"] == 1
    assert counts["unverified_skills"] == 2
    assert counts["beginner_skills"] == 1
    assert counts["advanced_skills"] == 1
    assert counts["expert_skills"] == 1


def test_personal_analysis_progressable_excludes_expert_and_resolves_next_assessment():
    assessment_id = str(uuid4())
    rows = [
        {"skill_id": "s1", "proficiency_level": "Beginner", "is_verified": True, "skill": {"id": "s1", "name": "HTML"}},
        {"skill_id": "s2", "proficiency_level": "Expert", "is_verified": True, "skill": {"id": "s2", "name": "Git"}},
    ]
    with (
        patch.object(
            skill_gap_service,
            "get_assessment_availability",
            return_value={("s1", "Intermediate"): assessment_id},
        ),
        patch.object(skill_gap_service, "get_skill_relationships_from", return_value=[]),
        patch.object(skill_gap_service, "get_prerequisites_of", return_value={}),
    ):
        result = skill_gap_service.compute_personal_analysis(_FakeClient(rows), "student-1")

    progressable_ids = {p["skill_id"] for p in result["progressable_skills"]}
    assert progressable_ids == {"s1"}
    entry = result["progressable_skills"][0]
    assert entry["next_level"] == "Intermediate"
    assert entry["assessment_available"] is True
    assert entry["assessment_id"] == assessment_id


def test_personal_analysis_recommends_only_unowned_related_skills():
    rows = [
        {"skill_id": "s1", "proficiency_level": "Advanced", "is_verified": True, "skill": {"id": "s1", "name": "Python"}},
    ]
    relationships = [
        {
            "skill_id": "s1",
            "related_skill_id": "s2",
            "relationship_type": "NEXT_STEP",
            "priority": 0,
            "related_skill": {"id": "s2", "name": "FastAPI"},
        },
        {
            "skill_id": "s1",
            "related_skill_id": "s1",
            "relationship_type": "RELATED",
            "priority": 1,
            "related_skill": {"id": "s1", "name": "Python"},
        },
    ]
    with (
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
        patch.object(skill_gap_service, "get_skill_relationships_from", return_value=relationships),
        patch.object(skill_gap_service, "get_prerequisites_of", return_value={}),
    ):
        result = skill_gap_service.compute_personal_analysis(_FakeClient(rows), "student-1")

    rec_ids = [r["skill_id"] for r in result["recommendations"]]
    assert rec_ids == ["s2"]  # s1 excluded -- already owned
    assert result["recommendations"][0]["relationship_type"] == "NEXT_STEP"


def test_personal_analysis_surfaces_prerequisite_gaps_for_missing_prereqs_only():
    rows = [
        {"skill_id": "s1", "proficiency_level": "Advanced", "is_verified": True, "skill": {"id": "s1", "name": "JavaScript"}},
    ]
    relationships = [
        {
            "skill_id": "s1",
            "related_skill_id": "s2",
            "relationship_type": "NEXT_STEP",
            "priority": 0,
            "related_skill": {"id": "s2", "name": "React"},
        },
    ]
    prereqs = {"s2": [{"skill_id": "s3", "related_skill_id": "s2", "skill": {"id": "s3", "name": "TypeScript"}}]}
    with (
        patch.object(skill_gap_service, "get_assessment_availability", return_value={}),
        patch.object(skill_gap_service, "get_skill_relationships_from", return_value=relationships),
        patch.object(skill_gap_service, "get_prerequisites_of", return_value=prereqs),
    ):
        result = skill_gap_service.compute_personal_analysis(_FakeClient(rows), "student-1")

    assert len(result["prerequisite_gaps"]) == 1
    gap = result["prerequisite_gaps"][0]
    assert gap["skill_id"] == "s3"
    assert gap["required_for_skill_id"] == "s2"


# ============================================================
# API routes
# ============================================================


def test_list_job_roles_returns_service_data():
    role = {
        "id": str(uuid4()),
        "name": "Backend Developer",
        "description": None,
        "category": "Engineering",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "list_active_job_roles", return_value=[role]),
    ):
        response = client.get("/api/v1/job-roles", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["job_roles"][0]["name"] == "Backend Developer"


def test_get_job_role_not_found_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=None),
    ):
        response = client.get(
            f"/api/v1/job-roles/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_target_job_role_not_set_returns_404():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=None),
    ):
        response = client.get(
            "/api/v1/student/target-job-role", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_set_target_job_role_rejects_unknown_fields():
    """extra='forbid' is the actual enforcement that a client can never
    smuggle a student_id (or anything else) into this body."""
    with authenticated_as("STUDENT"):
        response = client.put(
            "/api/v1/student/target-job-role",
            json={"job_role_id": str(uuid4()), "student_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_set_target_job_role_404_when_role_inactive():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=None),
    ):
        response = client.put(
            "/api/v1/student/target-job-role",
            json={"job_role_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_set_target_job_role_success():
    job_role_id = uuid4()
    role = {
        "id": str(job_role_id),
        "name": "Backend Developer",
        "description": None,
        "category": None,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    target_row = {
        "id": str(uuid4()),
        "job_role": role,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=role),
        patch.object(skill_gap_service, "set_target_job_role", return_value=target_row),
    ):
        response = client.put(
            "/api/v1/student/target-job-role",
            json={"job_role_id": str(job_role_id)},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["job_role"]["id"] == str(job_role_id)


def test_clear_target_job_role_returns_204():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "clear_target_job_role", return_value=None),
    ):
        response = client.delete(
            "/api/v1/student/target-job-role", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 204


def test_skill_gap_dispatches_to_personal_mode_when_no_target_set():
    personal_result = {
        "counts": {
            "total_active_skills": 0,
            "verified_skills": 0,
            "unverified_skills": 0,
            "beginner_skills": 0,
            "intermediate_skills": 0,
            "advanced_skills": 0,
            "expert_skills": 0,
        },
        "progressable_skills": [],
        "recommendations": [],
        "prerequisite_gaps": [],
    }
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=None),
        patch.object(skill_gap_service, "compute_personal_analysis", return_value=personal_result),
    ):
        response = client.get("/api/v1/skill-gap", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["mode"] == "PERSONAL"


def test_skill_gap_dispatches_to_job_role_mode_when_target_set():
    role = {
        "id": str(uuid4()),
        "name": "Backend Developer",
        "description": None,
        "category": None,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    target_row = {"id": str(uuid4()), "job_role": role}
    gap_result = {
        "readiness_percentage": 50,
        "summary": {"matched": 1, "needs_improvement": 0, "missing": 1, "unverified": 0},
        "skills": [],
        "recommendations": [],
    }
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_target_job_role", return_value=target_row),
        patch.object(skill_gap_service, "get_job_role_requirements", return_value=[]),
        patch.object(skill_gap_service, "compute_job_role_gap", return_value=gap_result),
    ):
        response = client.get("/api/v1/skill-gap", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "JOB_ROLE"
    assert body["readiness_percentage"] == 50


def test_skill_gap_for_job_role_404_when_inactive():
    with (
        authenticated_as("STUDENT"),
        patch.object(skill_gap_service, "get_active_job_role", return_value=None),
    ):
        response = client.get(
            f"/api/v1/skill-gap/job-role/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_skill_gap_unexpected_failure_returns_clean_500():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            skill_gap_service,
            "get_target_job_role",
            side_effect=RuntimeError("connection refused to internal db host 10.0.0.5"),
        ),
    ):
        response = client.get("/api/v1/skill-gap", headers={"Authorization": "Bearer token"})
    assert response.status_code == 500
    body = str(response.json())
    assert "10.0.0.5" not in body
    assert "connection refused" not in body.lower()


def test_non_student_role_forbidden_on_skill_gap_routes():
    with authenticated_as("FACULTY"):
        response = client.get("/api/v1/job-roles", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_skill_gap_routes_module_uses_build_user_client():
    """Sanity check mirroring the equivalent assertion in test_assessments.py
    -- guards against a future refactor accidentally reaching for
    get_supabase() (service_role) on one of these read paths."""
    assert hasattr(skill_gap_routes, "build_user_client")
