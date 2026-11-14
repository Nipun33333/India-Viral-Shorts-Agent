# India Viral Shorts AI Agent

A scheduled India-focused cloud Shorts pipeline. It discovers public YouTube trend signals, uses Gemini to write an original Hindi/Hinglish story, can generate cinematic 9:16 video through the Gemini Omni API, renders and validates an MP4, then can upload privately through the official YouTube Data API.

## Automated daily workflow

The GitHub Actions workflow is scheduled for **10:00 AM and 6:00 PM India time** (UTC 04:30 and 12:30). GitHub schedules are best-effort and can be delayed.

For each slot, the agent:
1. Searches recent public Indian YouTube videos through the official YouTube Data API when a key is configured.
2. Uses the topics only as broad trend signals. It does not download, copy, remix or re-upload other creators' videos or audio.
3. Uses Gemini to write an original six-scene Hindi/Hinglish story and three optional YouTube Create prompts.
4. Uses the selected video backend: Gemini Omni cloud video generation, or the no-video-API motion-graphics fallback. It renders a 9:16 MP4 and adds Hindi narration.
5. Validates that the MP4 is portrait, at least 720x1280, has audio, and is 20-30 seconds long.
6. Uploads to YouTube as **private** when the YouTube OAuth secrets are configured. The scheduled workflow is automatic; no manual Run workflow click is required.

The scheduled workflow defaults to motion graphics so that paid video-generation calls are never enabled unexpectedly. To run a fully generated cloud-video pipeline, select `gemini_video` manually or set the repository variable `VIDEO_BACKEND=gemini_video`. Uploads remain private for review; do not switch to public until you have reviewed the generated content and metadata.

## Fully cloud AI video generation

The cloud backend uses Google's **Gemini Omni 1.1 Flash** Interactions API directly. It does not open or automate the YouTube Create Android app, and it requires no phone, emulator, USB cable, persistent Android login, or device session.

For each Short, the pipeline:
1. Writes an original six-scene Hindi/Hinglish script from Indian trend signals.
2. Requests an initial 10-second vertical 9:16 video from Gemini Omni.
3. Extends that same video in another 10-second turn, preserving the characters and scene continuity. A 20-second Short uses two generation turns; a 30-second Short uses three.
4. Normalizes the generated MP4 to 720x1280 portrait, 24 fps, mixes generated ambience with Hindi TTS narration, validates 20/30 seconds, and marks synthetic media disclosure.
5. Uploads privately using the existing YouTube OAuth refresh-token flow.

### Enable cloud generation

Add the existing `GEMINI_API_KEY` under **Settings → Secrets and variables → Actions → Secrets**. Gemini Omni video generation is a paid-tier API capability.

For a manual test, open **Actions → India Viral Shorts - two daily slots → Run workflow** and select `gemini_video`. Keep `publish` unchecked for a private local artifact preview (no YouTube upload).

To enable scheduled cloud video generation, add the repository variable under **Settings → Secrets and variables → Actions → Variables**:

- `VIDEO_BACKEND` = `gemini_video`
- Optional: `GEMINI_VIDEO_TARGET_SECONDS` = `20` or `30` (default 20)
- Optional: `GEMINI_VIDEO_MODEL` = `gemini-omni-1.1-flash`

The scheduled jobs remain on the motion backend until `VIDEO_BACKEND` is explicitly set to `gemini_video`, to avoid unexpected paid API charges.

### Video generation cost

Google currently lists Gemini Omni 1.1 Flash video output at an effective price of approximately **US$0.10 per generated second at 720p**. Approximate video-generation charges, excluding script tokens, YouTube API, GitHub Actions and any taxes:

| Output length | Approx. per Short | Two Shorts/day for 30 days |
|---|---:|---:|
| 20 seconds | US$2.00 | US$120 |
| 30 seconds | US$3.00 | US$180 |

