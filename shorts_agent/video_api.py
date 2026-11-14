"""Cloud video generation through the Gemini Omni Interactions API.

This uses the paid Gemini video-generation API, not the YouTube Create mobile app.
It generates a 10-second scene, extends it to the configured 20/30-second target,
then normalizes the final MP4 for Shorts.
"""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import time

import requests

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-omni-1.1-flash"
CLIP_SECONDS = 10


def target_seconds():
    raw = os.getenv("GEMINI_VIDEO_TARGET_SECONDS", "20").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("GEMINI_VIDEO_TARGET_SECONDS must be 20 or 30.") from exc
    if value not in (20, 30):
        raise ValueError("GEMINI_VIDEO_TARGET_SECONDS must be 20 or 30.")
    return value


def build_segment_prompts(script, total_seconds):
    """Create continuity-aware 10-second prompt segments from the six-scene script."""
    scenes = script.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 6:
        raise ValueError("Cloud video generation requires exactly six script scenes.")

    count = total_seconds // CLIP_SECONDS
    group_size = len(scenes) // count
    prompts = []
    for index in range(count):
        group = scenes[index * group_size:(index + 1) * group_size]
        descriptions = []
        for local_index, scene in enumerate(group):
            start = local_index * CLIP_SECONDS // len(group)
            end = (local_index + 1) * CLIP_SECONDS // len(group)
            descriptions.append(
                f"[{start}-{end}s] Visual: {scene.get('visual', '')}. "
                f"Action/caption intent: {scene.get('caption', '')}."
            )

        if index == 0:
            lead = (
                "Create an original 10-second vertical 9:16 cinematic video, "
                "720p, 24 fps. This is the opening of a short fictional Hindi/Indian "
                "story. Establish the main character(s), location and visual style. "
                "Use realistic natural movement, expressive reactions, purposeful "
                "camera motion and coherent lighting. Follow the timed beats below."
            )
            task = "text_to_video"
        else:
            lead = (
                "Extend the previous generated video by exactly 10 seconds. Continue "
                "the same fictional story seamlessly from its current final frame. "
                "Preserve the exact same character identity, face, clothing, props, "
                "location, color grade, lighting and camera language. Do not restart "
                "or introduce unrelated characters. Follow the next timed story beats."
            )
            task = "extend"

        ending = (
            "Vertical 9:16, 720p, 24 fps. Original fictional content only. "
            "No brand logos, no watermark, no subtitles, no captions, no on-screen "
            "text, no copyrighted characters, no recognizable public figures, and "
            "no imitation of a known creator or film. Generate natural environmental "
            "sound and subtle background ambience only; no spoken dialogue because "
            "a separate Hindi narration track will be added during post-production."
        )
        prompts.append({
            "task": task,
            "input": lead + "\n\n" + "\n".join(descriptions) + "\n\n" + ending,
        })
    return prompts


def _request_headers(api_key):
    return {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }


def _raise_api_error(response, action):
    try:
        payload = response.json()
        detail = json.dumps(payload, ensure_ascii=False)[:1800]
    except ValueError:
        detail = (response.text or "")[:1800]
    raise RuntimeError(f"Gemini video API {action} failed (HTTP {response.status_code}): {detail}")


def _wait_for_interaction(payload, api_key, timeout_seconds=1800):
    interaction_id = payload.get("id")
    status = str(payload.get("status", "")).lower()
    if status in ("completed", "failed", "cancelled") or not interaction_id:
        if status == "failed":
            raise RuntimeError("Gemini video interaction failed: " + json.dumps(payload, ensure_ascii=False)[:1500])
        return payload

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = requests.get(
            f"{API_ROOT}/interactions/{interaction_id}",
            headers=_request_headers(api_key),
            timeout=(20, 90),
        )
        if not response.ok:
            _raise_api_error(response, "interaction polling")
        payload = response.json()
        status = str(payload.get("status", "")).lower()
        if status == "completed":
            return payload
        if status in ("failed", "cancelled"):
            raise RuntimeError(
                f"Gemini video interaction {status}: "
                + json.dumps(payload, ensure_ascii=False)[:1500]
            )
        time.sleep(10)
    raise TimeoutError(f"Gemini video interaction {interaction_id} did not finish within {timeout_seconds} seconds.")


def _video_output(payload):
    """Extract video output from SDK-style or raw REST Interactions response."""
    output = payload.get("output_video")
    if isinstance(output, dict):
        if output.get("data") or output.get("uri"):
            return output

    for step in reversed(payload.get("steps", []) or []):
        if step.get("type") != "model_output":
            continue
        for part in step.get("content", []) or []:
            if part.get("type") == "video" or part.get("mime_type") == "video/mp4":
                if part.get("data") or part.get("uri"):
                    return part
    raise RuntimeError(
        "Gemini interaction completed without an MP4 video output. "
        "Response keys: " + ", ".join(sorted(payload.keys()))
    )


