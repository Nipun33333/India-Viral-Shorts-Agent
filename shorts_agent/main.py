"""Two daily slot executions, also usable from CLI and GitHub Actions."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv

from shorts_agent.publish import publish
from shorts_agent.render import add_audio, flow_video, motion_video
from shorts_agent.trends import discover
from shorts_agent.writer import make_script

ROOT = Path(__file__).resolve().parents[1]


def get_slots(raw):
    if raw in ("1", "2"):
        return [int(raw)]
    if raw == "all":
        return [1, 2]
    if raw == "auto":
        now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
        return [1 if now.hour < 14 else 2]
    raise ValueError("slot must be 1, 2, all, or auto")


def run_agent(slot, backend):
    topics = discover()
    script = make_script(topics, slot)
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
    outdir = ROOT / "output" / today / f"slot{slot}"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    video = outdir / "short.mp4"
    with tempfile.TemporaryDirectory(prefix="india-shorts-") as d:
        workdir = Path(d)
        if backend == "motion":
            silent = motion_video(script, workdir)
        elif backend == "flow_manual":
            silent = flow_video(slot, workdir)
        else:
            raise ValueError("VIDEO_BACKEND must be motion or flow_manual; Google Flow has no public free-credit API integration.")
        add_audio(silent, script, workdir, video)
    results = publish(video, script)
    (outdir / "publish_result.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"READY {video} (20 sec, 9:16). Publish results: {results}")
    return results


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", default=os.getenv("VIDEO_SLOT", "auto"), choices=["1", "2", "all", "auto"])
    parser.add_argument("--backend", default=os.getenv("VIDEO_BACKEND", "motion"), choices=["motion", "flow_manual"])
    args = parser.parse_args()
    for slot in get_slots(args.slot):
        run_agent(slot, args.backend)


if __name__ == "__main__":
    main()
