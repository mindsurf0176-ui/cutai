"""Pydantic v2 models for CutAI.

All time values are in seconds (float).
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


# ── Basic types ──────────────────────────────────────────────────────────────


class TimeRange(BaseModel):
    """A time range within a video (seconds)."""

    start: float = Field(ge=0, description="Start time in seconds")
    end: float = Field(ge=0, description="End time in seconds")

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


# ── Analysis types ───────────────────────────────────────────────────────────


class SceneInfo(BaseModel):
    """Information about a detected scene."""

    id: int = Field(description="Scene index (0-based)")
    start_time: float = Field(ge=0, description="Start time in seconds")
    end_time: float = Field(ge=0, description="End time in seconds")
    duration: float = Field(ge=0, description="Scene duration in seconds")
    has_speech: bool = Field(default=False, description="Whether speech was detected")
    is_silent: bool = Field(default=False, description="Whether the scene is mostly silent")
    thumbnail_path: str | None = Field(default=None, description="Path to thumbnail frame")
    transcript: str | None = Field(default=None, description="Transcript text for this scene")
    avg_energy: float = Field(default=0.0, description="Average audio energy (RMS)")


class TranscriptSegment(BaseModel):
    """A single segment of transcribed speech."""

    start_time: float = Field(ge=0, description="Start time in seconds")
    end_time: float = Field(ge=0, description="End time in seconds")
    text: str = Field(description="Transcribed text")
    confidence: float = Field(default=1.0, ge=0, le=1, description="Confidence score")


class QualityReport(BaseModel):
    """Quality analysis report for a video."""

    silent_segments: list[TimeRange] = Field(default_factory=list, description="Silent segments")
    audio_energy: list[float] = Field(
        default_factory=list,
        description="RMS audio energy per scene",
    )
    overall_silence_ratio: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Ratio of silence to total duration",
    )


class VideoAnalysis(BaseModel):
    """Complete analysis of a video file."""

    file_path: str = Field(description="Path to the analyzed video")
    duration: float = Field(ge=0, description="Total duration in seconds")
    fps: float = Field(ge=0, description="Frames per second")
    width: int = Field(ge=0, description="Video width in pixels")
    height: int = Field(ge=0, description="Video height in pixels")
    scenes: list[SceneInfo] = Field(default_factory=list, description="Detected scenes")
    transcript: list[TranscriptSegment] = Field(
        default_factory=list,
        description="Transcribed segments",
    )
    quality: QualityReport = Field(
        default_factory=QualityReport,
        description="Quality analysis report",
    )


# ── Edit operation types ─────────────────────────────────────────────────────


class CutOperation(BaseModel):
    """Cut/trim operation."""

    type: Literal["cut"] = "cut"
    action: Literal["keep", "remove"] = Field(description="Whether to keep or remove the segment")
    start_time: float = Field(ge=0, description="Start time in seconds")
    end_time: float = Field(ge=0, description="End time in seconds")
    reason: str = Field(default="", description="Reason for this cut")


class SubtitleOperation(BaseModel):
    """Subtitle generation operation."""

    type: Literal["subtitle"] = "subtitle"
    style: Literal["default", "emphasis", "karaoke"] = Field(default="default")
    language: str = Field(default="auto", description="Subtitle language")
    font_size: int = Field(default=24, description="Font size")
    position: Literal["bottom", "center", "top"] = Field(default="bottom")


class BGMOperation(BaseModel):
    """Background music operation (Phase 2)."""

    type: Literal["bgm"] = "bgm"
    mood: Literal["upbeat", "calm", "dramatic", "funny", "emotional"] = Field(default="calm")
    volume: float = Field(default=15.0, ge=0, le=100, description="Volume as percentage")
    fade_in: float = Field(default=2.0, ge=0, description="Fade in duration in seconds")
    fade_out: float = Field(default=2.0, ge=0, description="Fade out duration in seconds")


class ColorGradeOperation(BaseModel):
    """Color grading operation (Phase 2)."""

    type: Literal["colorgrade"] = "colorgrade"
    preset: Literal["bright", "warm", "cool", "cinematic", "vintage"] = Field(default="bright")
    intensity: float = Field(default=50.0, ge=0, le=100)


class TransitionOperation(BaseModel):
    """Transition effect between scenes (Phase 2)."""

    type: Literal["transition"] = "transition"
    style: Literal["cut", "fade", "dissolve", "wipe"] = Field(default="fade")
    duration: float = Field(default=0.5, ge=0, description="Transition duration in seconds")
    between: tuple[int, int] = Field(description="Scene IDs to transition between")


class SpeedOperation(BaseModel):
    """Speed adjustment operation (Phase 2)."""

    type: Literal["speed"] = "speed"
    factor: float = Field(default=1.0, gt=0, description="Speed multiplier (0.5=slow, 2=fast)")
    start_time: float = Field(ge=0, description="Start time in seconds")
    end_time: float = Field(ge=0, description="End time in seconds")


# ── Union type for all operations ────────────────────────────────────────────

EditOperation = Annotated[
    Union[
        CutOperation,
        SubtitleOperation,
        BGMOperation,
        ColorGradeOperation,
        TransitionOperation,
        SpeedOperation,
    ],
    Field(discriminator="type"),
]


# ── Edit plan ────────────────────────────────────────────────────────────────


class EditPlan(BaseModel):
    """Complete edit plan generated by the planner."""

    instruction: str = Field(description="Original natural language instruction")
    operations: list[
        CutOperation
        | SubtitleOperation
        | BGMOperation
        | ColorGradeOperation
        | TransitionOperation
        | SpeedOperation
    ] = Field(default_factory=list, description="Ordered list of edit operations")
    estimated_duration: float = Field(default=0.0, ge=0, description="Estimated output duration")
    summary: str = Field(default="", description="Human-readable summary of the edit plan")


# ── Edit DNA types (Phase 2A — Style Transfer) ──────────────────────────────


class RhythmDNA(BaseModel):
    """Rhythm/pacing characteristics of an editing style."""

    avg_cut_length: float = Field(default=3.0, description="Average cut length in seconds")
    cut_length_variance: float = Field(
        default=1.5, description="Standard deviation of cut lengths"
    )
    pacing_curve: Literal[
        "constant", "slow-fast-slow", "fast-slow", "slow-fast", "dynamic"
    ] = Field(default="constant")
    cuts_per_minute: float = Field(default=10.0, description="Average cuts per minute")


class TransitionDNA(BaseModel):
    """Transition usage patterns."""

    jump_cut_ratio: float = Field(
        default=0.8, ge=0, le=1, description="Ratio of hard cuts"
    )
    fade_ratio: float = Field(default=0.1, ge=0, le=1)
    dissolve_ratio: float = Field(default=0.05, ge=0, le=1)
    wipe_ratio: float = Field(default=0.05, ge=0, le=1)
    avg_transition_duration: float = Field(
        default=0.5, description="Average transition duration in seconds"
    )


class VisualDNA(BaseModel):
    """Visual style characteristics."""

    avg_brightness: float = Field(
        default=0.0, description="Average brightness offset (-1 to 1)"
    )
    avg_saturation: float = Field(
        default=1.0, description="Average saturation multiplier"
    )
    avg_contrast: float = Field(
        default=1.0, description="Average contrast multiplier"
    )
    color_temperature: Literal["neutral", "warm", "cool"] = Field(default="neutral")


class AudioDNA(BaseModel):
    """Audio mixing characteristics."""

    has_bgm: bool = Field(
        default=False, description="Whether BGM is typically present"
    )
    bgm_volume_ratio: float = Field(
        default=0.15, ge=0, le=1, description="BGM volume relative to speech"
    )
    silence_tolerance: float = Field(
        default=1.0, description="Max silence before cut (seconds)"
    )
    speech_ratio: float = Field(
        default=0.6, ge=0, le=1, description="Ratio of video with speech"
    )


class SubtitleDNA(BaseModel):
    """Subtitle style characteristics."""

    has_subtitles: bool = Field(default=False)
    position: Literal["bottom", "center", "top"] = Field(default="bottom")
    font_size_category: Literal["small", "medium", "large"] = Field(default="medium")


class EditDNA(BaseModel):
    """Complete editing style fingerprint — the 'DNA' of a video's editing style."""

    name: str = Field(default="unnamed", description="Style name")
    description: str = Field(default="", description="Style description")
    source: str = Field(default="", description="Source video/channel")
    rhythm: RhythmDNA = Field(default_factory=RhythmDNA)
    transitions: TransitionDNA = Field(default_factory=TransitionDNA)
    visual: VisualDNA = Field(default_factory=VisualDNA)
    audio: AudioDNA = Field(default_factory=AudioDNA)
    subtitle: SubtitleDNA = Field(default_factory=SubtitleDNA)