Actual charges depend on output duration and API billing. Start with a single manual 20-second run and check Google AI Studio usage before enabling the daily schedule. [Official Gemini Omni docs](https://ai.google.dev/gemini-api/docs/omni) · [Official pricing](https://ai.google.dev/gemini-api/docs/pricing).

## YouTube Create app and Gemini Omni

YouTube Create is available in India. Google lists supported Android phones with at least 4 GB RAM. Its Gemini Omni video feature is experimental and available only to a limited number of creators in selected countries (including India); it can generate vertical clips up to 10 seconds, and each prompt is limited to 900 characters. It is not a public API that this repository can invoke, sign into, or control. See the [official YouTube Create AI guide](https://support.google.com/youtube/answer/16631240?hl=en-IN) and [supported countries / device requirements](https://support.google.com/youtube/answer/13952912?hl=en-IN).

This project therefore supports two paths:

- **Cloud video path — gemini_video:** Gemini Omni generates and extends a real video in the cloud; FFmpeg adds Hindi narration and formats the final 20/30-second Short. Enable it with the manual backend option or the repository variable described above.
- **YouTube Create-assisted path — yt_create_manual:** Gemini writes three 8-second shot prompts into the output artifact. Paste them into YouTube Create's Generate video feature if it is enabled on your account, export the three clips, then provide those MP4 files to this repository. The agent normalizes, joins, adds Hindi narration, validates and uploads the finished Short.

For the manual YouTube Create path, save the exported clips in the repository before running the workflow:

- Slot 1: yt_create_inputs/slot1/shot_1.mp4, shot_2.mp4, shot_3.mp4
- Slot 2: yt_create_inputs/slot2/shot_1.mp4, shot_2.mp4, shot_3.mp4

Each clip should be about 8 seconds and portrait. Choose the yt_create_manual backend in Actions. The final joined video is about 24 seconds. Generated clips are marked as containing synthetic media in the YouTube upload metadata.

The one-time Android screen workflow creates a Pixel 7 Pro hardware profile with 6 GB RAM, sets Android's locale to en-IN and timezone to Asia/Kolkata, and opens the Play Store listing for YouTube Create. This improves the emulator's declared hardware profile; it does **not** turn an emulator into a certified physical phone or bypass Play Integrity. The Google Play country is tied to the signed-in Google account's Play country/profile, not just the device's locale or timezone. If Play Store still says the device is incompatible, use a supported physical Android phone; do not spoof device integrity or bypass Google's compatibility checks.

Google account sign-in and any YouTube Create UI actions remain manual. Never put Google passwords, one-time codes, OAuth tokens or VNC passwords in the repository or in chat.

## GitHub secrets

Open **Settings → Secrets and variables → Actions** and add the credentials you intend to use:

| Secret | Purpose |
|---|---|
| GEMINI_API_KEY | Gemini text generation for original scripts and shot prompts |
| YOUTUBE_API_KEY | Optional official public Indian YouTube trend discovery |
| YOUTUBE_CLIENT_ID | YouTube OAuth client ID |
| YOUTUBE_CLIENT_SECRET | YouTube OAuth client secret |
| YOUTUBE_REFRESH_TOKEN | YouTube OAuth refresh token with youtube.upload scope |
| IG_USER_ID | Optional Instagram Professional account ID |
| IG_ACCESS_TOKEN | Optional Meta access token with Reels publishing permission |
| CLOUDINARY_CLOUD_NAME | Optional public MP4 hosting for Instagram |
| CLOUDINARY_API_KEY | Optional Cloudinary API key |
| CLOUDINARY_API_SECRET | Optional Cloudinary API secret |
| EMULATOR_VNC_PASSWORD | One-time Android screen workflow password; use at least 16 characters |

Enable YouTube Data API v3 in Google Cloud and create an OAuth client. The uploader uses the official YouTube Data API and OAuth scope https://www.googleapis.com/auth/youtube.upload. Do not commit client-secret JSON, refresh tokens, cookies or .env files.

The YouTube API upload explicitly sets privacy to private by default and sets the synthetic-media disclosure for the YouTube Create-assisted AI clip path. If content depicts realistic altered or synthetic scenes or people, review YouTube's disclosure requirements before making it public.

## Running a preview manually

Open **Actions → India Viral Shorts - two daily slots → Run workflow**:
- Choose slot 1, slot 2, or all.
- Choose gemini_video for paid cloud-generated video, motion for no-video-API motion graphics, or yt_create_manual for three MP4s exported from YouTube Create.
- Keep publish unchecked for a preview. Manual runs do not upload unless you explicitly check publish.

The scheduled runs publish automatically as private when YouTube OAuth is configured. If the credentials are missing, the workflow still creates the MP4 and prompt files and records that upload was skipped.

## Run locally

Requires Python 3.12+, FFmpeg/ffprobe, and optionally espeak-ng.

~~~bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Keep AUTO_PUBLISH=false while testing.
python -m shorts_agent.main --slot 1 --backend motion
python -m pytest -q
~~~

Output files are written to output/YYYY-MM-DD/slot1/ and slot2/. Each slot includes the MP4, script.json, quality_report.json, yt_create_prompts.md and publish_result.json.

## Limitations and safety

- Viral performance cannot be guaranteed. Public trend counts are signals, not proof that a video will go viral.
- The agent creates new stories. It must not download or reproduce viral creators' actual clips, dialogue, faces, music or edits.
- YouTube Create does not currently expose a supported public editor API for unattended automation; its prompts and clip exports are therefore a manual optional stage.
- Gemini Omni inside YouTube Create is available only to selected creators; availability of the app does not guarantee access to its generative video tools.
- Paid Gemini Omni video-generation calls are only made when the gemini_video backend is selected. The scheduled workflow defaults to motion until VIDEO_BACKEND=gemini_video is explicitly configured.
- YouTube uploads stay private by default. Review before making content public.
- GitHub scheduled runs are best-effort. Instagram publishing is optional and immediate if all Instagram secrets are configured.
