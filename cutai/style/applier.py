"""Style applier — convert EditDNA + VideoAnalysis into an EditPlan."""

from __future__ import annotations

import logging
import random

from cutai.models.types import (
    BGMOperation,
    ColorGradeOperation,
    CutOperation,
    EditDNA,
    EditPlan,
    SceneInfo,
    SubtitleOperation,
    TransitionOperation,
    VideoAnalysis,
)

logger = logging.getLogger(__name__)


def apply_style(
    analysis: VideoAnalysis,
    style: EditDNA,
    instruction: str = "",
) -> EditPlan:
    """Generate an EditPlan that applies the given EditDNA style to a video.

    Steps:
        1. **Rhythm**: Remove silent/low-energy scenes to match target pacing.
        2. **Transitions**: Distribute transition types according to DNA ratios.
        3. **Visual**: Map visual DNA to closest ``ColorGradeOperation`` preset.
        4. **Audio**: Add ``BGMOperation`` if the style uses BGM.
        5. **Subtitle**: Add ``SubtitleOperation`` if the style uses subtitles.

    Args:
        analysis: Complete analysis of the target video.
        style: EditDNA to apply.
        instruction: Optional additional instruction text.

    Returns:
        EditPlan with ordered operations.
    """
    operations: list = []
    summary_parts: list[str] = []

    # 1. Rhythm — determine cuts
    cut_ops, cut_summary = _apply_rhythm(analysis, style)
    operations.extend(cut_ops)
    if cut_summary:
        summary_parts.append(cut_summary)

    # 2. Transitions
    trans_ops, trans_summary = _apply_transitions(analysis, style, cut_ops)
    operations.extend(trans_ops)
    if trans_summary:
        summary_parts.append(trans_summary)

    # 3. Visual
    color_op = _apply_visual(style)
    if color_op:
        operations.append(color_op)
        summary_parts.append(f"Color grade: {color_op.preset}")

    # 4. Audio
    bgm_op = _apply_audio(style)
    if bgm_op:
        operations.append(bgm_op)
        summary_parts.append("Add BGM")

    # 5. Subtitles
    sub_op = _apply_subtitles(style)
    if sub_op:
        operations.append(sub_op)
        summary_parts.append("Add subtitles")

    # Estimate output duration
    removed_time = sum(
        op.end_time - op.start_time
        for op in operations
        if isinstance(op, CutOperation) and op.action == "remove"
    )
    estimated = max(0.0, analysis.duration - removed_time)

    return EditPlan(
        instruction=instruction or f"Apply style '{style.name}'",
        operations=operations,
        estimated_duration=round(estimated, 2),
        summary="; ".join(summary_parts) if summary_parts else f"Applied style '{style.name}'",
    )


# ── Rhythm ───────────────────────────────────────────────────────────────────


def _apply_rhythm(
    analysis: VideoAnalysis,
    style: EditDNA,
) -> tuple[list[CutOperation], str]:
    """Remove scenes to match target pacing from the style's rhythm DNA."""
    scenes = analysis.scenes
    if not scenes:
        return [], ""

    rhythm = style.rhythm
    silence_tol = style.audio.silence_tolerance

    # Remove silent segments that exceed tolerance
    cut_ops: list[CutOperation] = []
    for seg in analysis.quality.silent_segments:
        if seg.duration > silence_tol:
            cut_ops.append(
                CutOperation(
                    action="remove",
                    start_time=seg.start,
                    end_time=seg.end,
                    reason=f"Silent segment ({seg.duration:.1f}s) exceeds tolerance ({silence_tol:.1f}s)",
                )
            )

    # Estimate remaining duration after silence removal
    removed_silence = sum(op.end_time - op.start_time for op in cut_ops)
    remaining = analysis.duration - removed_silence

    # Target number of scenes based on cuts_per_minute
    if remaining > 0:
        target_scenes = max(1, int(rhythm.cuts_per_minute * (remaining / 60.0)))
    else:
        target_scenes = len(scenes)

    # If we have too many scenes, remove lowest-scoring ones
    current_scenes = len(scenes)
    if current_scenes > target_scenes:
        scored = _score_scenes(scenes)
        # Sort ascending by score — lowest first
        scored.sort(key=lambda x: x[1])
        excess = current_scenes - target_scenes

        for scene, score in scored[:excess]:
            # Skip scenes already covered by silence removal
            already_cut = any(
                op.start_time <= scene.start_time and op.end_time >= scene.end_time
                for op in cut_ops
            )
            if already_cut:
                continue

            cut_ops.append(
                CutOperation(
                    action="remove",
                    start_time=scene.start_time,
                    end_time=scene.end_time,
                    reason=f"Low engagement (score={score:.1f}) — matching target pacing",
                )
            )

    n_cuts = len(cut_ops)
    summary = f"Remove {n_cuts} segments (target: {rhythm.cuts_per_minute:.0f} cuts/min)" if n_cuts else ""
    return cut_ops, summary


def _score_scenes(scenes: list[SceneInfo]) -> list[tuple[SceneInfo, float]]:
    """Score scenes by engagement value. Higher = more worth keeping."""
    scored = []
    for scene in scenes:
        score = 0.0
        if scene.has_speech:
            score += 50.0
        if not scene.is_silent:
            score += 30.0
        # Energy: dBFS, closer to 0 = louder = more engaging
        if scene.avg_energy < 0:
            score += max(0.0, 60.0 + scene.avg_energy)
        elif scene.avg_energy == 0:
            score += 10.0
        scored.append((scene, score))
    return scored


