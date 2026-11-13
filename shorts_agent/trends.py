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


def discover(limit=20):
    """Official YouTube API, not a 'trending Reels' API. Seed/manual fallback."""
    items = []
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if key:
        try:
            base = "https://www.googleapis.com/youtube/v3"
            recent = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=4)).isoformat().replace("+00:00", "Z")
            # Search for recent short-duration Indian videos, then rank by views/hour.
            ids = []
            for query in ("hindi comedy shorts", "india funny reels", "indian relatable shorts"):
                data = _get(base + "/search", {
                    "part": "snippet", "type": "video", "regionCode": "IN",
                    "relevanceLanguage": "hi", "videoDuration": "short",
                    "order": "viewCount", "publishedAfter": recent,
                    "maxResults": 20, "q": query, "key": key,
                })
                ids.extend(v["id"]["videoId"] for v in data.get("items", []) if v.get("id", {}).get("videoId"))
            ids = list(dict.fromkeys(ids))[:50]
            if ids:
                response = _get(base + "/videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids), "key": key})
                now = dt.datetime.now(dt.timezone.utc)
                for v in response.get("items", []):
                    sn = v["snippet"]
                    published = dt.datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
                    age_hours = max((now - published).total_seconds() / 3600, 1)
                    views = int(v.get("statistics", {}).get("viewCount", 0))
                    likes = int(v.get("statistics", {}).get("likeCount", 0))
                    # This is only a trend signal: not proof that a specific video is a Short.
                    score = math.log1p(views / age_hours) + 0.2 * math.log1p(likes)
                    items.append({"title": sn["title"][:160], "theme": "inspired by public Indian YouTube trends", "source": "youtube", "video_id": v["id"], "score": round(score, 2)})
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Trend API unavailable; continuing with curated ideas: {e}")
    manual = ROOT / "manual_trends.json"
    if manual.exists():
        try:
            for title in json.loads(manual.read_text(encoding="utf-8")):
                if isinstance(title, str) and title.strip():
                    items.append({"title": title[:160], "theme": "manually supplied Indian trend", "source": "manual", "score": 15})
        except (ValueError, OSError) as e:
            print(f"manual_trends.json invalid: {e}")
    items.sort(key=lambda x: x.get("score", 0), reverse=True)
    items.extend(SEED_TOPICS)
    return items[:limit]
