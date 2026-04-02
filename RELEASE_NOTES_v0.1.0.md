# CutAI v0.1.0-alpha — First Public Release 🎬

> AI video editor with natural language instructions. Local-first, open-source.

## What is CutAI?

Give it a video and a sentence — CutAI analyzes scenes, generates an edit plan, and renders the result on your machine. No cloud upload required.

```bash
cutai edit vlog.mp4 -i "remove boring parts, add subtitles, make it warm and cinematic"
```

## Highlights

### 🎯 Natural Language Editing
Describe what you want in plain English or Korean. CutAI translates your intent into a concrete edit plan and executes it.

### ✂️ Smart Editing Pipeline
- **Scene detection** — content-aware scene boundary analysis
- **Silence trimming** — automatic dead air and low-value segment removal
- **Auto subtitles** — Whisper-powered transcription and burn-in
- **Color grading** — warm / bright / cool / cinematic presets
- **BGM mixing** — background music when requested
- **Transitions & speed control**

### 🎨 Edit Style Transfer (new)
- Extract editing patterns from a reference video as portable "Edit DNA"
- Apply styles across different videos
- Learn styles from multiple references
- Built-in presets: `cinematic`, `vlog-casual`

### 🔥 Smart Highlights
- Engagement scoring to rank scenes by interest
- Auto-generate short reels from strongest moments
- Target specific durations

### 🖥️ Desktop App (macOS alpha)
- Native Tauri app with drag-and-drop upload
- Analyze → plan → style → render workflow
- Signed and notarized for macOS

### 🔒 Local-First
- No cloud upload — everything runs on your machine
- Works offline with rule-based planning
- Optional LLM planning for richer instructions

## Install

### CLI (recommended)
```bash
pip install cutai
cutai --help
```

### Desktop (macOS)
Download `CutAI_0.1.0_aarch64.dmg` from the release assets below.  
Requires macOS 12+ and Apple Silicon (arm64).

## Known Limitations (alpha)

- Desktop preview is frame-scrubbing, not full playback yet
- Edge-case codecs and very long videos may need tuning
- Desktop exposes the core MVP flow; not all CLI features are surfaced yet

## What's Next

- Windows/Linux desktop builds
- Full video preview playback
- More style presets
- Plugin system for custom edit operations

---

**License:** MIT  
**Repo:** https://github.com/mindsurf0176-ui/cutai
