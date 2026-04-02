"""Tests for EDITSTYLE.md parser and converter."""

import pytest
from cutai.models.types import EditDNA
from cutai.style.editstyle_parser import parse_editstyle_text, EditStyleResult
from cutai.style.editstyle_converter import editdna_to_markdown


# ── Fixtures ─────────────────────────────────────────────────────────────────


FULL_EXAMPLE = """\
# Cinematic Style

> Source: https://youtube.com/example
> Author: Jane Doe
> CutAI EDITSTYLE v1

## Rhythm
- **Pacing**: medium (10 cuts/min)
- **Average cut length**: 5s (±1.5s)
- **Cut variance**: ±1.5s
- **Pacing curve**: slow-fast
- **Silence tolerance**: 1.0s

## Transitions
- **Jump cut**: 80% — dynamic storytelling
- **Fade**: 10%
- **Dissolve**: 5%
- **Wipe**: 5%
- **Transition duration**: 0.4s

## Visual
- **Color temperature**: warm — cozy and engaging vibe
- **Saturation**: 1.2
- **Contrast**: 1.1
- **Brightness**: 0.1

## Audio
- **BGM**: yes, cinematic / dramatic, 20% volume
- **Speech ratio**: 70%
- **Fade in/out**: 3s

## Subtitles
- **Enabled**: yes
- **Position**: bottom
- **Size**: medium
- **Language**: en

## Patterns
- **Cold open**: yes — start with a dramatic hook
- **Intro**: 5-10s title sequence
- **Outro**: fade to black

## Rules
- ✅ Always include subtitles
- ❌ No scene longer than 20 seconds
- ✅ Maintain continuity in transitions
"""

MINIMAL_EXAMPLE = """\
# Minimal Style

> Source: custom
> Author: Anonymous
> CutAI EDITSTYLE v1
"""


# ── Core parsing tests ───────────────────────────────────────────────────────


class TestFullParsing:
    def test_name(self):
        r = parse_editstyle_text(FULL_EXAMPLE)
        assert r.dna.name == "Cinematic Style"

    def test_source_and_author(self):
        r = parse_editstyle_text(FULL_EXAMPLE)
        assert r.dna.source == "https://youtube.com/example"
        assert "Jane Doe" in r.dna.description

    def test_rhythm(self):
        r = parse_editstyle_text(FULL_EXAMPLE)
        rhythm = r.dna.rhythm
        assert rhythm.cuts_per_minute == 10.0
        assert rhythm.avg_cut_length == 5.0
        assert rhythm.cut_length_variance == 1.5
        assert rhythm.pacing_curve == "slow-fast"

    def test_transitions(self):
        r = parse_editstyle_text(FULL_EXAMPLE)
        t = r.dna.transitions
        assert t.jump_cut_ratio == pytest.approx(0.80)
        assert t.fade_ratio == pytest.approx(0.10)
        assert t.dissolve_ratio == pytest.approx(0.05)
        assert t.wipe_ratio == pytest.approx(0.05)
        assert t.avg_transition_duration == 0.4

    def test_visual(self):
        r = parse_editstyle_text(FULL_EXAMPLE)
        v = r.dna.visual
        assert v.color_temperature == "warm"
        assert v.avg_saturation == 1.2
        assert v.avg_contrast == 1.1
        assert v.avg_brightness == pytest.approx(0.1)

    def test_audio(self):
        r = parse_editstyle_text(FULL_EXAMPLE)
        a = r.dna.audio
        assert a.has_bgm is True
        assert a.bgm_volume_ratio == pytest.approx(0.20)
        assert a.speech_ratio == pytest.approx(0.70)
        assert a.silence_tolerance == 1.0

    def test_subtitles(self):
        r = parse_editstyle_text(FULL_EXAMPLE)
        s = r.dna.subtitle
        assert s.has_subtitles is True
        assert s.position == "bottom"
        assert s.font_size_category == "medium"

    def test_patterns(self):
        r = parse_editstyle_text(FULL_EXAMPLE)
        assert len(r.patterns) == 3
        assert "Cold open" in r.patterns[0]
        assert "Intro" in r.patterns[1]
        assert "Outro" in r.patterns[2]

    def test_rules(self):
        r = parse_editstyle_text(FULL_EXAMPLE)
        assert len(r.rules) == 3
        assert "✅" in r.rules[0]
        assert "❌" in r.rules[1]


