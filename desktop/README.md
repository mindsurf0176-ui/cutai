# CutAI Desktop (Tauri)

CutAI Desktop is the local macOS desktop shell for the CutAI editing engine.
It wraps the Python backend with a Tauri + React UI so the main happy path works without opening a terminal.

## Current desktop scope

Today the desktop app is focused on the practical MVP flow:

- auto-start the bundled/local CutAI backend in the native Tauri app
- upload a video from the UI
- run analysis and generate an edit plan
- review detected scenes and planned operations
- render the final video locally
- surface backend/offline errors and allow retry

This is intentionally **local-first**. The app talks to a backend on `127.0.0.1:18910` and does not require a cloud upload pipeline.

## Status

**Alpha, but usable for the core flow.**

Recent validation confirmed:

- desktop auto-backend startup works in the native app
- upload → analyze works on the happy path
- render works on the happy path
- subtitles are burned in by default in the current pipeline
- warm/cinematic-style grading is available through the edit pipeline

## Project structure

- `src/` — React UI
- `src-tauri/` — native Tauri shell and backend launcher integration
- `package.json` — desktop frontend scripts

## Development

### Prerequisites

- Node.js 20+
- pnpm
- Rust toolchain
- Python environment with the CutAI backend dependencies installed
- FFmpeg available on PATH

### Install frontend deps

```bash
cd desktop
pnpm install
```

### Run the desktop frontend in browser dev mode

```bash
cd desktop
pnpm dev
```

In browser dev mode, backend auto-start is **not** available. Start the API server manually in another terminal:

```bash
cutai server --host 127.0.0.1 --port 18910
```

Then open the Vite URL shown in the terminal.

### Run the native Tauri app

```bash
cd desktop
pnpm tauri dev
```

In the native app, CutAI will try to auto-start the local backend when the window opens.

### Production build

```bash
cd desktop
pnpm build
pnpm tauri build
```

### macOS external-alpha release flow

Use the dedicated release guide and helper scripts in this folder:

- [`RELEASE_MACOS.md`](./RELEASE_MACOS.md)
- `pnpm release:macos:build`
- `pnpm release:macos:notarize`
- `pnpm release:macos:verify`

The repo now includes reproducible helper scripts for app signing, DMG signing, notarization, stapling, and Gatekeeper-oriented verification. Apple credentials/certificates are still required for the actual trust-bearing steps.

## Manual QA

Use the validation checklist in [`QA_CHECKLIST.md`](./QA_CHECKLIST.md) before calling the desktop flow release-ready.

## Known limitations

The desktop app is intentionally not pretending to be more finished than it is. Current gaps:

- preview is frame-scrubbing oriented, not full timeline playback
- final credential-backed Developer ID signing/notarization still needs one full machine validation run before wider external sharing
- browser dev mode requires manual backend startup
- advanced edit flows from the CLI are not all exposed in the desktop UI yet
- large/video-edge-case coverage still needs broader QA on real creator footage

## Troubleshooting

### App says backend is unavailable

- confirm `ffmpeg` is installed and available on PATH
- confirm the Python backend environment is installed
- retry from the in-app backend gate
- in browser dev mode, make sure `cutai server --host 127.0.0.1 --port 18910` is running

### Upload or analysis fails

- test with a smaller MP4 first
- check terminal logs from the backend process
- verify the file is readable and not in an unusual codec/container

### Render fails

- verify FFmpeg works from the terminal
- check free disk space in the output directory
- retry with a shorter sample clip to isolate environment issues
