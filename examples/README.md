# CutAI Examples

Practical workflows showing what CutAI can do.

---

## 1. Basic Edit — Remove Silence + Add Subtitles

The most common workflow: clean up a talking-head video.

```bash
$ cutai edit talking_head.mp4 -i "remove silence, add subtitles"

🎬 Analyzing talking_head.mp4...
  ✅ Detected 15 scenes (8:22)
  ✅ Transcribed 1,204 words
  ✅ Found 7 silent segments (1:45 total)

📋 Edit Plan:
  • Remove 7 silent segments
  • Add subtitles (auto-detected: English)

🎬 Rendering → output/talking_head_edited.mp4
  ✅ Done! 6:37 (trimmed 21%)
```

## 2. Style Transfer Workflow

Extract someone's editing style and apply it to your footage.

```bash
# Step 1: Extract the style
$ cutai style-extract reference_video.mp4 -o youtuber-style.yaml
  ✅ Extracted Edit DNA → youtuber-style.yaml

# Step 2: Inspect it
$ cutai style-show youtuber-style.yaml
  ╭──────────────────────────────────────╮
  │  Edit DNA: youtuber-style            │
  ├──────────────────────────────────────┤
  │  Rhythm:                             │
  │    Avg cut length: 2.8s              │
  │    Cuts/min: 15.2                    │
  │    Pacing: dynamic                   │
  │  Visual:                             │
  │    Temperature: warm                 │
  │    Saturation: 1.1×                  │
  │    Contrast: 1.05×                   │
  │  Transitions:                        │
  │    87% jump cuts, 10% fade           │
  │  Audio:                              │
  │    BGM: yes (15% volume)             │
  ╰──────────────────────────────────────╯

# Step 3: Apply to your video
$ cutai edit my_vlog.mp4 --style youtuber-style.yaml
  ✅ Applied youtuber-style to my_vlog.mp4
```

## 3. Highlight Generation

Create a highlight reel from a long video.

```bash
# Best-moments: top scenes by engagement score
$ cutai highlights lecture.mp4 --duration 120 --style best-moments
  ✅ Selected 8 scenes (2:03) from 45:00 source

# Narrative: preserves story arc (keeps intro + ending)
$ cutai highlights documentary.mp4 --duration 300 --style narrative
  ✅ Kept hook + 12 key scenes + conclusion (5:12)

# Shorts: best contiguous ~60s segment
$ cutai highlights gaming_stream.mp4 --duration 60 --style shorts
  ✅ Found best 62s segment starting at 14:23

# View engagement scores to understand the selection
$ cutai engagement lecture.mp4
  ┌─────┬───────────┬───────┬──────────┐
  │ ID  │ Time      │ Score │ Label    │
  ├─────┼───────────┼───────┼──────────┤
  │  0  │ 0:00-0:45 │  72   │ high     │
  │  1  │ 0:45-2:10 │  34   │ low      │
  │  2  │ 2:10-3:55 │  85   │ high     │
  │ ... │           │       │          │
  └─────┴───────────┴───────┴──────────┘
```

## 4. Interactive Chat Session

Edit iteratively through conversation.

```bash
$ cutai chat vlog.mp4

🎬 CutAI Chat — loaded vlog.mp4 (12:34, 23 scenes)
Type instructions or /help for commands.

> remove silence and boring parts
  ✅ Removed 4 silent segments + 3 low-engagement scenes → 8:42

> add subtitles
  ✅ Added subtitles (English, bottom)

> make it warmer
  ✅ Applied warm color grade

> /preview
  🎬 Generating preview (360p)...
  ✅ Preview saved to /tmp/cutai_preview_abc123.mp4

> hmm, undo the color grade
  ↩️ Undone: warm color grade → 2 operations remain

> try cinematic instead
  ✅ Applied cinematic color grade

> /plan
  📋 Current Plan:
    1. Remove 7 segments (silence + low engagement)
    2. Add subtitles (English, bottom, 24px)
    3. Color grade: cinematic

> /render
  🎬 Rendering final video...
  ✅ Done! → output/vlog_edited.mp4 (8:42)
```

### Chat Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/plan` | Display current edit plan |
| `/preview` | Generate low-res preview |
| `/render` | Render final video |
| `/undo` | Undo last edit |
| `/redo` | Redo last undone edit |
| `/style <name>` | Load a style preset |
| `/reset` | Clear all edits |
| `/quit` | Exit chat |

## 5. Multi-Video Edit

Combine multiple clips into one edited video.

```bash
# Travel montage from multiple days
$ cutai multi day1.mp4 day2.mp4 day3.mp4 -i "make a travel montage with fade transitions"
  🎬 Analyzing 3 videos...
  📋 Concatenating → applying edits
  ✅ Done! → combined_output.mp4 (5:23 from 18:45 total)

# Combine with a style preset
$ cutai multi clip1.mp4 clip2.mp4 -i "remove boring parts" --style vlog-casual
  ✅ Done! → combined_output.mp4
```
