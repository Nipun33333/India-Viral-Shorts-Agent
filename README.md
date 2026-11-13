# India Viral Shorts AI Agent

Creates two original **20-second, vertical 9:16 Hindi/Hinglish Shorts** per day and can publish to YouTube Shorts and Instagram Reels after you add your own API credentials.

## What it does

- Uses free-tier Gemini text API (optional) to write original five-scene scripts, hooks, captions and hashtags.
- Uses official YouTube Data API search signals for recent India-focused ideas; Instagram trends are not available through this workflow and can be added to `manual_trends.json`.
- Renders an original animated-card/cartoon-style MP4 with FFmpeg + Pillow. This is a free fallback, not cinematic Flow output.
- Optional Google Flow mode: manually export two 10-second clips per slot; the agent joins them into a 20-second vertical video.
- Schedules two GitHub Actions runs daily at **10:00 AM and 6:00 PM IST** (GitHub cron is best-effort).
- YouTube uploads default to **private** for review. Instagram publishing is immediate once its credentials are configured.

## Google Flow credits: important

Flow's daily credits belong to the Flow website/app; they are **not** developer API credits. This repository does not automate Flow login or spend Flow website credits. A free Gemini text API key does not provide free Veo video API access. To use Flow, generate/export clips manually and place them in `flow_inputs/slot1/` or `flow_inputs/slot2/` as `scene_1.mp4` and `scene_2.mp4`, then run the workflow with backend `flow_manual` only if the clips are available to the runner (for a local run, use the CLI below). No cookie scraping or reverse-engineered endpoints are used.

## Configure GitHub Actions

Open **Settings → Secrets and variables → Actions → New repository secret** and add only the credentials you intend to use:

| Secret | Purpose |
|---|---|
| `GEMINI_API_KEY` | Optional free-tier Gemini text generation; without it, built-in sample scripts are used |
| `YOUTUBE_API_KEY` | Optional official India-focused public YouTube trend search |
| `YOUTUBE_CLIENT_ID` | YouTube OAuth client ID |
| `YOUTUBE_CLIENT_SECRET` | YouTube OAuth client secret |
| `YOUTUBE_REFRESH_TOKEN` | OAuth refresh token with `youtube.upload` scope |
| `IG_USER_ID` | Instagram Professional account ID |
| `IG_ACCESS_TOKEN` | Meta access token with Reels publishing permissions |
| `CLOUDINARY_CLOUD_NAME` | Public MP4 hosting for Instagram's server-side fetch |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |

YouTube requires the YouTube Data API v3 and OAuth scope `https://www.googleapis.com/auth/youtube.upload`. Instagram requires an eligible Professional (Creator/Business) account and Meta permissions. Cloudinary hosts the video so Meta can fetch it. Never commit keys, refresh tokens, cookies or `.env` files.

### Safe first run

1. Add `GEMINI_API_KEY` and, optionally, `YOUTUBE_API_KEY`.
2. Open **Actions → India Viral Shorts - two daily slots → Run workflow**.
3. Choose `slot=1` and `backend=motion` to create a preview.
4. Inspect the artifact before configuring upload credentials. YouTube remains private by default; change `YOUTUBE_PRIVACY` in the workflow to `public` only after testing. Do not add Instagram secrets until you are ready for immediate publishing.

## Run locally

Requires Python 3.12+, FFmpeg, and optionally `espeak-ng` for local speech fallback.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set AUTO_PUBLISH=false in .env while testing
python -m shorts_agent.main --slot all --backend motion
python -m pytest -q
```

Videos and JSON receipts are written to `output/YYYY-MM-DD/slot1/` and `slot2/`. If no TTS engine is available, the video still renders with captions and silent audio.

### Optional local Flow mode

Export two original 10-second MP4 clips from Flow into the matching slot folder, named `scene_1.mp4` and `scene_2.mp4`, then run:

```bash
python -m shorts_agent.main --slot 1 --backend flow_manual
```

The same applies to slot 2. The tool normalizes and joins each pair to 20 seconds. A 360p input upscaled to 720×1280 does not become native HD.

## Limitations

- Viral performance is never guaranteed. The system learns from public trend signals but writes new material; it does not copy other creators' videos or audio.
- Instagram Reels trend discovery is not automated here.
- GitHub scheduled runs may be delayed or skipped. Uploading requires correctly configured credentials and successful platform API responses.
- No paid video API is called. For fully automatic cinematic video generation, a supported paid video API and explicit billing approval would be needed.
