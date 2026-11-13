"""20s portrait MP4 creation: original animated title cards or user-exported Flow clips."""
import asyncio
import math
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True, stdout=subprocess.DEVNULL)


def font(size, text=""):
    # Noto Devanagari font lacks ASCII Latin glyphs; FreeSerif supports mixed Hindi + Latin.
    is_hindi = any("\u0900" <= ch <= "\u097f" for ch in text)
    candidates = ([
        "/usr/share/fonts/opentype/freefont/FreeSerifBold.otf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "C:/Windows/Fonts/mangal.ttf",
    ] if is_hindi else [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/opentype/freefont/FreeSerifBold.otf",
        "C:/Windows/Fonts/arialbd.ttf",
    ])
    for f in candidates:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
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
    palettes = [((12, 13, 38), (70, 24, 118), (249, 211, 62)),
                ((10, 27, 38), (15, 102, 108), (132, 251, 198)),
                ((42, 14, 38), (115, 22, 84), (255, 181, 88)),
                ((22, 25, 48), (43, 55, 148), (133, 198, 255)),
                ((24, 15, 30), (101, 40, 61), (255, 197, 141))]
    start, end, accent = palettes[index % len(palettes)]
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        alpha = y / H
        fill = tuple(round(start[i] * (1-alpha) + end[i] * alpha) for i in range(3))
        d.line((0, y, W, y), fill=fill)
    # Original 2D cartoon motif, not copied footage.
    d.ellipse((370, 235, 820, 685), fill=tuple(min(255, c + 20) for c in end))
    d.ellipse((430, 260, 575, 400), fill=accent)
    d.ellipse((575, 260, 720, 400), fill=accent)
    d.ellipse((485, 310, 522, 360), fill=(13, 15, 38))
    d.ellipse((630, 310, 667, 360), fill=(13, 15, 38))
    d.arc((485, 342, 675, 550), 15, 160, fill=(255, 255, 255), width=15)
    for i in range(15):
        x = (i * 83 + 21) % W
        y = 460 + (i * 91) % 510
        r = 3 + i % 8
        d.ellipse((x-r, y-r, x+r, y+r), outline=accent, width=3)
    d.rounded_rectangle((40, 45, 680, 125), radius=21, fill=accent)
    d.text((65, 62), f"INDIA • 20 SEC STORY  |  {index + 1}/5", font=font(29), fill=(10, 15, 35))
    d.rounded_rectangle((37, 670, 683, 1100), radius=40, fill=(9, 13, 30), outline=accent, width=4)
    text = script["scenes"][index]["caption"].upper()
    fnt = font(59 if len(text) < 42 else 45, text)
    lines = wrapped(d, text, fnt, 560)
    y = 755
    for line in lines[:4]:
        d.text((70, y), line, font=fnt, fill=(255, 255, 255), stroke_width=1)
        y += 83
    d.text((50, 1170), "ORIGINAL • HINDI / HINGLISH", font=font(26), fill=(245, 235, 215))
    im.save(output, optimize=True)


def voice_script(script):
    return " ".join(s["narration"].strip() for s in script["scenes"])


async def _edge_speech(text, out):
    import edge_tts
    communicate = edge_tts.Communicate(text, "hi-IN-MadhurNeural", rate="+20%")
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
        except Exception as e:
            print(f"Edge speech unavailable: {e}")
            if backend == "edge":
                return None
    if backend in ("auto", "espeak") and shutil.which("espeak-ng"):
        wav = workdir / "voice.wav"
        try:
            run(["espeak-ng", "-v", "hi", "-s", "185", "-w", wav, content])
            return wav
        except Exception as e:
            print(f"eSpeak speech unavailable: {e}")
    print("No available TTS. Captions and video still render, with silent audio.")
    return None


def _normalize(source, target, duration):
    # Upscales/composites existing footage; does not claim to improve source detail.
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", source,
         "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30,format=yuv420p,tpad=stop_mode=clone:stop_duration=12",
         "-an", "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast", "-crf", "25", "-pix_fmt", "yuv420p", "-r", "30", target])


def motion_video(script, workdir):
    segments = []
    for i in range(5):
        png = workdir / f"card_{i + 1}.png"
        seg = workdir / f"clip_{i + 1}.mp4"
        card(script, i, png)
        # Small motion in every scene: mild pan; lightweight enough for GitHub runner.
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "30", "-i", png,
             "-vf", "scale=760:1351,crop=720:1280:x='20+12*sin(n/15)':y='35+12*cos(n/18)',format=yuv420p",
             "-t", "4", "-r", "30", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "27", seg])
        segments.append(seg)
    return _join(segments, workdir)


def flow_video(slot, workdir):
    folder = Path(__file__).resolve().parents[1] / "flow_inputs" / f"slot{slot}"
    clips = [folder / "scene_1.mp4", folder / "scene_2.mp4"]
    missing = [str(c) for c in clips if not c.is_file()]
    if missing:
        raise FileNotFoundError("Manual Flow mode needs two 10-second MP4 clips: " + ", ".join(missing))
    segments = []
    for idx, clip in enumerate(clips, 1):
        seg = workdir / f"flow_{idx}.mp4"
        _normalize(clip, seg, 10)
        segments.append(seg)
    return _join(segments, workdir)


def _join(segments, workdir):
    playlist = workdir / "concat.txt"
    playlist.write_text("".join(f"file '{p.resolve()}'\n" for p in segments), encoding="utf-8")
    out = workdir / "silent.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", playlist,
         "-c", "copy", "-movflags", "+faststart", out])
    return out


def add_audio(video, script, workdir, destination):
    audio = speech(script, workdir)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video]
    if audio:
        cmd.extend(["-i", audio, "-filter_complex", "[1:a]apad[a]", "-map", "0:v", "-map", "[a]"])
    else:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a"])
    cmd.extend(["-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-b:a", "128k", "-t", "20", "-movflags", "+faststart", destination])
    run(cmd)
    return destination