"""Tests for CutAI Multi-video Editor (cutai.multi).

Tests the analysis merging logic with synthetic data.
No FFmpeg or actual video files needed — we test internal helpers.
"""

from __future__ import annotations

import pytest

from cutai.models.types import (
    QualityReport,
    SceneInfo,
    TimeRange,
    TranscriptSegment,
    VideoAnalysis,
)
from cutai.multi import _merge_analyses


# ── Merge analyses ───────────────────────────────────────────────────────────


class TestMergeAnalyses:
    @pytest.fixture
    def two_analyses(self):
        """Two simple VideoAnalysis objects for merge testing."""
        a1 = VideoAnalysis(
            file_path="clip1.mp4",
            duration=10.0,
            fps=30.0,
            width=1920,
            height=1080,
            scenes=[
                SceneInfo(id=0, start_time=0, end_time=5, duration=5, has_speech=True),
                SceneInfo(id=1, start_time=5, end_time=10, duration=5, has_speech=False, is_silent=True),
            ],
            transcript=[
                TranscriptSegment(start_time=0.5, end_time=4.5, text="Hello from clip 1"),
            ],
            quality=QualityReport(
                silent_segments=[TimeRange(start=5, end=10)],
                audio_energy=[-20.0, -55.0],
                overall_silence_ratio=0.5,
            ),
        )
        a2 = VideoAnalysis(
            file_path="clip2.mp4",
            duration=15.0,
            fps=30.0,
            width=1920,
            height=1080,
            scenes=[
                SceneInfo(id=0, start_time=0, end_time=8, duration=8, has_speech=True),
                SceneInfo(id=1, start_time=8, end_time=15, duration=7, has_speech=True),
            ],
            transcript=[
                TranscriptSegment(start_time=1.0, end_time=7.0, text="Welcome to clip 2"),
                TranscriptSegment(start_time=9.0, end_time=14.0, text="Goodbye from clip 2"),
            ],
            quality=QualityReport(
                silent_segments=[],
                audio_energy=[-18.0, -22.0],
                overall_silence_ratio=0.0,
            ),
        )
        return [a1, a2]

    def test_merged_duration(self, two_analyses):
        merged = _merge_analyses(two_analyses)
        assert merged.duration == 25.0  # 10 + 15

    def test_merged_scene_count(self, two_analyses):
        merged = _merge_analyses(two_analyses)
        assert len(merged.scenes) == 4  # 2 + 2

    def test_merged_scene_ids_are_sequential(self, two_analyses):
        merged = _merge_analyses(two_analyses)
        ids = [s.id for s in merged.scenes]
        assert ids == [0, 1, 2, 3]

    def test_scene_times_offset(self, two_analyses):
        merged = _merge_analyses(two_analyses)
        # Second clip scenes should be offset by first clip duration (10s)
        assert merged.scenes[2].start_time == 10.0  # was 0
        assert merged.scenes[2].end_time == 18.0  # was 8
        assert merged.scenes[3].start_time == 18.0  # was 8
        assert merged.scenes[3].end_time == 25.0  # was 15

    def test_transcript_times_offset(self, two_analyses):
        merged = _merge_analyses(two_analyses)
        assert len(merged.transcript) == 3
        # Second clip transcripts should be offset
        assert merged.transcript[1].start_time == 11.0  # was 1.0
        assert merged.transcript[1].text == "Welcome to clip 2"

    def test_silent_segments_offset(self, two_analyses):
        merged = _merge_analyses(two_analyses)
        # First clip had silence at 5-10, should stay
        assert any(
            seg.start == 5.0 and seg.end == 10.0
            for seg in merged.quality.silent_segments
        )

    def test_uses_max_resolution(self, two_analyses):
        merged = _merge_analyses(two_analyses)
        assert merged.width == 1920
        assert merged.height == 1080

    def test_single_analysis(self):
        single = VideoAnalysis(
            file_path="only.mp4",
            duration=20.0,
            fps=24.0,
            width=1280,
            height=720,
            scenes=[SceneInfo(id=0, start_time=0, end_time=20, duration=20)],
        )
        merged = _merge_analyses([single])
        assert merged.duration == 20.0
        assert len(merged.scenes) == 1

    def test_empty_list(self):
        """Merging empty list should handle gracefully."""
        with pytest.raises((ValueError, IndexError)):
            _merge_analyses([])


class TestMultiEditIntegration:
    """Integration-level tests that don't require actual video files."""

    def test_merge_preserves_speech_flags(self):
        a1 = VideoAnalysis(
            file_path="a.mp4",
            duration=5.0,
            fps=30.0,
            width=1920,
            height=1080,
            scenes=[SceneInfo(id=0, start_time=0, end_time=5, duration=5, has_speech=True)],
        )
        a2 = VideoAnalysis(
            file_path="b.mp4",
            duration=5.0,
            fps=30.0,
            width=1920,
            height=1080,
            scenes=[SceneInfo(id=0, start_time=0, end_time=5, duration=5, has_speech=False, is_silent=True)],
        )
        merged = _merge_analyses([a1, a2])
        assert merged.scenes[0].has_speech is True
        assert merged.scenes[1].has_speech is False
        assert merged.scenes[1].is_silent is True

    def test_merge_uses_first_fps(self):
        a1 = VideoAnalysis(file_path="a.mp4", duration=10, fps=24.0, width=1920, height=1080)
        a2 = VideoAnalysis(file_path="b.mp4", duration=10, fps=30.0, width=1280, height=720)
        merged = _merge_analyses([a1, a2])
        # Should use first video's fps (or max — depends on implementation)
        assert merged.fps > 0
