"""Tests for CutAI Pydantic models (cutai.models.types).

Validates constructors, defaults, field constraints, and basic behaviour
for all major types. No FFmpeg or video files needed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cutai.models.types import (
    AudioDNA,
    BGMOperation,
    ColorGradeOperation,
    CutOperation,
    EditDNA,
    EditPlan,
    EngagementReport,
    FeedbackEntry,
    InstructionMemory,
    QualityReport,
    RhythmDNA,
    SceneEngagement,
    SceneInfo,
    SpeedOperation,
    SubtitleDNA,
    SubtitleOperation,
    TimeRange,
    TranscriptSegment,
    TransitionDNA,
    TransitionOperation,
    UserPreferences,
    VideoAnalysis,
    VisualDNA,
)


# ── TimeRange ────────────────────────────────────────────────────────────────


class TestTimeRange:
    def test_basic_creation(self):
        tr = TimeRange(start=1.0, end=5.0)
        assert tr.start == 1.0
        assert tr.end == 5.0

    def test_duration_property(self):
        tr = TimeRange(start=2.0, end=7.5)
        assert tr.duration == 5.5

    def test_zero_duration(self):
        tr = TimeRange(start=3.0, end=3.0)
        assert tr.duration == 0.0

    def test_negative_start_rejected(self):
        with pytest.raises(ValidationError):
            TimeRange(start=-1.0, end=5.0)


# ── SceneInfo ────────────────────────────────────────────────────────────────


class TestSceneInfo:
    def test_basic_creation(self):
        scene = SceneInfo(id=0, start_time=0, end_time=10, duration=10)
        assert scene.id == 0
        assert scene.duration == 10.0
        assert scene.has_speech is False
        assert scene.is_silent is False

    def test_with_all_fields(self):
        scene = SceneInfo(
            id=3,
            start_time=15.0,
            end_time=25.0,
            duration=10.0,
            has_speech=True,
            is_silent=False,
            thumbnail_path="/tmp/thumb.jpg",
            transcript="Hello world",
            avg_energy=-20.5,
        )
        assert scene.has_speech is True
        assert scene.transcript == "Hello world"
        assert scene.avg_energy == -20.5

    def test_defaults(self):
        scene = SceneInfo(id=0, start_time=0, end_time=1, duration=1)
        assert scene.thumbnail_path is None
        assert scene.transcript is None
        assert scene.avg_energy == 0.0


# ── TranscriptSegment ────────────────────────────────────────────────────────


class TestTranscriptSegment:
    def test_basic_creation(self):
        seg = TranscriptSegment(start_time=1.0, end_time=3.0, text="Hello")
        assert seg.text == "Hello"
        assert seg.confidence == 1.0

    def test_confidence_range(self):
        seg = TranscriptSegment(start_time=0, end_time=1, text="test", confidence=0.85)
        assert seg.confidence == 0.85

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            TranscriptSegment(start_time=0, end_time=1, text="test", confidence=1.5)


# ── QualityReport ────────────────────────────────────────────────────────────


class TestQualityReport:
    def test_defaults(self):
        qr = QualityReport()
        assert qr.silent_segments == []
        assert qr.audio_energy == []
        assert qr.overall_silence_ratio == 0.0

    def test_with_data(self):
        qr = QualityReport(
            silent_segments=[TimeRange(start=5, end=10)],
            audio_energy=[-30.0, -20.0],
            overall_silence_ratio=0.25,
        )
        assert len(qr.silent_segments) == 1
        assert qr.overall_silence_ratio == 0.25


# ── VideoAnalysis ────────────────────────────────────────────────────────────


class TestVideoAnalysis:
    def test_basic_creation(self):
        va = VideoAnalysis(
            file_path="test.mp4",
            duration=60.0,
            fps=30.0,
            width=1920,
            height=1080,
        )
        assert va.file_path == "test.mp4"
        assert va.scenes == []
        assert va.transcript == []

    def test_from_fixture(self, sample_analysis):
        assert sample_analysis.duration == 35.0
        assert len(sample_analysis.scenes) == 5
        assert len(sample_analysis.transcript) == 3
        assert len(sample_analysis.quality.silent_segments) == 2


# ── Edit Operations ──────────────────────────────────────────────────────────


class TestCutOperation:
    def test_remove(self):
        op = CutOperation(action="remove", start_time=5.0, end_time=10.0)
        assert op.type == "cut"
        assert op.action == "remove"

    def test_keep(self):
        op = CutOperation(action="keep", start_time=0.0, end_time=5.0, reason="Important scene")
        assert op.action == "keep"
        assert op.reason == "Important scene"

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            CutOperation(action="delete", start_time=0, end_time=1)


class TestSubtitleOperation:
    def test_defaults(self):
        op = SubtitleOperation()
        assert op.type == "subtitle"
        assert op.style == "default"
        assert op.language == "auto"
        assert op.font_size == 24
        assert op.position == "bottom"

    def test_custom_values(self):
        op = SubtitleOperation(style="emphasis", position="center", font_size=32)
        assert op.style == "emphasis"
        assert op.position == "center"


class TestBGMOperation:
    def test_defaults(self):
        op = BGMOperation()
        assert op.type == "bgm"
        assert op.mood == "calm"
        assert op.volume == 15.0
        assert op.fade_in == 2.0
        assert op.fade_out == 2.0

    def test_volume_range(self):
        with pytest.raises(ValidationError):
            BGMOperation(volume=150.0)


class TestColorGradeOperation:
    def test_defaults(self):
        op = ColorGradeOperation()
        assert op.type == "colorgrade"
        assert op.preset == "bright"
        assert op.intensity == 50.0

    def test_all_presets(self):
        for preset in ("bright", "warm", "cool", "cinematic", "vintage"):
            op = ColorGradeOperation(preset=preset)
            assert op.preset == preset


class TestTransitionOperation:
    def test_creation(self):
        op = TransitionOperation(style="fade", duration=0.5, between=(0, 1))
        assert op.type == "transition"
        assert op.between == (0, 1)

    def test_styles(self):
        for style in ("cut", "fade", "dissolve", "wipe"):
            op = TransitionOperation(style=style, between=(0, 1))
            assert op.style == style


class TestSpeedOperation:
    def test_creation(self):
        op = SpeedOperation(factor=2.0, start_time=0, end_time=10)
        assert op.type == "speed"
        assert op.factor == 2.0

    def test_zero_factor_rejected(self):
        with pytest.raises(ValidationError):
            SpeedOperation(factor=0.0, start_time=0, end_time=10)


# ── EditPlan ─────────────────────────────────────────────────────────────────


class TestEditPlan:
    def test_empty_plan(self):
        plan = EditPlan(instruction="test")
        assert plan.instruction == "test"
        assert plan.operations == []
        assert plan.estimated_duration == 0.0
        assert plan.summary == ""

    def test_plan_with_operations(self):
        plan = EditPlan(
            instruction="remove silence and add subtitles",
            operations=[
                CutOperation(action="remove", start_time=5.0, end_time=10.0),
                SubtitleOperation(),
            ],
            estimated_duration=25.0,
            summary="Remove silence; Add subtitles",
        )
        assert len(plan.operations) == 2
        assert plan.estimated_duration == 25.0


# ── EditDNA ──────────────────────────────────────────────────────────────────


class TestEditDNA:
    def test_defaults(self):
        dna = EditDNA()
        assert dna.name == "unnamed"
        assert dna.rhythm.avg_cut_length == 3.0
        assert dna.rhythm.cuts_per_minute == 10.0
        assert dna.transitions.jump_cut_ratio == 0.8
        assert dna.visual.color_temperature == "neutral"
        assert dna.audio.has_bgm is False
        assert dna.subtitle.has_subtitles is False

    def test_with_name(self):
        dna = EditDNA(name="cinematic", description="Cinematic style")
        assert dna.name == "cinematic"

    def test_rhythm_dna_defaults(self):
        r = RhythmDNA()
        assert r.avg_cut_length == 3.0
        assert r.pacing_curve == "constant"

    def test_transition_dna_defaults(self):
        t = TransitionDNA()
        assert t.jump_cut_ratio == 0.8
        assert t.fade_ratio == 0.1

    def test_visual_dna_defaults(self):
        v = VisualDNA()
        assert v.avg_brightness == 0.0
        assert v.avg_saturation == 1.0
        assert v.color_temperature == "neutral"

    def test_audio_dna_defaults(self):
        a = AudioDNA()
        assert a.has_bgm is False
        assert a.bgm_volume_ratio == 0.15

    def test_subtitle_dna_defaults(self):
        s = SubtitleDNA()
        assert s.has_subtitles is False
        assert s.position == "bottom"
        assert s.font_size_category == "medium"


# ── Engagement types ─────────────────────────────────────────────────────────


class TestSceneEngagement:
    def test_creation(self):
        se = SceneEngagement(scene_id=0, score=75.0)
        assert se.scene_id == 0
        assert se.score == 75.0
        assert se.label == "medium"

    def test_score_range(self):
        with pytest.raises(ValidationError):
            SceneEngagement(scene_id=0, score=150.0)

    def test_labels(self):
        for label in ("high", "medium", "low"):
            se = SceneEngagement(scene_id=0, score=50, label=label)
            assert se.label == label


class TestEngagementReport:
    def test_defaults(self):
        er = EngagementReport()
        assert er.scenes == []
        assert er.avg_score == 0
        assert er.high_count == 0

    def test_from_fixture(self, sample_engagement):
        assert len(sample_engagement.scenes) == 5
        assert sample_engagement.high_count == 3
        assert sample_engagement.low_count == 2


# ── Learning types ───────────────────────────────────────────────────────────


class TestInstructionMemory:
    def test_creation(self):
        mem = InstructionMemory(instruction="remove silence")
        assert mem.instruction == "remove silence"
        assert mem.was_accepted is True
        assert mem.operations_summary == []


class TestFeedbackEntry:
    def test_creation(self):
        fb = FeedbackEntry(instruction="test", feedback="good")
        assert fb.feedback == "good"
        assert fb.adjustment is None

    def test_adjusted(self):
        fb = FeedbackEntry(
            instruction="add subtitles",
            feedback="adjusted",
            adjustment="changed position to center",
        )
        assert fb.adjustment == "changed position to center"


class TestUserPreferences:
    def test_defaults(self):
        prefs = UserPreferences()
        assert prefs.preferred_style is None
        assert prefs.preferred_subtitle_position == "bottom"
        assert prefs.avg_keep_ratio == 0.7
        assert prefs.instruction_history == []
        assert prefs.feedback_history == []

    def test_from_fixture(self, sample_preferences):
        assert sample_preferences.preferred_style == "cinematic"
        assert len(sample_preferences.instruction_history) == 2
        assert len(sample_preferences.feedback_history) == 1
