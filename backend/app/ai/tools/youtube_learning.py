"""Read-only YouTube video-learning discovery boundary (Phase 4.7).

Deliberately its OWN abstraction (YouTubeLearningProvider), not forced
into app.ai.tools.course_discovery's CourseDiscoveryProvider: a YouTube
video is not a course (no price/certificate/instructor semantics), so
mixing it into CourseCandidate would be misleading metadata -- see
app.ai.schemas.youtube_learning.YouTubeVideoCandidate's own docstring.

Official YouTube Data API v3 only, API-key auth (no OAuth), two
endpoints per the current official docs
(https://developers.google.com/youtube/v3/docs):

    GET https://www.googleapis.com/youtube/v3/search    (find candidate video IDs)
    GET https://www.googleapis.com/youtube/v3/videos    (batch-enrich with
                                                           duration/statistics)

search.list alone can't return duration or view/like counts -- videos.list
enriches the IDs search.list already found, in ONE batched call (never a
second search for metadata already obtainable this way).

Every field on YouTubeVideoCandidate is source-owned; nothing here ever
infers a statistic, duration, or date the API didn't return, and this
module never asks Groq to help query or judge relevance -- see
_is_relevant and _rank below, both deterministic.

Quota discipline (the YouTube Data API's default daily search.list quota
is small -- 100 units per call, ~100 calls/day by default): at most one
search.list call per (skill name, target level) pair, shared across every
student via the module-level in-process cache below (`_search_cache`) --
never per-request, never per-user. Only public search results are
cached, never student identity/profile/skill-gap data.
"""

import hashlib
import html
import logging
import re
import time
from collections import OrderedDict
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.ai.config import YouTubeSettings, youtube_settings
from app.ai.schemas.youtube_learning import YouTubeVideoCandidate

logger = logging.getLogger("app.ai")

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

