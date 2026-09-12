"""Read-only discovery boundary. No external course-search API is
configured in this repository.

Adapters must return source-backed metadata and skill associations, never LLM facts.
The external adapter seam is server-side only; it accepts no URL or client input.

(Phase 4.6 briefly added a real Microsoft Learn adapter here behind this
same CourseDiscoveryProvider protocol. It was removed once Microsoft
Learn was replaced by a YouTube Data API v3 video-learning provider --
see app.ai.tools.youtube_learning, which is intentionally its OWN
abstraction (YouTubeLearningProvider), not forced into this one, because
a video is not a course -- see that module's own docstring. This file
is back to its original two-provider shape.)
"""

from collections.abc import Sequence
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError
from supabase import Client

from app.ai.schemas.course_recommendation import CourseCandidate, CourseSkill
from app.services import learning_recommendation_service

MAX_CANDIDATES = 12


class CourseDiscoveryProvider(Protocol):
    @property
    def available(self) -> bool: ...

    def discover(self, skills: Sequence[CourseSkill], *, limit: int) -> list[CourseCandidate]: ...


class InternalLearningResourceProvider:
    available = True

    def __init__(self, client: Client, student_id: str):
        self.client = client
        self.student_id = student_id

    def discover(self, skills: Sequence[CourseSkill], *, limit: int) -> list[CourseCandidate]:
        if not skills:
            return []
        entries = learning_recommendation_service.get_recommended_resources(
            self.client, self.student_id, [skill.model_dump() for skill in skills]
        )
        candidates = []
        selected = {s.skill_id: s for s in skills}
        for entry in entries:
            try:
                if not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict):
                    continue
                resource = entry["resource"]
                matched = list(
                    dict.fromkeys(
                        str(s["skill_id"])
                        for s in entry["matched_skills"]
                        if str(s["skill_id"]) in selected
                    )
                )
                minutes = resource.get("estimated_minutes")
                candidates.append(
                    CourseCandidate(
                        candidate_id=f"internal:{resource['id']}",
                        source_type="INTERNAL",
                        title=resource["title"],
                        url=resource["url"],
                        provider=resource.get("provider"),
                        description=resource.get("description"),
                        skill_ids=matched,
                        skill_names=[selected[sid].skill_name for sid in matched],
                        level=resource.get("difficulty"),
                        duration_text=f"{minutes} minutes" if minutes is not None else None,
                        metadata_source="learning_resources/learning_resource_skills",
                    )
                )
            except (KeyError, TypeError, ValueError, ValidationError):
                continue
        return normalize_candidates(candidates, skills, "INTERNAL", limit)


class UnconfiguredExternalProvider:
    """Explicitly unavailable; no pretend provider, scraping, or invented URLs."""

    available = False

    def discover(self, skills: Sequence[CourseSkill], *, limit: int) -> list[CourseCandidate]:
        return []


def get_external_provider() -> CourseDiscoveryProvider:
    # Replace only after choosing and configuring a real, reviewed source adapter.
    return UnconfiguredExternalProvider()


def discovery_query(skill: CourseSkill, target_role: str | None = None) -> str:
    """Bounded deterministic query for future adapters; never another LLM call."""
    return " ".join(
        filter(
            None, [skill.skill_name[:120], skill.target_level, (target_role or "")[:120], "course"]
        )
    )


def _url_identity(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def normalize_candidates(
    records, skills: Sequence[CourseSkill], source: str, limit: int = MAX_CANDIDATES
) -> list[CourseCandidate]:
    """Validate adapter output and deduplicate by ID/URL; first metadata wins.

    Duplicate mappings merge by skill ID. Names are attached from canonical skills.
    URLs are only returned, never fetched. Source provenance is mandatory.
    """
    selected = {s.skill_id: s for s in skills}
    out: list[CourseCandidate] = []
    by_id: dict[str, int] = {}
    by_url: dict[str, int] = {}
    for record in records[:100]:
        try:
            candidate = CourseCandidate.model_validate(record)
            if candidate.source_type != source:
                continue
            ids = list(dict.fromkeys(sid for sid in candidate.skill_ids if sid in selected))
            if not ids:
                continue
            candidate = candidate.model_copy(
                update={"skill_ids": ids, "skill_names": [selected[sid].skill_name for sid in ids]}
            )
            identity = _url_identity(candidate.url)
            existing = by_id.get(candidate.candidate_id, by_url.get(identity))
            if existing is not None:
                by_id[candidate.candidate_id] = existing
                by_url[identity] = existing
                old = out[existing]
                merged = list(dict.fromkeys([*old.skill_ids, *ids]))
                out[existing] = old.model_copy(
                    update={
                        "skill_ids": merged,
                        "skill_names": [selected[sid].skill_name for sid in merged],
                    }
                )
                continue
            if len(out) >= min(limit, MAX_CANDIDATES):
                continue
            by_id[candidate.candidate_id] = len(out)
            by_url[identity] = len(out)
            out.append(candidate)
        except (TypeError, ValueError, ValidationError):
            continue
    return out


def discover_candidates(client: Client, student_id: str, skills: Sequence[CourseSkill]):
    """Isolate failures by source. Never log exceptions or provider response text."""
    internal_available = True
    try:
        internal = InternalLearningResourceProvider(client, student_id).discover(
            skills, limit=MAX_CANDIDATES
        )
    except Exception:  # noqa: BLE001 -- isolate source failures; never expose provider text
        internal, internal_available = [], False
    external_status = "CONFIGURATION_REQUIRED"
    external = []
    try:
        provider = get_external_provider()
        if provider.available:
            external = normalize_candidates(
                provider.discover(skills, limit=MAX_CANDIDATES), skills, "EXTERNAL"
            )
            external_status = "AVAILABLE"
    except Exception:  # noqa: BLE001 -- isolate source failures; never expose provider text
        external_status = "FAILED"
    # Preserve internal metadata on cross-source duplicates. Never merge an
    # external association into the authoritative internal mapping.
    urls = {_url_identity(c.url) for c in internal}
    ids = {c.candidate_id for c in internal}
    combined = internal + [
        c for c in external if _url_identity(c.url) not in urls and c.candidate_id not in ids
    ]
    return combined[:MAX_CANDIDATES], internal_available, external_status
