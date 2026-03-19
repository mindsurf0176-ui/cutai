"""Color grading using FFmpeg video filters.

Applies ColorGradeOperation with preset-based filter chains
and intensity scaling.
"""

from __future__ import annotations

import logging
import subprocess

from cutai.config import ensure_ffmpeg
from cutai.models.types import ColorGradeOperation

logger = logging.getLogger(__name__)

# Preset filter definitions.
# Each preset is a list of (filter_name, {param: value}) tuples.
# Values represent the "full preset" level (intensity=50).
# Intensity linearly scales deviation from neutral:
#   0 = no change, 50 = preset as-is, 100 = 2× the preset deviation.

_PRESETS: dict[str, list[tuple[str, dict[str, float]]]] = {
    "bright": [
        ("eq", {"brightness": 0.06, "contrast": 1.05, "saturation": 1.1}),
    ],
    "warm": [
        ("eq", {"brightness": 0.03, "saturation": 1.15}),
        ("colorbalance", {"rs": 0.05, "gs": -0.02, "bs": -0.08}),
    ],
    "cool": [
        ("eq", {"brightness": 0.02, "saturation": 0.95}),
        ("colorbalance", {"rs": -0.05, "gs": 0.02, "bs": 0.08}),
    ],
    "cinematic": [
        ("eq", {"contrast": 1.2, "saturation": 0.85, "brightness": -0.02}),
        ("unsharp", {"lx": 3, "ly": 3, "la": 0.3}),
    ],
    "vintage": [
        ("eq", {"contrast": 1.1, "saturation": 0.7, "brightness": 0.03}),
        ("colorbalance", {"rs": 0.1, "gs": 0.05, "bs": -0.1}),
    ],
}

# Neutral values — used to compute intensity-scaled deviation.
_NEUTRAL: dict[str, float] = {
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "rs": 0.0,
    "gs": 0.0,
    "bs": 0.0,
    "lx": 3,
    "ly": 3,
    "la": 0.0,
}


def apply_color_grade(
    video_path: str,
    operation: ColorGradeOperation,
    output_path: str,
) -> str:
    """Apply color grading to a video.

    Args:
        video_path: Path to the source video.
        operation: ColorGradeOperation with preset and intensity.
        output_path: Path for the output video.

    Returns:
        Path to the color-graded output video.
    """
    preset = operation.preset
    intensity = operation.intensity

    if preset not in _PRESETS:
        logger.warning("Unknown color preset '%s'. Skipping color grade.", preset)
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    if intensity <= 0:
        logger.info("Intensity is 0 — no color grading applied.")
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    # Scale factor: intensity 50 = 1.0× preset, 100 = 2.0×, 0 = 0×.
    scale = intensity / 50.0

    vf_parts = _build_filter_string(preset, scale)

    if not vf_parts:
        logger.info("No filters generated. Skipping color grade.")
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    vf = ",".join(vf_parts)

    ffmpeg = ensure_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "copy",
        output_path,
    ]

    logger.info(
        "Applying color grade (preset=%s, intensity=%.0f, scale=%.2f)",
        preset,
        intensity,
        scale,
    )
    logger.debug("Video filter: %s", vf)

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=600)
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.decode() if isinstance(exc.stderr, bytes) else str(exc.stderr)
        logger.error("Color grading failed: %s", error_msg)
        raise RuntimeError(f"Failed to apply color grade: {error_msg}") from exc

    logger.info("Color grade applied → %s", output_path)
    return output_path


def _build_filter_string(preset: str, scale: float) -> list[str]:
    """Build FFmpeg filter string parts for a preset at a given scale.

    Args:
        preset: Preset name (must exist in _PRESETS).
        scale: Intensity scale factor (0 = neutral, 1 = full preset, 2 = 2×).

    Returns:
        List of FFmpeg filter strings (e.g. ["eq=brightness=0.06:contrast=1.05"]).
    """
    filters = _PRESETS[preset]
    parts: list[str] = []

    for filter_name, params in filters:
        scaled_params: dict[str, float] = {}

        for key, preset_val in params.items():
            neutral = _NEUTRAL.get(key, 0.0)
            deviation = preset_val - neutral
            scaled_val = neutral + (deviation * scale)
            scaled_params[key] = scaled_val

        if filter_name == "eq":
            param_str = ":".join(
                f"{k}={v:.4f}" for k, v in scaled_params.items()
            )
            parts.append(f"eq={param_str}")

        elif filter_name == "colorbalance":
            param_str = ":".join(
                f"{k}={v:.4f}" for k, v in scaled_params.items()
            )
            parts.append(f"colorbalance={param_str}")

        elif filter_name == "unsharp":
            # unsharp filter: luma_msize_x:luma_msize_y:luma_amount
            lx = int(scaled_params.get("lx", 3))
            ly = int(scaled_params.get("ly", 3))
            la = scaled_params.get("la", 0.0)
            # Ensure odd sizes for unsharp
            if lx % 2 == 0:
                lx += 1
            if ly % 2 == 0:
                ly += 1
            parts.append(f"unsharp={lx}:{ly}:{la:.3f}")

    return parts
