"""The Skill-Gap -> Learning bridge (Phase 6D).

The canonical Skill Gap engine (``app.services.skill_gap_service``) is the
ONLY thing that decides which skills are a student's gaps /
recommendations. This module does not recompute any of that: the route
hands it the recommendation list the existing engine already produced,
and this module only maps those canonical ``skill_id`` values -- via the
``learning_resource_skills`` bridge table -- to active
``learning_resources``.

Dependency direction is strictly one-way, so no import cycle is possible:

    skill_gap_service            (untouched)
        -> [route extracts analysis["recommendations"]]
        -> learning_recommendation_service   (this module)
        -> student_learning_service.list_resources_by_ids
        -> learning_resource_skills / learning_resources

This module imports ``student_learning_service`` but never
``skill_gap_service``.

Nothing here writes anything. ``learning_resources`` and
``learning_resource_skills`` are read-only to students; ``student_skills``
and every assessment table are never touched. Learning progress stays a
separate concern -- a resource is recommended purely because the
canonical Skill Gap still lists its skill, regardless of whether the
student has already saved or completed it.
"""

from supabase import Client

from app.services import student_learning_service

# The canonical Skill Gap engine already tags every recommendation with
# one of these three priorities. We reuse it purely as a stable sort key
# -- no new "relevance score" / "match percentage" is invented here.
_PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _matched_skill_rank(skill: dict) -> tuple[int, str]:
    return (
        _PRIORITY_RANK.get(skill.get("priority"), 99),
        (skill.get("skill_name") or "").lower(),
    )


def _resource_skill_links(client: Client, skill_ids: list[str]) -> list[dict]:
    """Every ``learning_resource_skills`` row whose ``skill_id`` is one of
    the given canonical skills. RLS already limits this to mappings whose
    parent resource is active."""
    if not skill_ids:
        return []
    response = (
        client.table("learning_resource_skills")
        .select("resource_id, skill_id")
        .in_("skill_id", skill_ids)
        .execute()
    )
    return response.data or []


def get_recommended_resources(
    client: Client, student_id: str, gap_skills: list[dict]
) -> list[dict]:
    """Map the canonical Skill Gap recommendation list to learning
    resources.

    ``gap_skills`` is ``analysis["recommendations"]`` straight from
    ``skill_gap_service`` -- each item a dict carrying at least
    ``skill_id`` / ``skill_name`` / ``reason`` / ``priority``. This module
    never builds that list itself and never reinterprets those fields
    (``reason`` in particular is the engine's own server-authored text).

    Returns one entry per active learning resource mapped (via
    ``learning_resource_skills.skill_id``) to at least one of those
    skills::

        {"resource": <shaped resource>, "matched_skills": [<gap skill>, ...]}

    A resource mapped to several gap skills appears exactly once, with
    every matched gap skill listed (never the same resource repeated).

    Ordering is deterministic and transparent:
      * ``matched_skills`` within a resource: Skill Gap ``priority``
        (HIGH -> MEDIUM -> LOW), then ``skill_name``;
      * resources: the priority of their best matched skill, then resource
        title (``list_resources_by_ids`` already returns them
        title-sorted).
    """
    by_skill: dict[str, dict] = {}
    for skill in gap_skills:
        sid = str(skill["skill_id"])
        # If the engine ever lists a skill twice, keep the first occurrence.
        by_skill.setdefault(sid, skill)

    if not by_skill:
        return []

    matched_by_resource: dict[str, list[str]] = {}
    for link in _resource_skill_links(client, list(by_skill)):
        sid = str(link["skill_id"])
        if sid not in by_skill:
            continue
        skills_for_resource = matched_by_resource.setdefault(link["resource_id"], [])
        if sid not in skills_for_resource:
            skills_for_resource.append(sid)

    if not matched_by_resource:
        return []

    resources = student_learning_service.list_resources_by_ids(
        client, student_id, list(matched_by_resource)
    )

    entries: list[dict] = []
    for resource in resources:
        matched = [
            by_skill[sid]
            for sid in matched_by_resource.get(resource["id"], [])
            if sid in by_skill
        ]
        if not matched:
            continue
        matched.sort(key=_matched_skill_rank)
        entries.append({"resource": resource, "matched_skills": matched})

    entries.sort(
        key=lambda entry: (
            _PRIORITY_RANK.get(entry["matched_skills"][0].get("priority"), 99),
            (entry["resource"]["title"] or "").lower(),
        )
    )
    return entries
