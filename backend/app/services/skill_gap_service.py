"""Business logic for Skill Gap Analysis -- job roles, the student's own
target role, and the deterministic (NO LLM) gap/recommendation engine.

Every function takes an already-constructed Supabase client, exactly like
app.services.assessment_service. All reads/writes here go through the
user-scoped client (app.core.security.build_user_client) -- RLS is the
real access-control boundary; nothing in this module needs service_role,
because every table it touches (job_roles, job_role_skills,
student_target_job_role, skill_relationships, student_skills, skills,
assessments) already has a "students can read/write their own data"
policy from 016_skill_gap.sql or an earlier migration.

The gap calculation reuses `student_skills` (003_skills.sql) as the ONLY
source of a student's declared/verified proficiency, and `assessments`
(004_assessments.sql) as the ONLY source of "is there an assessment for
skill X at level Y" -- this module caches neither in a new table, and
never recomputes or overrides is_verified.

Proficiency ordinal mapping (application-layer only -- see 016's own
header comment for why this isn't in the schema):
"""

from uuid import UUID

from supabase import Client

LEVEL_ORDER = {
    "Beginner": 1,
    "Intermediate": 2,
    "Advanced": 3,
    "Expert": 4,
}
LEVEL_BY_ORDER = {v: k for k, v in LEVEL_ORDER.items()}
MAX_LEVEL = max(LEVEL_ORDER.values())

IMPORTANCE_WEIGHT = {"CORE": 5, "IMPORTANT": 3, "OPTIONAL": 1}

_JOB_ROLE_COLUMNS = "id, name, description, category, is_active, created_at, updated_at"


# ============================================================
# job_roles / job_role_skills
# ============================================================


def list_active_job_roles(client: Client) -> list[dict]:
    """All job roles visible to the caller. RLS ("Students can view active
    job roles") already restricts this to is_active = true; the explicit
    .eq() here is defense in depth, matching assessment_service's own
    convention."""
    response = (
        client.table("job_roles").select(_JOB_ROLE_COLUMNS).eq("is_active", True).order("name").execute()
    )
    return response.data or []


