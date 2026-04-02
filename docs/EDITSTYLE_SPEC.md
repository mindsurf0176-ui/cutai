# EDITSTYLE.md — Specification v1

> The portable, markdown-based format for video editing styles — built for AI-native video editing.
> Inspired by Google Stitch's DESIGN.md for UI design systems.

---

## Overview

EDITSTYLE.md is a markdown file that captures everything an AI video editor needs to produce consistent edits: rhythm, transitions, color grading, audio mixing, subtitles, structural patterns, and editorial rules — all in plain text.

**EDITSTYLE.md is to video editing what DESIGN.md is to UI design.**

Unlike YAML presets or JSON configs, EDITSTYLE.md is:
- **Human-readable**: Creators (not just developers) can read and edit it
- **AI-native**: LLMs understand natural language context alongside numeric values
- **Version-controllable**: Plain text in git, reviewable in PRs
- **Tool-agnostic**: Works with CutAI, Claude Code, Cursor, or any AI that reads project files
- **Shareable**: Drop it on GitHub, and anyone can replicate your editing style

---

## Relationship to EditDNA (YAML)

EDITSTYLE.md is a **superset** of CutAI's existing EditDNA YAML format.

| Aspect | EditDNA (YAML) | EDITSTYLE.md |
|--------|---------------|--------------|
| Values | Numeric only | Numeric + natural language context |
| Audience | Developers | Creators + Developers + AI agents |
| Context | `color_temperature: warm` | "warm — 친근하고 일상적인 톤" |
| Patterns | Not supported | Intro/outro/segment structure |
| Rules | Not supported | Do's and don'ts for editing |
| Interop | CutAI only | Any AI tool that reads markdown |

Internally, CutAI parses EDITSTYLE.md into an EditDNA object, so all existing style application code works unchanged.

---

## File Format

### Header

```markdown
# <Style Name>

> Source: <origin — channel name, video URL, or "custom">
> Author: <who created/modified this>
> CutAI EDITSTYLE v1
```

The `CutAI EDITSTYLE v1` marker is **required** for auto-detection.

### Sections

All sections are optional. Missing sections use CutAI defaults.

---

### `## Rhythm`

Controls pacing and cut frequency.

| Field | Format | Maps to EditDNA | Description |
|-------|--------|-----------------|-------------|
| Pacing | keyword (slow/medium/fast) or number | `cuts_per_minute` | slow=6, medium=10, fast=14+ |
| Average cut length | `Xs` (seconds) | `avg_cut_length` | Target average duration per cut |
| Cut variance | `±Xs` | `cut_length_variance` | Standard deviation |
| Pacing curve | keyword | `pacing_curve` | constant, slow-fast-slow, fast-slow, slow-fast, dynamic |
| Silence tolerance | `Xs` | `audio.silence_tolerance` | Max silence before auto-cut |

**Example:**
```markdown
## Rhythm
- **Pacing**: fast (12 cuts/min)
- **Average cut length**: 4s (±2s)
- **Pacing curve**: slow-fast-slow
- **Silence tolerance**: 0.8s
```

---

### `## Transitions`

Defines transition type distribution and duration.

| Field | Format | Maps to EditDNA |
|-------|--------|-----------------|
| Jump cut | percentage | `jump_cut_ratio` |
| Fade | percentage | `fade_ratio` |
| Dissolve | percentage | `dissolve_ratio` |
| Wipe | percentage | `wipe_ratio` |
| Transition duration | `Xs` | `avg_transition_duration` |

Percentages should sum to 100%. Contextual notes after `—` are encouraged.

**Example:**
```markdown
## Transitions
- **Jump cut**: 85% — default energy-keeping transition
- **Fade**: 10% — only for part changes
- **Dissolve**: 5% — emotional scenes
- **Transition duration**: 0.3s
```

---

### `## Visual`

Color grading and visual tone.

| Field | Format | Maps to EditDNA |
|-------|--------|-----------------|
| Color temperature | warm/neutral/cool | `color_temperature` |
| Saturation | multiplier (1.0 = neutral) | `avg_saturation` |
| Contrast | multiplier | `avg_contrast` |
| Brightness | offset (-1 to 1) | `avg_brightness` |
| Preset | keyword | Used for ColorGradeOperation |

**Example:**
```markdown
## Visual
- **Color temperature**: warm — friendly, everyday tone
- **Saturation**: 1.1 (slightly vivid)
- **Contrast**: 1.05
- **Brightness**: +0.05
```

---

### `## Audio`

Background music and audio mixing.

| Field | Format | Maps to EditDNA |
|-------|--------|-----------------|
| BGM | yes/no + genre + volume% | `has_bgm`, `bgm_volume_ratio` |
| Speech ratio | percentage | `speech_ratio` |
| Fade in/out | `Xs` | BGMOperation defaults |

**Example:**
```markdown
## Audio
- **BGM**: yes, lo-fi / upbeat, 12% volume
- **Speech ratio**: 65%
- **Fade in/out**: 2s
```

---

### `## Subtitles`

Subtitle generation preferences.

| Field | Format | Maps to EditDNA |
|-------|--------|-----------------|
| Enabled | yes/no | `has_subtitles` |
| Position | bottom/center/top | `position` |
| Size | small/medium/large | `font_size_category` |
| Style | keyword | SubtitleOperation style |
| Language | ISO code or "auto" | SubtitleOperation language |

**Example:**
```markdown
## Subtitles
- **Enabled**: yes
- **Position**: bottom
- **Size**: large
- **Language**: ko
```

---

### `## Patterns` (EDITSTYLE.md exclusive — not in EditDNA)

Structural editing patterns. These are parsed as high-level instructions fed to the LLM planner, not mapped to EditDNA fields.

**Example:**
```markdown
## Patterns
- **Cold open**: yes — start with a highlight moment
- **Intro**: 3-5s title card
- **Outro**: natural ending, no subscribe CTA
- **Segment length**: ~45s per topic
```

---

### `## Rules` (EDITSTYLE.md exclusive — not in EditDNA)

Editorial do's and don'ts. Parsed as constraints for the LLM planner.

**Example:**
```markdown
## Rules
- ❌ No single scene longer than 10s
- ❌ No silent gaps without BGM
- ✅ Always include subtitles
- ✅ Keep 0.1s micro-gap on jump cuts for breathing room
```

---

## Auto-Detection

CutAI auto-detects EDITSTYLE.md in the following order:
1. `--editstyle <path>` CLI flag (explicit)
2. `EDITSTYLE.md` in the current working directory
3. `EDITSTYLE.md` next to the input video file
4. `~/.config/cutai/default-editstyle.md` (global default)

---

## CLI Commands

```bash
# Apply EDITSTYLE.md (auto-detected or explicit)
cutai edit video.mp4 -i "edit this"
cutai edit video.mp4 --editstyle ./styles/dingo.md

# Extract EDITSTYLE.md from a reference video
cutai style extract reference.mp4 --format md -o EDITSTYLE.md

# Convert between formats
cutai style convert cinematic.yaml --to md
cutai style convert EDITSTYLE.md --to yaml

# Validate an EDITSTYLE.md file
cutai style validate EDITSTYLE.md
```

---

## Versioning

The format version is indicated by the header marker:
- `CutAI EDITSTYLE v1` — current version (this spec)

Future versions will maintain backward compatibility. New sections are always optional.

---

## Community & Sharing

EDITSTYLE.md files can be shared via:
- GitHub repositories (drop in project root)
- `awesome-editstyles` community collection (planned)
- `cutai style install <name>` from registry (planned)

The markdown format makes them naturally previewable on GitHub, shareable on social media, and forkable by the community.
