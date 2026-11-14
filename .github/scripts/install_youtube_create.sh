#!/usr/bin/env bash
set -Eeuo pipefail

PACKAGE="com.google.android.apps.youtube.producer"
SESSION_MINUTES="${SESSION_MINUTES:-45}"

echo "Waiting for Android device and completed boot..."
for attempt in $(seq 1 180); do
  state="$(adb get-state 2>/dev/null || true)"
  boot="$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  if [[ "$state" == "device" && "$boot" == "1" ]]; then
    break
  fi
  sleep 2
done

state="$(adb get-state 2>/dev/null || true)"
boot="$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
if [[ "$state" != "device" || "$boot" != "1" ]]; then
  echo "::error::Android emulator did not finish booting."
  adb devices -l || true
  exit 1
fi

echo "Android is ready. Applying India locale and timezone..."
adb shell settings put system system_locales en-IN
adb shell settings put global time_zone Asia/Kolkata
adb shell setprop persist.sys.timezone Asia/Kolkata || true
adb shell am broadcast -a android.intent.action.LOCALE_CHANGED >/dev/null 2>&1 || true
# Reduce UI/GPU workload before Play Store opens.
adb shell wm size 720x1600 || true
adb shell wm density 320 || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell settings put global animator_duration_scale 0 || true
adb shell settings put system screen_off_timeout 2147483647 || true
adb shell settings put global stay_on_while_plugged_in 3 || true

echo "Opening the official YouTube Create Play Store listing..."
adb shell am start -a android.intent.action.VIEW -d "market://details?id=$PACKAGE"
sleep 8

if [[ -z "${EMULATOR_VNC_PASSWORD:-}" ]]; then
  echo "::error::EMULATOR_VNC_PASSWORD is missing."
  exit 1
fi

x11vnc -storepasswd "$EMULATOR_VNC_PASSWORD" /tmp/x11vnc.pass
x11vnc -display :99 -rfbauth /tmp/x11vnc.pass -forever -shared -rfbport 5900 -bg -o /tmp/x11vnc.log
websockify --web=/usr/share/novnc/ 6080 localhost:5900 >/tmp/websockify.log 2>&1 &
WEBSOCKIFY_PID=$!
cloudflared tunnel --no-autoupdate --url http://localhost:6080 >/tmp/cloudflared.log 2>&1 &
TUNNEL_PID=$!

cleanup() {
  kill "$TUNNEL_PID" "$WEBSOCKIFY_PID" 2>/dev/null || true
  adb emu kill 2>/dev/null || true
}
trap cleanup EXIT

TUNNEL_URL=""
for attempt in $(seq 1 60); do
  TUNNEL_URL="$(grep -Eo 'https://[a-z0-9-]+[.]trycloudflare[.]com' /tmp/cloudflared.log | head -n 1 || true)"
  if [[ -n "$TUNNEL_URL" ]]; then
    break
  fi
  sleep 2
done

if [[ -z "$TUNNEL_URL" ]]; then
  cat /tmp/cloudflared.log
  echo "::error::Could not create temporary emulator screen link."
  exit 1
fi

echo "============================================================"
echo "YT CREATE INSTALL SESSION IS READY"
echo "$TUNNEL_URL/vnc.html?autoconnect=true&resize=remote"
echo "VNC password: use the value stored in repository secret EMULATOR_VNC_PASSWORD."
echo "The Play Store is open on YouTube Create."
echo "Complete Google sign-in on this remote screen if requested."
echo "The installer will tap Install when the button becomes visible."
echo "Device: Pixel 7 Pro | Android 15 | RAM 8 GB | 4 vCPU | 720x1600 | locale en-IN | timezone Asia/Kolkata."
echo "Session duration: $SESSION_MINUTES minutes."
echo "============================================================"

python3 - <<'PY'
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET

PACKAGE = "com.google.android.apps.youtube.producer"
SESSION_MINUTES = int(os.environ.get("SESSION_MINUTES", "45"))

