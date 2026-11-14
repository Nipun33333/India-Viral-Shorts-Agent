# India Viral Shorts AI Agent

A scheduled India-focused Shorts pipeline. It discovers public YouTube trend signals, uses Gemini to write an original Hindi/Hinglish story, renders a 24-second vertical MP4, validates the output, and can upload it to YouTube through the official Data API.

## Automated daily workflow

The GitHub Actions workflow is scheduled for **10:00 AM and 6:00 PM India time** (UTC 04:30 and 12:30). GitHub schedules are best-effort and can be delayed.

For each slot, the agent:
1. Searches recent public Indian YouTube videos through the official YouTube Data API when a key is configured.
2. Uses the topics only as broad trend signals. It does not download, copy, remix or re-upload other creators' videos or audio.
3. Uses Gemini to write an original six-scene Hindi/Hinglish story and three optional YouTube Create prompts.
4. Renders a 24-second, 9:16 MP4 with original motion graphics, captions and Hindi voice-over (or a silent audio track if TTS is unavailable).
5. Validates that the MP4 is portrait, at least 720x1280, has audio, and is 20-30 seconds long.
6. Uploads to YouTube as **private** when the YouTube OAuth secrets are configured. The scheduled workflow is automatic; no manual Run workflow click is required.

The default automatic backend is an original motion-graphics renderer. It does not claim to be a cinematic video generator. Uploads remain private for review; do not switch to public until you have reviewed the generated content and metadata.

## YouTube Create app and Gemini Omni

YouTube Create is available in India. Google currently lists Android phones with at least 4 GB RAM as supported; Google Play may still exclude virtual devices. The Gemini Omni video-generation feature inside YouTube Create is experimental, limited to selected creators, and generates clips up to 10 seconds long. It is not a public API that this repository can invoke, sign into, or control.

This project therefore supports two paths:

- **Fully scheduled path — motion:** the GitHub workflow generates and uploads its own 24-second original animated Short automatically. This is the default.
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
- Choose motion for a fully automatic generated preview, or yt_create_manual for three MP4s exported from YouTube Create.
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
- No paid Veo/video-generation API is called by the default workflow.
- YouTube uploads stay private by default. Review before making content public.
- GitHub scheduled runs are best-effort. Instagram publishing is optional and immediate if all Instagram secrets are configured.
