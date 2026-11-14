"""Gemini-assisted original Shorts scripts and YouTube Create shot prompts."""
import json
import os
import re

SCENE_SECONDS = 4
SCENE_COUNT = 6


def _shot_prompts(topic):
    """Three optional 8-second YouTube Create / Gemini Omni prompts."""
    base = (
        "Create an original vertical 9:16, 8-second animated comedy shot. "
        "Use a fictional Indian setting, expressive original characters, "
        "clear visual storytelling, bright cinematic lighting, smooth motion, "
        "and no on-screen text. Keep the same character design and art style "
        "across all three shots. Do not imitate any real creator, real person, "
        "existing film, TV character, brand mascot, or copyrighted footage. "
        "No logos, no watermarks, no recognizable songs."
    )
    return [
        f"{base} Shot 1: Establish the fictional scene about {topic}; introduce one relatable visual problem in the first two seconds.",
        f"{base} Shot 2: Escalate the same fictional situation about {topic} with a surprising but harmless visual twist; preserve character and setting continuity.",
        f"{base} Shot 3: Deliver a funny visual payoff to the same {topic} story, then end on a pose or composition that can loop naturally to Shot 1.",
    ]


def fallback_script(topic, slot):
    idea = topic.get("title", "Indian everyday comedy")
    scenes = [
        {"caption": "YE TO HAR GHAR MEIN HOTA HAI!", "narration": "Bhai, aaj ka scene toh ekdum relatable hai!", "visual": "Fictional Indian home, a character spots an unexpected problem"},
        {"caption": "SAB NORMAL CHAL RAHA THA", "narration": "Sab kuch bilkul normal chal raha tha.", "visual": "Same character calmly handling an everyday situation"},
        {"caption": "PHIR AAYA TWIST...", "narration": f"Tabhi shuru hua {idea} wala scene.", "visual": "A harmless unexpected event interrupts the scene"},
        {"caption": "CONFUSION HI CONFUSION", "narration": "Ek second mein sab confuse ho gaye!", "visual": "Two original cartoon characters exchange exaggerated looks"},
        {"caption": "KISI NE YE EXPECT NAHI KIYA", "narration": "Lekin asli twist toh abhi baaki tha.", "visual": "A funny visual reveal with expressive reactions"},
        {"caption": "TUMHARE SAATH BHI?", "narration": "Aisa hua hai? Comment mein batao!", "visual": "Playful final pose that loops back to the opening"},
    ]
    return {
        "title": f"{idea[:65]} 😂 #Shorts",
        "description": (
            "Original Hindi/Hinglish short story inspired by a broad public trend, "
            "not a copy of another creator's video.\n\n"
            "#Shorts #HindiComedy #India #Original"
        ),
        "topic": idea,
        "scenes": scenes,
        "yt_create_prompts": _shot_prompts(idea),
        "duration_seconds": SCENE_COUNT * SCENE_SECONDS,
        "contains_synthetic_media": False,
    }


def _extract_json(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", s, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _valid_script(data):
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list) or len(data["scenes"]) != SCENE_COUNT:
        return False
    scenes_ok = all(
        isinstance(scene, dict)
        and all(isinstance(scene.get(key), str) and scene[key].strip() for key in ("caption", "narration", "visual"))
        for scene in data["scenes"]
    )
    prompts = data.get("yt_create_prompts")
    prompts_ok = (
        isinstance(prompts, list)
        and len(prompts) == 3
        and all(isinstance(prompt, str) and 30 <= len(prompt) <= 900 for prompt in prompts)
    )
    return scenes_ok and prompts_ok


def make_script(topics, slot):
    if not topics:
        raise ValueError("No trend topics were supplied to the script writer.")
    topic = topics[(slot - 1) % len(topics)]
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("No GEMINI_API_KEY; using clearly labeled creative fallback.")
        return fallback_script(topic, slot)
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        prompt = f"""You are an Indian YouTube Shorts writer and prompt engineer.
Write one ORIGINAL, advertiser-friendly Hindi/Hinglish comedy micro-story for a 9:16 vertical Short.
Public trend signals (use only as broad inspiration; do not reproduce their videos): {json.dumps(topics[:10], ensure_ascii=False)}
Chosen trend theme: {json.dumps(topic.get("title", ""), ensure_ascii=False)}
Make a 24-second story with exactly 6 scenes, 4 seconds each. A strong hook in scene 1, escalation, a harmless surprise payoff, and a loop-friendly ending. Narration should sound natural in spoken Indian Hindi/Hinglish, at most 10 short words per scene. Captions should be short and readable.
The visuals must be fictional and original. Do not copy any video, creator, dialogue, title phrasing, real person's likeness, celebrity, film/TV/game character, trademarked mascot, copyrighted soundtrack, or footage. Do not present an unverified viral claim as fact. No politics, dangerous stunts, medical advice, misinformation, harassment, or private individuals.
Also write exactly THREE distinct YouTube Create / Gemini Omni prompts, each 30-900 characters, for three continuous 8-second vertical 9:16 shots of the SAME original characters and setting. These prompts are for optional manual use inside YouTube Create; no app automation or API should be assumed. No text or logos in generated shots. Ensure shot 1 introduces, shot 2 escalates, shot 3 pays off and loops.
Return ONLY one JSON object with keys:
title (max 90 chars), description (include #Shorts and 2-4 relevant hashtags), topic, scenes (exactly 6 objects with caption/narration/visual strings), yt_create_prompts (exactly 3 strings).
"""
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        data = _extract_json(response.text or "")
        if not _valid_script(data):
            raise ValueError("Gemini response must contain 6 complete scenes and 3 valid YouTube Create prompts")
        data["topic"] = str(data.get("topic") or topic["title"])[:160]
        data["title"] = str(data.get("title") or topic["title"])[:90]
        description = str(data.get("description") or "#Shorts #HindiComedy #India")
        if "#Shorts" not in description:
            description = description.rstrip() + "\n\n#Shorts"
        data["description"] = description[:1900]
        data["duration_seconds"] = SCENE_COUNT * SCENE_SECONDS
        data["contains_synthetic_media"] = False
        return data
    except Exception as exc:
        print(f"Gemini unavailable/invalid; using local fallback: {type(exc).__name__}: {exc}")
        return fallback_script(topic, slot)
