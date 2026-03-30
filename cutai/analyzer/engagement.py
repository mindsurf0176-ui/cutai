"""CutAI Engagement Score Engine — Phase 3A.

Computes an engagement score (0-100) for each scene based on multiple
audio, visual, and structural signals.  All computation uses FFmpeg +
Python stdlib only (no PIL/Pillow).

Scoring signals (weighted sum, normalized to 0-100):
  1. Audio Energy      (0.25) — higher RMS = more engaging
  2. Speech Density    (0.20) — words/sec, silence → low engagement
  3. Visual Activity   (0.20) — inter-frame pixel diff via FFmpeg rawvideo
  4. Scene Duration Fit(0.10) — bell-curve around 4-5 s
  5. Audio Variety     (0.15) — variance of windowed RMS within a scene
  6. Position Bonus    (0.10) — first/last 10% of video get a boost
"""

from __future__ import annotations

import logging
import math
import struct
import subprocess
from typing import TYPE_CHECKING

from cutai.config import ensure_ffmpeg
from cutai.models.types import EngagementReport, SceneEngagement

if TYPE_CHECKING:
    from cutai.models.types import SceneInfo, VideoAnalysis

logger = logging.getLogger(__name__)

# ── Weights ──────────────────────────────────────────────────────────────────

W_AUDIO_ENERGY = 0.25
W_SPEECH_DENSITY = 0.20
W_VISUAL_ACTIVITY = 0.20
W_DURATION_FIT = 0.10
W_AUDIO_VARIETY = 0.15
W_POSITION = 0.10

# ── Tier thresholds ──────────────────────────────────────────────────────────

TIER_HIGH = 70.0
TIER_LOW = 40.0


# ── Public API ───────────────────────────────────────────────────────────────


def compute_engagement_scores(
    analysis: VideoAnalysis,
    video_path: str,
) -> EngagementReport:
    """Compute engagement scores for all scenes in a video.

    Args:
        analysis: Complete video analysis with scenes populated.
        video_path: Path to the source video file.

    Returns:
        EngagementReport with per-scene scores and overall stats.
    """
    scenes = analysis.scenes
    if not scenes:
        return EngagementReport()

    total_duration = analysis.duration or sum(s.duration for s in scenes)

    # 1. Audio energy (from pre-computed avg_energy in SceneInfo)
    audio_energy_scores = _score_audio_energy(scenes)

    # 2. Speech density
    speech_density_scores = _score_speech_density(scenes)

    # 3. Visual activity (FFmpeg-based)
    visual_activity_scores = _compute_visual_activity(video_path, scenes)

    # 4. Duration fit
    duration_fit_scores = [_score_duration_fit(s.duration) for s in scenes]

    # 5. Audio variety (FFmpeg-based)
    audio_variety_scores = _compute_audio_variety(video_path, scenes)

    # 6. Position bonus
    position_scores = _score_position(scenes, total_duration)

    # Combine into final scores
    engagements: list[SceneEngagement] = []
    for i, scene in enumerate(scenes):
        ae = audio_energy_scores[i]
        sd = speech_density_scores[i]
        va = visual_activity_scores[i]
        df = duration_fit_scores[i]
        av = audio_variety_scores[i]
        ps = position_scores[i]

        weighted = (
            W_AUDIO_ENERGY * ae
            + W_SPEECH_DENSITY * sd
            + W_VISUAL_ACTIVITY * va
            + W_DURATION_FIT * df
            + W_AUDIO_VARIETY * av
            + W_POSITION * ps
        )
        score = min(100.0, max(0.0, weighted))

        label: str
        if score >= TIER_HIGH:
            label = "high"
        elif score >= TIER_LOW:
            label = "medium"
        else:
            label = "low"

        engagements.append(SceneEngagement(
            scene_id=scene.id,
            score=round(score, 2),
            audio_energy_score=round(ae, 2),
            speech_density_score=round(sd, 2),
            visual_activity_score=round(va, 2),
            duration_fit_score=round(df, 2),
            audio_variety_score=round(av, 2),
            position_score=round(ps, 2),
            label=label,  # type: ignore[arg-type]
        ))

    avg = sum(e.score for e in engagements) / len(engagements)
    high_count = sum(1 for e in engagements if e.label == "high")
    low_count = sum(1 for e in engagements if e.label == "low")

    return EngagementReport(
        scenes=engagements,
        avg_score=round(avg, 2),
        high_count=high_count,
        low_count=low_count,
    )


# ── Signal 1: Audio Energy ──────────────────────────────────────────────────