# ── Transitions ──────────────────────────────────────────────────────────────


def _apply_transitions(
    analysis: VideoAnalysis,
    style: EditDNA,
    cut_ops: list[CutOperation],
) -> tuple[list[TransitionOperation], str]:
    """Distribute transitions between remaining scene boundaries."""
    scenes = analysis.scenes
    if len(scenes) < 2:
        return [], ""

    tdna = style.transitions
    # Gather IDs of scenes that will be removed
    removed_ranges = [
        (op.start_time, op.end_time)
        for op in cut_ops
        if op.action == "remove"
    ]

    def _is_removed(scene: SceneInfo) -> bool:
        return any(rs <= scene.start_time and re_ >= scene.end_time for rs, re_ in removed_ranges)

    kept = [s for s in scenes if not _is_removed(s)]
    if len(kept) < 2:
        return [], ""

    n_boundaries = len(kept) - 1

    # Calculate number of non-jump transitions
    n_fade = max(0, round(tdna.fade_ratio * n_boundaries))
    n_dissolve = max(0, round(tdna.dissolve_ratio * n_boundaries))
    n_wipe = max(0, round(tdna.wipe_ratio * n_boundaries))

    # Build style assignments — most are jump cuts (no op needed)
    assignments: list[str | None] = [None] * n_boundaries  # None = jump cut
    indices = list(range(n_boundaries))
    random.shuffle(indices)

    ptr = 0
    for style_name, count in [("fade", n_fade), ("dissolve", n_dissolve), ("wipe", n_wipe)]:
        for _ in range(count):
            if ptr >= len(indices):
                break
            assignments[indices[ptr]] = style_name
            ptr += 1

    ops: list[TransitionOperation] = []
    for idx, trans_style in enumerate(assignments):
        if trans_style is None:
            continue
        ops.append(
            TransitionOperation(
                style=trans_style,  # type: ignore[arg-type]
                duration=tdna.avg_transition_duration,
                between=(kept[idx].id, kept[idx + 1].id),
            )
        )

    summary = f"Add {len(ops)} transitions ({n_fade}×fade, {n_dissolve}×dissolve, {n_wipe}×wipe)" if ops else ""
    return ops, summary


# ── Visual ───────────────────────────────────────────────────────────────────


_PRESET_MAP = {
    # (brightness_offset_range, saturation_range, temperature) → preset
    "bright": {"brightness": (0.02, 1.0), "saturation": (0.9, 1.5), "temp": None},
    "warm": {"brightness": (-0.5, 0.5), "saturation": (0.9, 1.5), "temp": "warm"},
    "cool": {"brightness": (-0.5, 0.5), "saturation": (0.8, 1.3), "temp": "cool"},
    "cinematic": {"brightness": (-0.3, 0.0), "saturation": (0.6, 1.0), "temp": None},
    "vintage": {"brightness": (-0.2, 0.1), "saturation": (0.4, 0.8), "temp": "warm"},
}


def _apply_visual(style: EditDNA) -> ColorGradeOperation | None:
    """Map visual DNA to the closest ColorGradeOperation preset."""
    vdna = style.visual

    # Score each preset by how well it matches the visual DNA
    best_preset = "bright"
    best_score = -999.0

    for preset_name, criteria in _PRESET_MAP.items():
        score = 0.0
        bmin, bmax = criteria["brightness"]
        if bmin <= vdna.avg_brightness <= bmax:
            score += 2.0

        smin, smax = criteria["saturation"]
        if smin <= vdna.avg_saturation <= smax:
            score += 2.0

        expected_temp = criteria["temp"]
        if expected_temp is None:
            score += 0.5  # neutral bonus for presets without temp preference
        elif expected_temp == vdna.color_temperature:
            score += 3.0

        if score > best_score:
            best_score = score
            best_preset = preset_name

    # Only add colour grading if there's meaningful visual DNA (non-default)
    is_default = (
        abs(vdna.avg_brightness) < 0.01
        and abs(vdna.avg_saturation - 1.0) < 0.05
        and vdna.color_temperature == "neutral"
    )
    if is_default:
        return None

    return ColorGradeOperation(preset=best_preset, intensity=50.0)


# ── Audio ────────────────────────────────────────────────────────────────────


def _apply_audio(style: EditDNA) -> BGMOperation | None:
    """Add BGM if the style specifies it."""
    if not style.audio.has_bgm:
        return None

    volume_pct = round(style.audio.bgm_volume_ratio * 100.0, 1)
    return BGMOperation(mood="calm", volume=volume_pct, fade_in=2.0, fade_out=2.0)


# ── Subtitles ────────────────────────────────────────────────────────────────


def _apply_subtitles(style: EditDNA) -> SubtitleOperation | None:
    """Add subtitles if the style specifies them."""
    if not style.subtitle.has_subtitles:
        return None

    font_map = {"small": 18, "medium": 24, "large": 32}
    font_size = font_map.get(style.subtitle.font_size_category, 24)

    return SubtitleOperation(
        style="default",
        language="auto",
        font_size=font_size,
        position=style.subtitle.position,
    )
