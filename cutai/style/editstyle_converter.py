"""Bidirectional converter: EditDNA ↔ EDITSTYLE.md ↔ YAML.

Provides utilities to convert between CutAI's internal EditDNA YAML presets
and the human/AI-readable EDITSTYLE.md markdown format.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from cutai.models.types import EditDNA
from cutai.style.editstyle_parser import EditStyleResult, parse_editstyle, parse_editstyle_text
from cutai.style.io import load_style

__all__ = [
    "editdna_to_markdown",
    "yaml_to_editstyle",
    "editstyle_to_yaml",
]

# ── Reverse pacing map ───────────────────────────────────────────────────────

_PACING_LABEL: dict[str, tuple[float, float]] = {
    "slow": (0, 8),
    "medium": (8, 12),
    "fast": (12, 100),
}


def _pacing_keyword(cpm: float) -> str:
    for label, (lo, hi) in _PACING_LABEL.items():
        if lo <= cpm < hi:
            return label
    return "fast"


def _temp_description(temp: str) -> str:
    return {
        "warm": "warm — friendly, everyday tone",
        "cool": "cool — cinematic, moody feel",
        "neutral": "neutral",
    }.get(temp, temp)


# ── EditDNA → EDITSTYLE.md ───────────────────────────────────────────────────


def editdna_to_markdown(
    dna: EditDNA,
    patterns: list[str] | None = None,
    rules: list[str] | None = None,
) -> str:
    """Generate a valid EDITSTYLE.md string from an EditDNA object.

    Args:
        dna: The EditDNA to convert.
        patterns: Optional list of pattern strings for the Patterns section.
        rules: Optional list of rule strings for the Rules section.

    Returns:
        A complete EDITSTYLE.md string.
    """
    lines: list[str] = []

    # Header
    lines.append(f"# {dna.name}")
    lines.append("")
    lines.append(f"> Source: {dna.source or 'custom'}")
    if dna.description:
        # Extract author from description if present
        desc = dna.description
        if desc.lower().startswith("author:"):
            lines.append(f"> {desc}")
        else:
            lines.append(f"> Author: {desc}")
    else:
        lines.append("> Author: CutAI")
    lines.append("> CutAI EDITSTYLE v1")
    lines.append("")

    # Rhythm
    r = dna.rhythm
    kw = _pacing_keyword(r.cuts_per_minute)
    lines.append("## Rhythm")
    lines.append(f"- **Pacing**: {kw} ({r.cuts_per_minute:.0f} cuts/min)")
    lines.append(f"- **Average cut length**: {r.avg_cut_length}s (±{r.cut_length_variance}s)")
    lines.append(f"- **Pacing curve**: {r.pacing_curve}")
    lines.append(f"- **Silence tolerance**: {dna.audio.silence_tolerance}s")
    lines.append("")

    # Transitions
    t = dna.transitions
    lines.append("## Transitions")
    lines.append(f"- **Jump cut**: {t.jump_cut_ratio * 100:.0f}%")
    lines.append(f"- **Fade**: {t.fade_ratio * 100:.0f}%")
    lines.append(f"- **Dissolve**: {t.dissolve_ratio * 100:.0f}%")
    lines.append(f"- **Wipe**: {t.wipe_ratio * 100:.0f}%")
    lines.append(f"- **Transition duration**: {t.avg_transition_duration}s")
    lines.append("")

    # Visual
    v = dna.visual
    lines.append("## Visual")
    lines.append(f"- **Color temperature**: {_temp_description(v.color_temperature)}")
    lines.append(f"- **Saturation**: {v.avg_saturation}")
    lines.append(f"- **Contrast**: {v.avg_contrast}")
    lines.append(f"- **Brightness**: {v.avg_brightness:+.2f}")
    lines.append("")

    # Audio
    a = dna.audio
    bgm_str = f"yes, {a.bgm_volume_ratio * 100:.0f}% volume" if a.has_bgm else "no"
    lines.append("## Audio")
    lines.append(f"- **BGM**: {bgm_str}")
    lines.append(f"- **Speech ratio**: {a.speech_ratio * 100:.0f}%")
    lines.append("")

    # Subtitles
    s = dna.subtitle
    lines.append("## Subtitles")
    lines.append(f"- **Enabled**: {'yes' if s.has_subtitles else 'no'}")
    lines.append(f"- **Position**: {s.position}")
    lines.append(f"- **Size**: {s.font_size_category}")
    lines.append("")

    # Patterns (if provided)
    if patterns:
        lines.append("## Patterns")
        for p in patterns:
            lines.append(f"- {p}")
        lines.append("")

    # Rules (if provided)
    if rules:
        lines.append("## Rules")
        for r_item in rules:
            lines.append(f"- {r_item}")
        lines.append("")

    return "\n".join(lines)


# ── YAML → EDITSTYLE.md ─────────────────────────────────────────────────────


def yaml_to_editstyle(yaml_path: str | Path) -> str:
    """Read a CutAI YAML style preset and convert it to EDITSTYLE.md text.

    Args:
        yaml_path: Path to the .yaml preset file.

    Returns:
        EDITSTYLE.md content string.
    """
    dna = load_style(str(yaml_path))
    return editdna_to_markdown(dna)


# ── EDITSTYLE.md → YAML ─────────────────────────────────────────────────────


def editstyle_to_yaml(md_path: str | Path) -> str:
    """Read an EDITSTYLE.md file and convert it to YAML text.

    Args:
        md_path: Path to the EDITSTYLE.md file.

    Returns:
        YAML string compatible with CutAI's style preset format.
    """
    result = parse_editstyle(md_path)
    dna = result.dna
    data = {
        "name": dna.name,
        "description": dna.description,
        "source": dna.source or "editstyle",
        "rhythm": {
            "avg_cut_length": dna.rhythm.avg_cut_length,
            "cut_length_variance": dna.rhythm.cut_length_variance,
            "pacing_curve": dna.rhythm.pacing_curve,
            "cuts_per_minute": dna.rhythm.cuts_per_minute,
        },
        "transitions": {
            "jump_cut_ratio": dna.transitions.jump_cut_ratio,
            "fade_ratio": dna.transitions.fade_ratio,
            "dissolve_ratio": dna.transitions.dissolve_ratio,
            "wipe_ratio": dna.transitions.wipe_ratio,
            "avg_transition_duration": dna.transitions.avg_transition_duration,
        },
        "visual": {
            "avg_brightness": dna.visual.avg_brightness,
            "avg_saturation": dna.visual.avg_saturation,
            "avg_contrast": dna.visual.avg_contrast,
            "color_temperature": dna.visual.color_temperature,
        },
        "audio": {
            "has_bgm": dna.audio.has_bgm,
            "bgm_volume_ratio": dna.audio.bgm_volume_ratio,
            "silence_tolerance": dna.audio.silence_tolerance,
            "speech_ratio": dna.audio.speech_ratio,
        },
        "subtitle": {
            "has_subtitles": dna.subtitle.has_subtitles,
            "position": dna.subtitle.position,
            "font_size_category": dna.subtitle.font_size_category,
        },
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
