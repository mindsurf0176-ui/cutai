"""Background music mixing using FFmpeg.

Applies BGMOperation by mixing a background music track with
the video's existing audio.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from cutai.config import ensure_ffmpeg, ensure_ffprobe
from cutai.models.types import BGMOperation

logger = logging.getLogger(__name__)

# Directory for bundled BGM assets
BGM_ASSETS_DIR = Path(__file__).parent.parent / "assets" / "bgm"


def apply_bgm(
    video_path: str,
    operation: BGMOperation,
    output_path: str,
    bgm_file: str | None = None,
) -> str:
    """Mix background music with a video's existing audio.

    Args:
        video_path: Path to the source video.
        operation: BGMOperation with mood, volume, fade settings.
        output_path: Path for the output video.
        bgm_file: Path to the BGM audio file. If None, searches
            bundled assets by mood.

    Returns:
        Path to the output video with mixed audio.
    """
    # Resolve BGM file
    resolved_bgm = bgm_file or _find_bundled_bgm(operation.mood)

    if resolved_bgm is None:
        logger.warning(
            "No BGM file provided and no bundled track for mood '%s'. "
            "Skipping BGM — copying input to output.",
            operation.mood,
        )
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    if not Path(resolved_bgm).exists():
        logger.warning(
            "BGM file not found: '%s'. Skipping BGM — copying input to output.",
            resolved_bgm,
        )
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    ffmpeg = ensure_ffmpeg()
    video_duration = _get_duration(video_path)

    if video_duration <= 0:
        logger.warning("Could not determine video duration. Skipping BGM.")
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    # Build BGM audio filter chain
    vol = operation.volume / 100.0
    bgm_filters: list[str] = []

    # Volume adjustment
    bgm_filters.append(f"volume={vol:.3f}")

    # Fade in
    if operation.fade_in > 0:
        bgm_filters.append(f"afade=t=in:d={operation.fade_in:.2f}")

    # Fade out
    if operation.fade_out > 0:
        fade_out_start = max(0, video_duration - operation.fade_out)
        bgm_filters.append(
            f"afade=t=out:st={fade_out_start:.2f}:d={operation.fade_out:.2f}"
        )

    bgm_filter_chain = ",".join(bgm_filters)

    # Build complex filter: mix BGM with original audio
    filter_complex = (
        f"[1:a]{bgm_filter_chain}[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first"
    )

    cmd = [
        ffmpeg,
        "-y",
        "-i", video_path,
        "-i", resolved_bgm,
        "-filter_complex", filter_complex,
        "-c:v", "copy",
        "-shortest",
        output_path,
    ]

    logger.info(
        "Mixing BGM (mood=%s, vol=%d%%, fade_in=%.1fs, fade_out=%.1fs)",
        operation.mood,
        operation.volume,
        operation.fade_in,
        operation.fade_out,
    )

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=600)
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.decode() if isinstance(exc.stderr, bytes) else str(exc.stderr)
        logger.error("BGM mixing failed: %s", error_msg)
        raise RuntimeError(f"Failed to mix BGM: {error_msg}") from exc

    logger.info("BGM mixed → %s", output_path)
    return output_path


def _find_bundled_bgm(mood: str) -> str | None:
    """Search for a bundled BGM track matching the given mood.

    Looks for files named like ``{mood}.mp3``, ``{mood}.wav``, etc.
    in the assets/bgm directory.

    Args:
        mood: The mood to search for (e.g. "calm", "upbeat").

    Returns:
        Path to the BGM file, or None if not found.
    """
    if not BGM_ASSETS_DIR.exists():
        return None

    audio_extensions = {".mp3", ".wav", ".aac", ".ogg", ".m4a", ".flac"}

    for ext in audio_extensions:
        candidate = BGM_ASSETS_DIR / f"{mood}{ext}"
        if candidate.exists():
            logger.info("Found bundled BGM: %s", candidate)
            return str(candidate)

    # Also check for files containing the mood name
    for path in BGM_ASSETS_DIR.iterdir():
        if path.suffix.lower() in audio_extensions and mood in path.stem.lower():
            logger.info("Found bundled BGM (partial match): %s", path)
            return str(path)

    logger.debug("No bundled BGM found for mood '%s' in %s", mood, BGM_ASSETS_DIR)
    return None


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
