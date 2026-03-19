"""Tests for CutAI Personal Learning (cutai.learning).

Tests preference loading, saving, instruction recording, feedback,
and few-shot retrieval with synthetic data.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cutai.learning import (
    get_few_shot_examples,
    load_preferences,
    record_feedback,
    record_instruction,
    save_preferences,
    suggest_defaults,
)
from cutai.models.types import (
    CutOperation,
    EditPlan,
    FeedbackEntry,
    InstructionMemory,
    SubtitleOperation,
    UserPreferences,
)


# ── Load / Save ──────────────────────────────────────────────────────────────


class TestLoadSave:
    def test_load_missing_file(self):
        """Loading from a nonexistent path returns defaults."""
        prefs = load_preferences("/nonexistent/path/learning.json")
        assert isinstance(prefs, UserPreferences)
        assert prefs.preferred_style is None
        assert prefs.instruction_history == []

    def test_save_load_roundtrip(self):
        """Saving and loading preferences should preserve data."""
        prefs = UserPreferences(
            preferred_style="cinematic",
            preferred_subtitle_position="center",
            preferred_color_preset="warm",
            preferred_bgm_mood="upbeat",
            avg_keep_ratio=0.6,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "learning.json"
            save_preferences(prefs, path)
            assert path.exists()

            loaded = load_preferences(path)
            assert loaded.preferred_style == "cinematic"
            assert loaded.preferred_subtitle_position == "center"
            assert loaded.preferred_color_preset == "warm"
            assert loaded.preferred_bgm_mood == "upbeat"
            assert loaded.avg_keep_ratio == 0.6

    def test_load_corrupt_file(self):
        """Loading a corrupt file returns defaults."""
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("not valid json {{{")
            f.flush()
            prefs = load_preferences(f.name)
            assert isinstance(prefs, UserPreferences)

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "deep" / "nested" / "learning.json"
            prefs = UserPreferences()
            save_preferences(prefs, path)
            assert path.exists()

    def test_roundtrip_with_history(self, sample_preferences):
        """Preferences with instruction and feedback history roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "learning.json"
            save_preferences(sample_preferences, path)
            loaded = load_preferences(path)
            assert len(loaded.instruction_history) == 2
            assert len(loaded.feedback_history) == 1
            assert loaded.instruction_history[0].instruction == "remove silence add subtitles"


# ── Record Instruction ───────────────────────────────────────────────────────


class TestRecordInstruction:
    def test_records_instruction(self):
        prefs = UserPreferences()
        plan = EditPlan(
            instruction="remove silence",
            operations=[
                CutOperation(action="remove", start_time=5.0, end_time=10.0),
            ],
        )
        record_instruction(prefs, "remove silence", plan, accepted=True)
        assert len(prefs.instruction_history) == 1
        assert prefs.instruction_history[0].instruction == "remove silence"
        assert prefs.instruction_history[0].was_accepted is True

    def test_fifo_limit(self):
        """Should keep at most MAX_INSTRUCTION_HISTORY entries."""
        prefs = UserPreferences()
        plan = EditPlan(instruction="test", operations=[])
        for i in range(60):
            record_instruction(prefs, f"instruction {i}", plan)
        # MAX_INSTRUCTION_HISTORY is 50
        assert len(prefs.instruction_history) <= 50
        # Most recent should be preserved
        assert prefs.instruction_history[-1].instruction == "instruction 59"

    def test_records_operations_summary(self):
        prefs = UserPreferences()
        plan = EditPlan(
            instruction="test",
            operations=[
                CutOperation(action="remove", start_time=0, end_time=5),
                SubtitleOperation(),
            ],
        )
        record_instruction(prefs, "test", plan)
        assert len(prefs.instruction_history[0].operations_summary) > 0

    def test_rejected_instruction(self):
        prefs = UserPreferences()
        plan = EditPlan(instruction="bad edit", operations=[])
        record_instruction(prefs, "bad edit", plan, accepted=False)
        assert prefs.instruction_history[0].was_accepted is False


