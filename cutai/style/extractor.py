"""Style extractor — analyse a video and produce an EditDNA fingerprint."""

from __future__ import annotations

import json
import logging
import struct
import subprocess
from pathlib import Path
from statistics import mean, median, stdev

from cutai.config import ensure_ffmpeg, ensure_ffprobe
from cutai.models.types import (
    AudioDNA,
    EditDNA,
    RhythmDNA,
    SubtitleDNA,
    TransitionDNA,
    VideoAnalysis,
    VisualDNA,
)

logger = logging.getLogger(__name__)

# ── Public API ───────────────────────────────────────────────────────────────


def extract_style(video_path: str, whisper_model: str = "base") -> EditDNA:
    """Analyse a video and extract its editing style as EditDNA.

    Steps:
        1. Run ``analyze_video()`` for scenes, transcript, quality.
        2. Compute rhythm from scene durations.
        3. Compute visual from sampled frames (FFmpeg raw-pixel output).
        4. Compute audio from quality data.
        5. Detect subtitle streams.
        6. Transitions default to all hard-cuts for MVP.

    Args:
        video_path: Path to the video file.
        whisper_model: Whisper model size for transcription.

    Returns:
        EditDNA with all extracted parameters.
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    from cutai.analyzer import analyze_video

    logger.info("Extracting style from %s …", path.name)
    analysis = analyze_video(str(path), whisper_model=whisper_model)

    rhythm = _extract_rhythm(analysis)
    visual = _extract_visual(str(path), analysis)
    audio = _extract_audio(analysis)
    subtitle = _detect_subtitles(str(path))
    transitions = TransitionDNA()  # MVP: assume all hard-cuts

    return EditDNA(
        name=path.stem,
        description=f"Auto-extracted style from {path.name}",
        source=str(path),
        rhythm=rhythm,
        transitions=transitions,
        visual=visual,
        audio=audio,
        subtitle=subtitle,
    )


# ── Rhythm ───────────────────────────────────────────────────────────────────


def _extract_rhythm(analysis: VideoAnalysis) -> RhythmDNA:
    """Derive rhythm characteristics from scene durations."""
    scenes = analysis.scenes
    if not scenes:
        return RhythmDNA()

    durations = [s.duration for s in scenes]
    total_duration = analysis.duration if analysis.duration > 0 else sum(durations)

    avg = mean(durations) if durations else 3.0
    var = stdev(durations) if len(durations) >= 2 else 0.0
    cpm = (len(scenes) / (total_duration / 60.0)) if total_duration > 0 else 10.0

    pacing = _classify_pacing(durations)

    return RhythmDNA(
        avg_cut_length=round(avg, 2),
        cut_length_variance=round(var, 2),
        pacing_curve=pacing,
        cuts_per_minute=round(cpm, 2),
    )


def _classify_pacing(
    durations: list[float],
) -> str:
    """Classify pacing curve by splitting scenes into three equal segments."""
    n = len(durations)
    if n < 3:
        return "constant"

    third = n // 3
    seg1 = mean(durations[:third])
    seg2 = mean(durations[third : 2 * third])
    seg3 = mean(durations[2 * third :])

    # Threshold for "significantly different" (>20 %)
    def slower(a: float, b: float) -> bool:
        return a > b * 1.2

    def faster(a: float, b: float) -> bool:
        return a < b * 0.8

    if slower(seg1, seg2) and slower(seg3, seg2):
        return "slow-fast-slow"
    if faster(seg1, seg2) and faster(seg3, seg2):
        return "fast-slow"  # fast-slow-fast → map to "dynamic"
    if slower(seg1, seg2) and faster(seg3, seg2):
        return "slow-fast"
    if faster(seg1, seg2) and slower(seg3, seg2):
        return "fast-slow"

    # Check overall trend
    if faster(seg1, seg3):
        return "slow-fast"
    if slower(seg1, seg3):
        return "fast-slow"

    return "constant"


# ── Visual ───────────────────────────────────────────────────────────────────


def _extract_visual(video_path: str, analysis: VideoAnalysis) -> VisualDNA:
    """Sample frames and compute average brightness/saturation/contrast.

    Uses FFmpeg to output raw RGB24 pixels for sampled frames.
    No PIL/Pillow required.
    """
    ffmpeg = ensure_ffmpeg()
    duration = analysis.duration
    if duration <= 0:
        return VisualDNA()

    # Sample up to 15 evenly-spaced timestamps
    n_samples = min(15, max(1, int(duration)))
    timestamps = [duration * (i + 0.5) / n_samples for i in range(n_samples)]

    brightness_values: list[float] = []
    saturation_values: list[float] = []

    for ts in timestamps:
        try:
            rgb_stats = _sample_frame_rgb(ffmpeg, video_path, ts)
            if rgb_stats:
                brightness_values.append(rgb_stats["brightness"])
                saturation_values.append(rgb_stats["saturation"])
        except Exception as exc:
            logger.debug("Frame sample at %.1fs failed: %s", ts, exc)

    if not brightness_values:
        return VisualDNA()

    avg_brightness_raw = mean(brightness_values)  # 0–255 scale
    avg_saturation_raw = mean(saturation_values)   # 0–1 scale

    # Normalise brightness to -1..1 range (128 = neutral)
    brightness_offset = round((avg_brightness_raw - 128.0) / 128.0, 3)
    brightness_offset = max(-1.0, min(1.0, brightness_offset))

    # Saturation multiplier: 0.5 = desaturated, 1.0 = normal, >1 = vibrant
    sat_multiplier = round(avg_saturation_raw * 2.0, 3)  # rough mapping
    sat_multiplier = max(0.0, min(3.0, sat_multiplier))

    # Colour temperature heuristic
    temp = _guess_temperature(ffmpeg, video_path, timestamps[:5])

    return VisualDNA(
        avg_brightness=brightness_offset,
        avg_saturation=sat_multiplier,
        avg_contrast=1.0,  # Contrast requires more advanced analysis; default for MVP
        color_temperature=temp,
    )


def _sample_frame_rgb(
    ffmpeg: str, video_path: str, timestamp: float
) -> dict[str, float] | None:
    """Extract a single frame as raw RGB24 and compute brightness + saturation.

    Returns dict with ``brightness`` (0–255) and ``saturation`` (0–1), or None.
    """
    cmd = [
        ffmpeg,
        "-ss", str(round(timestamp, 3)),
        "-i", video_path,
        "-vframes", "1",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", "160x90",  # tiny resolution is enough for stats
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
    except (subprocess.TimeoutExpired, OSError):
        return None

    data = result.stdout
    if len(data) < 6:
        return None

    # Parse RGB triplets
    n_pixels = len(data) // 3
    total_r = 0.0
    total_g = 0.0
    total_b = 0.0

    # Process in bulk for speed (struct unpack_from)
    for i in range(n_pixels):
        off = i * 3
        r, g, b = data[off], data[off + 1], data[off + 2]
        total_r += r
        total_g += g
        total_b += b

    avg_r = total_r / n_pixels
    avg_g = total_g / n_pixels
    avg_b = total_b / n_pixels

    # Brightness ≈ luminance
    brightness = 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b

    # Simple saturation: (max-min)/max per pixel average
    max_c = max(avg_r, avg_g, avg_b)
    min_c = min(avg_r, avg_g, avg_b)
    saturation = ((max_c - min_c) / max_c) if max_c > 0 else 0.0

    return {"brightness": brightness, "saturation": saturation}


def _guess_temperature(
    ffmpeg: str, video_path: str, timestamps: list[float]
) -> str:
    """Estimate colour temperature from sampled frames (warm/neutral/cool)."""
    warm_score = 0
    cool_score = 0

    for ts in timestamps:
        cmd = [
            ffmpeg,
            "-ss", str(round(ts, 3)),
            "-i", video_path,
            "-vframes", "1",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", "80x45",
            "pipe:1",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode != 0 or len(result.stdout) < 6:
                continue
        except (subprocess.TimeoutExpired, OSError):
            continue

        data = result.stdout
        n_pixels = len(data) // 3
        total_r = 0
        total_b = 0
        for i in range(n_pixels):
            off = i * 3
            total_r += data[off]
            total_b += data[off + 2]

        avg_r = total_r / n_pixels
        avg_b = total_b / n_pixels

        if avg_r > avg_b * 1.1:
            warm_score += 1
        elif avg_b > avg_r * 1.1:
            cool_score += 1

    if warm_score > cool_score and warm_score >= 2:
        return "warm"
    if cool_score > warm_score and cool_score >= 2:
        return "cool"
    return "neutral"


# ── Audio ────────────────────────────────────────────────────────────────────


def _extract_audio(analysis: VideoAnalysis) -> AudioDNA:
    """Derive audio characteristics from analysis data."""
    scenes = analysis.scenes
    duration = analysis.duration

    if not scenes or duration <= 0:
        return AudioDNA()

    # Speech ratio
    speech_time = sum(s.duration for s in scenes if s.has_speech)
    speech_ratio = round(min(1.0, speech_time / duration), 3)

    # Silence tolerance (median duration of silent segments)
    silent_durations = [
        seg.duration for seg in analysis.quality.silent_segments
    ]
    silence_tol = round(median(silent_durations), 2) if silent_durations else 1.0

    # BGM detection heuristic:
    # If non-speech segments have notable energy, BGM is likely present.
    non_speech = [s for s in scenes if not s.has_speech and not s.is_silent]
    has_bgm = False
    if non_speech:
        avg_non_speech_energy = mean([s.avg_energy for s in non_speech])
        # Energy in dBFS; above -40 dB in non-speech segments suggests BGM
        has_bgm = avg_non_speech_energy > -40.0

    return AudioDNA(
        has_bgm=has_bgm,
        bgm_volume_ratio=0.15 if has_bgm else 0.0,
        silence_tolerance=silence_tol,
        speech_ratio=speech_ratio,
    )


# ── Subtitles ────────────────────────────────────────────────────────────────


def _detect_subtitles(video_path: str) -> SubtitleDNA:
    """Detect whether the video has embedded subtitle streams."""
    ffprobe = ensure_ffprobe()

    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "s",
        video_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return SubtitleDNA()
    except (subprocess.TimeoutExpired, OSError):
        return SubtitleDNA()

    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])

    if not streams:
        return SubtitleDNA()

    return SubtitleDNA(has_subtitles=True, position="bottom", font_size_category="medium")