# ── Engagement types (Phase 3A) ─────────────────────────────────────────────


class SceneEngagement(BaseModel):
    """Engagement analysis for a single scene."""

    scene_id: int = Field(description="Scene index")
    score: float = Field(ge=0, le=100, description="Overall engagement score 0-100")
    audio_energy_score: float = Field(default=0, ge=0, le=100)
    speech_density_score: float = Field(default=0, ge=0, le=100)
    visual_activity_score: float = Field(default=0, ge=0, le=100)
    duration_fit_score: float = Field(default=0, ge=0, le=100)
    audio_variety_score: float = Field(default=0, ge=0, le=100)
    position_score: float = Field(default=0, ge=0, le=100)
    label: Literal["high", "medium", "low"] = Field(
        default="medium", description="Engagement tier"
    )


class EngagementReport(BaseModel):
    """Complete engagement analysis for a video."""

    scenes: list[SceneEngagement] = Field(default_factory=list)
    avg_score: float = Field(default=0, ge=0, le=100)
    high_count: int = Field(default=0, description="Number of high-engagement scenes")
    low_count: int = Field(default=0, description="Number of low-engagement scenes")


# ── Personal Learning types (Phase 3B) ──────────────────────────────────────


class InstructionMemory(BaseModel):
    """A remembered instruction-result pair for few-shot learning."""

    instruction: str = Field(description="Original editing instruction")
    operations_summary: list[str] = Field(
        default_factory=list,
        description="Summary of operations (e.g. 'cut:remove 3 scenes')",
    )
    was_accepted: bool = Field(default=True, description="Did user render or undo?")
    timestamp: str = Field(default="", description="ISO 8601 datetime")


class FeedbackEntry(BaseModel):
    """User feedback on an edit result."""

    instruction: str = Field(description="The instruction that was evaluated")
    feedback: Literal["good", "bad", "adjusted"] = Field(description="Feedback type")
    adjustment: str | None = Field(default=None, description="What was changed")
    timestamp: str = Field(default="", description="ISO 8601 datetime")


class UserPreferences(BaseModel):
    """Learned user preferences from editing history."""

    preferred_style: str | None = Field(
        default=None, description="Most used style preset"
    )
    preferred_subtitle_position: str = Field(
        default="bottom", description="Preferred subtitle position"
    )
    preferred_color_preset: str | None = Field(
        default=None, description="Preferred color grading preset"
    )
    preferred_bgm_mood: str | None = Field(
        default=None, description="Preferred BGM mood"
    )
    avg_keep_ratio: float = Field(
        default=0.7,
        ge=0,
        le=1,
        description="How much of video user typically keeps",
    )
    instruction_history: list[InstructionMemory] = Field(
        default_factory=list, description="Few-shot instruction examples"
    )
    feedback_history: list[FeedbackEntry] = Field(
        default_factory=list, description="User feedback entries"
    )
