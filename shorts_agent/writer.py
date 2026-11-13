"""Use free-tier-capable Gemini text models; fall back to transparent template scripts."""
import json
import os
import re


def fallback_script(topic, slot):
    idea = topic.get("title", "Indian everyday comedy")
    scenes = [
        {"caption": "YE TO HAR GHAR MEIN HOTA HAI!", "narration": "Bhai, aaj ka scene toh ekdum relatable nikla!", "visual": "Colorful 2D cartoon room, exaggerated surprise"},
        {"caption": "PHIR AAYA TWIST...", "narration": f"Sab log {idea} mein busy the.", "visual": "Funny character enters from frame right"},
        {"caption": "EK CHHOTI SI GALTI", "narration": "Tabhi ek chhoti galti ne sabko hila diya!", "visual": "Cartoon freeze-frame, shock lines"},
        {"caption": "PURE CONFUSION!", "narration": "Aur sab ek dusre ko dekhkar hansne lage.", "visual": "Chaotic comic reaction, speech bubbles"},
        {"caption": "TUMHARE SAATH BHI?", "narration": "Aisa aapke saath bhi hua? Comment karo!", "visual": "Cartoon ending, playful bounce"},
    ]
    return {"title": f"{idea[:65]} 😂 #Shorts", "description": f"Original Hindi relatable comedy inspired by Indian everyday life.\n\n#Shorts #HindiComedy #India #Relatable", "topic": idea, "scenes": scenes}


def _extract_json(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", s, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _valid_script(data):
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list) or len(data["scenes"]) != 5:
        return False
    return all(isinstance(s, dict) and all(isinstance(s.get(k), str) and s[k].strip() for k in ("caption", "narration", "visual")) for s in data["scenes"])


def make_script(topics, slot):
    topic = topics[(slot - 1) % len(topics)]
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("No GEMINI_API_KEY; using clearly labeled creative fallback.")
        return fallback_script(topic, slot)
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        prompt = f"""You are a creator of ORIGINAL, advertiser-friendly, light, FUNNY 20-second Hindi/Hinglish 9:16 Indian cartoon Shorts.
Trending topic signals (NOT scripts to copy): {json.dumps(topics[:10], ensure_ascii=False)}
Create one different idea for SLOT {slot} anchored to "{topic['title']}" as a trend FORMAT only. Do not reproduce text, dialogue, trademarked fictional characters, recognizable footage, private people, copyrighted music, creator identities, or unsupported factual claims. Make clearly fictional, visually achievable action. Catchy first 2 seconds; quick escalation; sharp payoff; loopable final line; 5 scenes, exactly 4 seconds each; each narration max 11 short Hindi/Hinglish words. No politics, dangerous acts, medical advice or misinformation. The content must be independently original, not a clone of the trend.
Return ONLY a JSON object with keys: title (max 90 chars), description (3-5 hashtags), topic, scenes (exactly 5 objects, each with caption, narration, visual). Each caption max 45 characters. Ensure all strings. No markdown.
"""
        response = client.models.generate_content(model=model, contents=prompt, config={"response_mime_type": "application/json"})
        data = _extract_json(response.text)
        if not _valid_script(data):
            raise ValueError("Gemini response missing 5 scenes with all fields")
        data["topic"] = str(data.get("topic") or topic["title"])[:160]
        data["title"] = str(data.get("title") or topic["title"])[:90]
        data["description"] = str(data.get("description") or "#Shorts #HindiComedy #India")[:1900]
        return data
    except Exception as e:
        print(f"Gemini unavailable/invalid; using local fallback: {type(e).__name__}: {e}")
        return fallback_script(topic, slot)
