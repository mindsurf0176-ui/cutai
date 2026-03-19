"""CutAI Smart Highlight Generator — Phase 3A.

Generates highlight reels from the most engaging scenes of a video.
Supports three strategies:

- **best-moments**: Top N scenes by engagement score (re-sorted chronologically).
- **narrative**: Maintain chronological order, always keep hook + conclusion,
  drop lowest-scoring scenes until target duration is reached.
- **shorts**: Find the best contiguous ~60 s segment via sliding window.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cutai.models.types import CutOperation, EditPlan

if TYPE_CHECKING:
    from cutai.models.types import EngagementReport, SceneInfo, VideoAnalysis

logger = logging.getLogger(__name__)

# ── Public API ───────────────────────────────────────────────────────────────


def generate_highlights(
    video_path: str,
    analysis: VideoAnalysis,
    engagement: EngagementReport,
    target_duration: float | None = None,
    target_ratio: float = 0.2,
    min_scene_duration: float = 1.0,
    style: str = "best-moments",
) -> EditPlan:
    """Generate a highlight reel from the most engaging scenes.

    Args:
        video_path: Source video path.
        analysis: Full video analysis.
        engagement: Engagement scores for all scenes.
        target_duration: Target highlight duration in seconds.
            If None, uses ``target_ratio`` of total duration.
        target_ratio: Fraction of video to keep (default 20%).
        min_scene_duration: Minimum scene duration to include.
        style: Highlight style — ``"best-moments"``, ``"narrative"``,
            or ``"shorts"``.

    Returns:
        EditPlan with CutOperation(action="keep") entries.
    """
    scenes = analysis.scenes
    total_duration = analysis.duration

    if target_duration is None:
        target_duration = total_duration * target_ratio

    # Clamp
    target_duration = max(1.0, min(target_duration, total_duration))

    # Build engagement lookup {scene_id: score}
    score_map: dict[int, float] = {
        se.scene_id: se.score for se in engagement.scenes
    }

    # Filter out scenes shorter than min_scene_duration
    eligible = [s for s in scenes if s.duration >= min_scene_duration]
    if not eligible:
        eligible = list(scenes)  # fallback: use all

    if style == "shorts":
        kept = _strategy_shorts(eligible, score_map, target_duration)
    elif style == "narrative":
        kept = _strategy_narrative(eligible, score_map, target_duration)
    else:
        kept = _strategy_best_moments(eligible, score_map, target_duration)

    # Build CutOperations (keep)
    operations: list[CutOperation] = []
    for scene in kept:
        operations.append(CutOperation(
            action="keep",
            start_time=scene.start_time,
            end_time=scene.end_time,
            reason=f"Engagement score: {score_map.get(scene.id, 0):.0f}",
        ))

    estimated = sum(s.duration for s in kept)

    return EditPlan(
        instruction=f"Generate {style} highlights ({target_duration:.0f}s target)",
        operations=operations,
        estimated_duration=round(estimated, 2),
        summary=(
            f"{style} highlights: {len(kept)} scenes, "
            f"{estimated:.1f}s (target {target_duration:.0f}s)"
        ),
    )


def auto_highlight_duration(total_duration: float) -> float:
    """Suggest a highlight duration based on total video length.

    Rules:
        - <5 min:   30-60 s  (shorts-friendly)
        - 5-15 min: 60-180 s
        - 15-60 min: 180-300 s
        - >60 min:  300-600 s

    Returns a single recommended value (not a range).
    """
    if total_duration < 300:  # <5 min
        return max(30.0, min(60.0, total_duration * 0.3))
    elif total_duration < 900:  # 5-15 min
        return max(60.0, min(180.0, total_duration * 0.2))
    elif total_duration < 3600:  # 15-60 min
        return max(180.0, min(300.0, total_duration * 0.12))
    else:  # >60 min
        return max(300.0, min(600.0, total_duration * 0.08))


# ── Strategies ───────────────────────────────────────────────────────────────


def _strategy_best_moments(
    scenes: list[SceneInfo],
    score_map: dict[int, float],
    target_duration: float,
) -> list[SceneInfo]:
    """Pick top scenes by engagement score, then re-sort chronologically.

    Greedily add highest-scoring scenes until target duration is reached.
    """
    sorted_scenes = sorted(
        scenes,
        key=lambda s: score_map.get(s.id, 0),
        reverse=True,
    )

    kept: list[SceneInfo] = []
    accumulated = 0.0

    for scene in sorted_scenes:
        if accumulated >= target_duration:
            break
        kept.append(scene)
        accumulated += scene.duration

    # Re-sort chronologically
    kept.sort(key=lambda s: s.start_time)
    return kept


def _strategy_narrative(
    scenes: list[SceneInfo],
    score_map: dict[int, float],
    target_duration: float,
) -> list[SceneInfo]:
    """Keep chronological order; always keep first (hook) and last (conclusion).

    Remove lowest-scoring scenes until total duration ≤ target.
    """
    if not scenes:
        return []

    # Start with all scenes
    remaining = list(scenes)
    total = sum(s.duration for s in remaining)

    # Always protect first and last scene
    protected_ids = {scenes[0].id, scenes[-1].id}

    while total > target_duration and len(remaining) > 1:
        # Find lowest-scoring non-protected scene
        removable = [
            s for s in remaining if s.id not in protected_ids
        ]
        if not removable:
            break

        worst = min(removable, key=lambda s: score_map.get(s.id, 0))
        total -= worst.duration
        remaining.remove(worst)

    return remaining


def _strategy_shorts(
    scenes: list[SceneInfo],
    score_map: dict[int, float],
    target_duration: float,
) -> list[SceneInfo]:
    """Find the best contiguous segment of approximately target_duration.

    Uses a sliding window over scenes.  Window score = sum of engagement
    scores of scenes that fit within the window.  Pick the window with
    the highest total score.
    """
    if not scenes:
        return []

    # Default shorts target ≈ 60 seconds
    target = min(target_duration, 60.0)

    best_score = -1.0
    best_window: list[SceneInfo] = []

    for i in range(len(scenes)):
        window: list[SceneInfo] = []
        window_duration = 0.0
        window_score = 0.0

        for j in range(i, len(scenes)):
            if window_duration + scenes[j].duration > target * 1.2:
                # Allow up to 20% over target
                break
            window.append(scenes[j])
            window_duration += scenes[j].duration
            window_score += score_map.get(scenes[j].id, 0)

        if window and window_score > best_score:
            best_score = window_score
            best_window = list(window)

    return best_window
