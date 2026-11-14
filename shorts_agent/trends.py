"""Find public popular/recent Indian YouTube videos; never download or reuse them."""
import datetime as dt
import json
import math
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SEED_TOPICS = [
    {"title": "Indian family WhatsApp group ka drama", "theme": "relatable family comedy", "source": "evergreen"},
    {"title": "UPI payment ke baad awkward moment", "theme": "digital payments daily-life comedy", "source": "evergreen"},
    {"title": "Office meeting vs chai break", "theme": "workplace comedy", "source": "evergreen"},
    {"title": "Indian train journey aur phone charger", "theme": "travel comedy", "source": "evergreen"},
    {"title": "Online delivery ghar mein aate hi", "theme": "shopping comedy", "source": "evergreen"},
]


def _get(url, params):
    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()
    return response.json()


def _score_video(video, now):
    snippet = video.get("snippet", {})
    published_at = snippet.get("publishedAt")
    if not published_at:
        return None
    published = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    age_hours = max((now - published).total_seconds() / 3600, 1)
    statistics = video.get("statistics", {})
    views = int(statistics.get("viewCount", 0))
    likes = int(statistics.get("likeCount", 0))
    return round(math.log1p(views / age_hours) + 0.2 * math.log1p(likes), 2)


def discover(limit=20):
    """Use the official India popular chart and current Hindi/Indian search signals."""
    items = []
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    region_code = os.getenv("TRENDS_REGION", "IN").strip().upper() or "IN"
    language = os.getenv("TRENDS_LANGUAGE", "hi").strip().lower() or "hi"

    if key:
        base = "https://www.googleapis.com/youtube/v3"
        now = dt.datetime.now(dt.timezone.utc)
        recent = (now - dt.timedelta(days=4)).isoformat().replace("+00:00", "Z")

        # Chart and search are independent: a chart-region/API error must not stop search.
        try:
            chart = _get(base + "/videos", {
                "part": "snippet,statistics,contentDetails",
                "chart": "mostPopular",
                "regionCode": region_code,
                "maxResults": 50,
                "key": key,
            })
            for video in chart.get("items", []):
                score = _score_video(video, now)
                if score is None:
                    continue
                snippet = video.get("snippet", {})
                items.append({
                    "title": str(snippet.get("title", ""))[:160],
                    "theme": "current YouTube most-popular chart in India; original idea signal only",
                    "source": "youtube_most_popular_in",
                    "video_id": str(video.get("id", "")),
                    "score": score,
                })
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            print(f"India most-popular chart unavailable; trying search results: {exc}")

        try:
            ids = []
            queries = (
                "hindi comedy shorts",
                "india funny shorts",
                "indian relatable shorts",
                "india trending shorts",
            )
            for query in queries:
                data = _get(base + "/search", {
                    "part": "snippet",
                    "type": "video",
                    "regionCode": region_code,
                    "relevanceLanguage": language,
                    "videoDuration": "short",
                    "order": "viewCount",
                    "publishedAfter": recent,
                    "maxResults": 20,
                    "q": query,
                    "key": key,
                })
                ids.extend(
                    value["id"]["videoId"]
                    for value in data.get("items", [])
                    if value.get("id", {}).get("videoId")
                )
            ids = list(dict.fromkeys(ids))[:50]
            if ids:
                result = _get(base + "/videos", {
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(ids),
                    "key": key,
                })
                for video in result.get("items", []):
                    score = _score_video(video, now)
                    if score is None:
                        continue
                    snippet = video.get("snippet", {})
                    items.append({
                        "title": str(snippet.get("title", ""))[:160],
                        "theme": "recent Indian YouTube Shorts search signal; original idea only",
                        "source": "youtube_recent_search",
                        "video_id": str(video.get("id", "")),
                        "score": score,
                    })
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            print(f"Recent India Shorts search unavailable; continuing with other signals: {exc}")

    manual = ROOT / "manual_trends.json"
    if manual.exists():
        try:
            for title in json.loads(manual.read_text(encoding="utf-8")):
                if isinstance(title, str) and title.strip():
                    items.append({
                        "title": title[:160],
                        "theme": "manually supplied Indian trend",
                        "source": "manual",
                        "score": 0.5,
                    })
        except (ValueError, OSError) as exc:
            print(f"manual_trends.json invalid: {exc}")

    # Keep each public video once and prefer the strongest current signal.
    deduplicated = {}
    for item in items:
        video_id = item.get("video_id")
        key_id = f"video:{video_id}" if video_id else f"{item.get('source')}:{item.get('title')}"
        previous = deduplicated.get(key_id)
        if previous is None or item.get("score", 0) > previous.get("score", 0):
            deduplicated[key_id] = item

    ranked = sorted(deduplicated.values(), key=lambda item: item.get("score", 0), reverse=True)
    ranked.extend(SEED_TOPICS)
    return ranked[:limit]
