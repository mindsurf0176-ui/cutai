"""Tests for CutAI Smart Highlights (cutai.highlight).

Tests highlight generation strategies with synthetic data.
No FFmpeg or actual video files needed.
"""

from __future__ import annotations

import pytest

from cutai.highlight import (
    _strategy_best_moments,
    _strategy_narrative,
    _strategy_shorts,
    auto_highlight_duration,
    generate_highlights,
)
from cutai.models.types import (
    CutOperation,
    EditPlan,
    EngagementReport,
    SceneEngagement,
    SceneInfo,
    VideoAnalysis,
)


# ── auto_highlight_duration ──────────────────────────────────────────────────


class TestAutoHighlightDuration:
    def test_short_video(self):
        """<5 min video → 30-60s highlight."""
        dur = auto_highlight_duration(120.0)  # 2 min
        assert 30.0 <= dur <= 60.0

    def test_medium_video(self):
        """5-15 min video → 60-180s highlight."""
        dur = auto_highlight_duration(600.0)  # 10 min
        assert 60.0 <= dur <= 180.0

    def test_long_video(self):
        """15-60 min video → 180-300s highlight."""
        dur = auto_highlight_duration(1800.0)  # 30 min
        assert 180.0 <= dur <= 300.0

    def test_very_long_video(self):
        """>60 min video → 300-600s highlight."""
        dur = auto_highlight_duration(7200.0)  # 2 hours
        assert 300.0 <= dur <= 600.0

    def test_tiny_video(self):
        """Very short video → at least 30s or proportional."""
        dur = auto_highlight_duration(10.0)
        assert dur >= 3.0  # 10 * 0.3

    def test_monotonic_increase(self):
        """Longer videos should suggest longer highlights."""
        d1 = auto_highlight_duration(60)
        d2 = auto_highlight_duration(600)
        d3 = auto_highlight_duration(3600)
        assert d1 <= d2 <= d3


# ── _strategy_best_moments ───────────────────────────────────────────────────


class TestBestMoments:
    def test_selects_highest_scored(self, sample_scenes):
        score_map = {0: 72, 1: 15, 2: 85, 3: 12, 4: 68}
        kept = _strategy_best_moments(sample_scenes, score_map, target_duration=15.0)
        kept_ids = [s.id for s in kept]
        # Should pick scenes 2 (85, 10s) then 0 (72, 5s) = 15s
        assert 2 in kept_ids
        assert 0 in kept_ids

    def test_chronological_order(self, sample_scenes):
        score_map = {0: 72, 1: 15, 2: 85, 3: 12, 4: 68}
        kept = _strategy_best_moments(sample_scenes, score_map, target_duration=25.0)
        # Should be sorted by start_time
        for i in range(len(kept) - 1):
            assert kept[i].start_time <= kept[i + 1].start_time

    def test_respects_target(self, sample_scenes):
        score_map = {0: 72, 1: 15, 2: 85, 3: 12, 4: 68}
        kept = _strategy_best_moments(sample_scenes, score_map, target_duration=10.0)
        total = sum(s.duration for s in kept)
        # May slightly exceed target (greedy), but shouldn't be way over
        assert total <= 20.0

    def test_empty_scenes(self):
        kept = _strategy_best_moments([], {}, target_duration=30.0)
        assert kept == []


# ── _strategy_narrative ──────────────────────────────────────────────────────


class TestNarrative:
    def test_keeps_first_and_last(self, sample_scenes):
        score_map = {0: 72, 1: 15, 2: 85, 3: 12, 4: 68}
        kept = _strategy_narrative(sample_scenes, score_map, target_duration=15.0)
        kept_ids = [s.id for s in kept]
        # First and last scenes should always be kept
        assert 0 in kept_ids
        assert 4 in kept_ids

    def test_removes_lowest_scored(self, sample_scenes):
        score_map = {0: 72, 1: 15, 2: 85, 3: 12, 4: 68}
        kept = _strategy_narrative(sample_scenes, score_map, target_duration=20.0)
        kept_ids = [s.id for s in kept]
        # Lowest scored (3=12, 1=15) should be removed first
        # Total is 35s, target 20s → need to remove 15s
        assert 3 not in kept_ids  # 12 score, 5s — removed first
        assert 1 not in kept_ids  # 15 score, 5s — removed second

    def test_empty_scenes(self):
        kept = _strategy_narrative([], {}, target_duration=30.0)
        assert kept == []


# ── _strategy_shorts ─────────────────────────────────────────────────────────


class TestShorts:
    def test_finds_contiguous_segment(self, sample_scenes):
        score_map = {0: 72, 1: 15, 2: 85, 3: 12, 4: 68}
        kept = _strategy_shorts(sample_scenes, score_map, target_duration=60.0)
        assert len(kept) > 0
        # Should be contiguous — verify consecutive scene IDs
        ids = [s.id for s in kept]
        for i in range(len(ids) - 1):
            assert ids[i + 1] == ids[i] + 1

    def test_picks_highest_scoring_window(self, sample_scenes):
        score_map = {0: 72, 1: 15, 2: 85, 3: 12, 4: 68}
        kept = _strategy_shorts(sample_scenes, score_map, target_duration=15.0)
        # Window [2, 3] = 85+12=97 (15s) or [0, 1] = 72+15=87 (10s)
        # or [4] = 68 (10s) — best should include scene 2
        kept_ids = [s.id for s in kept]
        assert 2 in kept_ids

    def test_empty_scenes(self):
        kept = _strategy_shorts([], {}, target_duration=60.0)
        assert kept == []


# ── generate_highlights (integration) ────────────────────────────────────────


class TestGenerateHighlights:
    def test_best_moments_strategy(self, sample_analysis, sample_engagement):
        plan = generate_highlights(
            "test.mp4",
            sample_analysis,
            sample_engagement,
            target_duration=15.0,
            style="best-moments",
        )
        assert isinstance(plan, EditPlan)
        assert len(plan.operations) > 0
        # All operations should be "keep" cuts
        for op in plan.operations:
            assert isinstance(op, CutOperation)
            assert op.action == "keep"

    def test_narrative_strategy(self, sample_analysis, sample_engagement):
        plan = generate_highlights(
            "test.mp4",
            sample_analysis,
            sample_engagement,
            target_duration=15.0,
            style="narrative",
        )
        assert isinstance(plan, EditPlan)
        assert len(plan.operations) > 0

    def test_shorts_strategy(self, sample_analysis, sample_engagement):
        plan = generate_highlights(
            "test.mp4",
            sample_analysis,
            sample_engagement,
            target_duration=60.0,
            style="shorts",
        )
        assert isinstance(plan, EditPlan)
        assert len(plan.operations) > 0

    def test_target_ratio(self, sample_analysis, sample_engagement):
        plan = generate_highlights(
            "test.mp4",
            sample_analysis,
            sample_engagement,
            target_ratio=0.5,
            style="best-moments",
        )
        assert isinstance(plan, EditPlan)
        assert plan.estimated_duration > 0

    def test_auto_duration(self, sample_analysis, sample_engagement):
        """When no target_duration given, uses target_ratio."""
        plan = generate_highlights(
            "test.mp4",
            sample_analysis,
            sample_engagement,
            style="best-moments",
        )
        assert isinstance(plan, EditPlan)
        # Default ratio is 0.2, so estimated ≈ 7s for 35s video
        assert plan.estimated_duration > 0