def _score_audio_energy(scenes: list[SceneInfo]) -> list[float]:
    """Score scenes by audio energy using pre-computed avg_energy.

    avg_energy is typically in dBFS (negative), so we convert to a 0-100 scale.
    Silence is around -60 dBFS, loud speech around -10 dBFS.
    Speech presence adds a +10 bonus.
    """
    if not scenes:
        return []

    energies = [s.avg_energy for s in scenes]

    # Min-max normalize across scenes
    e_min = min(energies)
    e_max = max(energies)
    span = e_max - e_min

    scores: list[float] = []
    for scene in scenes:
        normalized = (scene.avg_energy - e_min) / span if span > 0 else 0.5  # 0.0 - 1.0/all same energy

        base = normalized * 90.0  # 0-90
        bonus = 10.0 if scene.has_speech else 0.0
        scores.append(min(100.0, base + bonus))

    return scores


# ── Signal 2: Speech Density ────────────────────────────────────────────────


def _score_speech_density(scenes: list[SceneInfo]) -> list[float]:
    """Score scenes by words per second.

    Higher word density = more information = more engaging.
    Target range: 2-4 words/sec is typical engaged speech.
    """
    scores: list[float] = []
    for scene in scenes:
        if not scene.transcript or scene.duration <= 0:
            scores.append(0.0)
            continue

        word_count = len(scene.transcript.split())
        wps = word_count / scene.duration

        # Score with diminishing returns past 4 wps
        # 0 wps → 0, 2 wps → 60, 3 wps → 80, 4+ wps → 90-100
        if wps <= 0:
            score = 0.0
        elif wps <= 2.0:
            score = wps * 30.0  # 0-60
        elif wps <= 4.0:
            score = 60.0 + (wps - 2.0) * 15.0  # 60-90
        else:
            score = min(100.0, 90.0 + (wps - 4.0) * 5.0)  # 90-100

        scores.append(score)

    return scores


# ── Signal 3: Visual Activity ───────────────────────────────────────────────


def _compute_visual_activity(
    video_path: str,
    scenes: list[SceneInfo],
) -> list[float]:
    """Compute visual activity scores for each scene.

    For each scene, extract 2 raw grayscale frames and compute
    mean absolute pixel difference.  Higher diff = more motion = engaging.

    Falls back to 50.0 (neutral) on any FFmpeg error.
    """
    ffmpeg = ensure_ffmpeg()
    raw_diffs: list[float] = []

    for scene in scenes:
        if scene.duration < 0.1:
            raw_diffs.append(0.0)
            continue

        # Sample two frames: 25% and 75% into the scene
        t1 = scene.start_time + scene.duration * 0.25
        t2 = scene.start_time + scene.duration * 0.75

        try:
            diff = _frame_pair_diff(ffmpeg, video_path, t1, t2)
            raw_diffs.append(diff)
        except Exception:
            logger.debug(
                "Visual activity fallback for scene %d (%.1fs-%.1fs)",
                scene.id, scene.start_time, scene.end_time,
            )
            raw_diffs.append(-1.0)  # sentinel for fallback

    # Normalize diffs to 0-100
    valid_diffs = [d for d in raw_diffs if d >= 0]
    if not valid_diffs:
        return [50.0] * len(scenes)

    d_max = max(valid_diffs) if valid_diffs else 1.0
    if d_max <= 0:
        d_max = 1.0

    scores: list[float] = []
    for d in raw_diffs:
        if d < 0:
            scores.append(50.0)  # neutral fallback
        else:
            scores.append(min(100.0, (d / d_max) * 100.0))

    return scores


def _frame_pair_diff(
    ffmpeg: str,
    video_path: str,
    t1: float,
    t2: float,
    width: int = 160,
    height: int = 90,
) -> float:
    """Extract two grayscale frames and compute mean absolute difference.

    Uses a small resolution (160×90) to keep it fast.
    """
    frame_size = width * height

    # Extract frame at t1
    f1_data = _extract_raw_frame(ffmpeg, video_path, t1, width, height)
    # Extract frame at t2
    f2_data = _extract_raw_frame(ffmpeg, video_path, t2, width, height)

    if len(f1_data) < frame_size or len(f2_data) < frame_size:
        return 0.0

    # Compute mean absolute difference
    total_diff = 0
    for i in range(frame_size):
        total_diff += abs(f1_data[i] - f2_data[i])

    return total_diff / frame_size


def _extract_raw_frame(
    ffmpeg: str,
    video_path: str,
    timestamp: float,
    width: int,
    height: int,
) -> bytes:
    """Extract a single raw grayscale frame at the given timestamp."""
    cmd = [
        ffmpeg,
        "-ss", f"{timestamp:.3f}",
        "-i", video_path,
        "-vframes", "1",
        "-s", f"{width}x{height}",
        "-f", "rawvideo",
        "-pix_fmt", "gray",
        "-v", "quiet",
        "pipe:1",
    ]
    result = subprocess.run(
        cmd, capture_output=True, timeout=15,
    )
    return result.stdout


