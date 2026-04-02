# Show HN Draft (Final)

## Title
Show HN: CutAI – Edit videos by describing what you want, learn styles from any video (open-source)

## URL
https://cutai.studio

## Text

Hi HN, I built CutAI — an open-source video editor where you describe edits in plain language and it does them on your machine.

```
cutai edit vlog.mp4 -i "remove boring parts, add subtitles, make it cinematic"
```

That one line: detects scenes, removes dead air, generates subtitles via Whisper, applies a cinematic color grade, and renders the output. No timeline dragging, no cloud upload.

**How it works:**
1. Scene analysis detects boundaries and transcribes speech
2. Your instruction gets translated into a concrete edit plan (what to cut, what to add, what to grade)
3. FFmpeg renders the result

Works in English and Korean. Rule-based planning runs fully offline; plug in an LLM for more nuanced instructions.

**The part I'm most excited about: Edit Style Transfer**

Beyond single instructions, CutAI can extract the editing "DNA" from any reference video:

```bash
cutai style-extract reference.mp4 -o style.yaml
cutai edit my-video.mp4 --style style.yaml
```

The Edit DNA captures cut rhythm (scene durations, pacing curves), visual style (color temperature, brightness), subtitle patterns, audio mixing, and transitions. Think of it as style transfer but for *editing decisions* rather than pixels.

You can also blend styles from multiple videos:

```bash
cutai style-learn vid1.mp4 vid2.mp4 vid3.mp4 -o brand.yaml
```

**What this enables:**
- Tell CutAI what you want in one sentence → done
- Extract a YouTuber's editing patterns → apply to your footage
- Build a reusable brand style → consistent edits across all your content
- Style files are plain YAML — version them, share them, tweak them

**Local-first:** everything runs on your machine. There's also a Tauri desktop app (macOS alpha, signed) for drag-and-drop workflows.

Python + FFmpeg + Whisper. MIT licensed.

What editing tasks would you throw at a tool like this?
