"""Transition effects between scenes using FFmpeg xfade.

Applies TransitionOperations at scene boundaries by splitting the video
at cut points, applying xfade between consecutive segments, and
concatenating the result.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from cutai.config import ensure_ffmpeg, ensure_ffprobe
from cutai.models.types import TransitionOperation

logger = logging.getLogger(__name__)

# Mapping of CutAI transition styles to FFmpeg xfade transition names.
_XFADE_MAP: dict[str, str] = {
    "fade": "fade",
    "dissolve": "smoothleft",
    "wipe": "wipeleft",
}


def apply_transitions(
    video_path: str,
    operations: list[TransitionOperation],
    cut_points: list[float],
    output_path: str,
) -> str:
    """Apply transition effects between scenes.

    MVP approach:
    1. Split video at cut_points into segments.
    2. For each transition operation, apply xfade between the two segments
       identified by ``between``.
    3. Concatenate all segments (with xfade applied where specified).

    Args:
        video_path: Path to the source video.
        operations: List of TransitionOperations.
        cut_points: Timestamps (seconds) where scene boundaries exist in the
            current (possibly already cut) video.
        output_path: Path for the output video.

    Returns:
        Path to the output video with transitions applied.
    """
    # Filter out "cut" style transitions (no effect needed)
    effective_ops = [op for op in operations if op.style != "cut"]

    if not effective_ops or not cut_points:
        logger.info("No transitions to apply — copying input to output.")
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    ffmpeg = ensure_ffmpeg()
    video_duration = _get_duration(video_path)

    if video_duration <= 0:
        logger.warning("Could not determine video duration. Skipping transitions.")
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    # Sort cut points and add boundaries
    sorted_points = sorted(set(cut_points))
    # Build segment boundaries: [0, cp1, cp2, ..., duration]
    boundaries = [0.0] + [cp for cp in sorted_points if 0 < cp < video_duration] + [video_duration]

    if len(boundaries) < 3:
        logger.info("Not enough segments for transitions. Skipping.")
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    # Build a map: (scene_i, scene_j) -> TransitionOperation
    transition_map: dict[tuple[int, int], TransitionOperation] = {}
    for configured_transition in effective_ops:
        transition_map[configured_transition.between] = configured_transition

    with tempfile.TemporaryDirectory(prefix="cutai_transition_") as tmpdir:
        # Step 1: Split video into segments
        segments: list[str] = []
        for i in range(len(boundaries) - 1):
            seg_path = str(Path(tmpdir) / f"seg_{i:04d}.mp4")
            _extract_segment(ffmpeg, video_path, boundaries[i], boundaries[i + 1], seg_path)
            segments.append(seg_path)

        if len(segments) < 2:
            import shutil
            shutil.copy2(video_path, output_path)
            return output_path

        # Step 2: Apply xfade sequentially between segments
        current = segments[0]
        for i in range(1, len(segments)):
            pair = (i - 1, i)
            pair_transition = transition_map.get(pair)

            if pair_transition is None:
                # No transition specified for this pair — simple concat
                concat_output = str(Path(tmpdir) / f"concat_{i:04d}.mp4")
                _concat_two(ffmpeg, current, segments[i], concat_output, tmpdir)
                current = concat_output
            else:
                # Apply xfade
                xfade_output = str(Path(tmpdir) / f"xfade_{i:04d}.mp4")
                _apply_xfade(ffmpeg, current, segments[i], pair_transition, xfade_output)
                current = xfade_output

        # Copy final result to output
        import shutil
        shutil.copy2(current, output_path)

    logger.info("Transitions applied → %s", output_path)
    return output_path


def _apply_xfade(
    ffmpeg: str,
    video_a: str,
    video_b: str,
    operation: TransitionOperation,
    output_path: str,
) -> None:
    """Apply xfade transition between two video segments.

    Args:
        ffmpeg: Path to FFmpeg binary.
        video_a: Path to the first video segment.
        video_b: Path to the second video segment.
        operation: TransitionOperation specifying style and duration.
        output_path: Path for the output video.
    """
    duration_a = _get_duration(video_a)
    xfade_name = _XFADE_MAP.get(operation.style, "fade")
    trans_dur = min(operation.duration, duration_a * 0.5)  # Don't exceed half of segment A

    if trans_dur <= 0:
        trans_dur = 0.5

    # xfade offset = duration of first video minus transition duration
    offset = max(0, duration_a - trans_dur)

    # Video filter: xfade
    vf = f"xfade=transition={xfade_name}:duration={trans_dur:.3f}:offset={offset:.3f}"

    # Audio filter: acrossfade
    af = f"acrossfade=d={trans_dur:.3f}"

    cmd = [
        ffmpeg,
        "-y",
        "-i", video_a,
        "-i", video_b,
        "-filter_complex",
        f"[0:v][1:v]{vf}[v];[0:a][1:a]{af}[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        output_path,
    ]

    logger.info(
        "Applying xfade (style=%s, duration=%.2fs, offset=%.2fs)",
        operation.style,
        trans_dur,
        offset,
    )

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=600)
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.decode() if isinstance(exc.stderr, bytes) else str(exc.stderr)
        logger.error("xfade failed: %s", error_msg)
        # Fallback: simple concat without transition
        logger.warning("Falling back to simple concat for this pair.")
        _concat_two_reencode(ffmpeg, video_a, video_b, output_path)


def _extract_segment(
    ffmpeg: str,
    video_path: str,
    start: float,
    end: float,
    output_path: str,
) -> None:
    """Extract a single segment from the video."""
    duration = end - start
    cmd = [
        ffmpeg,
        "-y",
        "-ss", f"{start:.3f}",
        "-i", video_path,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=300)
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.decode() if isinstance(exc.stderr, bytes) else str(exc.stderr)
        logger.error("Segment extraction [%.1f-%.1f] failed: %s", start, end, error_msg)
        raise


def _concat_two(
    ffmpeg: str,
    video_a: str,
    video_b: str,
    output_path: str,
    tmpdir: str,
) -> None:
    """Concatenate two video files using the concat demuxer."""
    list_path = str(Path(tmpdir) / "concat_pair.txt")
    with open(list_path, "w") as f:
        f.write(f"file '{video_a}'\n")
        f.write(f"file '{video_b}'\n")

    cmd = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=300)
    except subprocess.CalledProcessError:
        # If concat demuxer fails (codec mismatch), fallback to re-encode
        _concat_two_reencode(ffmpeg, video_a, video_b, output_path)


def _concat_two_reencode(
    ffmpeg: str,
    video_a: str,
    video_b: str,
    output_path: str,
) -> None:
    """Concatenate two videos with re-encoding (fallback)."""
    cmd = [
        ffmpeg,
        "-y",
        "-i", video_a,
        "-i", video_b,
        "-filter_complex",
        "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=600)


def _get_duration(video_path: str) -> float:
    """Get media file duration using FFprobe."""
    ffprobe = ensure_ffprobe()
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
