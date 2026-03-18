# CutAI — Comprehensive Code Review

> Reviewed: 2026-03-18
> Scope: All source files under `cutai/`, `pyproject.toml`, `PRD.md`
> Test reference: 2560×1440, HEVC, 60fps, 17.6min, ~3GB

---

## Table of Contents

1. [Architecture & Module Structure](#1-architecture--module-structure)
2. [Code Quality Review](#2-code-quality-review)
3. [Bug / Issue Detection](#3-bug--issue-detection)
4. [Performance & Optimization for Large Files](#4-performance--optimization-for-large-files)
5. [Feature Completeness](#5-feature-completeness)
6. [Specific Recommendations (Prioritized)](#6-specific-recommendations-prioritized)

---

## 1. Architecture & Module Structure

### Overall Assessment: **Solid foundation, clean separation**

The codebase follows a clear pipeline architecture:

```
CLI (cli.py)
 └─ analyze_video()       — analyzer/
     ├─ scene_detector.py  — PySceneDetect
     ├─ transcriber.py     — Whisper
     └─ quality_analyzer.py — FFmpeg silencedetect + astats
 └─ create_edit_plan()    — planner/
     └─ edit_planner.py    — Rule-based + LLM
 └─ render()              — editor/
     ├─ cutter.py          — FFmpeg segment extraction + concat
     ├─ subtitle.py        — ASS generation + burn
     └─ renderer.py        — Orchestrator
```

**Strengths:**
- Clean Pydantic v2 models with proper validation (`types.py`)
- Config uses env vars → file → defaults priority chain (good practice)
- `__init__.py` files provide clean public APIs
- Rich/Typer CLI gives excellent UX out of the box
- Sidecar subtitle mode (default) avoids unnecessary re-encoding — smart design choice

**Weaknesses:**
- `renderer.py` lives inside `editor/` but acts as the orchestrator — could be confusing. Consider moving to top-level or renaming to `editor/pipeline.py`.
- No dependency injection: modules import `load_config()` directly, making testing harder.
- `models/__init__.py` re-exports everything from `types.py` — fine for now, but the `EditOperation` discriminated union is imported but not used by consumers directly.

---

## 2. Code Quality Review

### 2.1 Error Handling

| Module | Grade | Notes |
|--------|-------|-------|
| `config.py` | ✅ Good | Graceful fallbacks for missing config/ffmpeg |
| `analyzer/__init__.py` | ✅ Good | FileNotFoundError, ValueError for invalid video |
| `transcriber.py` | ⚠️ Partial | Falls back on unknown model name, but Whisper's `load_model()` itself can throw (network, disk space) — uncaught |
| `scene_detector.py` | ⚠️ Partial | No try/except around PySceneDetect calls — an invalid/corrupt video would crash with an opaque error |
| `quality_analyzer.py` | ✅ Good | Timeout handling, fallback to video file if audio extraction fails |
| `edit_planner.py` | ✅ Good | Rule-based fallback when LLM fails, graceful degradation |
| `cutter.py` | ⚠️ Partial | `CalledProcessError` is caught and re-raised, but `_get_duration` returning 0.0 on failure causes silent bugs (see §3) |
| `subtitle.py` | ⚠️ Partial | `burn_subtitles` catches CalledProcessError but wraps as RuntimeError — the CLI doesn't catch RuntimeError specifically |
| `renderer.py` | ❌ Missing | No try/except — if `shutil.copy2` fails (disk full, permissions), the whole pipeline crashes with no cleanup |
| `cli.py` | ⚠️ Partial | Uses `typer.Exit(1)` for file-not-found, but all other exceptions bubble as raw tracebacks |

**Recommendation:** Add a top-level exception handler in `cli.py` that catches known exceptions and displays user-friendly Rich errors instead of Python tracebacks.

### 2.2 Type Safety & Validation

**Good:**
- Pydantic v2 models enforce field constraints (`ge=0`, `le=1`, `Literal` types)
- `EditOperation` uses a discriminated union with `Field(discriminator="type")`
- `TranscriptSegment.confidence` is properly bounded `[0, 1]`

**Issues:**
- `EditPlan.operations` type annotation uses an inline union (`CutOperation | SubtitleOperation | ...`) instead of the `EditOperation` type alias defined just above it. This means the discriminated union validation is bypassed when constructing an `EditPlan` directly.
- `_try_rule_based` returns `list` (untyped) for `operations` variable — should be `list[CutOperation | SubtitleOperation]`
- `_adjust_transcript_for_cuts` takes `list` (untyped) for both parameters — should use the proper types.
- `SceneInfo.duration` is a stored field but could drift from `end_time - start_time` — consider making it a computed property or adding a validator.

### 2.3 Edge Cases Not Covered

1. **Zero-duration video** — `_get_duration` returning 0.0 would cause division-by-zero in `compute_scene_energy` (`total_duration` denominator).
2. **Audio-only files** — `_get_video_metadata` raises ValueError("No video stream"), but user might pass an audio file accidentally.
3. **No audio track** — `_extract_audio` will fail on videos with no audio stream; quality analysis would crash.
4. **Very short video (<1s)** — Scene detection may return 0 scenes, which is handled, but `min_scene_len_frames` calculation could produce unexpected results.
5. **Unicode paths** — FFmpeg filter escaping in `burn_subtitles` handles `\`, `:`, `'` but Korean characters in paths could cause issues on some systems.
6. **Concurrent runs** — No locking on temp directories; unlikely but possible name collision in `tempfile`.

---

## 3. Bug / Issue Detection

### 🐛 Bug 1: `EditPlan.operations` bypasses discriminated union (Medium)

**File:** `cutai/models/types.py`, line ~130

```python
class EditPlan(BaseModel):
    operations: list[
        CutOperation | SubtitleOperation | BGMOperation | ...
    ] = Field(...)
```

The `EditOperation` type alias (with `Field(discriminator="type")`) is defined but **not used** in `EditPlan`. This means:
- JSON deserialization won't use the discriminator for dispatch
- Invalid `type` values won't be caught during validation

**Fix:** Change to `operations: list[EditOperation] = ...`

### 🐛 Bug 2: `_get_duration` silent failure causes incorrect keep ranges (High)

**File:** `cutai/editor/cutter.py`

If `_get_duration` returns 0.0 (FFprobe failure), `_compute_keep_ranges` uses `total_duration=0.0`, which means `_invert_ranges` produces an empty keep list → the guard clause copies the original unedited video. **The user gets no cuts applied with no warning.**

**Fix:** Raise an exception or log a warning when duration is 0.0.

### 🐛 Bug 3: Transcript timestamp adjustment — partial overlap not handled (High)

**File:** `cutai/editor/renderer.py`, `_adjust_transcript_for_cuts`

```python
is_removed = any(
    seg.start_time >= r_start and seg.end_time <= r_end
    for r_start, r_end in removes
)
```

This only removes transcript segments **fully contained** within a remove range. A segment that partially overlaps (e.g., segment 5.0–8.0, remove range 6.0–10.0) will survive with incorrect text — the user would see subtitle text for audio that's been cut.

**Fix:** Either trim partially-overlapping segments or remove any segment with >50% overlap.

### 🐛 Bug 4: `_extract_audio` timeout too short for 3GB file (Medium)

**File:** `cutai/analyzer/quality_analyzer.py`

```python
subprocess.run(cmd, capture_output=True, check=True, timeout=120)
```

Extracting audio from a 3GB HEVC file at 17.6 minutes could easily exceed 120 seconds, especially on a machine without hardware HEVC decoding. The fallback catches `TimeoutExpired` but falls back to the full video file, negating the entire optimization.

**Fix:** Increase timeout to 600s or use `-c:a copy` if possible (WAV conversion requires decoding, but for silence detection PCM is needed — consider keeping opus/aac instead of PCM for faster I/O).

### 🐛 Bug 5: Scene thumbnails create temp directory that's never cleaned up (Low)

**File:** `cutai/analyzer/scene_detector.py`

```python
thumb_dir = Path(thumbnail_dir) if thumbnail_dir else Path(tempfile.mkdtemp(prefix="cutai_thumbs_"))
```

When `thumbnail_dir` is None (the default), `mkdtemp` creates a directory that persists after the process exits. For a 23-scene video, that's ~23 JPEG files left behind. Over multiple runs, this accumulates.

**Fix:** Use `tempfile.TemporaryDirectory` as a context manager, or clean up in `analyze_video`.

### 🐛 Bug 6: `shutil.copy2` for large files in renderer (Medium)

**File:** `cutai/editor/renderer.py`

```python
shutil.copy2(current_video, output_path)
```

For a 3GB file, `shutil.copy2` reads the entire file into memory in chunks and writes it. This is slow and wasteful when the source is already in the right format. When no subtitles and no cuts are needed, the original file gets needlessly copied.

**Fix:** Use `os.link()` (hard link) or `os.symlink()` when source and destination are on the same filesystem, falling back to `shutil.copy2`.

### 🐛 Bug 7: No `--check` on silence detection subprocess (Low)

**File:** `cutai/analyzer/quality_analyzer.py`, `detect_silence`

```python
result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
output = result.stderr
```

The return code is not checked. If FFmpeg encounters an error, it may still produce partial output on stderr that gets parsed, potentially yielding incorrect silence segments.

### ⚠️ Warning 1: `_extract_segment` uses `-c copy` which may cause keyframe issues

**File:** `cutai/editor/cutter.py`

```python
"-c", "copy",
```

Stream copy (`-c copy`) is very fast but cuts only at keyframes for video. For HEVC with typical GOP sizes of 2-5 seconds, the actual cut point could be several seconds off from the requested timestamp. This means:
- Segments may start with a few seconds of "removed" content
- Total duration after cuts may not match `estimated_duration`

**Fix:** For frame-accurate cutting, either:
1. Use `-c:v libx264 -crf 18` (slow but accurate) — or offer as `--precise` flag
2. Use a two-pass approach: `-ss` before `-i` for fast seek, then re-encode a small window around the cut point

---

## 4. Performance & Optimization for Large Files

### 4.1 Current Bottlenecks (for 2560×1440 HEVC 60fps 17.6min 3GB)

| Stage | Estimated Time | Bottleneck |
|-------|---------------|-----------|
| Scene detection | 5-15 min | Full video decode at ~30fps (frame_skip=1 for 60fps) |
| Whisper transcription | 10-30 min | Audio processing, model inference (CPU) |
| Audio extraction | 1-3 min | HEVC demux + PCM conversion |
| Silence detection | 1-2 min | Single-pass FFmpeg filter (fast on extracted audio) |
| Scene energy | 1-2 min | Single-pass FFmpeg astats (fast on extracted audio) |
| Segment extraction | 1-5 min | N × FFmpeg seeks (stream copy = fast) |
| Concatenation | 10-30s | Remux only |
| Subtitle burn | 10-30 min | Full re-encode at 1440p (if burn mode) |

**Total estimate: 20-80 minutes** (highly dependent on CPU/GPU)

### 4.2 Specific Optimizations

#### A. Scene Detection — High Impact

**Current:** PySceneDetect decodes every frame (with frame_skip=1 for 60fps).
```python
# 60fps → processing at ~30fps = still 31,680 frames for 17.6min
```

**Optimizations:**
1. **Downscale before detection:** Add `-vf scale=640:-1` to a pre-processing step. Scene detection doesn't need 1440p resolution.
2. **Increase frame_skip:** For a 60fps video, `frame_skip=2` (20fps effective) would cut processing time by 33% with minimal quality loss.
3. **Use PySceneDetect's `downscale_factor`:** The API supports `open_video(path, backend='opencv', downscale_factor=4)`.

```python
# Suggested: add downscale_factor to open_video call
video = open_video(video_path, downscale_factor=4)  # Process at 360p
```

#### B. Whisper Transcription — High Impact

**Current:** Uses `openai-whisper` (original, PyTorch-based).

**Optimizations:**
1. **Switch to `faster-whisper`:** Uses CTranslate2 — 4-8× faster than original Whisper, lower memory.
   ```
   # pip install faster-whisper
   from faster_whisper import WhisperModel
   model = WhisperModel("base", device="cpu", compute_type="int8")
   ```
2. **Extract audio first:** Whisper on a raw video file re-decodes video. Pre-extract audio as 16kHz mono WAV (already done in quality_analyzer — share this step).
3. **GPU acceleration:** The PRD mentions local GPU — add CUDA/MPS device selection.

#### C. Audio Extraction — Medium Impact

**Current:** Extracts to PCM WAV (16kHz mono) — a 17.6min video produces ~34MB WAV.

The 120s timeout is too short for HEVC decoding of the full stream. However, FFmpeg only needs to demux + decode the audio track — use `-vn` (already done) but the HEVC container can still cause slow demuxing.

**Optimizations:**
1. **Increase timeout to 600s** (or remove timeout entirely for local operations)
2. **Share extracted audio** between quality_analyzer and transcriber — currently both independently process the audio.

#### D. Segment Extraction — Medium Impact

**Current:** One FFmpeg invocation per keep segment.

**Optimizations:**
1. **Batch extraction:** Use FFmpeg's `-segment_times` for multi-segment extraction in one pass:
   ```
   ffmpeg -i input.mp4 -f segment -segment_times "10,20,30" \
     -c copy -reset_timestamps 1 seg_%03d.mp4
   ```
2. **Single-pass filter_complex:** For a small number of segments (<10), use `trim`/`atrim` filters in one FFmpeg command to avoid N seek operations.

#### E. Subtitle Burning — High Impact (when enabled)

**Current:** `libx264 -preset medium -crf 18` for 1440p = very slow.

**Optimizations:**
1. **Use hardware encoders:**
   - macOS: `-c:v hevc_videotoolbox -q:v 65` (Apple Silicon, near-instant)
   - NVIDIA: `-c:v h264_nvenc -crf 18`
2. **Match input codec:** If input is HEVC, output should be HEVC too (smaller file).
3. **Allow preset control:** `--preset ultrafast` for previews, `--preset slow` for final render.
4. **Consider resolution-based preset:** Auto-select `-preset fast` for >1080p.

#### F. Memory Optimization

**Current concerns:**
- Whisper loads the entire model into RAM (~1GB for `base`, ~5GB for `large`)
- `shutil.copy2` for 3GB files uses chunked I/O but still slow
- PySceneDetect holds frame buffer in memory

**Optimizations:**
1. Unload Whisper model after transcription (`del model; gc.collect()`)
2. Use `os.link()` instead of `shutil.copy2` when possible
3. Clean up temp directories promptly (some already use context managers, but thumbnails don't)

#### G. Shared Audio Extraction (Architecture)

Both `quality_analyzer` and `transcriber` need audio. Currently:
- `quality_analyzer._extract_audio()` → 16kHz mono WAV
- `transcriber` → Whisper decodes audio internally

**Recommendation:** Extract audio once in `analyze_video()`, pass the audio path to both modules. This saves one full demux + decode cycle.

```python
# In analyzer/__init__.py
audio_path = _extract_shared_audio(video_path, tmpdir)
transcript = transcribe(audio_path, model_name=whisper_model)  # Use audio file
quality = analyze_quality(audio_path, scenes=scenes)  # Already uses audio
```

---

## 5. Feature Completeness

### 5.1 Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| Scene detection | ✅ Fully implemented | ContentDetector with auto frame_skip |
| Whisper transcription | ✅ Fully implemented | Model selection, language auto-detect |
| Silence detection | ✅ Fully implemented | FFmpeg silencedetect, configurable threshold |
| Per-scene audio energy | ✅ Fully implemented | Single-pass astats |
| Rule-based planning | ✅ Fully implemented | Silence removal, subtitles, boring scene removal, speech-only, trim to duration |
| LLM-based planning | ✅ Fully implemented | OpenAI API with system prompt, JSON output |
| Cut/trim editing | ✅ Fully implemented | Segment extraction + concat, stream copy |
| Subtitle generation (ASS) | ✅ Fully implemented | Proper ASS format, configurable style |
| Subtitle burn | ✅ Fully implemented | FFmpeg ass filter + libx264 |
| Sidecar subtitles | ✅ Fully implemented | .ass file saved alongside output |
| CLI (analyze/plan/edit) | ✅ Fully implemented | Rich progress, tables, panels |
| Transcript timestamp adjustment | ⚠️ Partial | Fully-contained segments only (see Bug 3) |
| BGM mixing | ❌ Not implemented | Type defined, no executor |
| Color grading | ❌ Not implemented | Type defined, no executor |
| Transitions | ❌ Not implemented | Type defined, no executor |
| Speed adjustment | ❌ Not implemented | Type defined, no executor |
| Face tracking | ❌ Not implemented | Not in codebase at all |
| Scene description (LLM) | ❌ Not implemented | Not in codebase |
| Chat mode | ❌ Not implemented | Not in codebase |
| Edit Style Transfer | ❌ Not implemented | Phase 2 per PRD |
| Ollama (local LLM) | ❌ Not implemented | Config mentions it, no code |

### 5.2 End-to-End: `cutai edit video.mp4 -i "remove silence and add subtitles"`

**This command works end-to-end.** The pipeline:

1. ✅ `analyze_video` → detects scenes, transcribes, finds silence
2. ✅ `create_edit_plan` → rule-based matching for "remove silence" + "add subtitles"
3. ✅ `render` → `apply_cuts` removes silent segments → `generate_ass` creates subtitle sidecar
4. ✅ Output: edited MP4 + `.ass` subtitle file

**Known issues with this specific flow:**
- Cut accuracy depends on keyframe alignment (see Warning 1)
- Subtitle timestamps may be slightly off if segments partially overlap cuts (see Bug 3)
- For a 3GB HEVC file, analysis could take 30-60 minutes

### 5.3 What's Missing for a Polished MVP

1. **No `--dry-run` flag** — Can't preview what would be cut without rendering.
   - Workaround: use `cutai plan` command, but it doesn't show duration savings clearly.

2. **No progress reporting during FFmpeg operations** — Long operations (segment extraction, subtitle burn) show a spinner but no ETA/percentage.

3. **No input validation for instruction** — Empty string, only whitespace, or gibberish instructions produce an empty plan with no helpful error.

4. **No output file format control** — Always outputs MP4; no way to choose MKV, WebM, etc.

5. **No resume/cache** — Re-running the same video re-analyzes everything from scratch. A cache for analysis results would be a huge QoL improvement.

---

## 6. Specific Recommendations (Prioritized)

### 🔴 Critical (Fix before first real use)

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 1 | **Fix transcript timestamp adjustment** (Bug 3) — partial overlaps cause misaligned subtitles | 30 min | Subtitle quality |
| 2 | **Increase `_extract_audio` timeout** (Bug 4) — 120s will timeout on 3GB HEVC | 5 min | 3GB file support |
| 3 | **Fix `_get_duration` returning 0.0** (Bug 2) — causes silent cut failures | 15 min | Correctness |
| 4 | **Add top-level error handler in CLI** — raw tracebacks are bad UX | 20 min | User experience |

### 🟡 Important (Before public release)

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 5 | **Use `EditOperation` type in `EditPlan.operations`** (Bug 1) | 5 min | Type safety |
| 6 | **Share audio extraction** between transcriber and quality_analyzer | 1 hour | Performance (save 1-3 min) |
| 7 | **Add `downscale_factor` to scene detection** | 10 min | Performance (2-4× faster) |
| 8 | **Switch to `faster-whisper`** | 2 hours | Performance (4-8× faster transcription) |
| 9 | **Clean up thumbnail temp directory** (Bug 5) | 15 min | Disk hygiene |
| 10 | **Add `--precise` flag for frame-accurate cutting** or document keyframe limitation | 1 hour | Cut accuracy |
| 11 | **Add analysis caching** (save/load `VideoAnalysis` JSON) | 2 hours | Huge QoL for iterative editing |

### 🟢 Nice to Have (Improvement backlog)

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 12 | Use hardware encoder for subtitle burn (VideoToolbox on macOS) | 1 hour | 5-10× faster burn |
| 13 | Add FFmpeg progress parsing (percentage/ETA) | 2 hours | UX |
| 14 | Implement BGM mixing executor | 4 hours | Feature |
| 15 | Implement color grading executor | 2 hours | Feature |
| 16 | Add Ollama support for local LLM planning | 3 hours | Offline mode |
| 17 | Replace `shutil.copy2` with `os.link()` where possible (Bug 6) | 15 min | Disk I/O |
| 18 | Add `--dry-run` flag to `edit` command | 30 min | UX |
| 19 | Batch segment extraction (single FFmpeg pass) | 3 hours | Performance |
| 20 | Add input validation for empty/gibberish instructions | 15 min | UX |

### Quick Wins (< 30 min each, high value)

1. ✅ Increase `_extract_audio` timeout: `120` → `600` (1 line)
2. ✅ Use `EditOperation` in `EditPlan.operations` (1 line)
3. ✅ Add `downscale_factor=4` to `open_video()` (1 line)
4. ✅ Guard `_get_duration() == 0.0` with a warning/exception (3 lines)
5. ✅ Clean up thumbnail temp dir with `TemporaryDirectory` context manager (5 lines)
6. ✅ Add `gc.collect()` after Whisper model use (2 lines)

### Larger Refactors

1. **Shared audio pipeline** — Extract audio once, share across modules
2. **Switch to faster-whisper** — Different API, needs adapter
3. **Analysis cache** — JSON serialization already works via Pydantic; need cache key (file hash + mtime)
4. **Hardware encoder detection** — Auto-detect VideoToolbox/NVENC availability

---

## Summary

CutAI has a **strong foundation**. The architecture is clean, the Pydantic models are well-designed, and the core pipeline (analyze → plan → edit → render) works end-to-end for the primary use case. The code quality is above average for a v0.1 project.

The main concerns are:
1. **Performance on large files** — The 3GB test video will be slow without the optimizations listed above (especially scene detection downscaling and faster-whisper).
2. **Frame accuracy** — Stream copy cutting at keyframes could produce noticeable artifacts. Users will notice when "removed" content appears at the start of segments.
3. **A few correctness bugs** — Transcript adjustment and duration fallback issues need fixing before the subtitles can be trusted.

The project is **~60% complete** relative to the MVP scope defined in the PRD. Cuts and subtitles work; BGM, color grading, transitions, speed, face tracking, and chat mode are defined but not implemented. This is appropriate for Phase 1.

**Bottom line:** Fix the 4 critical issues, apply the quick wins, and CutAI is ready for dogfooding with Minseo's vlog.
