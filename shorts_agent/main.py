"""Scheduled/CLI India Shorts generator with optional manual YouTube Create imports."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv

from shorts_agent.publish import publish
from shorts_agent.render import (
    add_audio,
    flow_video,
    motion_video,
    validate_video,
    yt_create_manual_video,
)
from shorts_agent.trends import discover
from shorts_agent.writer import make_script

ROOT = Path(__file__).resolve().parents[1]
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def get_slots(raw):
    if raw in ("1", "2"):
        return [int(raw)]
    if raw == "all":
        return [1, 2]
    if raw == "auto":
        now = dt.datetime.now(IST)
        return [1 if now.hour < 14 else 2]
    raise ValueError("slot must be 1, 2, all, or auto")


def _write_youtube_create_prompts(script, outdir):
    prompts = script.get("yt_create_prompts", [])
    lines = [
        "# YouTube Create / Gemini Omni prompts",
        "",
        "Optional manual step: paste one prompt at a time into YouTube Create's Generate video tool.",
        "Each prompt targets an 8-second vertical shot. The three clips can be exported and joined by this agent.",
        "YouTube Create does not expose a supported public API for this workflow to operate its editor automatically.",
        "",
    ]
    for index, prompt in enumerate(prompts, 1):
        lines.extend([f"## Shot {index}", "", prompt, ""])
    path = outdir / "yt_create_prompts.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_agent(slot, backend):
    topics = discover()
    if not topics:
        raise RuntimeError("Trend discovery returned no ideas; refusing to create an empty Short.")
    script = make_script(topics, slot)
    today_dt = dt.datetime.now(IST)
    today = today_dt.strftime("%Y-%m-%d")
    publish_id = f"{today}-slot{slot}"
    outdir = ROOT / "output" / today / f"slot{slot}"
    outdir.mkdir(parents=True, exist_ok=True)

    (outdir / "script.json").write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    prompt_file = _write_youtube_create_prompts(script, outdir)
    video = outdir / "short.mp4"

    with tempfile.TemporaryDirectory(prefix="india-shorts-") as temp_dir:
        workdir = Path(temp_dir)
        if backend == "motion":
            silent = motion_video(script, workdir)
        elif backend == "flow_manual":
            silent = flow_video(slot, workdir)
        elif backend == "yt_create_manual":
            silent = yt_create_manual_video(slot, workdir)
            # YouTube Create Gemini-generated visuals may be realistic synthetic media.
            script["contains_synthetic_media"] = True
        else:
            raise ValueError("VIDEO_BACKEND must be motion, flow_manual, or yt_create_manual.")
        add_audio(silent, script, workdir, video)

    report = validate_video(video)
    report.update({
        "backend": backend,
        "topic": script.get("topic", ""),
        "publish_id": publish_id,
        "youtube_create_prompts": str(prompt_file.relative_to(ROOT)),
    })
    (outdir / "quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    results = publish(
        video,
        script,
        contains_synthetic_media=bool(script.get("contains_synthetic_media", False)),
    )
    (outdir / "publish_result.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"READY {video} ({report['duration_seconds']} sec, "
        f"{report['width']}x{report['height']}). Publish results: {results}"
    )
    return results


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--slot", default=os.getenv("VIDEO_SLOT", "auto"),
        choices=["1", "2", "all", "auto"],
    )
    parser.add_argument(
        "--backend", default=os.getenv("VIDEO_BACKEND", "motion"),
        choices=["motion", "flow_manual", "yt_create_manual"],
    )
    args = parser.parse_args()
    for slot in get_slots(args.slot):
        run_agent(slot, args.backend)


if __name__ == "__main__":
    main()
