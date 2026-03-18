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
