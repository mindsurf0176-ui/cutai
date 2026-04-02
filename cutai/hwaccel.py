"""Hardware acceleration detection and FFmpeg codec selection.

Detects available hardware encoders and provides the optimal FFmpeg
codec flags for the current system.

Supported backends:
- **VideoToolbox** (macOS) — Apple Silicon / Intel Mac hardware H.264/HEVC
- **NVENC** (NVIDIA CUDA) — NVIDIA GPU hardware encoding
- **VAAPI** (Linux) — Intel/AMD GPU hardware encoding
- **Software** (fallback) — libx264/libx265
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def detect_hwaccel() -> str:
    """Detect the best available hardware encoder.

    Returns:
        One of: "videotoolbox", "nvenc", "vaapi", "software"
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return "software"

    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        )
        encoders = result.stdout
    except Exception:
        return "software"

    system = platform.system()

    # macOS: VideoToolbox
    if system == "Darwin" and "h264_videotoolbox" in encoders:
        logger.info("Hardware acceleration: VideoToolbox (macOS)")
        return "videotoolbox"

    # NVIDIA
    if "h264_nvenc" in encoders:
        logger.info("Hardware acceleration: NVENC (NVIDIA)")
        return "nvenc"

    # Linux VAAPI
    if system == "Linux" and "h264_vaapi" in encoders:
        logger.info("Hardware acceleration: VAAPI (Linux)")
        return "vaapi"

    logger.info("Hardware acceleration: none (software encoding)")
    return "software"


def get_encode_flags(
    hwaccel: str | None = None,
    codec: str = "h264",
    quality: str = "balanced",
) -> list[str]:
    """Get FFmpeg encoding flags for the detected/specified hardware.

    Args:
        hwaccel: Override hardware backend. None = auto-detect.
        codec: Target codec ("h264" or "hevc").
        quality: Quality preset ("fast", "balanced", "quality").

    Returns:
        List of FFmpeg command-line flags (e.g. ["-c:v", "h264_videotoolbox", ...]).
    """
    if hwaccel is None:
        hwaccel = detect_hwaccel()

    if hwaccel == "videotoolbox":
        encoder = f"{codec}_videotoolbox"
        flags = ["-c:v", encoder]
        # VideoToolbox quality control
        if quality == "fast":
            flags.extend(["-q:v", "65"])
        elif quality == "quality":
            flags.extend(["-q:v", "40"])
        else:  # balanced
            flags.extend(["-q:v", "50"])
        # Realtime encoding for speed
        flags.extend(["-realtime", "1"])
        return flags

    if hwaccel == "nvenc":
        encoder = f"{codec}_nvenc"
        flags = ["-c:v", encoder]
        preset_map = {"fast": "p1", "balanced": "p4", "quality": "p7"}
        flags.extend(["-preset", preset_map.get(quality, "p4")])
        return flags

    if hwaccel == "vaapi":
        encoder = f"{codec}_vaapi"
        return [
            "-vaapi_device", "/dev/dri/renderD128",
            "-c:v", encoder,
            "-vf", "format=nv12,hwupload",
        ]

    # Software fallback
    encoder = "libx264" if codec == "h264" else "libx265"
    flags = ["-c:v", encoder]
    preset_map = {"fast": "veryfast", "balanced": "medium", "quality": "slow"}
    flags.extend(["-preset", preset_map.get(quality, "medium")])
    if encoder == "libx265":
        flags.extend(["-tag:v", "hvc1"])  # Apple compatibility
    return flags


def get_hwaccel_info() -> dict:
    """Get a summary of hardware acceleration status.

    Returns:
        Dict with backend name, encoder, and system info.
    """
    backend = detect_hwaccel()
    return {
        "backend": backend,
        "system": platform.system(),
        "machine": platform.machine(),
        "encoder_h264": get_encode_flags(backend, "h264", "balanced")[:2],
        "encoder_hevc": get_encode_flags(backend, "hevc", "balanced")[:2],
        "accelerated": backend != "software",
    }
