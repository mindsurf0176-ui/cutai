"""Render pipeline — orchestrates cut → subtitle → final output.

This is the main entry point for applying an EditPlan to a video.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from cutai.models.types import (
    CutOperation,
    EditPlan,
    SubtitleOperation,
    VideoAnalysis,
)

logger = logging.getLogger(__name__)


def render(
    video_path: str,
    plan: EditPlan,
    analysis: VideoAnalysis,
    output_path: str,
    burn_subtitles: bool = False,
) -> str:
    """Apply an edit plan and render the final video.

    Pipeline:
    1. Apply CutOperations (segment extraction + concat)
    2. Apply SubtitleOperations (generate ASS — sidecar or burn)
    3. Output final MP4

    Args:
        video_path: Path to the source video.
        plan: The edit plan to apply.
        analysis: Video analysis (needed for transcript data).
        output_path: Path for the final output video.
        burn_subtitles: If True, burn subtitles into video (slow, re-encodes).
            If False (default), save .ass file as sidecar next to output.

    Returns:
        Path to the rendered output video.
    """
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Separate operations by type
    cut_ops = [op for op in plan.operations if isinstance(op, CutOperation)]
    sub_ops = [op for op in plan.operations if isinstance(op, SubtitleOperation)]

    has_cuts = len(cut_ops) > 0
    has_subs = len(sub_ops) > 0

    current_video = video_path

    with tempfile.TemporaryDirectory(prefix="cutai_render_") as tmpdir:
        # Step 1: Apply cuts
        if has_cuts:
            from cutai.editor.cutter import apply_cuts

            cut_output = str(Path(tmpdir) / "cut.mp4")
            logger.info("Step 1/2: Applying %d cut operations...", len(cut_ops))
            current_video = apply_cuts(current_video, cut_ops, cut_output)
        else:
            logger.info("Step 1/2: No cuts to apply — skipping")

        # Step 2: Apply subtitles
        if has_subs and analysis.transcript:
            from cutai.editor.subtitle import burn_subtitles as _burn_subs, generate_ass

            sub_op = sub_ops[0]  # Use first subtitle operation

            # If cuts were applied, we need to adjust transcript timestamps
            transcript = analysis.transcript
            if has_cuts:
                transcript = _adjust_transcript_for_cuts(analysis.transcript, cut_ops)

            if burn_subtitles:
                # Burn subtitles into video (slow — full re-encode)
                ass_path = str(Path(tmpdir) / "subtitles.ass")
                generate_ass(transcript, ass_path, sub_op)

                logger.info("Step 2/2: Burning subtitles into video...")
                sub_output = output_path  # Final output
                current_video = _burn_subs(current_video, ass_path, sub_output)
            else:
                # Save .ass as sidecar file next to output (instant, no re-encode)
                sidecar_path = str(Path(output_path).with_suffix(".ass"))
                generate_ass(transcript, sidecar_path, sub_op)
                logger.info("Step 2/2: Subtitles saved as sidecar: %s", sidecar_path)
                # Still need to copy the cut video to output
                if current_video != output_path:
                    import shutil
                    shutil.copy2(current_video, output_path)
                    current_video = output_path
        else:
            logger.info("Step 2/2: No subtitles to apply — skipping")
            # If no subtitles, just copy the current video to output
            if current_video != output_path:
                import shutil

                shutil.copy2(current_video, output_path)
                current_video = output_path

    logger.info("✅ Render complete → %s", output_path)
    return output_path


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

        # Clamp segment to exclude removed ranges.
        # Find the effective kept portions of this segment.
        # A segment can be fully removed, partially trimmed, or fully kept.
        kept_start = seg_start
        kept_end = seg_end

        for r_start, r_end in removes:
            # If remove range fully contains the segment → remove it
            if r_start <= seg_start and r_end >= seg_end:
                kept_start = kept_end  # zero-length → will be skipped
                break

            # If segment starts inside a removed range, clamp start forward
            if r_start <= kept_start < r_end:
                kept_start = r_end

            # If segment ends inside a removed range, clamp end backward
            if r_start < kept_end <= r_end:
                kept_end = r_start

        # Skip segments that are fully removed or have negligible duration
        if kept_end - kept_start < 0.05:
            continue

        # Skip segments where >50% of original duration was removed
        remaining_ratio = (kept_end - kept_start) / seg_duration if seg_duration > 0 else 0
        if remaining_ratio < 0.5:
            continue

        # Calculate cumulative time shift (total time removed before this segment's kept_start)
        shift = 0.0
        for r_start, r_end in removes:
            if r_end <= kept_start:
                # Entire remove range is before our segment
                shift += r_end - r_start
            elif r_start < kept_start:
                # Remove range partially overlaps our start
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
