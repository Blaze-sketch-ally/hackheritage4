"""Phase 4.7 offline tests. Every YouTube Data API v3 network call is
mocked -- no live HTTP request ever reaches googleapis.com from this
file.
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai.agents import course_recommendation_agent as agent
from app.ai.agents import youtube_recommendation_agent as yt_agent
from app.ai.client import GroqClient
from app.ai.config import AISettings, YouTubeSettings
from app.ai.guardrails.youtube_learning import deterministic_recommendations, ground
from app.ai.schemas.course_recommendation import CourseCanonical, CourseSkill
from app.ai.schemas.youtube_learning import YouTubeLLMOutput, YouTubeSkillRef, YouTubeVideoCandidate
from app.ai.tools import course_discovery as discovery
from app.ai.tools import youtube_learning as yt
from app.main import app
from tests.conftest import authenticated_as
from tests.test_ai_skill_gap_agent import _job_role_section, _personal_section

SID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SID2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_REQUEST = httpx.Request("GET", "https://www.googleapis.com/youtube/v3/search")


@pytest.fixture(autouse=True)
def _reset_cache():
    yt._search_cache.clear()
    yield
    yt._search_cache.clear()


def configured_settings(**overrides) -> YouTubeSettings:
    return YouTubeSettings(
        youtube_api_key=overrides.get("api_key", "test-key-value"),
        youtube_timeout_seconds=overrides.get("timeout", 5.0),
        youtube_max_results_per_skill=overrides.get("max_results", 5),
        youtube_cache_ttl_seconds=overrides.get("ttl", 21600),
    )


def skill(ref="G1", skill_id=SID, skill_name="Python", status="MISSING", importance="CORE", target_level="Beginner"):
    return CourseSkill(
        ref=ref,
        skill_id=skill_id,
        skill_name=skill_name,
        status=status,
        priority="HIGH",
        importance=importance,
        target_level=target_level,
    )


def search_item(video_id="dQw4w9WgXcQ") -> dict:
    return {"id": {"kind": "youtube#video", "videoId": video_id}, "snippet": {"title": "irrelevant here"}}


def video_item(
    video_id="dQw4w9WgXcQ",
    title="Python Full Course for Beginners",
    description="Learn python basics in this course.",
    channel_title="Example Academy",
    duration="PT1H20M",
    view_count="12345",
    like_count="678",
    published_at="2026-01-01T00:00:00Z",
    thumbnails=None,
    **overrides,
) -> dict:
    item = {
        "id": video_id,
        "snippet": {
            "title": title,
            "description": description,
            "channelId": "UCabc123",
            "channelTitle": channel_title,
            "publishedAt": published_at,
            "thumbnails": thumbnails
            if thumbnails is not None
            else {"high": {"url": "https://i.ytimg.com/vi/x/hqdefault.jpg"}},
        },
        "contentDetails": {"duration": duration} if duration is not None else {},
        "statistics": {
            k: v
            for k, v in {"viewCount": view_count, "likeCount": like_count}.items()
            if v is not None
        },
    }
    item.update(overrides)
    return item


def _resp(status_code=200, json_body=None, raise_json=None):
    response = MagicMock()
    response.status_code = status_code
    if raise_json is not None:
        response.json.side_effect = raise_json
    else:
        response.json.return_value = json_body
    return response


def _get_router(search_items=None, video_items=None, search_error=None, videos_error=None):
    """A fake httpx.get that dispatches on the request URL -- search.list
    vs videos.list -- mirroring the two real endpoints."""

    def fake_get(url, **kwargs):
        if url == yt._SEARCH_URL:
            if search_error is not None:
                return search_error
            return _resp(json_body={"items": search_items or []})
        if url == yt._VIDEOS_URL:
            if videos_error is not None:
                return videos_error
            return _resp(json_body={"items": video_items or []})
        raise AssertionError(f"unexpected url {url}")

    return fake_get


# ---- Config / availability ----


def test_unconfigured_returns_unconfigured_provider():
    with patch.object(yt, "youtube_settings", YouTubeSettings(youtube_api_key="")):
        provider = yt.get_youtube_provider()
    assert provider.available is False
    assert provider.search_for_skill("Python", "Beginner", limit=3) == []


def test_configured_returns_youtube_provider():
    with patch.object(yt, "youtube_settings", configured_settings()):
        provider = yt.get_youtube_provider()
    assert isinstance(provider, yt.YouTubeLearningProvider)
    assert provider.available is True


def test_discover_for_skills_no_skills_never_calls_network():
    with (
        patch.object(yt, "youtube_settings", configured_settings()),
        patch.object(yt.httpx, "get") as get,
        patch.object(yt.httpx, "post") as post,
    ):
        found, status = yt.discover_for_skills([])
    assert found == [] and status == "AVAILABLE"
    get.assert_not_called()
    post.assert_not_called()


def test_unconfigured_provider_yields_configuration_required():
    with patch.object(yt, "youtube_settings", YouTubeSettings(youtube_api_key="")):
        found, status = yt.discover_for_skills([skill()])
    assert found == [] and status == "CONFIGURATION_REQUIRED"


def test_secret_never_appears_in_unavailable_message():
    provider = yt.YouTubeLearningProvider(configured_settings(api_key="super-secret-api-key"))
    with (
        patch.object(yt.httpx, "get", return_value=_resp(status_code=403, json_body={})),
        pytest.raises(yt.YouTubeUnavailable) as excinfo,
    ):
        provider.search_for_skill("Python", "Beginner", limit=3)
    assert "super-secret-api-key" not in str(excinfo.value)


# ---- search.list + videos.list normalization ----


def test_successful_search_and_enrich_normalizes_candidate():
    provider = yt.YouTubeLearningProvider(configured_settings())
    with patch.object(
        yt.httpx, "get", side_effect=_get_router(search_items=[search_item()], video_items=[video_item()])
    ):
        result = provider.search_for_skill("Python", "Beginner", limit=3)
    assert len(result) == 1
    candidate = result[0]
    assert candidate.video_id == "dQw4w9WgXcQ"
    assert candidate.title == "Python Full Course for Beginners"
    assert candidate.channel_title == "Example Academy"
    assert candidate.watch_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert candidate.duration_text == "1h 20m"
    assert candidate.view_count == 12345
    assert candidate.like_count == 678
    assert candidate.source == "YouTube"
    assert candidate.resource_type == "VIDEO"
    assert candidate.metadata_source == "YOUTUBE_DATA_API"
    assert candidate.thumbnail_url.startswith("https://")


def test_empty_search_results_yield_no_candidates():
    provider = yt.YouTubeLearningProvider(configured_settings())
    with patch.object(yt.httpx, "get", side_effect=_get_router(search_items=[])):
        assert provider.search_for_skill("Python", "Beginner", limit=3) == []


def test_malformed_search_item_missing_video_id_skipped():
    provider = yt.YouTubeLearningProvider(configured_settings())
    broken = [{"id": {}, "snippet": {}}, {"id": {"videoId": "short"}}, None]
    with patch.object(yt.httpx, "get", side_effect=_get_router(search_items=broken)):
        assert provider.search_for_skill("Python", "Beginner", limit=3) == []


def test_malformed_video_item_missing_title_or_channel_skipped():
    provider = yt.YouTubeLearningProvider(configured_settings())
    items = [
        {"id": "aaaaaaaaaaa", "snippet": {"title": "", "channelTitle": "X"}},
        {"id": "bbbbbbbbbbb", "snippet": {"title": "Python course", "channelTitle": ""}},
        {"id": "ccccccccccc"},
        video_item(video_id="ddddddddddd"),
    ]
    with patch.object(
        yt.httpx,
        "get",
        side_effect=_get_router(
            search_items=[search_item(i) for i in ("aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc", "ddddddddddd")],
            video_items=items,
        ),
    ):
        result = provider.search_for_skill("Python", "Beginner", limit=3)
    assert len(result) == 1
    assert result[0].video_id == "ddddddddddd"


def test_deleted_or_private_video_omitted_from_videos_list_is_skipped():
    """videos.list simply omits an ID that's now private/deleted -- the
    provider must not crash or fabricate a placeholder for it."""
    provider = yt.YouTubeLearningProvider(configured_settings())
    with patch.object(
        yt.httpx,
        "get",
        side_effect=_get_router(
            search_items=[search_item("aaaaaaaaaaa"), search_item("bbbbbbbbbbb")],
            video_items=[video_item(video_id="aaaaaaaaaaa")],
        ),
    ):
        result = provider.search_for_skill("Python", "Beginner", limit=3)
    assert len(result) == 1
    assert result[0].video_id == "aaaaaaaaaaa"


def test_irrelevant_video_excluded_by_relevance_filter():
    provider = yt.YouTubeLearningProvider(configured_settings())
    unrelated = video_item(title="Excel spreadsheets for beginners", description="Learn Excel basics.")
    with patch.object(
        yt.httpx, "get", side_effect=_get_router(search_items=[search_item()], video_items=[unrelated])
    ):
        assert provider.search_for_skill("Python", "Beginner", limit=3) == []


def test_missing_statistics_and_duration_stay_null_not_guessed():
    provider = yt.YouTubeLearningProvider(configured_settings())
    sparse = video_item(duration=None, view_count=None, like_count=None)
    with patch.object(
        yt.httpx, "get", side_effect=_get_router(search_items=[search_item()], video_items=[sparse])
    ):
        result = provider.search_for_skill("Python", "Beginner", limit=3)
    assert len(result) == 1
    candidate = result[0]
    assert candidate.duration_text is None
    assert candidate.duration_iso8601 is None
    assert candidate.view_count is None
    assert candidate.like_count is None


@pytest.mark.parametrize(
    "iso,seconds,text",
    [
        ("PT45M", 2700, "45m"),
        ("PT1H20M", 4800, "1h 20m"),
        ("PT2H", 7200, "2h"),
        ("PT30S", 30, "30s"),
        ("garbage", None, None),
        ("PT0S", None, None),
        (None, None, None),
    ],
)
def test_duration_parsing(iso, seconds, text):
    assert yt.parse_duration(iso) == (seconds, text)


# ---- Failure handling: timeout / 4xx / 429/quota / 5xx / malformed JSON ----


def test_search_timeout_raises_temporarily_unavailable():
    provider = yt.YouTubeLearningProvider(configured_settings())
    with (
        patch.object(yt.httpx, "get", side_effect=httpx.TimeoutException("timed out")),
        pytest.raises(yt.YouTubeUnavailable) as excinfo,
    ):
        provider.search_for_skill("Python", "Beginner", limit=3)
    assert excinfo.value.status == "TEMPORARILY_UNAVAILABLE"


def test_search_403_key_invalid_raises_failed():
    provider = yt.YouTubeLearningProvider(configured_settings())
    error_body = {"error": {"errors": [{"reason": "keyInvalid"}]}}
    with patch.object(
        yt.httpx, "get", side_effect=_get_router(search_error=_resp(403, error_body))
    ), pytest.raises(yt.YouTubeUnavailable) as excinfo:
        provider.search_for_skill("Python", "Beginner", limit=3)
    assert excinfo.value.status == "FAILED"


@pytest.mark.parametrize("status_code,reason", [(403, "quotaExceeded"), (429, None)])
def test_quota_exceeded_classified_correctly(status_code, reason):
    provider = yt.YouTubeLearningProvider(configured_settings())
    body = {"error": {"errors": [{"reason": reason}]}} if reason else {}
    with patch.object(
        yt.httpx, "get", side_effect=_get_router(search_error=_resp(status_code, body))
    ), pytest.raises(yt.YouTubeUnavailable) as excinfo:
        provider.search_for_skill("Python", "Beginner", limit=3)
    assert excinfo.value.status == "QUOTA_EXCEEDED"


def test_5xx_raises_temporarily_unavailable():
    provider = yt.YouTubeLearningProvider(configured_settings())
    with (
        patch.object(yt.httpx, "get", side_effect=_get_router(search_error=_resp(503, {}))),
        pytest.raises(yt.YouTubeUnavailable) as excinfo,
    ):
        provider.search_for_skill("Python", "Beginner", limit=3)
    assert excinfo.value.status == "TEMPORARILY_UNAVAILABLE"


def test_malformed_json_raises_failed():
    provider = yt.YouTubeLearningProvider(configured_settings())
    bad = _resp(200, raise_json=json.JSONDecodeError("bad", "doc", 0))
    with (
        patch.object(yt.httpx, "get", side_effect=_get_router(search_error=bad)),
        pytest.raises(yt.YouTubeUnavailable) as excinfo,
    ):
        provider.search_for_skill("Python", "Beginner", limit=3)
    assert excinfo.value.status == "FAILED"


def test_videos_list_failure_also_raises_unavailable():
    provider = yt.YouTubeLearningProvider(configured_settings())
    with patch.object(
        yt.httpx,
        "get",
        side_effect=_get_router(search_items=[search_item()], videos_error=_resp(500, {})),
    ), pytest.raises(yt.YouTubeUnavailable) as excinfo:
        provider.search_for_skill("Python", "Beginner", limit=3)
    assert excinfo.value.status == "TEMPORARILY_UNAVAILABLE"


# ---- Cache ----


def test_first_query_miss_second_query_hit_no_extra_search_call():
    provider = yt.YouTubeLearningProvider(configured_settings())
    with patch.object(
        yt.httpx, "get", side_effect=_get_router(search_items=[search_item()], video_items=[video_item()])
    ) as get:
        provider.search_for_skill("Python", "Beginner", limit=3)
        provider.search_for_skill("Python", "Beginner", limit=3)
    assert get.call_count == 2  # one search.list + one videos.list, ONCE total


def test_cache_expiry_triggers_new_call():
    provider = yt.YouTubeLearningProvider(configured_settings(ttl=1))
    with (
        patch.object(
            yt.httpx, "get", side_effect=_get_router(search_items=[search_item()], video_items=[video_item()])
        ) as get,
        patch.object(yt.time, "monotonic", side_effect=[0.0, 10_000.0]),
    ):
        provider.search_for_skill("Python", "Beginner", limit=3)
        provider.search_for_skill("Python", "Beginner", limit=3)
    assert get.call_count == 4  # two full round trips


def test_different_level_uses_separate_cache_key():
    provider = yt.YouTubeLearningProvider(configured_settings())
    with patch.object(
        yt.httpx, "get", side_effect=_get_router(search_items=[search_item()], video_items=[video_item()])
    ) as get:
        provider.search_for_skill("Python", "Beginner", limit=3)
        provider.search_for_skill("Python", "Intermediate", limit=3)
    assert get.call_count == 4  # separate keys -> two full round trips


def test_cache_is_bounded():
    now = 0.0
    for i in range(yt._YouTubeSearchCache._MAX_ENTRIES + 10):
        yt._search_cache.set((f"skill-{i}", "Beginner"), [], now, 21600)
    assert len(yt._search_cache._store) == yt._YouTubeSearchCache._MAX_ENTRIES
    assert ("skill-0", "Beginner") not in yt._search_cache._store  # oldest evicted


# ---- Quota safety ----


def test_max_three_skills_searched_per_request():
    skills = [skill(f"G{n}", f"skill-{n}", f"Skill{n}") for n in range(1, 6)]
    provider = MagicMock()
    provider.available = True
    provider.search_for_skill.return_value = []
    with patch.object(yt, "get_youtube_provider", return_value=provider):
        yt.discover_for_skills(skills)
    assert provider.search_for_skill.call_count == yt.MAX_SKILLS_PER_REQUEST == 3


def test_one_search_call_per_unique_uncached_query_duplicate_skills():
    skills = [skill("G1", "id-a", "Python"), skill("G2", "id-b", "Python")]
    with patch.object(
        yt,
        "youtube_settings",
        configured_settings(),
    ), patch.object(
        yt.httpx, "get", side_effect=_get_router(search_items=[search_item()], video_items=[video_item()])
    ) as get:
        found, status = yt.discover_for_skills(skills)
    assert get.call_count == 2  # ONE search.list + ONE videos.list total, not doubled
    assert status == "AVAILABLE"
    assert {c.skill_id for c in found} == {"id-a", "id-b"}


def test_no_pagination_only_one_get_per_endpoint():
    provider = yt.YouTubeLearningProvider(configured_settings())
    with patch.object(
        yt.httpx, "get", side_effect=_get_router(search_items=[search_item()], video_items=[video_item()])
    ) as get:
        provider.search_for_skill("Python", "Beginner", limit=3)
    urls = [call.args[0] for call in get.call_args_list]
    assert urls == [yt._SEARCH_URL, yt._VIDEOS_URL]


def test_videos_list_batched_in_one_call_for_multiple_ids():
    provider = yt.YouTubeLearningProvider(configured_settings())
    ids = ["aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"]
    with patch.object(
        yt.httpx,
        "get",
        side_effect=_get_router(
            search_items=[search_item(i) for i in ids], video_items=[video_item(video_id=i) for i in ids]
        ),
    ) as get:
        result = provider.search_for_skill("Python", "Beginner", limit=5)
    videos_call = next(c for c in get.call_args_list if c.args[0] == yt._VIDEOS_URL)
    assert videos_call.kwargs["params"]["id"] == ",".join(ids)
    assert len(result) == 3


def test_discover_for_skills_isolates_one_skill_failure_from_another():
    skills = [skill("G1", "id-a", "Python"), skill("G2", "id-b", "SQL")]
    provider = MagicMock()
    provider.available = True

    def side_effect(skill_name, target_level, *, limit):
        if skill_name == "Python":
            raise yt.YouTubeUnavailable("QUOTA_EXCEEDED")
        return [video_item_candidate("id-b")]

    provider.search_for_skill.side_effect = side_effect
    with patch.object(yt, "get_youtube_provider", return_value=provider):
        found, status = yt.discover_for_skills(skills)
    assert status == "AVAILABLE"
    assert len(found) == 1


def video_item_candidate(skill_id: str) -> YouTubeVideoCandidate:
    return YouTubeVideoCandidate(
        video_id="dQw4w9WgXcQ",
        skill_id=skill_id,
        skill_name="SQL",
        title="SQL tutorial",
        channel_title="Example",
    )


# ---- Grounding / security ----


def _candidate(**overrides) -> YouTubeVideoCandidate:
    defaults = {
        "video_id": "dQw4w9WgXcQ",
        "skill_id": SID,
        "skill_name": "Python",
        "title": "Python beginner full course",
        "description": "Learn python basics",
        "channel_title": "Example Academy",
    }
    defaults.update(overrides)
    return YouTubeVideoCandidate(**defaults)


def _skill_ref(**overrides) -> YouTubeSkillRef:
    defaults = {"ref": "G1", "skill_id": SID, "skill_name": "Python", "status": "MISSING", "target_level": "Beginner"}
    defaults.update(overrides)
    return YouTubeSkillRef(**defaults)


def test_ground_preserves_metadata_and_reconstructs_ranking():
    candidate = _candidate()
    output = YouTubeLLMOutput(
        recommended_video_refs=["Y1"],
        recommendation_codes=["Y1 -> G1: SKILL_GAP_MATCH"],
        learning_order=["Y1"],
    )
    ranked = ground(output, {"Y1": candidate}, {"G1": _skill_ref()})
    assert len(ranked) == 1
    assert ranked[0].video == candidate
    assert ranked[0].rank == 1
    assert "learning priorities" in ranked[0].reason


@pytest.mark.parametrize(
    "field",
    [
        "title",
        "video_id",
        "watch_url",
        "channel_title",
        "thumbnail_url",
        "duration_text",
        "view_count",
        "published_at",
    ],
)
def test_llm_cannot_supply_video_metadata(field):
    with pytest.raises(ValidationError):
        YouTubeLLMOutput.model_validate(
            {
                "recommended_video_refs": ["Y1"],
                "recommendation_codes": ["Y1 -> G1: SKILL_GAP_MATCH"],
                "learning_order": ["Y1"],
                field: "invented",
            }
        )


@pytest.mark.parametrize(
    "code_line",
    [
        "Y99 -> G1: SKILL_GAP_MATCH",
        "Y1 -> G99: SKILL_GAP_MATCH",
        "Y1 -> G1: FAKE_CODE",
        "Y1 -> G1: https://invented.test",
        "Y1: provider=Fake",
    ],
)
def test_unknown_refs_and_unapproved_codes_drop(code_line):
    output = YouTubeLLMOutput(
        recommended_video_refs=["Y1", "Y99"], recommendation_codes=[code_line], learning_order=["Y99", "Y1"]
    )
    assert ground(output, {"Y1": _candidate()}, {"G1": _skill_ref()}) == []


def test_level_match_requires_real_title_evidence():
    output = YouTubeLLMOutput(
        recommended_video_refs=["Y1"], recommendation_codes=["Y1 -> G1: LEVEL_MATCH"], learning_order=["Y1"]
    )
    no_evidence = _candidate(title="Python advanced deep dive", description=None)
    assert ground(output, {"Y1": no_evidence}, {"G1": _skill_ref(target_level="Beginner")}) == []
    with_evidence = _candidate(title="Python beginner crash course")
    ranked = ground(output, {"Y1": with_evidence}, {"G1": _skill_ref(target_level="Beginner")})
    assert len(ranked) == 1


def test_video_id_must_be_valid_pattern():
    with pytest.raises(ValidationError):
        _candidate(video_id="not-an-id!!")


def test_watch_url_is_always_derived_from_video_id():
    candidate = _candidate(video_id="abcdefghijk")
    assert candidate.watch_url == "https://www.youtube.com/watch?v=abcdefghijk"


def test_thumbnail_must_be_https():
    with pytest.raises(ValidationError):
        _candidate(thumbnail_url="http://insecure.example.com/thumb.jpg")


def test_html_entities_and_control_chars_cleaned():
    provider = yt.YouTubeLearningProvider(configured_settings())
    dirty = video_item(title="Python &amp; SQL Course", description="Line1\x07Line2 &lt;tag&gt;")
    with patch.object(
        yt.httpx, "get", side_effect=_get_router(search_items=[search_item()], video_items=[dirty])
    ):
        result = provider.search_for_skill("Python", "Beginner", limit=3)
    assert result[0].title == "Python & SQL Course"
    assert "\x07" not in result[0].description
    assert "<tag>" in result[0].description


def test_deterministic_recommendations_used_when_no_ai():
    candidates = {"Y1": _candidate()}
    skills = {"G1": _skill_ref()}
    ranked = deterministic_recommendations(candidates, skills)
    assert len(ranked) == 1
    assert ranked[0].reason == "This video is for a skill in your learning priorities."


# ---- Agent-level pipeline ----


def _canonical_with_skills(*skills_list) -> CourseCanonical:
    from app.schemas.skill_gap import AnalysisMode

    return CourseCanonical(mode=AnalysisMode.JOB_ROLE, target_role="Backend Developer", skills_considered=list(skills_list))


def test_select_youtube_skills_prioritizes_missing_core_first():
    canonical = _canonical_with_skills(
        skill("G1", "s1", "A", status="NEEDS_IMPROVEMENT", importance="CORE"),
        skill("G2", "s2", "B", status="MISSING", importance="IMPORTANT"),
        skill("G3", "s3", "C", status="MISSING", importance="CORE"),
    )
    top = yt_agent.select_youtube_skills(canonical)
    assert [s.skill_name for s in top] == ["C", "A", "B"]


def test_select_youtube_skills_caps_at_three():
    canonical = _canonical_with_skills(*[skill(f"G{n}", f"s{n}", f"Skill{n}") for n in range(1, 6)])
    assert len(yt_agent.select_youtube_skills(canonical)) == 3


def test_no_skill_gaps_means_no_youtube_call():
    canonical = _canonical_with_skills()
    with patch.object(yt, "discover_for_skills") as discover:
        recs, available, ai_available, status = yt_agent.recommend_youtube_videos(canonical)
    discover.assert_not_called()
    assert recs == [] and not available and not ai_available and status == "CONFIGURATION_REQUIRED"


def test_agent_unexpected_groq_error_propagates_for_outer_isolation():
    """Only AIError subclasses degrade to deterministic ranking here
    (see test_agent_ai_error_falls_back_to_deterministic) -- a genuinely
    unexpected exception propagates up to
    course_recommendation_agent.recommend_courses()'s own outer
    try/except, which isolates the whole YouTube channel from courses
    (see test_youtube_failure_does_not_affect_course_recommendations)."""
    canonical = _canonical_with_skills(skill())
    candidate = _candidate()
    with (
        patch.object(yt_agent.youtube_learning, "discover_for_skills", return_value=([candidate], "AVAILABLE")),
        patch.object(yt_agent.groq_client, "complete_structured", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        yt_agent.recommend_youtube_videos(canonical)


def test_agent_ai_error_falls_back_to_deterministic():
    from app.ai.exceptions import AIProviderError

    canonical = _canonical_with_skills(skill())
    candidate = _candidate()
    with (
        patch.object(yt_agent.youtube_learning, "discover_for_skills", return_value=([candidate], "AVAILABLE")),
        patch.object(yt_agent.groq_client, "complete_structured", side_effect=AIProviderError("private")),
    ):
        recs, available, ai_available, status = yt_agent.recommend_youtube_videos(canonical)
    assert len(recs) == 1 and available and not ai_available and status == "AVAILABLE"
    assert "private" not in recs[0].reason


def test_agent_uses_groq_ranking_when_available():
    canonical = _canonical_with_skills(skill())
    candidate = _candidate()
    output = YouTubeLLMOutput(
        recommended_video_refs=["Y1"], recommendation_codes=["Y1 -> G1: SKILL_GAP_MATCH"], learning_order=["Y1"]
    )
    with (
        patch.object(yt_agent.youtube_learning, "discover_for_skills", return_value=([candidate], "AVAILABLE")),
        patch.object(yt_agent.groq_client, "complete_structured", return_value=output),
    ):
        recs, _available, ai_available, _status = yt_agent.recommend_youtube_videos(canonical)
    assert ai_available and len(recs) == 1


# ---- Full course_recommendation_agent integration ----


def test_youtube_present_when_course_discovery_degrades():
    """discover_candidates() already isolates its own internal/external
    failures and never raises (see app.ai.tools.course_discovery) --
    the realistic failure shape is a degraded return, not an
    exception. YouTube must still populate independently of it."""
    with (
        patch.object(agent.skill_gap_tools, "get_current_skill_gap", return_value=_job_role_section()),
        patch.object(discovery, "discover_candidates", return_value=([], False, "FAILED")),
        patch.object(
            yt_agent.youtube_learning,
            "discover_for_skills",
            return_value=([_candidate()], "AVAILABLE"),
        ),
    ):
        result = agent.recommend_courses(MagicMock(), "student")
    assert result.recommendations == []
    assert result.meta.internal_discovery_available is False
    assert len(result.youtube_videos) == 1


def test_youtube_failure_does_not_affect_course_recommendations():
    from app.ai.tools import course_discovery as course_disc

    internal = course_disc.CourseCandidate(
        candidate_id="internal:1",
        source_type="INTERNAL",
        title="Internal course",
        url="https://example.org/course",
        skill_ids=[SID],
        skill_names=["Python"],
        metadata_source="learning_resources/learning_resource_skills",
    )
    with (
        patch.object(agent.skill_gap_tools, "get_current_skill_gap", return_value=_job_role_section()),
        patch.object(discovery, "discover_candidates", return_value=([internal], True, "CONFIGURATION_REQUIRED")),
        patch.object(yt_agent.youtube_learning, "discover_for_skills", return_value=([], "TEMPORARILY_UNAVAILABLE")),
    ):
        result = agent.recommend_courses(MagicMock(), "student")
    assert result.recommendations and result.recommendations[0].course == internal
    assert result.youtube_videos == []
    assert result.meta.youtube_status == "TEMPORARILY_UNAVAILABLE"


def test_matched_only_student_triggers_no_youtube_search():
    with (
        patch.object(agent.skill_gap_tools, "get_current_skill_gap", return_value=_personal_section()),
        patch.object(yt_agent.youtube_learning, "discover_for_skills") as discover,
    ):
        result = agent.recommend_courses(MagicMock(), "student")
    discover.assert_not_called()
    assert result.meta.ranking_status == "NO_GAPS"
    assert result.youtube_videos == []


def test_full_pipeline_youtube_reaches_response_grounded():
    candidate = _candidate()
    output = YouTubeLLMOutput(
        recommended_video_refs=["Y1"], recommendation_codes=["Y1 -> G1: SKILL_GAP_MATCH"], learning_order=["Y1"]
    )
    with (
        patch.object(agent.skill_gap_tools, "get_current_skill_gap", return_value=_job_role_section()),
        patch.object(discovery, "discover_candidates", return_value=([], True, "CONFIGURATION_REQUIRED")),
        patch.object(
            yt_agent.youtube_learning, "discover_for_skills", return_value=([candidate], "AVAILABLE")
        ),
        patch.object(yt_agent.groq_client, "complete_structured", return_value=output),
    ):
        result = agent.recommend_courses(MagicMock(), "student")
    assert len(result.youtube_videos) == 1
    yt_rec = result.youtube_videos[0]
    assert yt_rec.video.title == candidate.title
    assert yt_rec.video.watch_url == candidate.watch_url
    assert result.meta.youtube_available and result.meta.youtube_ai_ranking_available
    assert result.meta.youtube_status == "AVAILABLE"


# ---- API ----


def test_api_returns_youtube_videos_when_configured():
    candidate = _candidate()
    with (
        authenticated_as("STUDENT", user_id="authenticated-student"),
        patch.object(agent.skill_gap_tools, "get_current_skill_gap", return_value=_job_role_section()),
        patch.object(discovery, "discover_candidates", return_value=([], True, "CONFIGURATION_REQUIRED")),
        patch.object(
            yt_agent.youtube_learning, "discover_for_skills", return_value=([candidate], "AVAILABLE")
        ),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/course-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["youtube_status"] == "AVAILABLE"
    assert len(data["youtube_videos"]) == 1
    assert data["youtube_videos"][0]["video"]["source"] == "YouTube"
    assert data["youtube_videos"][0]["video"]["watch_url"] == candidate.watch_url


def test_api_youtube_unconfigured_does_not_break_internal_results():
    from app.ai.tools import course_discovery as course_disc

    internal = course_disc.CourseCandidate(
        candidate_id="internal:1",
        source_type="INTERNAL",
        title="Internal course",
        url="https://example.org/course",
        skill_ids=[SID],
        skill_names=["Python"],
        metadata_source="learning_resources/learning_resource_skills",
    )
    with (
        authenticated_as("STUDENT"),
        patch.object(agent.skill_gap_tools, "get_current_skill_gap", return_value=_job_role_section()),
        patch.object(discovery, "discover_candidates", return_value=([internal], True, "CONFIGURATION_REQUIRED")),
        # Forces the scenario this test is actually about, regardless of
        # whether a real YOUTUBE_API_KEY happens to be configured in the
        # local dev environment.
        patch.object(agent, "recommend_youtube_videos", return_value=([], False, False, "CONFIGURATION_REQUIRED")),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/course-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["youtube_status"] == "CONFIGURATION_REQUIRED"
    assert data["youtube_videos"] == []
    assert len(data["recommendations"]) == 1


def test_api_quota_exceeded_does_not_fail_endpoint():
    with (
        authenticated_as("STUDENT"),
        patch.object(agent.skill_gap_tools, "get_current_skill_gap", return_value=_job_role_section()),
        patch.object(discovery, "discover_candidates", return_value=([], True, "CONFIGURATION_REQUIRED")),
        patch.object(
            yt_agent.youtube_learning, "discover_for_skills", return_value=([], "QUOTA_EXCEEDED")
        ),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/course-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["meta"]["youtube_status"] == "QUOTA_EXCEEDED"


def test_api_no_provider_internals_leaked():
    with (
        authenticated_as("STUDENT"),
        patch.object(agent.skill_gap_tools, "get_current_skill_gap", return_value=_job_role_section()),
        patch.object(discovery, "discover_candidates", return_value=([], True, "CONFIGURATION_REQUIRED")),
        patch.object(
            yt_agent.youtube_learning,
            "discover_for_skills",
            side_effect=RuntimeError("gaia_key=AIzaSecretValue quotaExceeded raw json"),
        ),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/course-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert "AIzaSecretValue" not in response.text


def test_career_guidance_includes_youtube_videos():
    candidate = _candidate()
    output = YouTubeLLMOutput(
        recommended_video_refs=["Y1"], recommendation_codes=["Y1 -> G1: SKILL_GAP_MATCH"], learning_order=["Y1"]
    )
    with (
        authenticated_as("STUDENT"),
        patch.object(agent.skill_gap_tools, "get_current_skill_gap", return_value=_job_role_section()),
        patch.object(discovery, "discover_candidates", return_value=([], True, "CONFIGURATION_REQUIRED")),
        patch.object(
            yt_agent.youtube_learning, "discover_for_skills", return_value=([candidate], "AVAILABLE")
        ),
        patch.object(yt_agent.groq_client, "complete_structured", return_value=output),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/career-guidance", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data["youtube_videos"]) == 1
    assert data["youtube_videos"][0]["video"]["title"] == candidate.title


def test_populated_agent_runs_real_client_validation_with_mocked_network():
    """One real GroqClient (schema validation, retries, etc. all real)
    with only the network call itself mocked -- mirrors the equivalent
    course_recommendation test."""
    candidate = _candidate()
    canonical = _canonical_with_skills(skill())
    output = YouTubeLLMOutput(
        recommended_video_refs=["Y1"], recommendation_codes=["Y1 -> G1: SKILL_GAP_MATCH"], learning_order=["Y1"]
    )
    client = GroqClient(AISettings(groq_api_key="test-only"))
    completion = MagicMock()
    completion.choices[0].message.content = output.model_dump_json()
    with (
        patch.object(yt_agent.youtube_learning, "discover_for_skills", return_value=([candidate], "AVAILABLE")),
        patch.object(yt_agent, "groq_client", client),
        patch.object(client, "_create_completion", return_value=completion) as network,
    ):
        recs, _available, ai_available, _status = yt_agent.recommend_youtube_videos(canonical)
    assert ai_available
    assert recs[0].video.video_id == candidate.video_id
    assert recs[0].video.title == candidate.title
    payload = json.loads(network.call_args.kwargs["messages"][1]["content"])
    assert payload["video_candidates"][0]["ref"] == "Y1"
    assert "video_id" not in payload["video_candidates"][0]
    assert "watch_url" not in payload["video_candidates"][0]
