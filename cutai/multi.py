"""CutAI Multi-video Editor — combine and edit multiple video clips.

Provides pipeline for analyzing, merging, and editing multiple video files
into a single output video.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path

from cutai.config import ensure_ffmpeg, ensure_ffprobe
from cutai.models.types import (
    QualityReport,
    SceneInfo,
    TimeRange,
    TranscriptSegment,
    VideoAnalysis,
)

logger = logging.getLogger(__name__)


def multi_edit(
    video_paths: list[str],
    instruction: str = "",
    output_path: str = "combined_output.mp4",
    whisper_model: str = "base",
    llm_model: str = "gpt-4o",
    use_llm: bool = True,
    style: str | None = None,
    burn_subtitles: bool = True,
) -> str:
    """Edit and combine multiple video files into one output.

    Pipeline:
    1. Analyze each video independently
    2. Create a merged analysis (combined timeline)
    3. Generate edit plan for the combined content
    4. Concatenate source videos
    5. Apply edit plan to the concatenated video

    Args:
        video_paths: List of video file paths.
        instruction: Natural language editing instruction.
        output_path: Path for output video.
        whisper_model: Whisper model for transcription.
        llm_model: LLM model for planning.
        use_llm: Whether to use LLM planning.
        style: Optional path to Edit DNA YAML file.
        burn_subtitles: If True (default), burn subtitles into the output video.

    Returns:
        Path to the output video.

    Raises:
        FileNotFoundError: If any video file is missing.
        ValueError: If fewer than 2 videos are provided.
    """
    if len(video_paths) < 2:
        raise ValueError("multi_edit requires at least 2 video files")

    for vp in video_paths:
        if not Path(vp).exists():
            raise FileNotFoundError(f"Video file not found: {vp}")

    logger.info("Multi-edit: %d video files", len(video_paths))

    # Step 1: Analyze each video
    analyses = _analyze_multiple(video_paths, whisper_model)
    logger.info("Analysis complete for %d videos", len(analyses))

    # Step 2: Merge analyses
    merged = _merge_analyses(analyses)
    logger.info(
        "Merged analysis: %.1fs, %d scenes, %d transcript segments",
        merged.duration,
        len(merged.scenes),
        len(merged.transcript),
    )

    # Step 3: Create edit plan
    if style:
        from cutai.style import apply_style, load_style

        style_dna = load_style(style)
        edit_plan = apply_style(merged, style_dna, instruction=instruction)
    elif instruction:
        from cutai.planner import create_edit_plan

        edit_plan = create_edit_plan(
            merged,
            instruction,
            llm_model=llm_model,
            use_llm=use_llm,
        )
    else:
        # No instruction or style — just concatenate without editing
        from cutai.models.types import EditPlan

        edit_plan = EditPlan(
            instruction="",
            operations=[],
            estimated_duration=merged.duration,
            summary="Concatenation only (no edits applied)",
        )

    # Step 4: Concatenate source videos
    with tempfile.TemporaryDirectory(prefix="cutai_multi_") as tmpdir:
        concat_path = os.path.join(tmpdir, "concatenated.mp4")
        _concat_videos(video_paths, concat_path)
        logger.info("Concatenation complete: %s", concat_path)

        # Step 5: Apply edit plan
        if edit_plan.operations:
            from cutai.editor.renderer import render

            result = render(
                concat_path,
                edit_plan,
                merged,
                output_path,
                burn_subtitles=burn_subtitles,
            )
        else:
            # No operations — just copy the concatenated file
            import shutil

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(concat_path, output_path)
            result = output_path

    logger.info("Multi-edit complete: %s", result)
    return result


def _analyze_multiple(
    video_paths: list[str],
    whisper_model: str,
) -> list[VideoAnalysis]:
    """Analyze each video file independently.

    Args:
        video_paths: Paths to video files.
        whisper_model: Whisper model for transcription.

    Returns:
        List of VideoAnalysis, one per input video.
    """
    from cutai.analyzer import analyze_video

    analyses: list[VideoAnalysis] = []
    for i, vp in enumerate(video_paths):
        logger.info("Analyzing video %d/%d: %s", i + 1, len(video_paths), vp)
        analysis = analyze_video(vp, whisper_model=whisper_model)
        analyses.append(analysis)

    return analyses


def _merge_analyses(analyses: list[VideoAnalysis]) -> VideoAnalysis:
    """Merge multiple VideoAnalysis into one combined analysis.

    - Concatenates scene lists, adjusting timestamps by cumulative duration
    - Concatenates transcripts with timestamp offsets
    - Merges quality reports (silent segments offset)
    - Combined duration = sum of individual durations
    - Uses first video's resolution/fps as reference

    Args:
        analyses: List of VideoAnalysis to merge.

    Returns:
        A single merged VideoAnalysis.

    Raises:
        ValueError: If analyses list is empty.
    """
    if not analyses:
        raise ValueError("Cannot merge empty list of analyses")

    if len(analyses) == 1:
        return analyses[0].model_copy(deep=True)

    first = analyses[0]
    all_scenes: list[SceneInfo] = []
    all_transcript: list[TranscriptSegment] = []
    all_silent: list[TimeRange] = []
    all_energy: list[float] = []
    total_duration = 0.0
    total_silence_duration = 0.0
    scene_counter = 0
    cumulative_offset = 0.0

    for analysis in analyses:
        # Offset scenes
        for scene in analysis.scenes:
            all_scenes.append(
                SceneInfo(
                    id=scene_counter,
                    start_time=scene.start_time + cumulative_offset,
                    end_time=scene.end_time + cumulative_offset,
                    duration=scene.duration,
                    has_speech=scene.has_speech,
                    is_silent=scene.is_silent,
                    thumbnail_path=scene.thumbnail_path,
                    transcript=scene.transcript,
                    avg_energy=scene.avg_energy,
                )
            )
            scene_counter += 1

        # Offset transcript segments
        for seg in analysis.transcript:
            all_transcript.append(
                TranscriptSegment(
                    start_time=seg.start_time + cumulative_offset,
                    end_time=seg.end_time + cumulative_offset,
                    text=seg.text,
                    confidence=seg.confidence,
                )
            )

        # Offset silent segments
        for seg in analysis.quality.silent_segments:
            all_silent.append(
                TimeRange(
                    start=seg.start + cumulative_offset,
                    end=seg.end + cumulative_offset,
                )
            )

        # Collect audio energy
        all_energy.extend(analysis.quality.audio_energy)

        # Track silence
        for seg in analysis.quality.silent_segments:
            total_silence_duration += seg.duration

        total_duration += analysis.duration
        cumulative_offset += analysis.duration

    # Calculate overall silence ratio
    overall_silence_ratio = (
        total_silence_duration / total_duration if total_duration > 0 else 0.0
    )

    merged_quality = QualityReport(
        silent_segments=all_silent,
        audio_energy=all_energy,
        overall_silence_ratio=min(1.0, overall_silence_ratio),
    )

    return VideoAnalysis(
        file_path=f"merged({len(analyses)} videos)",
        duration=total_duration,
        fps=first.fps,
        width=first.width,
        height=first.height,
        scenes=all_scenes,
        transcript=all_transcript,
        quality=merged_quality,
    )


def _concat_videos(video_paths: list[str], output_path: str) -> str:
    """Concatenate multiple videos using FFmpeg concat demuxer.

    Auto-detects whether re-encoding is needed by comparing stream info.
    Uses stream copy when possible for speed; re-encodes when necessary.

    Args:
        video_paths: List of video file paths to concatenate.
        output_path: Path for the concatenated output.

    Returns:
        Path to the concatenated video.

    Raises:
        subprocess.CalledProcessError: If FFmpeg fails.
    """
    ffmpeg = ensure_ffmpeg()

    # Create concat list file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="cutai_concat_"
    ) as f:
        for vp in video_paths:
            # Escape single quotes in file paths for FFmpeg concat format
            escaped = vp.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
        list_path = f.name

    try:
        if _need_reencode(video_paths):
            logger.info("Videos have different formats — re-encoding for concat")
            cmd = [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_path,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_path,
            ]
        else:
            logger.info("Videos are compatible — using stream copy for concat")
            cmd = [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_path,
                "-c", "copy",
                "-movflags", "+faststart",
                output_path,
            ]

        logger.debug("FFmpeg concat command: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=1800,  # 30 minutes for large files
        )
        logger.debug("FFmpeg concat stderr: %s", result.stderr.decode()[:500])
    finally:
        # Clean up the temp list file
        with suppress(OSError):
            os.unlink(list_path)

    return output_path


def _need_reencode(video_paths: list[str]) -> bool:
    """Check if videos need re-encoding for concatenation.

    Compares video codec, resolution, and fps across all files.
    If any differ, re-encoding is needed.

    Args:
        video_paths: List of video file paths.

    Returns:
        True if re-encoding is needed, False if stream copy is safe.
    """
    if len(video_paths) < 2:
        return False

    ffprobe = ensure_ffprobe()
    infos: list[dict] = []

    for vp in video_paths:
        cmd = [
            ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-select_streams", "v:0",
            vp,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            if streams:
                stream = streams[0]
                infos.append({
                    "codec": stream.get("codec_name", ""),
                    "width": int(stream.get("width", 0)),
                    "height": int(stream.get("height", 0)),
                    "fps": stream.get("r_frame_rate", ""),
                    "pix_fmt": stream.get("pix_fmt", ""),
                })
            else:
                # Can't determine — safer to re-encode
                return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
            # Can't probe — safer to re-encode
            return True

    if not infos:
        return True

    # Compare all against the first
    ref = infos[0]
    for info in infos[1:]:
        if (
            info["codec"] != ref["codec"]
            or info["width"] != ref["width"]
            or info["height"] != ref["height"]
            or info["fps"] != ref["fps"]
            or info["pix_fmt"] != ref["pix_fmt"]
        ):
            logger.debug(
                "Format mismatch detected: ref=%s vs current=%s",
                ref,
                info,
            )
            return True

    return False