# ── Record Feedback ──────────────────────────────────────────────────────────


class TestRecordFeedback:
    def test_good_feedback(self):
        prefs = UserPreferences()
        record_feedback(prefs, "remove silence", "good")
        assert len(prefs.feedback_history) == 1
        assert prefs.feedback_history[0].feedback == "good"

    def test_bad_feedback(self):
        prefs = UserPreferences()
        record_feedback(prefs, "add bgm", "bad")
        assert prefs.feedback_history[0].feedback == "bad"

    def test_adjusted_feedback(self):
        prefs = UserPreferences()
        record_feedback(
            prefs,
            "add subtitles",
            "adjusted",
            adjustment="moved to center",
        )
        assert prefs.feedback_history[0].feedback == "adjusted"
        assert prefs.feedback_history[0].adjustment == "moved to center"

    def test_invalid_feedback_defaults_good(self):
        prefs = UserPreferences()
        record_feedback(prefs, "test", "invalid_value")
        assert prefs.feedback_history[0].feedback == "good"


# ── Few-shot Examples ────────────────────────────────────────────────────────


class TestFewShotExamples:
    def test_returns_relevant_examples(self, sample_preferences):
        examples = get_few_shot_examples(
            sample_preferences, "remove silence from video", max_examples=3
        )
        assert len(examples) > 0
        # "remove silence add subtitles" should match "remove silence from video"
        assert any("silence" in e.instruction for e in examples)

    def test_empty_history(self):
        prefs = UserPreferences()
        examples = get_few_shot_examples(prefs, "remove silence")
        assert examples == []

    def test_max_examples_limit(self):
        prefs = UserPreferences(
            instruction_history=[
                InstructionMemory(
                    instruction=f"instruction with word{i}",
                    operations_summary=[],
                    was_accepted=True,
                )
                for i in range(10)
            ]
        )
        examples = get_few_shot_examples(prefs, "instruction with word1", max_examples=2)
        assert len(examples) <= 2

    def test_excludes_rejected(self):
        prefs = UserPreferences(
            instruction_history=[
                InstructionMemory(
                    instruction="remove silence",
                    operations_summary=["cut:remove"],
                    was_accepted=False,
                ),
            ]
        )
        examples = get_few_shot_examples(prefs, "remove silence")
        assert len(examples) == 0

    def test_no_overlap(self):
        prefs = UserPreferences(
            instruction_history=[
                InstructionMemory(
                    instruction="completely different words",
                    operations_summary=[],
                    was_accepted=True,
                ),
            ]
        )
        examples = get_few_shot_examples(prefs, "add subtitles")
        assert len(examples) == 0


# ── Suggest Defaults ─────────────────────────────────────────────────────────


class TestSuggestDefaults:
    def test_from_preferences(self, sample_preferences):
        defaults = suggest_defaults(sample_preferences)
        assert defaults["color_preset"] == "warm"
        assert defaults["subtitle_position"] == "bottom"
        assert defaults["keep_ratio"] == 0.65

    def test_empty_preferences(self):
        prefs = UserPreferences()
        defaults = suggest_defaults(prefs)
        assert "subtitle_position" in defaults
        assert "keep_ratio" in defaults

    def test_history_overrides(self):
        """If instruction history has a strong pattern, it should appear."""
        prefs = UserPreferences(
            instruction_history=[
                InstructionMemory(
                    instruction="test",
                    operations_summary=["colorgrade:cinematic"],
                    was_accepted=True,
                ),
                InstructionMemory(
                    instruction="test2",
                    operations_summary=["colorgrade:cinematic"],
                    was_accepted=True,
                ),
                InstructionMemory(
                    instruction="test3",
                    operations_summary=["colorgrade:warm"],
                    was_accepted=True,
                ),
            ]
        )
        defaults = suggest_defaults(prefs)
        assert defaults.get("color_preset") == "cinematic"
