"""Publish original Shorts using official YouTube and Meta APIs."""
import os
import time
from pathlib import Path

import requests


def _truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def youtube_upload(video, script, contains_synthetic_media=False):
    needed = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    if not all(os.getenv(name) for name in needed):
        print("SKIP YouTube: OAuth secrets are not configured.")
        return None

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials = Credentials(
        None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    credentials.refresh(Request())
    client = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    title = str(script.get("title") or "India Hindi Short")[:90]
    if "#Shorts" not in title and "#Shorts" not in str(script.get("description", "")):
        title = f"{title} #Shorts"[:100]
    description = str(script.get("description") or "#Shorts #India #Hindi")
    if "#Shorts" not in description and "#Shorts" not in title:
        description = description.rstrip() + "\n\n#Shorts"
    description = description[:4900]

    synthetic_disclosure = (
        bool(contains_synthetic_media)
        or _truthy(os.getenv("YOUTUBE_CONTAINS_SYNTHETIC_MEDIA", "false"))
    )
    request = client.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["Shorts", "India", "Hindi", "Hinglish", "original"],
                "categoryId": "24",
                "defaultLanguage": "hi",
            },
            "status": {
                "privacyStatus": os.getenv("YOUTUBE_PRIVACY", "private"),
                "selfDeclaredMadeForKids": False,
                "containsSyntheticMedia": synthetic_disclosure,
            },
        },
        media_body=MediaFileUpload(
            str(video),
            mimetype="video/mp4",
            resumable=True,
            chunksize=5 * 1024 * 1024,
        ),
    )
    result = None
    while result is None:
        _, result = request.next_chunk()
    video_id = result["id"]
    privacy = os.getenv("YOUTUBE_PRIVACY", "private")
    print(f"YouTube uploaded as {privacy}: https://youtu.be/{video_id}")
    print(f"Altered/synthetic-media disclosure set to: {synthetic_disclosure}")
    return video_id


def instagram_upload(video, script):
    needed = (
        "IG_USER_ID", "IG_ACCESS_TOKEN", "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
    )
    if not all(os.getenv(name) for name in needed):
        print("SKIP Instagram: IG professional-account token + Cloudinary credentials required.")
        return None

    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
        api_key=os.environ["CLOUDINARY_API_KEY"],
        api_secret=os.environ["CLOUDINARY_API_SECRET"],
        secure=True,
    )
    hosted = cloudinary.uploader.upload(
        str(video), resource_type="video",
        folder="india-viral-shorts", overwrite=False,
    )
    public_url = hosted["secure_url"]
    base = f"https://graph.facebook.com/{os.getenv('META_GRAPH_VERSION', 'v24.0')}"
    token = os.environ["IG_ACCESS_TOKEN"]
    user = os.environ["IG_USER_ID"]
    caption = f"{script.get('title', '')}\n\n{script.get('description', '')}"[:2100]

    response = requests.post(
        f"{base}/{user}/media",
        data={
            "media_type": "REELS",
            "video_url": public_url,
            "caption": caption,
            "access_token": token,
        },
        timeout=45,
    )
    response.raise_for_status()
    container_id = response.json()["id"]

    for _ in range(30):
        time.sleep(10)
        status_response = requests.get(
            f"{base}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=30,
        )
        status_response.raise_for_status()
        status_data = status_response.json()
        state = status_data.get("status_code")
        if state == "FINISHED":
            break
        if state in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {status_data}")
    else:
        raise TimeoutError(
            "Instagram Reel not ready within 5 minutes; do not retry blindly "
            "to avoid duplicate containers."
        )

    published = requests.post(
        f"{base}/{user}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=45,
    )
    published.raise_for_status()
    media_id = published.json()["id"]
    print(f"Instagram published: media_id={media_id}")
    return media_id


def publish(video: Path, script: dict, contains_synthetic_media=False):
    if os.getenv("AUTO_PUBLISH", "true").lower() not in ("true", "1", "yes"):
        print("AUTO_PUBLISH=false: only rendered preview; no publishing.")
        return {}

    results = {}
    errors = []
    uploads = [
        ("youtube", lambda path, data: youtube_upload(path, data, contains_synthetic_media)),
    ]
    if _truthy(os.getenv("ENABLE_INSTAGRAM_PUBLISH", "false")):
        uploads.append(("instagram", instagram_upload))
    else:
        print("SKIP Instagram: publishing is disabled; set ENABLE_INSTAGRAM_PUBLISH=true to opt in.")

    for name, upload in uploads:
        try:
            results[name] = upload(video, script)
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"ERROR publishing to {name}: {type(exc).__name__}: {exc}")
    if errors:
        results["errors"] = errors
    return results
