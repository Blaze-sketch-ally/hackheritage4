"""Aggregate Student opportunity + learning recommendations (Phase S7).

Adopted from a collaborator branch during a cross-branch integration pass
and adapted: the source branch's `resolve_context` dispatched on its own
skill_gap_service (a persisted "target job role" the student could set).
This project has no such persisted target (see
app.services.skill_recommendation_service's own docstring), so
`resolve_context` here always resolves to one mode ("AGGREGATE") via that
module's `get_aggregate_skill_gaps` instead -- identical adaptation to
app.api.student_learning's GET /student/learning/recommended.

A thin ADAPTER/COMPOSER over three canonical, UNCHANGED-here sources. It
recomputes no gap, invents no score, and writes nothing:

  1. app.services.skill_recommendation_service
     -- the ONE source of the student's aggregate skill-gap context (see
        above). `resolve_context` below is the only place this module
        touches it.

  2. app.services.student_opportunity_service (+ app.services.match_service)
     -- `list_opportunities` for the published internship/job set;
        `compute_opportunity_match` (which is the canonical deterministic
        `match_service.compute_match` scorer) for each one's skill match.
        No new matching algorithm is written here.

  3. app.services.learning_recommendation_service
     -- `get_recommended_resources` reused verbatim: the canonical Skill
        Gap -> learning_resource_skills -> learning_resources mapping.

Dependency direction is one-way (this module imports the three services;
none imports it), so no cycle is possible.
"""

from supabase import Client

from app.services import (
    learning_recommendation_service,
    skill_recommendation_service,
    student_opportunity_service,
)

# Safe bounded page sizes -- a recommendation surface never needs more,
# and this stops a client asking for an unbounded scan. Applied per
# section (opportunities and learning each capped independently).
DEFAULT_LIMIT = 6
MAX_LIMIT = 20


def clamp_limit(limit: int | None) -> int:
    if not limit or limit < 1:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)


def _detail_path(source_type: str, opportunity_id: str) -> str:
    """Fixed-prefix Student route for an opportunity. `opportunity_id` is
    the existing `internship_<uuid>` / `job_<uuid>` string, which is what
    /student/internships/[id] and /student/jobs/[id] already expect."""
    segment = "internships" if source_type == "INTERNSHIP" else "jobs"
    return f"/student/{segment}/{opportunity_id}"


def resolve_context(client: Client, student_id: str) -> tuple[str, dict | None, dict]:
    """(mode, job_role|None, analysis) -- always ("AGGREGATE", None,
    {"recommendations": [...]}). This project has no persisted
    "target role" to dispatch on (see module docstring), so `job_role` is
    always None and `analysis["recommendations"]` is always
    skill_recommendation_service.get_aggregate_skill_gaps's own output.
    Read-only: never sets or changes anything, never touches
    student_skills."""
    gap_skills = skill_recommendation_service.get_aggregate_skill_gaps(client, student_id)
    return "AGGREGATE", None, {"recommendations": gap_skills}


def recommend_opportunities(client: Client, student_id: str, *, limit: int | None = None) -> list[dict]:
    """Published internships + jobs the student hasn't applied to, that
    share >=1 required skill with the student's own skills, ranked by the
    canonical match_service score. Deterministic and stable.

    Ranking (each a stable sort, applied in reverse order of precedence):
      1. canonical match_score            descending
      2. matched_skill_count              descending
      3. created_at                       descending (newer first)
      4. title                            ascending  (final tie-break)
    """
    cap = clamp_limit(limit)
    summaries = student_opportunity_service.list_opportunities(client, student_id)

    items: list[dict] = []
    for summary in summaries:
        if summary.get("has_applied"):
            # Don't "recommend" something the student has already applied to.
            continue

        match = student_opportunity_service.compute_opportunity_match(
            client, student_id, summary["id"]
        )
        matched = match["matched_count"]
        if matched < 1:
            # Honest: only surface a genuine skill overlap.
            continue

        industry = summary.get("industry") or {}
        source_type = summary["source_type"]
        items.append(
            {
                "type": source_type,
                "id": summary["id"],
                "title": summary["title"],
                "description": summary["description"],
                "company": industry.get("company_name"),
                "location": summary.get("location"),
                "work_mode": summary.get("work_mode"),
                "detail_path": _detail_path(source_type, summary["id"]),
                "match_score": match["score"],
                "match_band": match["recommendation"],
                "matched_skill_count": matched,
                "required_skill_count": match["required_count"],
                "relevant_skills": [s["skill_name"] for s in match["matched_skills"]],
                "_created_at": summary.get("created_at") or "",
            }
        )

    items.sort(key=lambda it: (it["title"] or "").lower())
    items.sort(key=lambda it: it["_created_at"], reverse=True)
    items.sort(key=lambda it: (-it["match_score"], -it["matched_skill_count"]))

    for it in items:
        it.pop("_created_at", None)
    return items[:cap]


def recommend_learning(
    client: Client, student_id: str, analysis: dict, *, limit: int | None = None
) -> list[dict]:
    """Canonical Skill Gap -> learning resource mapping, reused verbatim.
    `analysis` is whatever `resolve_context` returned, so the gap skills
    are exactly the canonical engine's `recommendations` list."""
    gap_skills = analysis.get("recommendations", [])
    entries = learning_recommendation_service.get_recommended_resources(
        client, student_id, gap_skills
    )
    return entries[: clamp_limit(limit)]
