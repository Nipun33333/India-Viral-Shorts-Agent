"""Render original 24-second vertical Shorts or assemble user-exported clips."""
import asyncio
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
SCENE_SECONDS = 4


def run(cmd, capture=False):
    return subprocess.run(
        [str(item) for item in cmd],
        check=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
        text=capture,
    )


def font(size, text=""):
    is_hindi = any("\u0900" <= char <= "\u097f" for char in text)
    candidates = ([
        "/usr/share/fonts/opentype/freefont/FreeSerifBold.otf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "C:/Windows/Fonts/mangal.ttf",
    ] if is_hindi else [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/opentype/freefont/FreeSerifBold.otf",
        "C:/Windows/Fonts/arialbd.ttf",
    ])
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrapped(draw, text, fnt, maxwidth):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= maxwidth or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines[:7]


def card(script, index, output):
    palettes = [
        ((12, 13, 38), (70, 24, 118), (249, 211, 62)),
        ((10, 27, 38), (15, 102, 108), (132, 251, 198)),
        ((42, 14, 38), (115, 22, 84), (255, 181, 88)),
        ((22, 25, 48), (43, 55, 148), (133, 198, 255)),
        ((24, 15, 30), (101, 40, 61), (255, 197, 141)),
        ((19, 30, 40), (92, 58, 22), (255, 224, 130)),
    ]
    start, end, accent = palettes[index % len(palettes)]
    im = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(im)
    for y in range(H):
        alpha = y / H
        fill = tuple(round(start[i] * (1 - alpha) + end[i] * alpha) for i in range(3))
        draw.line((0, y, W, y), fill=fill)

    # Original abstract cartoon character; no real creator footage or characters.
    shift = (index % 3) * 15
    draw.ellipse((370 - shift, 235, 820 - shift, 685), fill=tuple(min(255, c + 20) for c in end))
    draw.ellipse((430 - shift, 260, 575 - shift, 400), fill=accent)
    draw.ellipse((575 - shift, 260, 720 - shift, 400), fill=accent)
    draw.ellipse((485 - shift, 310, 522 - shift, 360), fill=(13, 15, 38))
    draw.ellipse((630 - shift, 310, 667 - shift, 360), fill=(13, 15, 38))
    draw.arc((485 - shift, 342, 675 - shift, 550), 15, 160, fill=(255, 255, 255), width=15)
    for n in range(15):
        x = (n * 83 + 21 + index * 29) % W
        y = 460 + (n * 91 + index * 17) % 510
        radius = 3 + n % 8
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=accent, width=3)

    draw.rounded_rectangle((40, 45, 680, 125), radius=21, fill=accent)
    draw.text((65, 62), f"INDIA • ORIGINAL STORY  |  {index + 1}/{len(script['scenes'])}", font=font(27), fill=(10, 15, 35))
    draw.rounded_rectangle((37, 670, 683, 1100), radius=40, fill=(9, 13, 30), outline=accent, width=4)
    text = script["scenes"][index]["caption"].upper()
    fnt = font(59 if len(text) < 42 else 45, text)
    lines = wrapped(draw, text, fnt, 560)
    y = 755
    for line in lines[:4]:
        draw.text((70, y), line, font=fnt, fill=(255, 255, 255), stroke_width=1)
        y += 83
    draw.rounded_rectangle((50, 1150, 670, 1162), radius=6, fill=(65, 65, 85))
    progress = int(620 * (index + 1) / len(script["scenes"]))
    draw.rounded_rectangle((50, 1150, 50 + progress, 1162), radius=6, fill=accent)
    draw.text((50, 1190), "HINDI / HINGLISH  •  #SHORTS", font=font(25), fill=(245, 235, 215))
    im.save(output, optimize=True)


def voice_script(script):
    return " ".join(scene["narration"].strip() for scene in script["scenes"])


async def _edge_speech(text, out):
    import edge_tts
    communicate = edge_tts.Communicate(text, "hi-IN-MadhurNeural", rate="+12%")
    await communicate.save(str(out))


def speech(script, workdir):
    backend = os.getenv("TTS_BACKEND", "auto").lower()
    if backend == "none":
        return None
    content = voice_script(script)
    audio = workdir / "voice.mp3"
    if backend in ("auto", "edge"):
        try:
            asyncio.run(_edge_speech(content, audio))
            if audio.exists() and audio.stat().st_size > 1000:
                return audio
        except Exception as exc:
            print(f"Edge speech unavailable: {type(exc).__name__}: {exc}")
            if backend == "edge":
                return None
    if backend in ("auto", "espeak") and shutil.which("espeak-ng"):
        wav = workdir / "voice.wav"
        try:
            run(["espeak-ng", "-v", "hi", "-s", "185", "-w", wav, content])
            return wav
        except Exception as exc:
            print(f"eSpeak speech unavailable: {type(exc).__name__}: {exc}")
    print("No available TTS. Captions render with silent audio.")
    return None


def _normalize(source, target, duration):
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", source,
        "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30,format=yuv420p,tpad=stop_mode=clone:stop_duration=12",
        "-an", "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "23", "-pix_fmt", "yuv420p", "-r", "30", target,
    ])