def _download_video(video_output, api_key, destination, timeout_seconds=900):
    data = video_output.get("data")
    if data:
        try:
            content = base64.b64decode(data, validate=False)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Gemini returned invalid base64 video data.") from exc
        if len(content) < 50_000:
            raise RuntimeError("Gemini returned an unexpectedly small video payload.")
        Path(destination).write_bytes(content)
        return Path(destination)

    uri = str(video_output.get("uri") or "")
    if not uri:
        raise RuntimeError("Gemini video output has neither data nor URI.")

    match = re.search(r"/files/([^/:?]+)", uri) or re.search(r"files/([^/:?]+)", uri)
    if not match:
        raise RuntimeError(f"Could not identify the Gemini Files API ID from video URI: {uri[:300]}")
    file_id = match.group(1)
    headers = _request_headers(api_key)
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        info_response = requests.get(
            f"{API_ROOT}/files/{file_id}",
            headers=headers,
            timeout=(20, 90),
        )
        if not info_response.ok:
            _raise_api_error(info_response, "file-state polling")
        info = info_response.json()
        state = str(info.get("state", "")).upper()
        if state == "ACTIVE":
            break
        if state == "FAILED":
            raise RuntimeError("Gemini Files API reported FAILED for generated video.")
        time.sleep(5)
    else:
        raise TimeoutError(f"Gemini file {file_id} did not become ACTIVE.")

    if ":download" in uri:
        download_url = uri
    else:
        download_url = f"{API_ROOT}/files/{file_id}:download?alt=media"

    response = requests.get(
        download_url,
        headers=headers,
        stream=True,
        timeout=(30, 300),
    )
    if not response.ok:
        _raise_api_error(response, "video download")
    path = Path(destination)
    with path.open("wb") as output_file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                output_file.write(chunk)
    if not path.exists() or path.stat().st_size < 50_000:
        raise RuntimeError("Downloaded Gemini video is missing or unexpectedly small.")
    return path


def _interaction(prompt, task, api_key, model, previous_id=None):
    body = {
        "model": model,
        "input": prompt,
        "response_format": {
            "type": "video",
            "delivery": "uri",
            "aspect_ratio": "9:16",
            "resolution": "720p",
        },
        "generation_config": {
            "video_config": {
                "task": task,
            }
        },
    }
    if previous_id:
        body["previous_interaction_id"] = previous_id

    response = requests.post(
        f"{API_ROOT}/interactions",
        headers=_request_headers(api_key),
        json=body,
        timeout=(30, 1200),
    )
    if not response.ok:
        _raise_api_error(response, "video generation")
    payload = response.json()
    return _wait_for_interaction(payload, api_key)


def _probe_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _has_audio(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _normalize_segment(source, destination, seconds):
    """Encode each generated scene to one stable portrait MP4 with an audio stream."""
    video_filter = (
        "scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280,fps=24,format=yuv420p,"
        f"tpad=stop_mode=clone:stop_duration={seconds}"
    )
    if _has_audio(source):
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", source,
            "-vf", video_filter, "-af", "apad",
            "-map", "0:v:0", "-map", "0:a:0",
            "-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "21", "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-ar", "48000", "-b:a", "128k",
            "-movflags", "+faststart", destination,
        ]
    else:
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", source,
            "-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=48000:cl=stereo",
            "-vf", video_filter, "-map", "0:v:0", "-map", "1:a:0",
            "-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "21", "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-ar", "48000", "-b:a", "128k",
            "-movflags", "+faststart", destination,
        ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return Path(destination)


def _concat_segments(segments, workdir, destination):
    playlist = Path(workdir) / "gemini_video_concat.txt"
    playlist.write_text(
        "".join(f"file '{Path(segment).resolve().as_posix()}'\n" for segment in segments),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(playlist),
            "-c", "copy", "-movflags", "+faststart", str(destination),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    return Path(destination)


def generate_gemini_video(script, workdir):
    """Generate a cloud-native 20- or 30-second 9:16 MP4 using Gemini Omni."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "VIDEO_BACKEND=gemini_video requires GEMINI_API_KEY in GitHub Actions secrets."
        )

    total_seconds = target_seconds()
    model = os.getenv("GEMINI_VIDEO_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    prompts = build_segment_prompts(script, total_seconds)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    previous_interaction_id = None
    previous_full = None
    previous_duration = 0.0

    for index, segment in enumerate(prompts, 1):
        task = segment["task"]
        print(
            f"Gemini cloud video: generating segment {index}/{len(prompts)} "
            f"with {model} ({task}).",
            flush=True,
        )
        interaction = _interaction(
            segment["input"],
            task,
            api_key,
            model,
            previous_id=previous_interaction_id,
        )
        current_id = interaction.get("id")
        if not current_id and index < len(prompts):
            raise RuntimeError("Gemini did not return an interaction ID for video continuation.")

        raw_path = workdir / f"gemini_interaction_{index}.mp4"
        _download_video(_video_output(interaction), api_key, raw_path)
        current_duration = _probe_duration(raw_path)
        print(f"Gemini segment {index} returned {current_duration:.2f} seconds.", flush=True)

        # Some Interactions responses contain the full extended video; others may
        # contain only the latest extension. Detect the latter and concatenate.
        if previous_full is not None and current_duration <= CLIP_SECONDS + 1.5:
            current_piece = _normalize_segment(
                raw_path, workdir / f"gemini_piece_{index}.mp4", CLIP_SECONDS
            )
            full_piece = _normalize_segment(
                previous_full, workdir / f"gemini_prefix_{index}.mp4",
                max(CLIP_SECONDS, min(total_seconds, round(previous_duration))),
            )
            merged = workdir / f"gemini_cumulative_{index}.mp4"
            previous_full = _concat_segments([full_piece, current_piece], workdir, merged)
            previous_duration = _probe_duration(previous_full)
        else:
            previous_full = raw_path
            previous_duration = current_duration

        previous_interaction_id = current_id
        if previous_duration >= total_seconds - 1.0:
            break

    if previous_full is None:
        raise RuntimeError("Gemini did not return a video.")

    final_path = workdir / "gemini_cloud_video.mp4"
    _normalize_segment(previous_full, final_path, total_seconds)
    print(
        f"Gemini cloud video ready: {final_path} "
        f"({total_seconds}s target, model={model}).",
        flush=True,
    )
    return final_path
