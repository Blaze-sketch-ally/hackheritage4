"""Deterministic candidate/opportunity match scoring (Phase 9).

Pure -- no Supabase client, no FastAPI, no LLM, no service_role. Takes the
required-skill x candidate-skill rows produced by the
public.application_skill_match RPC (021_application_skill_match.sql) and
returns a reproducible match result: same rows in => same result out.

Conventions match app.services.skill_gap_service:
    proficiency ordinals   Beginner=1, Intermediate=2, Advanced=3, Expert=4
    importance weights     CORE=5, IMPORTANT=3, OPTIONAL=1

Per required skill, the applicant earns a fraction of that skill's weight:
    MATCHED (has it at/above the required level)   -> 1.0
    NEEDS_IMPROVEMENT (has it, below required)     -> candidate_ord / required_ord
    MISSING (doesn't have it)                       -> 0.0
A skill the applicant self-reported but that isn't verified earns
_UNVERIFIED_FACTOR of what it otherwise would (self-reported, unproven).

    score = round(100 * sum(weight * fraction) / sum(weight))   clamped 0-100

Recommendation band is derived from the score, then capped at PARTIAL if
any CORE requirement is entirely missing (a strong overall number should
never read as "STRONG" while a core skill is absent).
"""

_LEVEL_ORDER: dict[str, int] = {
    "Beginner": 1,
    "Intermediate": 2,
    "Advanced": 3,
    "Expert": 4,
}
_IMPORTANCE_WEIGHT: dict[str, int] = {"CORE": 5, "IMPORTANT": 3, "OPTIONAL": 1}

# A self-reported but unverified skill earns slightly less than a verified one.
_UNVERIFIED_FACTOR = 0.85

# (min score, band) -- highest threshold first, first match wins.
_BANDS: tuple[tuple[int, str], ...] = (
    (80, "STRONG"),
    (60, "GOOD"),
    (35, "PARTIAL"),
    (0, "LOW"),
)


def _ordinal(level: str | None) -> int:
    return _LEVEL_ORDER.get(level or "", 0)


def _status(candidate_ord: int, required_ord: int) -> str:
    if candidate_ord == 0:
        return "MISSING"
    if candidate_ord >= required_ord:
        return "MATCHED"
    return "NEEDS_IMPROVEMENT"


def _recommendation(score: int, missing_core: bool) -> str:
    band = next(name for threshold, name in _BANDS if score >= threshold)
    if missing_core and band in ("STRONG", "GOOD"):
        return "PARTIAL"
    return band


def _sort_key(skill: dict) -> tuple[int, str]:
    # CORE first, then IMPORTANT, then OPTIONAL; alphabetical within a tier.
    return (-_IMPORTANCE_WEIGHT.get(skill["importance"], 0), skill["skill_name"].lower())


def compute_match(application_id: str, rows: list[dict]) -> dict:
    """`rows` is the RPC output: dicts with skill_id, skill_name,
    required_level, importance, candidate_has, candidate_level,
    candidate_verified. Duplicate skill_ids are ignored (the RPC already
    guarantees uniqueness; this is defence in depth so a duplicate can
    never inflate the score)."""
    matched: list[dict] = []
    needs_improvement: list[dict] = []
    missing: list[dict] = []
    total_weight = 0.0
    earned_weight = 0.0
    missing_core = False
    seen: set[str] = set()

    for row in rows:
        skill_id = row["skill_id"]
        if skill_id in seen:
            continue
        seen.add(skill_id)

        required_level = row["required_level"]
        importance = row["importance"]
        required_ord = _LEVEL_ORDER[required_level]
        weight = _IMPORTANCE_WEIGHT[importance]
        total_weight += weight

        has = bool(row["candidate_has"])
        candidate_level = row.get("candidate_level") if has else None
        candidate_ord = _ordinal(candidate_level)
        verified = bool(row.get("candidate_verified"))

        status = _status(candidate_ord, required_ord)
        if status == "MATCHED":
            fraction = 1.0
        elif status == "NEEDS_IMPROVEMENT":
            fraction = candidate_ord / required_ord
        else:
            fraction = 0.0
        if status != "MISSING" and not verified:
            fraction *= _UNVERIFIED_FACTOR

        earned_weight += weight * fraction

        skill = {
            "skill_id": skill_id,
            "skill_name": row["skill_name"],
            "required_level": required_level,
            "importance": importance,
            "candidate_has": has,
            "candidate_level": candidate_level,
            "candidate_verified": verified,
            "status": status,
        }
        if status == "MATCHED":
            matched.append(skill)
        elif status == "NEEDS_IMPROVEMENT":
            needs_improvement.append(skill)
        else:
            missing.append(skill)
            if importance == "CORE":
                missing_core = True

    required_count = len(seen)
    score = 0 if total_weight == 0 else round(100 * earned_weight / total_weight)
    score = max(0, min(100, score))
    covered = len(matched) + len(needs_improvement)

    for bucket in (matched, needs_improvement, missing):
        bucket.sort(key=_sort_key)

    return {
        "application_id": application_id,
        "score": score,
        "recommendation": _recommendation(score, missing_core),
        "skill_coverage": f"{covered} / {required_count}",
        "required_count": required_count,
        "matched_count": len(matched),
        "needs_improvement_count": len(needs_improvement),
        "missing_count": len(missing),
        "matched_skills": matched,
        "needs_improvement_skills": needs_improvement,
        "missing_skills": missing,
    }