# ── Signal 4: Duration Fit ──────────────────────────────────────────────────


def _score_duration_fit(duration: float) -> float:
    """Score how well a scene duration fits the 'ideal' editing range.

    Bell curve centered around 5 seconds:
    - 2-8 seconds → high score (intentional/edited)
    - <1 second or >30 seconds → low score
    """
    if duration <= 0:
        return 0.0

    # Gaussian-like scoring around 5 seconds, σ ≈ 4
    ideal = 5.0
    sigma = 4.0
    raw = math.exp(-0.5 * ((duration - ideal) / sigma) ** 2) * 100.0

    # Penalize very short scenes (<1s) more aggressively
    if duration < 1.0:
        raw *= duration  # 0.5s → half score

    return min(100.0, raw)


# ── Signal 5: Audio Variety ─────────────────────────────────────────────────


def _compute_audio_variety(
    video_path: str,
    scenes: list[SceneInfo],
) -> list[float]:
    """Compute audio energy variance within each scene.

    Extract raw PCM audio for each scene, compute windowed RMS (0.1s windows),
    then score based on variance of those RMS values.
    Higher variance = music, laughter, emphasis = more engaging.
    """
    ffmpeg = ensure_ffmpeg()
    raw_variances: list[float] = []

    for scene in scenes:
        if scene.duration < 0.2:
            raw_variances.append(0.0)
            continue

        try:
            variance = _scene_audio_variance(ffmpeg, video_path, scene)
            raw_variances.append(variance)
        except Exception:
            logger.debug(
                "Audio variety fallback for scene %d", scene.id,
            )
            raw_variances.append(-1.0)  # sentinel

    # Normalize to 0-100
    valid = [v for v in raw_variances if v >= 0]
    if not valid:
        return [50.0] * len(scenes)

    v_max = max(valid) if valid else 1.0
    if v_max <= 0:
        v_max = 1.0

    scores: list[float] = []
    for v in raw_variances:
        if v < 0:
            scores.append(50.0)
        else:
            scores.append(min(100.0, (v / v_max) * 100.0))

    return scores


def _scene_audio_variance(
    ffmpeg: str,
    video_path: str,
    scene: SceneInfo,
    window_sec: float = 0.1,
    sample_rate: int = 8000,
) -> float:
    """Extract PCM audio for a scene and compute variance of windowed RMS.

    Uses 8kHz mono s16le for speed.
    """
    cmd = [
        ffmpeg,
        "-ss", f"{scene.start_time:.3f}",
        "-t", f"{scene.duration:.3f}",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-f", "s16le",
        "-v", "quiet",
        "pipe:1",
    ]
    result = subprocess.run(
        cmd, capture_output=True, timeout=30,
    )
    pcm_data = result.stdout

    if len(pcm_data) < 4:
        return 0.0

    # Parse s16le samples
    n_samples = len(pcm_data) // 2
    samples = struct.unpack(f"<{n_samples}h", pcm_data[:n_samples * 2])

    # Compute RMS in windows
    window_samples = max(1, int(window_sec * sample_rate))
    rms_values: list[float] = []

    for start in range(0, n_samples, window_samples):
        end = min(start + window_samples, n_samples)
        window = samples[start:end]
        if not window:
            continue
        sum_sq = sum(s * s for s in window)
        rms = math.sqrt(sum_sq / len(window))
        rms_values.append(rms)

    if len(rms_values) < 2:
        return 0.0

    # Variance of RMS values
    mean_rms = sum(rms_values) / len(rms_values)
    variance = sum((r - mean_rms) ** 2 for r in rms_values) / len(rms_values)
    return variance


# ── Signal 6: Position Bonus ────────────────────────────────────────────────


def _score_position(scenes: list[SceneInfo], total_duration: float) -> list[float]:
    """Score scenes based on their position in the video.

    First 10% = hook (bonus).
    Last 10% = conclusion (slight bonus).
    Middle = neutral baseline.
    """
    if total_duration <= 0:
        return [50.0] * len(scenes)

    hook_end = total_duration * 0.10
    conclusion_start = total_duration * 0.90

    scores: list[float] = []
    for scene in scenes:
        mid = (scene.start_time + scene.end_time) / 2.0

        if mid <= hook_end:
            # Hook: linear bonus, strongest at very start
            progress = mid / hook_end if hook_end > 0 else 0
            score = 100.0 - progress * 30.0  # 100→70
        elif mid >= conclusion_start:
            # Conclusion: moderate bonus
            progress = (mid - conclusion_start) / (total_duration - conclusion_start) if total_duration > conclusion_start else 0
            score = 70.0 + progress * 15.0  # 70→85
        else:
            # Middle: neutral
            score = 50.0

        scores.append(score)

    return scores
