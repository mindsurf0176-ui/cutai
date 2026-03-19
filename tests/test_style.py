"""Tests for CutAI Style Transfer (cutai.style).

Tests style I/O, applier, and preset loading with synthetic data.
No FFmpeg or actual video files needed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from cutai.models.types import (
    AudioDNA,
    BGMOperation,
    ColorGradeOperation,
    CutOperation,
    EditDNA,
    EditPlan,
    RhythmDNA,
    SubtitleDNA,
    SubtitleOperation,
    TransitionDNA,
    TransitionOperation,
    VisualDNA,
)
from cutai.style.io import load_style, save_style


# ── Style I/O ────────────────────────────────────────────────────────────────


class TestStyleIO:
    def test_save_load_roundtrip(self, sample_edit_dna):
        """Save EditDNA to YAML and load it back — should be identical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test_style.yaml")
            saved_path = save_style(sample_edit_dna, path)
            assert Path(saved_path).exists()

            loaded = load_style(saved_path)
            assert loaded.name == sample_edit_dna.name
            assert loaded.description == sample_edit_dna.description
            assert loaded.rhythm.avg_cut_length == sample_edit_dna.rhythm.avg_cut_length
            assert loaded.transitions.jump_cut_ratio == sample_edit_dna.transitions.jump_cut_ratio
            assert loaded.visual.color_temperature == sample_edit_dna.visual.color_temperature
            assert loaded.audio.has_bgm == sample_edit_dna.audio.has_bgm
            assert loaded.subtitle.has_subtitles == sample_edit_dna.subtitle.has_subtitles

    def test_save_load_cinematic(self, cinematic_dna):
        """Cinematic style with non-default values roundtrips correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "cinematic.yaml")
            save_style(cinematic_dna, path)
            loaded = load_style(path)

            assert loaded.name == "cinematic"
            assert loaded.rhythm.avg_cut_length == 6.0
            assert loaded.rhythm.pacing_curve == "slow-fast-slow"
            assert loaded.transitions.fade_ratio == 0.3
            assert loaded.visual.avg_saturation == 0.8
            assert loaded.visual.color_temperature == "cool"
            assert loaded.audio.has_bgm is True
            assert loaded.audio.bgm_volume_ratio == 0.2

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_style("/nonexistent/path/style.yaml")

    def test_load_invalid_yaml_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("not a mapping\n- just a list\n")
            f.flush()
            with pytest.raises(ValueError, match="Expected a YAML mapping"):
                load_style(f.name)

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "deep" / "nested" / "style.yaml")
            dna = EditDNA(name="nested-test")
            saved = save_style(dna, path)
            assert Path(saved).exists()

    def test_yaml_is_human_readable(self, cinematic_dna):
        """Saved YAML should be human-readable (not flow style)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "readable.yaml")
            save_style(cinematic_dna, path)
            content = Path(path).read_text()
            # Should contain multi-line keys, not inline dicts
            assert "name:" in content
            assert "rhythm:" in content
            assert "avg_cut_length:" in content


# ── Preset Loading ───────────────────────────────────────────────────────────


class TestPresetLoading:
    def test_cinematic_preset_exists(self):
        preset_path = Path(__file__).parent.parent / "cutai" / "style" / "presets" / "cinematic.yaml"
        assert preset_path.exists(), f"Cinematic preset not found at {preset_path}"

    def test_load_cinematic_preset(self):
        preset_path = Path(__file__).parent.parent / "cutai" / "style" / "presets" / "cinematic.yaml"
        dna = load_style(str(preset_path))
        assert dna.name == "cinematic"
        assert dna.rhythm.avg_cut_length == 6.0
        assert dna.audio.has_bgm is True

    def test_vlog_casual_preset_exists(self):
        preset_path = Path(__file__).parent.parent / "cutai" / "style" / "presets" / "vlog-casual.yaml"
        assert preset_path.exists(), f"Vlog-casual preset not found at {preset_path}"

    def test_load_vlog_casual_preset(self):
        preset_path = Path(__file__).parent.parent / "cutai" / "style" / "presets" / "vlog-casual.yaml"
        dna = load_style(str(preset_path))
        assert dna.name is not None
        assert isinstance(dna.rhythm.avg_cut_length, float)


# ── Style Applier ────────────────────────────────────────────────────────────


class TestApplyStyle:
    def test_apply_cinematic_style(self, sample_analysis, cinematic_dna):
        from cutai.style.applier import apply_style

        plan = apply_style(sample_analysis, cinematic_dna)
        assert isinstance(plan, EditPlan)
        assert len(plan.operations) > 0

    def test_apply_generates_color_grade(self, sample_analysis, cinematic_dna):
        """Cinematic DNA (cool, desaturated) should produce a color grade op."""
        from cutai.style.applier import apply_style

        plan = apply_style(sample_analysis, cinematic_dna)
        color_ops = [op for op in plan.operations if isinstance(op, ColorGradeOperation)]
        assert len(color_ops) >= 1

    def test_apply_generates_bgm(self, sample_analysis, cinematic_dna):
        """Cinematic DNA (has_bgm=True) should produce a BGM op."""
        from cutai.style.applier import apply_style

        plan = apply_style(sample_analysis, cinematic_dna)
        bgm_ops = [op for op in plan.operations if isinstance(op, BGMOperation)]
        assert len(bgm_ops) == 1

    def test_apply_no_subtitles_when_disabled(self, sample_analysis, cinematic_dna):
        """Cinematic DNA (has_subtitles=False) should not add subtitles."""
        from cutai.style.applier import apply_style

        plan = apply_style(sample_analysis, cinematic_dna)
        sub_ops = [op for op in plan.operations if isinstance(op, SubtitleOperation)]
        assert len(sub_ops) == 0

    def test_apply_with_subtitles(self, sample_analysis):
        """Style with has_subtitles=True should add subtitles."""
        from cutai.style.applier import apply_style

        dna = EditDNA(
            name="sub-style",
            subtitle=SubtitleDNA(has_subtitles=True, position="center"),
        )
        plan = apply_style(sample_analysis, dna)
        sub_ops = [op for op in plan.operations if isinstance(op, SubtitleOperation)]
        assert len(sub_ops) == 1
        assert sub_ops[0].position == "center"

    def test_apply_default_dna(self, sample_analysis):
        """Applying default EditDNA should produce a valid plan."""
        from cutai.style.applier import apply_style

        dna = EditDNA()
        plan = apply_style(sample_analysis, dna)
        assert isinstance(plan, EditPlan)
