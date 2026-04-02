# CutAI v0.2.0 — Agent Mode, MCP Server, EDITSTYLE.md 🎬🤖

> AI video editor with natural language instructions. Local-first, open-source.

This release transforms CutAI from a single-pipeline editor into an **agentic video editing platform**.

---

## What's new

### 🤖 Agent Mode

Goal-driven autonomous editing. Give it a high-level goal — it analyzes, plans, renders, self-evaluates, and iterates until the result is good enough.

```bash
cutai agent video.mp4 --goal "make a warm, casual vlog with subtitles" --iterations 3
cutai agent clip1.mp4 clip2.mp4 --goal "best moments reel, 3 minutes"
```

- Multi-step edit loop with self-evaluation
- Feedback from previous iterations feeds into the next
- EDITSTYLE.md auto-detection in agent loop
- Configurable iteration count and quality threshold

### 🔌 MCP Server

Connect CutAI to AI coding agents (Claude Code, Cursor, Gemini CLI) via the Model Context Protocol.

```json
{
  "mcpServers": {
    "cutai": {
      "command": "cutai",
      "args": ["mcp-server"]
    }
  }
}
```

8 tools exposed: `cutai_analyze`, `cutai_plan`, `cutai_edit`, `cutai_agent`, `cutai_style_extract`, `cutai_highlights`, `cutai_engagement`, `cutai_editstyle_parse`.

### 📝 EDITSTYLE.md

A portable, markdown-based format for video editing styles — inspired by Google Stitch's DESIGN.md.

```markdown
# My Vlog Style

> Source: custom
> CutAI EDITSTYLE v1

## Rhythm
- **Pacing**: fast (12 cuts/min)

## Visual
- **Color temperature**: warm
```

- Human-readable AND AI-native
- Auto-detected in project root
- Full spec: `docs/EDITSTYLE_SPEC.md`
- New commands: `cutai style-convert`, `cutai style-validate`

### 🎨 awesome-editstyles

7 curated presets ready to use:

| Preset | Best for |
|--------|----------|
| `cinematic` | Travel, documentary |
| `vlog-casual` | Daily vlogs, talking head |
| `cooking-show` | Recipe videos, food content |
| `tech-review` | Product reviews, tutorials |
| `music-video` | MVs, dance covers |
| `podcast-clip` | Interview highlights |
| `shorts-reels` | TikTok, YouTube Shorts, Reels |

### ⚡ Performance

- **MLX Whisper** support — 3-5x faster transcription on Apple Silicon
- **VideoToolbox** detection — hardware H.264/HEVC encoding on macOS
- **Analysis cache** — skip re-analysis for previously processed videos
- Backend auto-detection: mlx-whisper → faster-whisper → openai-whisper

---

## New commands

| Command | Description |
|---------|-------------|
| `cutai agent` | 🤖 Goal-driven autonomous editing |
| `cutai mcp-server` | 🔌 MCP Server for AI agent integration |
| `cutai style-convert` | Convert YAML ↔ EDITSTYLE.md |
| `cutai style-validate` | Validate EDITSTYLE.md files |

---

## Stats

- 219 tests passing
- 20 CLI commands total
- E2E tested: analyze → plan → render → agent loop

---

## Install / Upgrade

```bash
pip install --upgrade cutai
```

---

## What's next (v0.3.0)

- NLE export (FCPXML, EDL, Premiere XML)
- Web UI
- Community Style Hub
- GPU-accelerated rendering pipeline
- Plugin system

---

**License:** MIT
**Repo:** https://github.com/mindsurf0176-ui/cutai