def motion_video(script, workdir):
    segments = []
    scenes = script["scenes"]
    if not scenes:
        raise ValueError("No scenes were generated.")
    for index, _scene in enumerate(scenes):
        png = workdir / f"card_{index + 1}.png"
        segment = workdir / f"clip_{index + 1}.mp4"
        card(script, index, png)
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-framerate", "30", "-i", png,
            "-vf", "scale=760:1351,crop=720:1280:x='20+12*sin(n/15)':y='35+12*cos(n/18)',format=yuv420p",
            "-t", str(SCENE_SECONDS), "-r", "30", "-an",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25", segment,
        ])
        segments.append(segment)
    return _join(segments, workdir)


def flow_video(slot, workdir):
    folder = Path(__file__).resolve().parents[1] / "flow_inputs" / f"slot{slot}"
    clips = [folder / "scene_1.mp4", folder / "scene_2.mp4"]
    missing = [str(clip) for clip in clips if not clip.is_file()]
    if missing:
        raise FileNotFoundError("Manual Flow mode needs two 10-second MP4 clips: " + ", ".join(missing))
    segments = []
    for index, clip in enumerate(clips, 1):
        segment = workdir / f"flow_{index}.mp4"
        _normalize(clip, segment, 10)
        segments.append(segment)
    return _join(segments, workdir)


def yt_create_manual_video(slot, workdir):
    """Assemble three user-exported 8s clips generated manually in YouTube Create."""
    folder = Path(__file__).resolve().parents[1] / "yt_create_inputs" / f"slot{slot}"
    clips = [folder / f"shot_{index}.mp4" for index in range(1, 4)]
    missing = [str(clip) for clip in clips if not clip.is_file()]
    if missing:
        raise FileNotFoundError(
            "YouTube Create mode needs three exported MP4 clips (about 8 seconds each): "
            + ", ".join(missing)
        )
    segments = []
    for index, clip in enumerate(clips, 1):
        segment = workdir / f"yt_create_{index}.mp4"
        _normalize(clip, segment, 8)
        segments.append(segment)
    return _join(segments, workdir)


def _join(segments, workdir):
    playlist = workdir / "concat.txt"
    playlist.write_text(
        "".join(f"file '{str(path.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for path in segments),
        encoding="utf-8",
    )
    output = workdir / "silent.mp4"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", playlist,
        "-c", "copy", "-movflags", "+faststart", output,
    ])
    return output


def _has_audio_stream(video):
    result = run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_type", "-of", "csv=p=0", video,
    ], capture=True)
    return bool(result.stdout.strip())


def add_audio(video, script, workdir, destination):
    """Add Hindi narration while retaining and ducking any generated ambience."""
    duration = int(script.get("duration_seconds") or len(script["scenes"]) * SCENE_SECONDS)
    if not 20 <= duration <= 30:
        raise ValueError(f"Shorts duration must be 20-30 seconds; got {duration}.")
    audio = speech(script, workdir)
    source_has_audio = _has_audio_stream(video)
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video]

    if audio and source_has_audio:
        command.extend([
            "-i", audio,
            "-filter_complex",
            "[0:a:0]volume=0.32[ambience];"
            "[1:a:0]apad,volume=1.10[voice];"
            "[ambience][voice]amix=inputs=2:duration=longest:dropout_transition=2,"
            "alimiter=limit=0.95[mixed]",
            "-map", "0:v:0", "-map", "[mixed]",
        ])
    elif audio:
        command.extend([
            "-i", audio,
            "-filter_complex", "[1:a:0]apad[a]",
            "-map", "0:v:0", "-map", "[a]",
        ])
    elif source_has_audio:
        command.extend(["-map", "0:v:0", "-map", "0:a:0"])
    else:
        command.extend([
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-map", "0:v:0", "-map", "1:a:0",
        ])

    command.extend([
        "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-b:a", "128k",
        "-t", str(duration), "-movflags", "+faststart", destination,
    ])
    run(command)
    return destination


def validate_video(video):
    """Fail closed unless a valid 20-30 second portrait MP4 is ready to upload."""
    path = Path(video)
    if not path.is_file() or path.stat().st_size < 50_000:
        raise ValueError("Rendered MP4 is missing or unexpectedly small.")
    result = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of", "json", path,
    ], capture=True)
    info = json.loads(result.stdout)
    duration = float(info.get("format", {}).get("duration", 0))
    video_streams = [stream for stream in info.get("streams", []) if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in info.get("streams", []) if stream.get("codec_type") == "audio"]
    if not 20 <= duration <= 30:
        raise ValueError(f"Output duration {duration:.2f}s is outside the 20-30 second Shorts target.")
    if not video_streams:
        raise ValueError("Output has no video stream.")
    width, height = int(video_streams[0].get("width", 0)), int(video_streams[0].get("height", 0))
    if width < 720 or height < 1280 or height <= width:
        raise ValueError(f"Output must be portrait and at least 720x1280; got {width}x{height}.")
    if not audio_streams:
        raise ValueError("Output has no audio stream (speech or silence track).")
    return {"duration_seconds": round(duration, 2), "width": width, "height": height, "size_bytes": path.stat().st_size}
