# CutAI Desktop QA Checklist

Use this checklist for a practical final-pass validation of the desktop MVP.

## Test environment

Record before testing:

- Date:
- Tester:
- OS / version:
- Machine:
- FFmpeg version:
- Python env / install method:
- Git commit:

## Required test assets

Prepare at least:

- 1 short MP4 (15–60s, simple happy-path sample)
- 1 medium MP4 (2–5 min real-world sample)
- Optional: 1 failure-case file (odd codec, missing audio, or very large file)

## 1) Native app launch + backend auto-start

- [ ] `pnpm tauri dev` launches the app window successfully
- [ ] App initially shows backend checking/starting state
- [ ] Backend reaches **online** state without manual terminal work
- [ ] If backend is unavailable, retry button remains usable and error copy is understandable

Pass notes:

## 2) Browser dev mode fallback

- [ ] `pnpm dev` launches the frontend
- [ ] Without backend running, app explains that manual backend start is required in browser dev mode
- [ ] Running `cutai server --host 127.0.0.1 --port 18910` restores connectivity

Pass notes:

## 3) Upload → analyze happy path

- [ ] Short MP4 uploads successfully
- [ ] Video metadata appears in the editor
- [ ] Analysis completes without crashing
- [ ] Scene timeline renders
- [ ] Edit plan is generated and visible in the side panel

Pass notes:

## 4) Render happy path

- [ ] Render can be started from the analyzed/uploaded clip
- [ ] Progress UI updates during render
- [ ] Final render completes successfully
- [ ] Output file is playable
- [ ] Subtitles are burned in by default when subtitle ops are present

Pass notes:

## 5) Real-world medium sample

- [ ] Medium video uploads successfully
- [ ] Analysis completes within an acceptable time for local use
- [ ] Edit plan is sensible enough for MVP expectations
- [ ] Render completes or fails with actionable feedback

Pass notes:

## 6) Failure modes

- [ ] Killing the backend causes the UI to show a clear offline/retry state
- [ ] Retry recovers after backend becomes available again
- [ ] Invalid/unreadable input fails with visible feedback instead of silent failure
- [ ] Render failure surfaces an error banner or actionable message

Pass notes:

## 7) Packaging smoke check

- [ ] `pnpm build` succeeds
- [ ] `pnpm tauri build` succeeds on the release machine
- [ ] Built app launches locally
- [ ] Built app can still reach or launch the backend

Pass notes:

## 8) Release notes / known limitations review

Before publishing or sharing a build, confirm docs mention:

- [ ] desktop is alpha
- [ ] browser dev mode needs manual backend startup
- [ ] preview is currently frame-scrubbing oriented, not full playback
- [ ] local-first scope and current limitations are documented

## Sign-off

- Overall result: Pass / Pass with caveats / Blocked
- Main blockers:
- Follow-up issues:
- Recommended for external testing: Yes / No
