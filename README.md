# 🎬 CutAI

> AI video editor that takes natural language instructions and edits videos locally.

```bash
cutai edit video.mp4 --instruction "remove silence, add subtitles"
```

## Features

- **Natural language editing** — describe what you want, AI does the rest
- **100% local** — no cloud uploads, complete privacy
- **Scene detection** — automatic scene boundary detection
- **Transcription** — OpenAI Whisper for speech-to-text
- **Smart cuts** — remove silence, trim to duration, keep interesting parts
- **Subtitles** — auto-generated from transcript (ASS format, burned in)
- **Open source** — MIT license, free forever

## Installation

```bash
# Prerequisites
brew install ffmpeg  # macOS

# Install CutAI
pip install -e .

# Verify
cutai --help
```

## Quick Start

### Analyze a video

```bash
cutai analyze video.mp4
cutai analyze video.mp4 --output analysis.json
```

### Remove silence and add subtitles

```bash
cutai edit video.mp4 -i "remove silence and add subtitles"
```

### Plan only (no render)

```bash
cutai plan video.mp4 -i "trim to 5 minutes" --no-llm
```

### Use rule-based planning (no API key needed)

```bash
cutai edit video.mp4 -i "무음 제거" --no-llm
```

## Configuration

Create `~/.cutai/config.yaml`:

```yaml
openai_api_key: sk-...
default_whisper_model: base
default_llm: gpt-4o
output_dir: ./output
```

Or use environment variables:

```bash
export OPENAI_API_KEY=sk-...
export CUTAI_WHISPER_MODEL=base
```

## Requirements

- Python ≥ 3.10
- FFmpeg
- ~2GB disk for Whisper base model

## License

MIT
