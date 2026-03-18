"""Subtitle generation and burning.

Generates ASS subtitle files from transcript segments and burns
them into the video using FFmpeg.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from cutai.config import ensure_ffmpeg
from cutai.models.types import SubtitleOperation, TranscriptSegment

logger = logging.getLogger(__name__)

# Default ASS subtitle template
ASS_HEADER = """[Script Info]
Title: CutAI Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,{alignment},20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def generate_ass(
    transcript: list[TranscriptSegment],
    output_path: str,
    operation: SubtitleOperation | None = None,
) -> str:
    """Generate an ASS subtitle file from transcript segments.

    Args:
        transcript: List of transcribed segments.
        output_path: Path to write the .ass file.
        operation: Optional subtitle operation with style preferences.

    Returns:
        Path to the generated ASS file.
    """
    op = operation or SubtitleOperation()

    font_size = op.font_size
    alignment = _position_to_alignment(op.position)
    margin_v = 50 if op.position == "bottom" else 30

    # Scale font size for 1080p playback resolution
    scaled_font = int(font_size * (1080 / 720))

    header = ASS_HEADER.format(
        font_size=scaled_font,
        alignment=alignment,
        margin_v=margin_v,
    )

    lines: list[str] = [header.strip()]

    for seg in transcript:
        start_tc = _seconds_to_ass_time(seg.start_time)
        end_tc = _seconds_to_ass_time(seg.end_time)
        # Escape special ASS characters
        text = seg.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        # Line breaks
        text = text.replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start_tc},{end_tc},Default,,0,0,0,,{text}")

    content = "\n".join(lines) + "\n"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Generated ASS subtitle: %s (%d segments)", output_path, len(transcript))
    return output_path


def burn_subtitles(
    video_path: str,
    subtitle_path: str,
    output_path: str,
) -> str:
    """Burn ASS subtitles into a video using FFmpeg.

    Args:
        video_path: Path to the input video.
        subtitle_path: Path to the .ass subtitle file.
        output_path: Path for the output video.

    Returns:
        Path to the output video with burned subtitles.
    """
    ffmpeg = ensure_ffmpeg()

    # Escape special characters in path for FFmpeg filter
    escaped_sub_path = subtitle_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")

    cmd = [
        ffmpeg,
        "-y",
        "-i", video_path,
        "-vf", f"ass='{escaped_sub_path}'",
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        output_path,
    ]

    logger.info("Burning subtitles into video...")

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=1200)
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr.decode() if isinstance(exc.stderr, bytes) else str(exc.stderr)
        logger.error("Subtitle burn failed: %s", error_msg)
        raise RuntimeError(f"Failed to burn subtitles: {error_msg}") from exc

    logger.info("Subtitles burned → %s", output_path)
    return output_path


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format (H:MM:SS.cc)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _position_to_alignment(position: str) -> int:
    """Convert position string to ASS alignment number.

    ASS alignment numpad:
    7 8 9  (top)
    4 5 6  (middle)
    1 2 3  (bottom)
    """
    return {"bottom": 2, "center": 5, "top": 8}.get(position, 2)