class TestMinimalParsing:
    def test_defaults(self):
        r = parse_editstyle_text(MINIMAL_EXAMPLE)
        assert r.dna.name == "Minimal Style"
        assert r.dna.source == "custom"
        # All sub-models should have their defaults
        assert r.dna.rhythm.cuts_per_minute == 10.0
        assert r.dna.transitions.jump_cut_ratio == 0.8
        assert r.dna.visual.color_temperature == "neutral"
        assert r.dna.audio.has_bgm is False
        assert r.dna.subtitle.has_subtitles is False

    def test_empty_patterns_and_rules(self):
        r = parse_editstyle_text(MINIMAL_EXAMPLE)
        assert r.patterns == []
        assert r.rules == []


class TestValidation:
    def test_missing_marker_raises(self):
        with pytest.raises(ValueError, match="Missing"):
            parse_editstyle_text("# No marker\n\n> Source: test\n")


# ── Conversion helpers ───────────────────────────────────────────────────────


class TestPacingKeywords:
    @pytest.mark.parametrize(
        "keyword,expected",
        [("slow", 6.0), ("medium", 10.0), ("fast", 14.0)],
    )
    def test_keyword_to_cpm(self, keyword, expected):
        text = f"""\
# Test

> CutAI EDITSTYLE v1

## Rhythm
- **Pacing**: {keyword}
"""
        r = parse_editstyle_text(text)
        assert r.dna.rhythm.cuts_per_minute == expected

    def test_explicit_number(self):
        text = """\
# Test

> CutAI EDITSTYLE v1

## Rhythm
- **Pacing**: fast (12 cuts/min)
"""
        r = parse_editstyle_text(text)
        # "fast" keyword takes priority since it starts with "fast"
        assert r.dna.rhythm.cuts_per_minute == 14.0


class TestPercentageParsing:
    def test_basic(self):
        text = """\
# Test

> CutAI EDITSTYLE v1

## Transitions
- **Jump cut**: 85%
- **Fade**: 15%
"""
        r = parse_editstyle_text(text)
        assert r.dna.transitions.jump_cut_ratio == pytest.approx(0.85)
        assert r.dna.transitions.fade_ratio == pytest.approx(0.15)


class TestDurationParsing:
    def test_seconds(self):
        text = """\
# Test

> CutAI EDITSTYLE v1

## Rhythm
- **Average cut length**: 4s
- **Silence tolerance**: 0.8s
"""
        r = parse_editstyle_text(text)
        assert r.dna.rhythm.avg_cut_length == 4.0
        assert r.dna.audio.silence_tolerance == 0.8


# ── Round-trip test ──────────────────────────────────────────────────────────


class TestRoundTrip:
    def test_editdna_to_md_and_back(self):
        """Parse full example → convert DNA to markdown → re-parse → values match."""
        original = parse_editstyle_text(FULL_EXAMPLE)

        # Convert to markdown
        md = editdna_to_markdown(original.dna, original.patterns, original.rules)

        # Re-parse
        reparsed = parse_editstyle_text(md)

        # Compare key values (not exact equality due to formatting differences)
        assert reparsed.dna.name == original.dna.name
        assert reparsed.dna.rhythm.cuts_per_minute == original.dna.rhythm.cuts_per_minute
        assert reparsed.dna.rhythm.avg_cut_length == original.dna.rhythm.avg_cut_length
        assert reparsed.dna.transitions.jump_cut_ratio == pytest.approx(
            original.dna.transitions.jump_cut_ratio, abs=0.01
        )
        assert reparsed.dna.visual.color_temperature == original.dna.visual.color_temperature
        assert reparsed.dna.audio.has_bgm == original.dna.audio.has_bgm
        assert reparsed.dna.subtitle.has_subtitles == original.dna.subtitle.has_subtitles
