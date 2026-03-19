"""Render pipeline — orchestrates all edit operations into a final video.

Pipeline order:
1. Cut (segment extraction + concat)
2. Speed adjustments
3. Color grading
4. BGM mixing
5. Subtitles (ASS generation — sidecar or burn)
6. Transitions (applied during concat step)

This is the main entry point for applying an EditPlan to a video.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from cutai.models.types import (
    BGMOperation,
    ColorGradeOperation,
    CutOperation,
    EditPlan,
    SpeedOperation,
    SubtitleOperation,
    TransitionOperation,
    VideoAnalysis,
)

logger = logging.getLogger(__name__)


def render(
    video_path: str,
    plan: EditPlan,
    analysis: VideoAnalysis,
    output_path: str,
    burn_subtitles: bool = False,
    bgm_file: str | None = None,
) -> str:
    """Apply an edit plan and render the final video.

    Pipeline:
    1. Apply CutOperations (segment extraction + concat)
    2. Apply SpeedOperations (playback speed adjustment)
    3. Apply ColorGradeOperations (color grading filters)
    4. Apply BGMOperations (background music mixing)
    5. Apply SubtitleOperations (generate ASS — sidecar or burn)
    6. Apply TransitionOperations (xfade between scenes)

    Args:
        video_path: Path to the source video.
        plan: The edit plan to apply.
        analysis: Video analysis (needed for transcript data).
        output_path: Path for the final output video.
        burn_subtitles: If True, burn subtitles into video (slow, re-encodes).
            If False (default), save .ass file as sidecar next to output.
        bgm_file: Optional path to a BGM audio file to use.

    Returns:
        Path to the rendered output video.
    """
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Separate operations by type
    cut_ops = [op for op in plan.operations if isinstance(op, CutOperation)]
    speed_ops = [op for op in plan.operations if isinstance(op, SpeedOperation)]
    color_ops = [op for op in plan.operations if isinstance(op, ColorGradeOperation)]
    bgm_ops = [op for op in plan.operations if isinstance(op, BGMOperation)]
    sub_ops = [op for op in plan.operations if isinstance(op, SubtitleOperation)]
    trans_ops = [op for op in plan.operations if isinstance(op, TransitionOperation)]

    total_steps = sum([
        bool(cut_ops),
        bool(speed_ops),
        bool(color_ops),
        bool(bgm_ops),
        bool(sub_ops),
        bool(trans_ops),
    ])
    step_num = 0

    current_video = video_path

    with tempfile.TemporaryDirectory(prefix="cutai_render_") as tmpdir:

        # ── Step 1: Apply cuts ───────────────────────────────────────────
        if cut_ops:
            from cutai.editor.cutter import apply_cuts

            step_num += 1
            cut_output = str(Path(tmpdir) / "step1_cut.mp4")
            logger.info(
                "Step %d/%d: Applying %d cut operations...",
                step_num, total_steps, len(cut_ops),
            )
            current_video = apply_cuts(current_video, cut_ops, cut_output)
        else:
            logger.info("Cuts: skipped (none)")

        # ── Step 2: Apply speed adjustments ──────────────────────────────
        if speed_ops:
            from cutai.editor.speed import apply_speed

            step_num += 1
            for i, speed_op in enumerate(speed_ops):
                speed_output = str(Path(tmpdir) / f"step2_speed_{i}.mp4")
                logger.info(
                    "Step %d/%d: Applying speed ×%.2f...",
                    step_num, total_steps, speed_op.factor,
                )
                current_video = apply_speed(current_video, speed_op, speed_output)

        else:
            logger.info("Speed: skipped (none)")

        # ── Step 3: Apply color grading ──────────────────────────────────
        if color_ops:
            from cutai.editor.color import apply_color_grade

            step_num += 1
            # Apply only the first color grade operation (stacking is rare)
            color_op = color_ops[0]
            color_output = str(Path(tmpdir) / "step3_color.mp4")
            logger.info(
                "Step %d/%d: Applying color grade (preset=%s, intensity=%.0f)...",
                step_num, total_steps, color_op.preset, color_op.intensity,
            )
            current_video = apply_color_grade(
                current_video, color_op, color_output,
            )
        else:
            logger.info("Color grade: skipped (none)")

        # ── Step 4: Apply BGM ────────────────────────────────────────────
        if bgm_ops:
            from cutai.editor.bgm import apply_bgm

            step_num += 1
            bgm_op = bgm_ops[0]
            bgm_output = str(Path(tmpdir) / "step4_bgm.mp4")
            logger.info(
                "Step %d/%d: Mixing BGM (mood=%s, vol=%d%%)...",
                step_num, total_steps, bgm_op.mood, bgm_op.volume,
            )
            current_video = apply_bgm(
                current_video, bgm_op, bgm_output, bgm_file=bgm_file,
            )
        else:
            logger.info("BGM: skipped (none)")

        # ── Step 5: Apply subtitles ──────────────────────────────────────
        if sub_ops and analysis.transcript:
            from cutai.editor.subtitle import burn_subtitles as _burn_subs
            from cutai.editor.subtitle import generate_ass

            step_num += 1
            sub_op = sub_ops[0]

            # If cuts were applied, adjust transcript timestamps
            transcript = analysis.transcript
            if cut_ops:
                transcript = _adjust_transcript_for_cuts(
                    analysis.transcript, cut_ops,
                )

            if burn_subtitles:
                ass_path = str(Path(tmpdir) / "subtitles.ass")
                generate_ass(transcript, ass_path, sub_op)

                logger.info(
                    "Step %d/%d: Burning subtitles into video...",
                    step_num, total_steps,
                )
                sub_output = str(Path(tmpdir) / "step5_subs.mp4")
                current_video = _burn_subs(current_video, ass_path, sub_output)
            else:
                sidecar_path = str(Path(output_path).with_suffix(".ass"))
                generate_ass(transcript, sidecar_path, sub_op)
                logger.info(
                    "Step %d/%d: Subtitles saved as sidecar: %s",
                    step_num, total_steps, sidecar_path,
                )
        else:
            logger.info("Subtitles: skipped (none or no transcript)")

        # ── Step 6: Apply transitions ────────────────────────────────────
        if trans_ops:
            from cutai.editor.transition import apply_transitions

            step_num += 1
            # Compute cut points from the current state of the video.
            # Use scene boundaries from analysis, adjusted for any cuts.
            cut_points = _compute_cut_points(analysis, cut_ops)
            if cut_points:
                trans_output = str(Path(tmpdir) / "step6_trans.mp4")
                logger.info(
                    "Step %d/%d: Applying %d transitions...",
                    step_num, total_steps, len(trans_ops),
                )
                current_video = apply_transitions(
                    current_video, trans_ops, cut_points, trans_output,
                )
            else:
                logger.info("Transitions: skipped (no cut points)")
        else:
            logger.info("Transitions: skipped (none)")

        # ── Final: copy to output ────────────────────────────────────────
        if current_video != output_path:
            shutil.copy2(current_video, output_path)

    logger.info("✅ Render complete → %s", output_path)
    return output_path


def _compute_cut_points(
    analysis: VideoAnalysis,
    cut_ops: list[CutOperation],
) -> list[float]:
    """Compute scene boundary timestamps in the edited video.

    Takes the original scene boundaries and adjusts them for
    any removed segments.
    """
    if len(analysis.scenes) < 2:
        return []

    # Original scene boundaries (end of each scene except last)
    boundaries = [scene.end_time for scene in analysis.scenes[:-1]]

    if not cut_ops:
        return boundaries

    # Compute cumulative removed time before each boundary
    removes = sorted(
        [(op.start_time, op.end_time) for op in cut_ops if op.action == "remove"],
        key=lambda x: x[0],
    )

    adjusted: list[float] = []
    for boundary in boundaries:
        shift = 0.0
        removed = False
        for r_start, r_end in removes:
            if r_end <= boundary:
                shift += r_end - r_start
            elif r_start < boundary < r_end:
                # Boundary falls inside a removed range — skip it
                removed = True
                break
        if not removed:
            adjusted_boundary = boundary - shift
            if adjusted_boundary > 0:
                adjusted.append(round(adjusted_boundary, 3))

    return adjusted


def _adjust_transcript_for_cuts(
    transcript: list,
    cut_ops: list[CutOperation],
) -> list:
    """Adjust transcript timestamps after cut operations.

    When segments are removed, subsequent transcript times need to shift.
    Handles partial overlaps by clamping segment boundaries to kept ranges.
    """
    from cutai.models.types import TranscriptSegment

    # Get sorted remove ranges
    removes = sorted(
        [(op.start_time, op.end_time) for op in cut_ops if op.action == "remove"],
        key=lambda x: x[0],
    )

    if not removes:
        return transcript

    adjusted: list[TranscriptSegment] = []

    for seg in transcript:
        seg_start = seg.start_time
        seg_end = seg.end_time
        seg_duration = seg_end - seg_start

        kept_start = seg_start
        kept_end = seg_end

        for r_start, r_end in removes:
            if r_start <= seg_start and r_end >= seg_end:
                kept_start = kept_end
                break
            if r_start <= kept_start < r_end:
                kept_start = r_end
            if r_start < kept_end <= r_end:
                kept_end = r_start

        if kept_end - kept_start < 0.05:
            continue

        remaining_ratio = (
            (kept_end - kept_start) / seg_duration if seg_duration > 0 else 0
        )
        if remaining_ratio < 0.5:
            continue

        shift = 0.0
        for r_start, r_end in removes:
            if r_end <= kept_start:
                shift += r_end - r_start
            elif r_start < kept_start:
                shift += kept_start - r_start

        adjusted.append(
            TranscriptSegment(
                start_time=round(max(0.0, kept_start - shift), 3),
                end_time=round(max(0.0, kept_end - shift), 3),
                text=seg.text,
                confidence=seg.confidence,
            )
        )

    return adjusted