def get_active_job_role(client: Client, job_role_id: UUID) -> dict | None:
    """One job role, or None if it doesn't exist / isn't active / isn't
    visible. Callers must turn None into a 404 -- never reveal whether an
    inactive role exists."""
    response = (
        client.table("job_roles")
        .select(_JOB_ROLE_COLUMNS)
        .eq("id", str(job_role_id))
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def get_job_role_requirements(client: Client, job_role_id: UUID) -> list[dict]:
    """This role's required skills, each with its skill name/category
    embedded -- a bare skill_id is never useful on its own to a caller.
    RLS ("Students can view job role skills for active roles") already
    scopes this to roles that are currently active."""
    response = (
        client.table("job_role_skills")
        .select(
            "skill_id, required_level, importance, "
            "skill:skills(id, name, category:skill_categories(name))"
        )
        .eq("job_role_id", str(job_role_id))
        .execute()
    )
    rows = response.data or []
    requirements = []
    for row in rows:
        skill = row.get("skill") or {}
        category = skill.get("category") or {}
        requirements.append(
            {
                "skill_id": row["skill_id"],
                "skill_name": skill.get("name", ""),
                "category_name": category.get("name"),
                "required_level": row["required_level"],
                "importance": row["importance"],
            }
        )
    return requirements


# ============================================================
# student_target_job_role
# ============================================================

_TARGET_ROLE_COLUMNS = f"id, created_at, updated_at, job_role:job_roles({_JOB_ROLE_COLUMNS})"


def get_target_job_role(client: Client, student_id: str) -> dict | None:
    """The caller's own target role, or None if they haven't set one -- OR
    if the role they targeted has since been deactivated (the nested
    job_role embed comes back None in that case, since job_roles' own RLS
    only allows is_active = true rows through; this function treats that
    the same as "no usable target role" rather than returning a broken
    partial object)."""
    response = (
        client.table("student_target_job_role")
        .select(_TARGET_ROLE_COLUMNS)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if row is None or row.get("job_role") is None:
        return None
    return row


def set_target_job_role(client: Client, student_id: str, job_role_id: UUID) -> dict:
    """Create or replace the caller's own target role.

    student_target_job_role_one_per_student enforces exactly one row per
    student -- upsert on that natural key, never a separate delete-then-
    insert (which would leave a window with no row at all if the second
    statement failed). RLS's own insert/update `with check` already
    guarantees student_id = auth.uid() for both branches upsert can take.
    """
    client.table("student_target_job_role").upsert(
        {"student_id": student_id, "job_role_id": str(job_role_id)},
        on_conflict="student_id",
    ).execute()
    row = get_target_job_role(client, student_id)
    if row is None:
        # The role was just set but is somehow not active/visible -- only
        # possible if job_role_id itself pointed at an inactive role,
        # which the route layer must reject before ever calling this.
        raise ValueError("Target job role could not be read back after being set.")
    return row


def clear_target_job_role(client: Client, student_id: str) -> None:
    """Delete the caller's own target role row, if any. A no-op (not an
    error) if none exists -- RLS ("Students can clear their own target job
    role") already scopes the delete to the caller."""
    client.table("student_target_job_role").delete().eq("student_id", student_id).execute()


# ============================================================
# student_skills / assessments lookups
# ============================================================


def get_student_skill_map(client: Client, student_id: str) -> dict[str, dict]:
    """The caller's own active skills, keyed by skill_id -- RLS ("Students
    can view their own skills") already scopes this to the caller."""
    response = (
        client.table("student_skills")
        .select("skill_id, proficiency_level, is_verified")
        .eq("student_id", student_id)
        .execute()
    )
    rows = response.data or []
    return {row["skill_id"]: row for row in rows}


def get_assessment_availability(client: Client, skill_ids: list[str]) -> dict[tuple[str, str], str]:
    """{(skill_id, difficulty): assessment_id} for every currently active
    assessment covering one of the given skills -- the ONLY place
    "is there an assessment for X at level Y" is looked up; never
    duplicated as a cached flag anywhere else."""
    if not skill_ids:
        return {}
    response = (
        client.table("assessments")
        .select("id, skill_id, difficulty")
        .in_("skill_id", skill_ids)
        .eq("is_active", True)
        .execute()
    )
    rows = response.data or []
    return {(row["skill_id"], row["difficulty"]): row["id"] for row in rows}


def get_skill_relationships_from(client: Client, skill_ids: list[str]) -> list[dict]:
    """Every skill_relationships row whose *source* (skill_id) is one of
    the given skills -- used to find "what should I learn next, given what
    I already have" (personal mode) and, for job-role mode, "what would
    help this missing/weak requirement" is deliberately NOT sourced from
    here (see compute_job_role_gap's own docstring for why job-role
    recommendations stay derived from job_role_skills directly)."""
    if not skill_ids:
        return []
    response = (
        client.table("skill_relationships")
        .select(
            "skill_id, related_skill_id, relationship_type, priority, "
            "related_skill:skills!skill_relationships_related_skill_id_fkey(id, name)"
        )
        .in_("skill_id", skill_ids)
        .order("priority")
        .execute()
    )
    return response.data or []


def get_prerequisites_of(client: Client, skill_ids: list[str]) -> dict[str, list[dict]]:
    """{related_skill_id: [prerequisite skill rows]} -- rows where
    relationship_type = PREREQUISITE and related_skill_id (the skill that
    HAS a prerequisite) is one of the given skills."""
    if not skill_ids:
        return {}
    response = (
        client.table("skill_relationships")
        .select("skill_id, related_skill_id, skill:skills!skill_relationships_skill_id_fkey(id, name)")
        .in_("related_skill_id", skill_ids)
        .eq("relationship_type", "PREREQUISITE")
        .execute()
    )
    rows = response.data or []
    by_target: dict[str, list[dict]] = {}
    for row in rows:
        by_target.setdefault(row["related_skill_id"], []).append(row)
    return by_target


# ============================================================
# Deterministic gap calculation
# ============================================================


def _ordinal(level: str | None) -> int:
    return LEVEL_ORDER.get(level, 0) if level else 0


def calculate_status(current_ordinal: int, required_ordinal: int) -> str:
    if current_ordinal == 0:
        return "MISSING"
    if current_ordinal < required_ordinal:
        return "NEEDS_IMPROVEMENT"
    return "MATCHED"


def calculate_priority(status: str, importance: str, gap: int) -> str:
    """Priority is evaluated top-down, first match wins -- fully
    deterministic and explainable from (status, importance, gap) alone:

      1. Already MATCHED                              -> LOW
      2. A 2+ level gap (MISSING or NEEDS_IMPROVEMENT) -> HIGH
      3. MISSING a CORE requirement                    -> HIGH
      4. MISSING an IMPORTANT requirement               -> MEDIUM
      5. NEEDS_IMPROVEMENT by exactly 1 level, not
         OPTIONAL                                      -> MEDIUM
      6. Anything OPTIONAL left                        -> LOW
      7. Fallback (MISSING + OPTIONAL with gap < 2)     -> MEDIUM
    """
    if status == "MATCHED":
        return "LOW"
    if gap >= 2:
        return "HIGH"
    if status == "MISSING" and importance == "CORE":
        return "HIGH"
    if status == "MISSING" and importance == "IMPORTANT":
        return "MEDIUM"
    if status == "NEEDS_IMPROVEMENT" and gap == 1 and importance != "OPTIONAL":
        return "MEDIUM"
    if importance == "OPTIONAL":
        return "LOW"
    return "MEDIUM"


def _build_reason(skill_name: str, role_name: str, status: str, importance: str, required_level: str, current_level: str | None) -> str:
    if status == "MISSING":
        if importance == "CORE":
            return f"{skill_name} is a core requirement for {role_name} and isn't in your skill list yet."
        if importance == "IMPORTANT":
            return f"{skill_name} is an important skill for {role_name} that you haven't added yet."
        return f"{skill_name} is a nice-to-have skill for {role_name}."
    # NEEDS_IMPROVEMENT
    return (
        f"{role_name} requires {skill_name} at {required_level} level, "
        f"but your current level is {current_level}."
    )


def compute_job_role_gap(client: Client, student_id: str, job_role: dict, requirements: list[dict]) -> dict:
    """The full deterministic gap analysis against one job role.

    Job-role recommendations are derived DIRECTLY from job_role_skills gaps
    (every MISSING/NEEDS_IMPROVEMENT requirement, most urgent first) --
    not from skill_relationships. This keeps "why is this recommended"
    fully traceable to the role's own stated requirements; the
    relationship graph is used instead for PERSONAL-mode recommendations
    (see compute_personal_analysis), matching the different question each
    mode answers ("what does this specific role need" vs. "what should I
    learn next in general").
    """
    role_name = job_role["name"]
    skill_ids = [req["skill_id"] for req in requirements]
    student_skills = get_student_skill_map(client, student_id)
    assessment_map = get_assessment_availability(client, skill_ids)

    items: list[dict] = []
    matched = needs_improvement = missing = unverified = 0
    total_weight = 0
    earned_weight = 0.0

    for req in requirements:
        skill_id = req["skill_id"]
        required_level = req["required_level"]
        importance = req["importance"]
        required_ordinal = LEVEL_ORDER[required_level]
        weight = IMPORTANCE_WEIGHT[importance]
        total_weight += weight

        owned = student_skills.get(skill_id)
        current_level = owned["proficiency_level"] if owned else None
        current_ordinal = _ordinal(current_level)
        is_verified = bool(owned and owned["is_verified"])

        status = calculate_status(current_ordinal, required_ordinal)
        gap = max(0, required_ordinal - current_ordinal)
        priority = calculate_priority(status, importance, gap)

        if status == "MATCHED":
            matched += 1
            earned_weight += weight
        elif status == "NEEDS_IMPROVEMENT":
            needs_improvement += 1
            earned_weight += weight * (current_ordinal / required_ordinal)
        else:
            missing += 1

        if owned is not None and not is_verified:
            unverified += 1

        next_difficulty = required_level if status != "MATCHED" else current_level
        assessment_id = assessment_map.get((skill_id, next_difficulty)) if next_difficulty else None

        items.append(
            {
                "skill_id": skill_id,
                "skill_name": req["skill_name"],
                "current_level": current_level,
                "required_level": required_level,
                "gap": gap,
                "status": status,
                "verification_status": "VERIFIED" if is_verified else "UNVERIFIED",
                "importance": importance,
                "priority": priority,
                "assessment_available": assessment_id is not None,
                "assessment_id": assessment_id,
                "_role_name": role_name,
            }
        )

    readiness = 0 if total_weight == 0 else round(100 * earned_weight / total_weight)
    readiness = max(0, min(100, readiness))

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendations = [
        {
            "skill_id": item["skill_id"],
            "skill_name": item["skill_name"],
            "reason": _build_reason(
                item["skill_name"], role_name, item["status"], item["importance"],
                item["required_level"], item["current_level"],
            ),
            "current_level": item["current_level"],
            "target_level": item["required_level"],
            "gap": item["gap"],
            "priority": item["priority"],
            "relationship_type": None,
            "is_missing": item["status"] == "MISSING",
            "is_verified": item["verification_status"] == "VERIFIED",
            "assessment_available": item["assessment_available"],
            "assessment_id": item["assessment_id"],
        }
        for item in items
        if item["status"] != "MATCHED"
    ]
    recommendations.sort(key=lambda rec: priority_order[rec["priority"]])

    for item in items:
        item.pop("_role_name", None)

    return {
        "readiness_percentage": readiness,
        "summary": {
            "matched": matched,
            "needs_improvement": needs_improvement,
            "missing": missing,
            "unverified": unverified,
        },
        "skills": items,
        "recommendations": recommendations,
    }


_RELATIONSHIP_REASON = {
    "NEXT_STEP": "A natural next step after {source} is {target}.",
    "RELATED": "{target} is commonly used alongside {source}, which you already have.",
    "COMPLEMENTARY": "{target} pairs well with {source} and would round out your skill set.",
}
_RELATIONSHIP_PRIORITY = {
    "NEXT_STEP": "MEDIUM",
    "RELATED": "LOW",
    "COMPLEMENTARY": "LOW",
}


def compute_personal_analysis(client: Client, student_id: str) -> dict:
    """The no-job-role personal analysis: a summary of the student's own
    active skills, which of them have a next-level assessment available,
    and skill-relationship-graph-driven suggestions for what to learn
    next -- entirely independent of any job role. Recommends ONLY skills
    that appear as a NEXT_STEP/RELATED/COMPLEMENTARY target of a skill the
    student already owns (never an arbitrary/unrelated skill)."""
    owned_response = (
        client.table("student_skills")
        .select("skill_id, proficiency_level, is_verified, skill:skills(id, name)")
        .eq("student_id", student_id)
        .execute()
    )
    owned_rows = owned_response.data or []
    owned_skill_ids = {row["skill_id"] for row in owned_rows}

    counts = {
        "total_active_skills": len(owned_rows),
        "verified_skills": sum(1 for row in owned_rows if row["is_verified"]),
        "unverified_skills": sum(1 for row in owned_rows if not row["is_verified"]),
        "beginner_skills": sum(1 for row in owned_rows if row["proficiency_level"] == "Beginner"),
        "intermediate_skills": sum(1 for row in owned_rows if row["proficiency_level"] == "Intermediate"),
        "advanced_skills": sum(1 for row in owned_rows if row["proficiency_level"] == "Advanced"),
        "expert_skills": sum(1 for row in owned_rows if row["proficiency_level"] == "Expert"),
    }

    assessment_map = get_assessment_availability(client, list(owned_skill_ids))
    progressable = []
    for row in owned_rows:
        current_level = row["proficiency_level"]
        current_ordinal = LEVEL_ORDER[current_level]
        if current_ordinal >= MAX_LEVEL:
            continue
        next_level = LEVEL_BY_ORDER[current_ordinal + 1]
        assessment_id = assessment_map.get((row["skill_id"], next_level))
        progressable.append(
            {
                "skill_id": row["skill_id"],
                "skill_name": (row.get("skill") or {}).get("name", ""),
                "current_level": current_level,
                "next_level": next_level,
                "assessment_available": assessment_id is not None,
                "assessment_id": assessment_id,
            }
        )

    owned_names = {row["skill_id"]: (row.get("skill") or {}).get("name", "") for row in owned_rows}
    relationships = get_skill_relationships_from(client, list(owned_skill_ids))

    recommendations: dict[str, dict] = {}
    for rel in relationships:
        target_id = rel["related_skill_id"]
        if target_id in owned_skill_ids:
            continue
        rel_type = rel["relationship_type"]
        if rel_type not in _RELATIONSHIP_REASON:
            continue
        target = rel.get("related_skill") or {}
        target_name = target.get("name", "")
        source_name = owned_names.get(rel["skill_id"], "")
        if target_id in recommendations:
            continue
        recommendations[target_id] = {
            "skill_id": target_id,
            "skill_name": target_name,
            "reason": _RELATIONSHIP_REASON[rel_type].format(source=source_name, target=target_name),
            "current_level": None,
            "target_level": None,
            "gap": None,
            "priority": _RELATIONSHIP_PRIORITY[rel_type],
            "relationship_type": rel_type,
            "is_missing": True,
            "is_verified": False,
            "assessment_available": False,
            "assessment_id": None,
        }

    recommendation_list = list(recommendations.values())
    if recommendation_list:
        candidate_map = get_assessment_availability(client, [r["skill_id"] for r in recommendation_list])
        for rec in recommendation_list:
            assessment_id = candidate_map.get((rec["skill_id"], "Beginner"))
            rec["assessment_available"] = assessment_id is not None
            rec["assessment_id"] = assessment_id

    prerequisite_gaps = []
    if recommendation_list:
        prereq_map = get_prerequisites_of(client, [r["skill_id"] for r in recommendation_list])
        for rec in recommendation_list:
            for prereq_row in prereq_map.get(rec["skill_id"], []):
                prereq_skill_id = prereq_row["skill_id"]
                if prereq_skill_id in owned_skill_ids:
                    continue
                prereq_skill = prereq_row.get("skill") or {}
                prerequisite_gaps.append(
                    {
                        "skill_id": prereq_skill_id,
                        "skill_name": prereq_skill.get("name", ""),
                        "required_for_skill_id": rec["skill_id"],
                        "required_for_skill_name": rec["skill_name"],
                    }
                )

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendation_list.sort(key=lambda rec: priority_order[rec["priority"]])

    return {
        "counts": counts,
        "progressable_skills": progressable,
        "recommendations": recommendation_list,
        "prerequisite_gaps": prerequisite_gaps,
    }
