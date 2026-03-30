"""Video quality analysis using FFmpeg.

Detects silent segments and computes per-scene audio energy (RMS).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile

from cutai.config import ensure_ffmpeg, ensure_ffprobe
from cutai.models.types import QualityReport, SceneInfo, TimeRange

logger = logging.getLogger(__name__)


def _extract_audio(video_path: str, tmpdir: str) -> str:
    """Extract audio track to a temp WAV file for fast analysis.

    By extracting audio only (``-vn``), we skip video decoding entirely,
    which is the main bottleneck for large HEVC / high-res files.
    """
    ffmpeg = ensure_ffmpeg()
    audio_path = os.path.join(tmpdir, "audio.wav")
    cmd = [
        ffmpeg, "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_path,
    ]
    logger.info("Extracting audio track for fast analysis...")
    subprocess.run(cmd, capture_output=True, check=True, timeout=600)
    logger.info("Audio extracted to %s", audio_path)
    return audio_path


def analyze_quality(
    video_path: str,
    scenes: list[SceneInfo] | None = None,
    silence_threshold_db: float = -40.0,
    silence_min_duration: float = 0.5,
    audio_path: str | None = None,
) -> QualityReport:
    """Analyze audio quality of a video.

    Args:
        video_path: Path to the video file.
        scenes: Optional list of scenes to compute per-scene energy.
        silence_threshold_db: dB threshold for silence detection.
        silence_min_duration: Minimum silence duration in seconds.
        audio_path: Optional pre-extracted audio file path. If provided,
            skips audio extraction (saves time when called from analyze_video
            which already extracted audio for the transcriber).

    Returns:
        QualityReport with silent segments and audio energy data.
    """
    logger.info("Analyzing quality for %s", video_path)

    if audio_path and os.path.exists(audio_path):
        # Use pre-extracted audio (from shared cache in analyze_video)
        logger.info("Using pre-extracted audio: %s", audio_path)
        audio_file = audio_path
        silent_segments = detect_silence(audio_file, silence_threshold_db, silence_min_duration)
        audio_energy: list[float] = []
        if scenes:
            audio_energy = compute_scene_energy(audio_file, scenes)
    else:
        # Extract audio ourselves (standalone usage)
        with tempfile.TemporaryDirectory(prefix="cutai_audio_") as tmpdir:
            try:
                audio_file = _extract_audio(video_path, tmpdir)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                logger.warning("Audio extraction failed (%s), falling back to video file", exc)
                audio_file = video_path

            silent_segments = detect_silence(audio_file, silence_threshold_db, silence_min_duration)

            audio_energy = []
            if scenes:
                audio_energy = compute_scene_energy(audio_file, scenes)

    # Compute overall silence ratio
    total_duration = _get_duration(video_path)
    silence_total = sum(seg.duration for seg in silent_segments)
    silence_ratio = silence_total / total_duration if total_duration > 0 else 0.0

    return QualityReport(
        silent_segments=silent_segments,
        audio_energy=audio_energy,
        overall_silence_ratio=round(min(silence_ratio, 1.0), 4),
    )


def detect_silence(
    video_path: str,
    threshold_db: float = -40.0,
    min_duration: float = 0.5,
) -> list[TimeRange]:
    """Detect silent segments using FFmpeg silencedetect filter.

    Returns:
        List of TimeRange for each silent segment.
    """
    ffmpeg = ensure_ffmpeg()

    cmd = [
        ffmpeg,
        "-i", video_path,
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null",
        "-",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
        # silencedetect writes to stderr
        output = result.stderr
    except subprocess.TimeoutExpired:
        logger.warning("Silence detection timed out")
        return []
    except FileNotFoundError:
        logger.error("FFmpeg not found")
        return []

    return _parse_silence_output(output)


def _parse_silence_output(output: str) -> list[TimeRange]:
    """Parse FFmpeg silencedetect output into TimeRange list."""
    segments: list[TimeRange] = []

    # Pattern: silence_start: 1.234 | silence_end: 5.678 | silence_duration: 4.444
    start_pattern = re.compile(r"silence_start:\s*([\d.]+)")
    end_pattern = re.compile(r"silence_end:\s*([\d.]+)")

    starts: list[float] = []
    ends: list[float] = []

    for line in output.split("\n"):
        start_match = start_pattern.search(line)
        if start_match:
            starts.append(float(start_match.group(1)))
        end_match = end_pattern.search(line)
        if end_match:
            ends.append(float(end_match.group(1)))

    for s, e in zip(starts, ends, strict=False):
        segments.append(TimeRange(start=round(s, 3), end=round(e, 3)))

    logger.info("Found %d silent segments", len(segments))
    return segments


def compute_scene_energy(
    video_path: str,
    scenes: list[SceneInfo],
) -> list[float]:
    """Compute RMS audio energy per scene using a single FFmpeg pass.

    Instead of spawning one FFmpeg process per scene (N subprocesses),
    this runs a single pass over the entire video and distributes
    RMS values to scenes proportionally.

    Returns:
        List of RMS energy values in dB (one per scene).
    """
    ffmpeg = ensure_ffmpeg()

    if not scenes:
        return []

    # Single pass: get frame-level RMS for entire video
    cmd = [
        ffmpeg, "-i", video_path,
        "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
        "-f", "null", "-",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        output = result.stderr
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return [0.0] * len(scenes)

    rms_values = _parse_all_rms(output)
    if not rms_values:
        return [0.0] * len(scenes)

    # Map RMS values to scenes proportionally based on duration
    total_duration = sum(s.duration for s in scenes)
    energy_result: list[float] = []
    idx = 0
    for scene in scenes:
        fraction = scene.duration / total_duration if total_duration > 0 else 0
        count = max(1, int(len(rms_values) * fraction))
        scene_values = rms_values[idx:idx + count]
        idx += count
        avg = sum(scene_values) / len(scene_values) if scene_values else 0.0
        energy_result.append(round(avg, 2))

    return energy_result


def _parse_all_rms(output: str) -> list[float]:
    """Parse all RMS level values from FFmpeg astats output."""
    rms_pattern = re.compile(r"lavfi\.astats\.Overall\.RMS_level=([-\d.]+)")
    values: list[float] = []

    for match in rms_pattern.finditer(output):
        try:
            val = float(match.group(1))
            if val != float("-inf"):
                values.append(val)
        except ValueError:
            continue

    return values


def _get_duration(video_path: str) -> float:
    """Get video duration in seconds using FFprobe."""
    try:
        ffprobe = ensure_ffprobe()
    except FileNotFoundError:
        return 0.0

    cmd = [
        ffprobe,
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return 0.0
