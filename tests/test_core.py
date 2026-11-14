import ast
from pathlib import Path

import pytest

from shorts_agent.main import get_slots
from shorts_agent.writer import SCENE_COUNT, SCENE_SECONDS, _valid_script, fallback_script
from shorts_agent.trends import SEED_TOPICS, discover
from shorts_agent.publish import _truthy
from shorts_agent.video_api import build_segment_prompts, _video_output, target_seconds


def test_fallback_has_twenty_four_second_six_scene_story():
    result = fallback_script(SEED_TOPICS[0], 1)
    assert _valid_script(result)
    assert len(result["scenes"]) == SCENE_COUNT == 6
    assert result["duration_seconds"] == SCENE_COUNT * SCENE_SECONDS == 24


def test_youtube_create_prompts_are_three_short_mobile_prompts():
    result = fallback_script(SEED_TOPICS[0], 1)
    prompts = result["yt_create_prompts"]
    assert len(prompts) == 3
    assert all(30 <= len(prompt) <= 900 for prompt in prompts)
    assert all("vertical 9:16" in prompt for prompt in prompts)


def test_invalid_script_without_prompts_is_rejected():
    result = fallback_script(SEED_TOPICS[0], 1)
    result.pop("yt_create_prompts")
    assert not _valid_script(result)


def test_slot_selection():
    assert get_slots("1") == [1]
    assert get_slots("2") == [2]
    assert get_slots("all") == [1, 2]
    with pytest.raises(ValueError):
        get_slots("3")


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_truthy_values(value):
    assert _truthy(value)


@pytest.mark.parametrize("value", ["false", "0", "", None, "no"])
def test_falsey_values(value):
    assert not _truthy(value)


def test_all_python_modules_parse():
    for path in Path("shorts_agent").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_publishing_module_has_valid_syntax():
    path = Path("shorts_agent/publish.py")
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_india_chart_video_ranks_above_manual_and_seed_topics(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("TRENDS_REGION", "IN")
    monkeypatch.setenv("TRENDS_LANGUAGE", "hi")

    def fake_get(url, params):
        if url.endswith("/videos") and params.get("chart") == "mostPopular":
            return {
                "items": [{
                    "id": "viral-india-1",
                    "snippet": {
                        "title": "Current India viral topic",
                        "publishedAt": "2026-11-14T08:00:00Z",
                    },
                    "statistics": {"viewCount": "500000", "likeCount": "12000"},
                }]
            }
        if url.endswith("/search"):
            return {"items": []}
        if url.endswith("/videos"):
            return {"items": []}
        raise AssertionError(f"Unexpected endpoint: {url}")

    monkeypatch.setattr("shorts_agent.trends._get", fake_get)
    topics = discover()
    assert topics[0]["video_id"] == "viral-india-1"
    assert topics[0]["source"] == "youtube_most_popular_in"


def test_chart_error_does_not_prevent_recent_shorts_search(monkeypatch):
    from requests import HTTPError

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    search_calls = []

    def fake_get(url, params):
        if url.endswith("/videos") and params.get("chart") == "mostPopular":
            raise HTTPError("chart unavailable for test")
        if url.endswith("/search"):
            search_calls.append(params["q"])
            return {"items": [{"id": {"videoId": "recent-1"}}]}
        if url.endswith("/videos"):
            return {
                "items": [{
                    "id": "recent-1",
                    "snippet": {
                        "title": "Recent India short",
                        "publishedAt": "2026-11-14T08:00:00Z",
                    },
                    "statistics": {"viewCount": "100000", "likeCount": "2000"},
                }]
            }
        raise AssertionError(f"Unexpected endpoint: {url}")

    monkeypatch.setattr("shorts_agent.trends._get", fake_get)
    topics = discover()
    assert len(search_calls) == 4
    assert any(topic.get("video_id") == "recent-1" for topic in topics)


def test_gemini_cloud_video_builds_two_continuous_segments_for_twenty_seconds():
    script = fallback_script(SEED_TOPICS[0], 1)
    prompts = build_segment_prompts(script, 20)
    assert len(prompts) == 2
    assert prompts[0]["task"] == "text_to_video"
    assert prompts[1]["task"] == "extend"
    assert "vertical 9:16" in prompts[0]["input"]
    assert "seamlessly" in prompts[1]["input"].lower()


def test_gemini_cloud_video_builds_three_segments_for_thirty_seconds():
    script = fallback_script(SEED_TOPICS[0], 1)
    prompts = build_segment_prompts(script, 30)
    assert len(prompts) == 3
    assert [item["task"] for item in prompts] == ["text_to_video", "extend", "extend"]


def test_gemini_video_output_parser_supports_raw_interactions_rest_schema():
    payload = {
        "steps": [{
            "type": "model_output",
            "content": [{
                "type": "video",
                "mime_type": "video/mp4",
                "uri": "https://generativelanguage.googleapis.com/v1beta/files/video-123:download?alt=media",
            }],
        }]
    }
    result = _video_output(payload)
    assert result["mime_type"] == "video/mp4"
    assert "video-123" in result["uri"]


@pytest.mark.parametrize("seconds", ["20", "30"])
def test_gemini_video_duration_configuration(monkeypatch, seconds):
    monkeypatch.setenv("GEMINI_VIDEO_TARGET_SECONDS", seconds)
    assert target_seconds() == int(seconds)


def test_gemini_video_duration_rejects_unbounded_or_invalid_cost_settings(monkeypatch):
    monkeypatch.setenv("GEMINI_VIDEO_TARGET_SECONDS", "60")
    with pytest.raises(ValueError):
        target_seconds()
