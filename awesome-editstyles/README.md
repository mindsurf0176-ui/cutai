# awesome-editstyles 🎬

> A curated collection of EDITSTYLE.md presets for [CutAI](https://github.com/mindsurf0176-ui/cutai) — the open-source AI video editor.

**EDITSTYLE.md** is a portable, markdown-based format for video editing styles. Think [DESIGN.md](https://designmd.ai) but for video editing.

Drop one into your project root → your AI editor follows your style automatically.

---

## What is EDITSTYLE.md?

```markdown
# My Vlog Style

> Source: custom
> CutAI EDITSTYLE v1

## Rhythm
- **Pacing**: fast (12 cuts/min)
- **Silence tolerance**: 0.8s

## Visual
- **Color temperature**: warm

## Subtitles
- **Enabled**: yes
- **Size**: large
```

That's it. A markdown file that captures your editing DNA — readable by both humans and AI.

→ [Full spec](https://github.com/mindsurf0176-ui/cutai/blob/main/docs/EDITSTYLE_SPEC.md)

---

## Presets

### Built-in

| Preset | Style | Best for |
|--------|-------|----------|
| [cinematic](presets/cinematic.md) | Slow pacing, cool tones, dramatic fades | Travel, documentary, b-roll heavy |
| [vlog-casual](presets/vlog-casual.md) | Fast cuts, warm colors, big subtitles | Daily vlogs, talking head, storytime |

### Genre-specific

| Preset | Style | Best for |
|--------|-------|----------|
| [cooking-show](presets/cooking-show.md) | Medium pacing, warm, close-up focus | Recipe videos, mukbang, food content |
| [tech-review](presets/tech-review.md) | Clean cuts, neutral colors, info-dense | Product reviews, unboxing, tutorials |
| [music-video](presets/music-video.md) | Beat-synced cuts, high contrast, no subtitles | MVs, dance covers, performance |
| [podcast-clip](presets/podcast-clip.md) | Minimal cuts, centered subtitles, clean | Podcast highlights, interview clips |
| [shorts-reels](presets/shorts-reels.md) | Ultra-fast, vertical-optimized, punchy | YouTube Shorts, TikTok, Reels |

---

## Usage

```bash
# Apply a preset
cutai edit video.mp4 --editstyle awesome-editstyles/presets/vlog-casual.md

# Or copy to your project root as EDITSTYLE.md (auto-detected)
cp awesome-editstyles/presets/cinematic.md ./EDITSTYLE.md
cutai edit video.mp4 -i "edit this"

# Convert existing YAML to EDITSTYLE.md
cutai style-convert style.yaml --to md
```

---

## Contributing

1. Create a new `.md` file in `presets/` or `community/`
2. Follow the [EDITSTYLE.md spec](https://github.com/mindsurf0176-ui/cutai/blob/main/docs/EDITSTYLE_SPEC.md)
3. Include the `> CutAI EDITSTYLE v1` marker in the header
4. Add a brief description of when this style works best
5. PR it!

### Validation

```bash
cutai style-validate your-style.md
```

---

## License

CC0 1.0 — Public domain. Use these presets however you want.
