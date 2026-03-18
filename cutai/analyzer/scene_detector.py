"""Scene detection using PySceneDetect.

Detects scene boundaries via content-aware detection and extracts
a thumbnail frame for each scene.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from cutai.models.types import SceneInfo

logger = logging.getLogger(__name__)


def detect_scenes(
    video_path: str,
    threshold: float = 27.0,
    min_scene_len_sec: float = 1.0,
    thumbnail_dir: str | None = None,
    frame_skip: int = 0,
    downscale_factor: int = 0,
) -> list[SceneInfo]:
    """Detect scenes in a video using PySceneDetect ContentDetector.

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

    logger.info("Detecting scenes in %s (threshold=%.1f)", video_path, threshold)

    video = open_video(video_path)
    fps = video.frame_rate
    min_scene_len_frames = max(1, int(min_scene_len_sec * fps))

    # Auto downscale for high-resolution videos
    if downscale_factor == 0:
        frame_size = video.frame_size  # (width, height)
        height = frame_size[1] if frame_size else 0
        if height > 1080:
            downscale_factor = 4  # e.g., 2560×1440 → 640×360
            logger.info("Auto downscale=%dx for %dp video", downscale_factor, height)
        elif height > 720:
            downscale_factor = 2  # e.g., 1920×1080 → 960×540
            logger.info("Auto downscale=%dx for %dp video", downscale_factor, height)

    # Auto frame_skip for high FPS videos to reduce processing time
    if frame_skip == 0 and fps > 30:
        frame_skip = max(1, int(fps / 30) - 1)  # e.g., 60fps → skip 1
        logger.info("Auto frame_skip=%d for %.0ffps video", frame_skip, fps)

    scene_manager = SceneManager()
    scene_manager.add_detector(
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len_frames)
    )
    # Pass downscale_factor if set (reduces processing resolution)
    detect_kwargs = {"frame_skip": frame_skip}
    if downscale_factor and downscale_factor > 1:
        try:
            # scenedetect >= 0.6.2 supports downscale parameter
            scene_manager.detect_scenes(video, frame_skip=frame_skip, downscale=downscale_factor)
        except TypeError:
            # Older scenedetect versions don't support downscale kwarg
            logger.debug("scenedetect doesn't support downscale kwarg, skipping")
            scene_manager.detect_scenes(video, frame_skip=frame_skip)
    else:
        scene_manager.detect_scenes(video, frame_skip=frame_skip)

    scene_list = scene_manager.get_scene_list()
    logger.info("Detected %d scenes", len(scene_list))

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
