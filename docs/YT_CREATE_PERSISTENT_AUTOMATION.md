# Persistent YouTube Create automation

## Why the temporary Actions emulator is not the right place to sign in

The GitHub-hosted Android emulator is temporary. A fresh hosted runner is provisioned for each job, and its disk is discarded after the job. A Google sign-in completed there is not a durable login for future jobs.

Do not put a signed-in Android AVD, Google account state, cookies, or app session files in GitHub Actions cache or public artifacts. The repository is public, and authentication state is sensitive.

## Recommended setup

Use a real Android phone that stays connected by USB to an always-on Windows PC. Install YouTube Create from Google Play and sign in directly on that phone once. The Google login stays on that phone, not in the repository.

1. On the Android phone, install YouTube Create from Google Play.
2. Sign in to YouTube Create with the intended Google account.
3. On the phone, enable Developer options and USB debugging.
4. Connect the phone to the Windows PC by USB, unlock it, and accept the USB debugging RSA prompt.
5. On Windows, install Android SDK Platform-Tools and add the platform-tools folder to PATH.
6. Open PowerShell in the repository folder and run:

   powershell
   .\tools\yt_create_phone_preflight.ps1

The preflight script confirms the phone is authorized, checks that YouTube Create is installed, launches it, and saves a local accessibility/UI snapshot under .runtime. It does not read passwords, OTPs, or session tokens. The snapshot is ignored by Git and should not be posted publicly.

## What can be automated after the device is connected

Android UI automation can drive apps through Appium's UiAutomator2 driver. The next implementation step is to inspect the actual signed-in YouTube Create screens on this account, then automate only the buttons and screens that are actually present. This matters because YouTube Create's AI features are experimental and are not enabled for every creator.

Google's documented Gemini Omni feature in YouTube Create generates clips up to 10 seconds, and the prompt limit is 900 characters. Google's Edit with AI flow starts from selected media items, then offers voiceover, music, and captions. It exports or uploads from the app. A 20–30 second Short will therefore need multiple generated clips or an Edit-with-AI source-media workflow.

## Scheduling and persistence

For unattended creation, the phone must remain powered on and connected, and the Windows PC must remain awake and online. A Windows Task Scheduler job can run the local pipeline at the chosen times and use ADB/Appium to control the phone.

A GitHub-hosted runner cannot reach a phone attached to your PC. A GitHub self-hosted runner is another option, but this repository is currently public. GitHub warns that self-hosted runners on public repositories can be exposed to untrusted pull-request code. Do not attach a personal device/account to a runner for this public repository without first moving the device workflow to a private, restricted repository.

## Current boundary

The current GitHub workflow validates installation on a disposable emulator. It is not yet an unattended YouTube Create video generator. The signed-in-device preflight is the next prerequisite; after its screen snapshot is inspected, the app-specific UI automation can be implemented and tested.
