"""Scene detection using PySceneDetect.

Detects scene boundaries via content-aware detection and extracts
a thumbnail frame for each scene.

Performance: For high-resolution videos (>720p), an FFmpeg proxy video is
created at reduced resolution before running PySceneDetect. This avoids
processing full 2560×1440 or 4K frames for scene boundary detection, which
is resolution-independent. Typical speedup: 10-20× for 1440p60 content.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

from cutai.models.types import SceneInfo

logger = logging.getLogger(__name__)


def _get_video_info(video_path: str, ffprobe: str) -> tuple[int, int, float]:
    """Get video width, height, and fps using ffprobe.

    Returns:
        (width, height, fps) tuple. Falls back to (0, 0, 30.0) on error.
    """
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "csv=p=0",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        parts = result.stdout.strip().split(",")
        width = int(parts[0])
        height = int(parts[1])
        # r_frame_rate is like "60/1" or "30000/1001"
        num, den = parts[2].split("/")
        fps = float(num) / float(den)
        return width, height, fps
    except Exception as exc:
        logger.warning("ffprobe failed, cannot determine resolution: %s", exc)
        return 0, 0, 30.0


def _create_proxy_video(
    video_path: str,
    ffmpeg: str,
    downscale_factor: int,
    target_fps: int = 30,
) -> str | None:
    """Create a lightweight proxy video for scene detection.

    The proxy is downscaled, has no audio, and is capped at target_fps.
    Scene timestamps from the proxy are valid for the original since
    we only reduce spatial resolution and frame rate (timing is preserved).

    Args:
        video_path: Path to the original video.
        ffmpeg: Path to the ffmpeg binary.
        downscale_factor: Spatial downscale factor (2 or 4).
        target_fps: Maximum frame rate for the proxy.

    Returns:
        Path to the proxy video, or None if creation failed.
    """
    # Create temp file in the same directory to avoid cross-device issues
    video_dir = os.path.dirname(os.path.abspath(video_path))
    fd, proxy_path = tempfile.mkstemp(suffix=".mp4", prefix="cutai_proxy_", dir=video_dir)
    os.close(fd)

    vf = f"scale=iw/{downscale_factor}:ih/{downscale_factor}"

    cmd = [
        ffmpeg,
        "-y",
        "-i", video_path,
        "-vf", vf,
        "-an",               # drop audio — not needed for scene detection
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-r", str(target_fps),
        proxy_path,
    ]

    logger.info(
        "Creating proxy video (downscale=%dx, fps=%d): %s",
        downscale_factor, target_fps, proxy_path,
    )
    start_time = time.monotonic()

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=300)
        elapsed = time.monotonic() - start_time
        proxy_size_mb = os.path.getsize(proxy_path) / (1024 * 1024)
        logger.info(
            "Proxy video created in %.1fs (%.1f MB)",
            elapsed, proxy_size_mb,
        )
        return proxy_path
    except subprocess.TimeoutExpired:
        logger.error("Proxy video creation timed out after 300s")
        _safe_remove(proxy_path)
        return None
    except subprocess.CalledProcessError as exc:
        logger.error("Proxy video creation failed: %s", exc.stderr)
        _safe_remove(proxy_path)
        return None


def _safe_remove(path: str | None) -> None:
    """Remove a file if it exists, ignoring errors."""
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


def detect_scenes(
    video_path: str,
    threshold: float = 27.0,
    min_scene_len_sec: float = 1.0,
    thumbnail_dir: str | None = None,
    frame_skip: int = 0,
    downscale_factor: int = 0,
) -> list[SceneInfo]:
    """Detect scenes in a video using PySceneDetect ContentDetector.

    For high-resolution videos, an FFmpeg proxy video is created at reduced
    resolution before analysis. This dramatically improves performance
    (e.g., 1440p60 17min video: 43min → ~3min).

    Args:
        video_path: Path to the video file.
        threshold: ContentDetector threshold (higher = fewer scenes).
        min_scene_len_sec: Minimum scene length in seconds.
        thumbnail_dir: Directory to save thumbnails.  Defaults to a temp dir.
        frame_skip: Number of frames to skip between detections.
            0 means auto: for videos >30fps, skip frames to approximate
            30fps processing speed (e.g. 60fps → skip 1).
        downscale_factor: Factor to downscale frames before processing.
            0 means auto-detect based on resolution (>1080p → 4x, >720p → 2x).
            Scene boundaries are resolution-independent; downscaling saves
            significant CPU time on 1440p/4K video.

    Returns:
        List of SceneInfo with start/end times and thumbnail paths.
    """
    from scenedetect import ContentDetector, open_video, SceneManager

    from cutai.config import ensure_ffmpeg

    logger.info("Detecting scenes in %s (threshold=%.1f)", video_path, threshold)

    # --- Determine if we need a proxy video ---
    proxy_path: str | None = None
    detection_path = video_path  # path we actually feed to PySceneDetect

    try:
        ffmpeg = ensure_ffmpeg()
        # Use ffprobe (sibling of ffmpeg) to get video info
        ffmpeg_path = Path(ffmpeg)
        ffprobe = str(ffmpeg_path.parent / "ffprobe") if ffmpeg_path.parent != Path(".") else "ffprobe"

        orig_width, orig_height, orig_fps = _get_video_info(video_path, ffprobe)
        logger.info(
            "Original video: %dx%d @ %.1ffps",
            orig_width, orig_height, orig_fps,
        )

        # Auto downscale based on resolution
        if downscale_factor == 0:
            if orig_height > 1080:
                downscale_factor = 4  # e.g., 2560×1440 → 640×360
            elif orig_height > 720:
                downscale_factor = 2  # e.g., 1920×1080 → 960×540

        # Create proxy if downscaling is needed
        if downscale_factor >= 2:
            logger.info(
                "High-res video detected (%dp). Creating %dx downscaled proxy for scene detection.",
                orig_height, downscale_factor,
            )
            proxy_path = _create_proxy_video(video_path, ffmpeg, downscale_factor)
            if proxy_path:
                detection_path = proxy_path
            else:
                logger.warning(
                    "Proxy creation failed — falling back to full-resolution detection. "
                    "This will be slow for high-res video."
                )
    except FileNotFoundError:
        logger.warning(
            "FFmpeg not found — skipping proxy creation, will process at full resolution"
        )

    # --- Run PySceneDetect on the (possibly proxy) video ---
    try:
        video = open_video(detection_path)
        fps = video.frame_rate
        min_scene_len_frames = max(1, int(min_scene_len_sec * fps))

        # Auto frame_skip for high FPS videos
        if frame_skip == 0 and fps > 30:
            frame_skip = max(1, int(fps / 30) - 1)  # e.g., 60fps → skip 1
            logger.info("Auto frame_skip=%d for %.0ffps video", frame_skip, fps)

        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(threshold=threshold, min_scene_len=min_scene_len_frames)
        )

        # Log progress info so user knows it's working
        total_frames = video.duration.get_frames()
        effective_frames = total_frames // (frame_skip + 1) if frame_skip else total_frames
        logger.info(
            "Starting scene detection: ~%d frames to process (frame_skip=%d)",
            effective_frames, frame_skip,
        )
        detect_start = time.monotonic()

        scene_manager.detect_scenes(video, frame_skip=frame_skip)

        detect_elapsed = time.monotonic() - detect_start
        logger.info("Scene detection completed in %.1fs", detect_elapsed)

        scene_list = scene_manager.get_scene_list()
        logger.info("Detected %d scenes", len(scene_list))
    finally:
        # Always clean up the proxy video
        if proxy_path:
            _safe_remove(proxy_path)
            logger.debug("Cleaned up proxy video: %s", proxy_path)

    if not scene_list:
        # No cuts detected → treat the entire video as one scene
        duration = video.duration.get_seconds()
        return [
            SceneInfo(
                id=0,
                start_time=0.0,
                end_time=duration,
                duration=duration,
            )
        ]

    # Set up thumbnail directory
    thumb_dir = Path(thumbnail_dir) if thumbnail_dir else Path(tempfile.mkdtemp(prefix="cutai_thumbs_"))
    thumb_dir.mkdir(parents=True, exist_ok=True)

    # Thumbnails are extracted from the ORIGINAL video (not proxy)
    scenes: list[SceneInfo] = []
    for idx, (start, end) in enumerate(scene_list):
        start_sec = start.get_seconds()
        end_sec = end.get_seconds()
        dur = end_sec - start_sec

        thumb_path = _extract_thumbnail(video_path, start_sec, dur, thumb_dir, idx)

        scenes.append(
            SceneInfo(
                id=idx,
                start_time=round(start_sec, 3),
                end_time=round(end_sec, 3),
                duration=round(dur, 3),
                thumbnail_path=str(thumb_path) if thumb_path else None,
            )
        )

    return scenes


def _extract_thumbnail(
    video_path: str,
    start_sec: float,
    duration: float,
    thumb_dir: Path,
    scene_idx: int,
) -> Path | None:
    """Extract a single thumbnail frame at the middle of a scene.

    Uses FFmpeg for reliability across all codecs.
    """
    import subprocess

    from cutai.config import ensure_ffmpeg

    try:
        ffmpeg = ensure_ffmpeg()
    except FileNotFoundError:
        logger.warning("FFmpeg not found — skipping thumbnail extraction")
        return None

    mid_time = start_sec + duration / 2.0
    out_path = thumb_dir / f"scene_{scene_idx:04d}.jpg"

    cmd = [
        ffmpeg,
        "-y",
        "-ss", f"{mid_time:.3f}",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        str(out_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        return out_path
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        logger.warning("Failed to extract thumbnail for scene %d: %s", scene_idx, exc)
        return None