# Good candidates retained per skill AFTER enrichment/filtering -- the
# raw search.list maxResults (settings.youtube_max_results_per_skill,
# default 5) is a separate, larger bound on the initial search only.
MAX_GOOD_CANDIDATES_PER_SKILL = 3
# Skills searched per recommendation request -- quota control; the
# caller (the YouTube Learning Agent) is responsible for only ever
# passing its own top actionable gaps, already capped to this same
# number, but this module enforces it again defensively.
MAX_SKILLS_PER_REQUEST = 3
# Combined candidates returned across every skill in one request --
# never sent in bulk to Groq.
MAX_TOTAL_CANDIDATES = 6

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DURATION_RE = re.compile(r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$")
# A short, fixed, approved vocabulary -- never Groq-generated -- used only
# to bias the query and as a deterministic learning-format signal (see
# _format_signal). Order matters for the query phrase, not for matching.
_LEVEL_QUERY_PHRASE = {
    "Beginner": "beginner full course",
    "Intermediate": "intermediate tutorial",
    "Advanced": "advanced tutorial",
    "Expert": "advanced tutorial",
}
_COURSE_FORMAT_TERMS = ("full course", "complete course", "crash course", "tutorial", "course")
_SHORT_VIDEO_SECONDS = 180
_MIN_LEARNING_SECONDS = 600
_FULL_COURSE_SECONDS = 1800


class YouTubeUnavailable(Exception):
    """Any YouTube auth/network/quota/shape failure. `status` is one of
    "QUOTA_EXCEEDED" / "TEMPORARILY_UNAVAILABLE" / "FAILED" -- never a
    raw provider message, and the API key is never included in it."""

    def __init__(self, status: str, detail: str = "") -> None:
        super().__init__(detail or status)
        self.status = status


class YouTubeProvider(Protocol):
    @property
    def available(self) -> bool: ...

    def search_for_skill(
        self, skill_name: str, target_level: str | None, *, limit: int
    ) -> list[YouTubeVideoCandidate]: ...


class UnconfiguredYouTubeProvider:
    """Explicitly unavailable; no pretend provider, scraping, or invented data."""

    available = False

    def search_for_skill(
        self, skill_name: str, target_level: str | None, *, limit: int
    ) -> list[YouTubeVideoCandidate]:
        return []


class _CacheEntry:
    __slots__ = ("candidates", "expires_at")

    def __init__(self, candidates: list[YouTubeVideoCandidate], expires_at: float) -> None:
        self.candidates = candidates
        self.expires_at = expires_at


class _YouTubeSearchCache:
    """In-process, bounded cache of PUBLIC search results only -- see
    this module's own docstring for why sharing across students is
    safe. Keyed by (normalized skill name, target level); never by
    student/session. Bounded to _MAX_ENTRIES with LRU eviction so an
    unbounded stream of distinct skill names can't grow this forever."""

    _MAX_ENTRIES = 256

    def __init__(self) -> None:
        self._store: OrderedDict[tuple[str, str], _CacheEntry] = OrderedDict()

    def get(self, key: tuple[str, str], now: float) -> list[YouTubeVideoCandidate] | None:
        entry = self._store.get(key)
        if entry is None or now >= entry.expires_at:
            return None
        self._store.move_to_end(key)
        return entry.candidates

    def set(
        self, key: tuple[str, str], candidates: list[YouTubeVideoCandidate], now: float, ttl_seconds: float
    ) -> None:
        self._store[key] = _CacheEntry(candidates, now + ttl_seconds)
        self._store.move_to_end(key)
        while len(self._store) > self._MAX_ENTRIES:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


_search_cache = _YouTubeSearchCache()


def _query_hash(query: str) -> str:
    """A safe, non-reversible log field -- never the raw query text or
    any part of a request URL/key (see this module's own docstring)."""
    return hashlib.sha256(query.encode()).hexdigest()[:12]


def build_query(skill_name: str, target_level: str | None) -> str:
    """Deterministic, bounded -- never Groq-generated (see this
    module's own docstring)."""
    phrase = _LEVEL_QUERY_PHRASE.get(target_level or "", "tutorial")
    return f"{skill_name.strip()[:80]} {phrase}"[:150]


def _clean_text(text: str) -> str:
    """Untrusted source text (YouTube title/description) -- decode HTML
    entities for correct display, then strip control characters. This
    is normalization for safe plain-text display only; it never
    executes or interprets anything, and the result is still truncated
    by the caller before ever reaching Groq (see
    app.ai.agents.youtube_recommendation_agent)."""
    return _CONTROL_CHARS.sub("", html.unescape(text)).strip()


def _valid_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def _parse_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def parse_duration(value: object) -> tuple[int | None, str | None]:
    """ISO 8601 (YouTube's own subset, PT#H#M#S) -> (seconds, display
    text). Malformed/unrecognized input -> (None, None); never guessed.
    Examples: PT45M -> (2700, "45m"); PT1H20M -> (4800, "1h 20m");
    PT2H -> (7200, "2h")."""
    if not isinstance(value, str):
        return None, None
    match = _DURATION_RE.fullmatch(value.strip())
    if not match or not any(match.groups()):
        return None, None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    total_seconds = hours * 3600 + minutes * 60 + seconds
    if total_seconds <= 0:
        return None, None
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not hours and not minutes and seconds:
        parts.append(f"{seconds}s")
    return total_seconds, " ".join(parts)


def _is_relevant(title: str, description: str | None, skill_name: str) -> bool:
    """Real evidence only: the skill name (or a meaningful token of a
    multi-word skill name) must appear in the source's own title or
    description. Never trusts search.list's relevance ordering alone."""
    needle = skill_name.strip().lower()
    if len(needle) < 2:
        return False
    tokens = {needle, *(t for t in re.split(r"[\s/+\-]+", needle) if len(t) >= 2)}
    haystack = f"{title} {description or ''}".lower()
    return any(token in haystack for token in tokens)


def _best_thumbnail(thumbnails: object) -> str | None:
    if not isinstance(thumbnails, dict):
        return None
    for key in ("high", "medium", "default"):
        entry = thumbnails.get(key)
        if isinstance(entry, dict) and isinstance(entry.get("url"), str) and entry["url"].startswith("https://"):
            return entry["url"]
    return None


def _extract_video_id(search_item: object) -> str | None:
    if not isinstance(search_item, dict):
        return None
    id_obj = search_item.get("id")
    video_id = id_obj.get("videoId") if isinstance(id_obj, dict) else id_obj if isinstance(id_obj, str) else None
    return video_id if isinstance(video_id, str) and _VIDEO_ID_RE.fullmatch(video_id) else None


def _to_candidate(video_item: object, skill_name: str) -> tuple[YouTubeVideoCandidate, int | None] | None:
    """One videos.list item -> a validated candidate, or None if
    malformed (missing videoId, empty title/channel, etc.) -- skipped,
    never failing the whole batch. Returns (candidate, duration_seconds)
    so the caller can rank without re-parsing duration."""
    if not isinstance(video_item, dict):
        return None
    video_id = video_item.get("id")
    snippet = video_item.get("snippet") if isinstance(video_item.get("snippet"), dict) else {}
    title = snippet.get("title")
    channel_title = snippet.get("channelTitle")
    if (
        not isinstance(video_id, str)
        or not _VIDEO_ID_RE.fullmatch(video_id)
        or not isinstance(title, str)
        or not title.strip()
        or not isinstance(channel_title, str)
        or not channel_title.strip()
    ):
        return None
    description = snippet.get("description")
    description = _clean_text(description)[:2000] if isinstance(description, str) and description else None
    published_at = snippet.get("publishedAt")
    published_at = published_at if isinstance(published_at, str) and _valid_iso_datetime(published_at) else None
    channel_id = snippet.get("channelId") if isinstance(snippet.get("channelId"), str) else None
    content_details = video_item.get("contentDetails") if isinstance(video_item.get("contentDetails"), dict) else {}
    duration_seconds, duration_text = parse_duration(content_details.get("duration"))
    statistics = video_item.get("statistics") if isinstance(video_item.get("statistics"), dict) else {}
    try:
        candidate = YouTubeVideoCandidate(
            video_id=video_id,
            skill_id="",  # filled in by the caller once mapped to a canonical skill
            skill_name=skill_name[:200],
            title=_clean_text(title)[:300],
            description=description,
            channel_id=channel_id,
            channel_title=_clean_text(channel_title)[:200],
            published_at=published_at,
            thumbnail_url=_best_thumbnail(snippet.get("thumbnails")),
            duration_iso8601=content_details.get("duration")
            if isinstance(content_details.get("duration"), str)
            else None,
            duration_text=duration_text,
            view_count=_parse_int(statistics.get("viewCount")),
            like_count=_parse_int(statistics.get("likeCount")),
        )
    except ValidationError:
        return None
    return candidate, duration_seconds


def _format_signal(title: str, duration_seconds: int | None) -> int:
    """Deterministic learning-format evidence -- a documented heuristic,
    never a hidden 'quality score'. Course/tutorial vocabulary and
    sufficient length each add one point; nothing here is derived from
    view count (see _popularity_bucket for why raw views are only ever
    a coarse, modest tie-break)."""
    text = title.lower()
    score = 0
    if any(term in text for term in _COURSE_FORMAT_TERMS):
        score += 2
    if duration_seconds is not None and duration_seconds >= _MIN_LEARNING_SECONDS:
        score += 1
    if duration_seconds is not None and duration_seconds >= _FULL_COURSE_SECONDS:
        score += 1
    return score


def _popularity_bucket(view_count: int | None) -> int:
    """Coarse, bounded popularity tie-break -- deliberately NOT a raw
    sort on view count (see step 16's own instruction against
    over-weighting views); views only ever break a tie after relevance
    and format evidence already agree."""
    views = view_count or 0
    if views >= 1_000_000:
        return 3
    if views >= 100_000:
        return 2
    if views >= 10_000:
        return 1
    return 0


def _rank(pairs: list[tuple[YouTubeVideoCandidate, int | None]]) -> list[YouTubeVideoCandidate]:
    """relevance (already filtered) -> learning-format evidence ->
    modest popularity tie-break -> recency tie-break. Shorts-style
    (<3 min) content is deprioritized, never hard-excluded (an empty
    candidate pool is worse than a short video)."""

    def sort_key(pair: tuple[YouTubeVideoCandidate, int | None]) -> tuple[int, int, int, str]:
        candidate, duration_seconds = pair
        is_short = duration_seconds is not None and duration_seconds < _SHORT_VIDEO_SECONDS
        return (
            0 if is_short else 1,
            _format_signal(candidate.title, duration_seconds),
            _popularity_bucket(candidate.view_count),
            candidate.published_at or "",
        )

    return [candidate for candidate, _ in sorted(pairs, key=sort_key, reverse=True)]


def _get(url: str, params: dict[str, str], timeout: float) -> dict:
    """The one call site that reaches the network. Never logs `params`
    (which carries the API key) -- only a classified failure status."""
    try:
        response = httpx.get(url, params=params, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise YouTubeUnavailable("TEMPORARILY_UNAVAILABLE", "timeout") from exc
    except httpx.HTTPError as exc:
        raise YouTubeUnavailable("TEMPORARILY_UNAVAILABLE", "network error") from exc
    if response.status_code == 200:
        try:
            data = response.json()
        except ValueError as exc:
            raise YouTubeUnavailable("FAILED", "malformed json") from exc
        return data if isinstance(data, dict) else {}
    status = _classify_error_status(response)
    logger.warning("YouTube Data API request failed: http_status=%s classified=%s", response.status_code, status)
    raise YouTubeUnavailable(status, f"http {response.status_code}")


def _classify_error_status(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    reason = None
    if isinstance(payload, dict):
        errors = payload.get("error", {}).get("errors") if isinstance(payload.get("error"), dict) else None
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            reason = errors[0].get("reason")
    if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded") or response.status_code == 429:
        return "QUOTA_EXCEEDED"
    if response.status_code >= 500:
        return "TEMPORARILY_UNAVAILABLE"
    return "FAILED"


class YouTubeLearningProvider:
    """Real provider: the official YouTube Data API v3, API-key auth
    only. Only instantiated by get_youtube_provider() once
    YouTubeSettings.is_configured is True."""

    available = True

    def __init__(self, settings: YouTubeSettings) -> None:
        self._settings = settings

    def search_for_skill(
        self, skill_name: str, target_level: str | None, *, limit: int
    ) -> list[YouTubeVideoCandidate]:
        query = build_query(skill_name, target_level)
        cache_key = (skill_name.strip().lower(), target_level or "")
        now = time.monotonic()
        cached = _search_cache.get(cache_key, now)
        if cached is not None:
            logger.info("YouTube cache hit query_hash=%s candidates=%d", _query_hash(query), len(cached))
            return cached[:limit]
        logger.info("YouTube cache miss query_hash=%s", _query_hash(query))
        candidates = self._search_and_enrich(query, skill_name)
        _search_cache.set(cache_key, candidates, now, self._settings.youtube_cache_ttl_seconds)
        return candidates[:limit]

    def _search_and_enrich(self, query: str, skill_name: str) -> list[YouTubeVideoCandidate]:
        search_data = _get(
            _SEARCH_URL,
            {
                "part": "snippet",
                "type": "video",
                "q": query,
                "maxResults": str(self._settings.youtube_max_results_per_skill),
                "order": "relevance",
                "safeSearch": "strict",
                "relevanceLanguage": "en",
                "key": self._settings.youtube_api_key,
            },
            self._settings.youtube_timeout_seconds,
        )
        items = search_data.get("items")
        video_ids = list(dict.fromkeys(filter(None, (_extract_video_id(item) for item in items or []))))
        if not video_ids:
            return []
        videos_data = _get(
            _VIDEOS_URL,
            {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(video_ids),
                "key": self._settings.youtube_api_key,
            },
            self._settings.youtube_timeout_seconds,
        )
        pairs = list(filter(None, (_to_candidate(item, skill_name) for item in videos_data.get("items") or [])))
        relevant = [pair for pair in pairs if _is_relevant(pair[0].title, pair[0].description, skill_name)]
        return _rank(relevant)[:MAX_GOOD_CANDIDATES_PER_SKILL]


def get_youtube_provider() -> YouTubeProvider:
    if youtube_settings.is_configured:
        return YouTubeLearningProvider(youtube_settings)
    return UnconfiguredYouTubeProvider()


def discover_for_skills(
    skills: Sequence, *, limit_per_skill: int = MAX_GOOD_CANDIDATES_PER_SKILL
) -> tuple[list[YouTubeVideoCandidate], str]:
    """One entry point for the agent layer. `skills` is any sequence of
    objects exposing `.skill_id` / `.skill_name` / `.target_level`
    (CourseSkill already satisfies this; duck-typed rather than
    imported to avoid a circular import -- see this module's own
    module docstring and app.ai.schemas.youtube_learning's).

    Isolates one skill's failure from the others: a quota/timeout on
    one query never blocks a later, possibly-cached query for a
    different skill. Never raises -- returns (candidates, status)
    where status is "AVAILABLE" / "CONFIGURATION_REQUIRED" /
    "QUOTA_EXCEEDED" / "TEMPORARILY_UNAVAILABLE" / "FAILED".
    """
    provider = get_youtube_provider()
    if not provider.available:
        return [], "CONFIGURATION_REQUIRED"
    if not skills:
        return [], "AVAILABLE"

    all_candidates: list[YouTubeVideoCandidate] = []
    any_success = False
    last_failure_status = "FAILED"
    for skill in list(skills)[:MAX_SKILLS_PER_REQUEST]:
        try:
            found = provider.search_for_skill(skill.skill_name, skill.target_level, limit=limit_per_skill)
        except YouTubeUnavailable as exc:
            last_failure_status = exc.status
            continue
        any_success = True
        for candidate in found:
            all_candidates.append(candidate.model_copy(update={"skill_id": skill.skill_id}))

    if any_success:
        return all_candidates[:MAX_TOTAL_CANDIDATES], "AVAILABLE"
    return [], last_failure_status