def adb(*args):
    return subprocess.run(
        ["adb", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=30,
    ).stdout

def package_installed():
    return f"package:{PACKAGE}" in adb("shell", "pm", "list", "packages")

deadline = time.monotonic() + SESSION_MINUTES * 60
last_tap = 0.0
last_launcher_kill = 0.0
last_notice = ""
last_heartbeat = 0.0
last_labels = []

while time.monotonic() < deadline:
    if package_installed():
        print("YT_CREATE_INSTALLED=true", flush=True)
        subprocess.run(
            ["adb", "shell", "monkey", "-p", PACKAGE, "1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        break

    try:
        adb("shell", "uiautomator", "dump", "--compressed", "/sdcard/ytcreate-window.xml")
        xml_text = adb("shell", "cat", "/sdcard/ytcreate-window.xml")
    except (subprocess.TimeoutExpired, OSError):
        time.sleep(5)
        continue

    labels = []
    install_bounds = None
    wait_bounds = None
    try:
        root = ET.fromstring(xml_text)
        for node in root.iter("node"):
            text = (node.attrib.get("text") or "").strip()
            desc = (node.attrib.get("content-desc") or "").strip()
            label = text or desc
            if label:
                labels.append(label)
            bounds = node.attrib.get("bounds", "")
            match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
            if match and label.lower() in {"install", "install app"}:
                install_bounds = tuple(map(int, match.groups()))
            if match and label.lower() == "wait":
                wait_bounds = tuple(map(int, match.groups()))
    except ET.ParseError:
        pass

    last_labels = labels
    joined = " | ".join(labels).lower()

    # The Pixel Launcher ANR dialog blocks Play Store interaction.
    # Stop only the frozen launcher process, then bring Play Store back to front.
    if "pixel launcher isn't responding" in joined and time.monotonic() - last_launcher_kill > 30:
        print("Pixel Launcher ANR detected; force-stopping frozen launcher and restoring Play Store (not tapping Wait repeatedly).", flush=True)
        subprocess.run(
            ["adb", "shell", "am", "force-stop", "com.google.android.apps.nexuslauncher"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        time.sleep(2)
        subprocess.run(
            ["adb", "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", f"market://details?id={PACKAGE}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        last_launcher_kill = time.monotonic()

    if "checking info" in joined and last_notice != "checking":
        print("GOOGLE_PLAY_CHECKING_INFO: Play Services is checking the Google account; leaving this screen open.", flush=True)
        last_notice = "checking"
    elif "checking info" not in joined and last_notice == "checking":
        last_notice = ""

    if "sign in" in joined and last_notice != "signin":
        print("WAITING_FOR_GOOGLE_SIGN_IN: Complete sign-in on the remote emulator screen.", flush=True)
        last_notice = "signin"
    elif "sign in" not in joined and last_notice == "signin":
        print("Google sign-in screen is no longer detected; checking Play Store again.", flush=True)
        last_notice = ""

    if any(term in joined for term in (
        "isn't compatible", "not compatible", "not available for your device",
        "this app isn't available", "your device isn't compatible"
    )) and last_notice != "compat":
        print("PLAY_STORE_COMPATIBILITY_WARNING: " + " | ".join(labels[-20:]), flush=True)
        last_notice = "compat"

    if install_bounds and time.monotonic() - last_tap > 15:
        x1, y1, x2, y2 = install_bounds
        x, y = (x1 + x2) // 2, (y1 + y2) // 2
        print(f"Play Store Install button found; tapping at {x},{y}.", flush=True)
        subprocess.run(
            ["adb", "shell", "input", "tap", str(x), str(y)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        last_tap = time.monotonic()

    if time.monotonic() - last_heartbeat >= 45:
        print("Still checking Play Store for Install / Google sign-in. App installed: false.", flush=True)
        last_heartbeat = time.monotonic()

    time.sleep(12)
else:
    print("YT_CREATE_INSTALLED=false (remote session ended before package installation).", flush=True)
    print("Final Play Store screen text: " + " | ".join(last_labels[-30:]), flush=True)
PY

echo "YouTube Create install watcher finished."
