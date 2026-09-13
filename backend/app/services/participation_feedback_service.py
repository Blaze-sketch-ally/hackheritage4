"""Business logic for Participation Feedback and Skill Recommendations
(`participation_feedback` / `participation_skill_recommendations`,
database/migrations/064_participation_submissions_feedback.sql).

Skill recommendations are ADVISORY ONLY: nothing here reads or writes
student_skills. See that migration's header for the full reasoning.
"""

from supabase import Client

_FEEDBACK_SELECT = "id, workspace_id, industry_id, feedback_type, title, feedback, created_at"
_RECOMMENDATION_SELECT = (
    "id, workspace_id, skill_id, recommended_level, reason, priority, created_by, created_at, "
    "skill:skills(name)"
)


def list_feedback(client: Client, workspace_id: str) -> list[dict]:
    return (
        client.table("participation_feedback")
        .select(_FEEDBACK_SELECT)
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


def create_feedback(client: Client, workspace_id: str, data: dict) -> dict:
    payload = {
        "workspace_id": workspace_id,
        "feedback_type": data["feedback_type"],
        "title": data.get("title"),
        "feedback": data["feedback"],
    }
    response = client.table("participation_feedback").insert(payload).execute()
    return response.data[0]


def _shape_recommendation(row: dict) -> dict:
    skill = row.pop("skill", None)
    row["skill_name"] = skill.get("name") if skill else None
    return row


def list_recommendations(client: Client, workspace_id: str) -> list[dict]:
    rows = (
        client.table("participation_skill_recommendations")
        .select(_RECOMMENDATION_SELECT)
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return [_shape_recommendation(r) for r in rows]


def create_recommendation(client: Client, workspace_id: str, data: dict) -> dict:
    payload = {
        "workspace_id": workspace_id,
        "skill_id": data["skill_id"],
        "recommended_level": data.get("recommended_level"),
        "reason": data["reason"],
        "priority": data.get("priority", "MEDIUM"),
    }
    response = client.table("participation_skill_recommendations").insert(payload).execute()
    new_id = response.data[0]["id"]
    row = (
        client.table("participation_skill_recommendations")
        .select(_RECOMMENDATION_SELECT)
        .eq("id", new_id)
        .maybe_single()
        .execute()
        .data
    )
    return _shape_recommendation(dict(row))
