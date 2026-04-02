"""Parser for EDITSTYLE.md files → EditDNA + patterns + rules.

Reads Markdown files formatted per ``docs/EDITSTYLE_SPEC.md`` and converts
them into structured ``EditDNA`` objects reusable by the existing style pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from cutai.models.types import (
    AudioDNA,
    EditDNA,
    RhythmDNA,
    SubtitleDNA,
    TransitionDNA,
    VisualDNA,
)

__all__ = ["EditStyleResult", "parse_editstyle", "parse_editstyle_text"]

# ── Result container ─────────────────────────────────────────────────────────


class EditStyleResult(BaseModel):
    """Structured result of parsing an EDITSTYLE.md file."""

    dna: EditDNA
    patterns: list[str] = []
    rules: list[str] = []


# ── Public API ───────────────────────────────────────────────────────────────


def parse_editstyle(path: str | Path) -> EditStyleResult:
    """Parse an EDITSTYLE.md file from disk.

    Args:
        path: Path to the EDITSTYLE.md file.

    Returns:
        EditStyleResult with dna, patterns, and rules.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the marker ``CutAI EDITSTYLE v1`` is missing.
    """
    text = Path(path).read_text(encoding="utf-8")
    return parse_editstyle_text(text)


def parse_editstyle_text(text: str) -> EditStyleResult:
    """Parse EDITSTYLE.md content from a string.

    Args:
        text: Full markdown content.

    Returns:
        EditStyleResult with dna, patterns, and rules.

    Raises:
        ValueError: If the ``CutAI EDITSTYLE v1`` marker is missing.
    """
    if not re.search(r"CutAI EDITSTYLE v1", text):
        raise ValueError(
            "Missing 'CutAI EDITSTYLE v1' marker. "
            "Is this a valid EDITSTYLE.md file?"
        )

    name = _parse_name(text)
    source, author = _parse_header_meta(text)
    sections = _split_sections(text)

    rhythm = _parse_rhythm(sections.get("rhythm", ""))
    transitions = _parse_transitions(sections.get("transitions", ""))
    visual = _parse_visual(sections.get("visual", ""))
    audio_dna = _parse_audio(sections.get("audio", ""))
    subtitle = _parse_subtitles(sections.get("subtitles", ""))

    # Silence tolerance lives in audio section but maps to AudioDNA
    silence_tol = _extract_duration(sections.get("rhythm", ""), "silence tolerance")
    if silence_tol is not None:
        audio_dna = audio_dna.model_copy(update={"silence_tolerance": silence_tol})

    patterns = _parse_list_section(sections.get("patterns", ""))
    rules = _parse_list_section(sections.get("rules", ""))

    dna = EditDNA(
        name=name,
        description=f"Author: {author}" if author else "",
        source=source,
        rhythm=rhythm,
        transitions=transitions,
        visual=visual,
        audio=audio_dna,
        subtitle=subtitle,
    )

    return EditStyleResult(dna=dna, patterns=patterns, rules=rules)


# ── Internal helpers ─────────────────────────────────────────────────────────

_PACING_MAP: dict[str, float] = {
    "slow": 6.0,
    "medium": 10.0,
    "fast": 14.0,
}


def _parse_name(text: str) -> str:
    """Extract style name from the first H1 header."""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else "unnamed"


def _parse_header_meta(text: str) -> tuple[str, str]:
    """Extract source and author from the blockquote header."""
    source = ""
    author = ""
    for m in re.finditer(r"^>\s*(.+)$", text, re.MULTILINE):
        line = m.group(1).strip()
        if line.lower().startswith("source:"):
            source = line.split(":", 1)[1].strip()
        elif line.lower().startswith("author:"):
            author = line.split(":", 1)[1].strip()
    return source, author


def _split_sections(text: str) -> dict[str, str]:
    """Split text by ## headers into a dict keyed by lowercase section name."""
    sections: dict[str, str] = {}
    parts = re.split(r"^##\s+", text, flags=re.MULTILINE)
    for part in parts[1:]:  # skip everything before first ##
        lines = part.split("\n", 1)
        header = lines[0].strip().lower()
        body = lines[1] if len(lines) > 1 else ""
        sections[header] = body
    return sections


def _get_field(body: str, key: str) -> str | None:
    """Extract value from ``- **Key**: value — optional context`` lines."""
    pattern = rf"-\s*\*\*{re.escape(key)}\*\*\s*:\s*(.+)"
    m = re.search(pattern, body, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).strip()
    # Strip trailing context after em-dash or double-dash
    raw = re.split(r"\s*[—–]\s*", raw, maxsplit=1)[0].strip()
    return raw


def _parse_float(s: str | None, default: float = 0.0) -> float:
    """Parse a float from a string, stripping units like 's', '%', '±'.

    Handles formats like ``5s``, ``5s (±1.5s)``, ``±1.5s``, ``+0.05``.
    Takes the **first** number found before any parenthetical.
    """
    if not s:
        return default
    # Strip parenthetical suffix like "(±1.5s)" first
    cleaned = re.sub(r"\s*\(.*?\)", "", s).strip()
    # Now extract the first number (possibly with +/- sign)
    m = re.search(r"[+-]?[\d.]+", cleaned)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return default
    return default


def _parse_percentage(s: str | None, default: float = 0.0) -> float:
    """Parse percentage string to 0-1 ratio."""
    if not s:
        return default
    m = re.search(r"([\d.]+)\s*%", s)
    if m:
        return float(m.group(1)) / 100.0
    return default


def _extract_duration(body: str, key: str) -> float | None:
    """Extract a duration value (in seconds) for the given key."""
    val = _get_field(body, key)
    if val is None:
        return None
    m = re.search(r"([\d.]+)\s*s", val)
    return float(m.group(1)) if m else None


def _parse_pacing(s: str | None) -> float:
    """Convert pacing keyword or explicit number to cuts_per_minute."""
    if not s:
        return 10.0
    low = s.lower().strip()
    # Check keywords first
    for kw, val in _PACING_MAP.items():
        if low.startswith(kw):
            return val
    # Try explicit number like "12 cuts/min" or "(12 cuts/min)"
    m = re.search(r"([\d.]+)\s*(?:cuts?/min)?", low)
    if m:
        return float(m.group(1))
    return 10.0


def _parse_rhythm(body: str) -> RhythmDNA:
    """Parse ## Rhythm section."""
    pacing_raw = _get_field(body, "pacing") or _get_field(body, "Pacing")
    avg_cut = _get_field(body, "average cut length") or _get_field(body, "Average cut length")
    variance = _get_field(body, "cut variance") or _get_field(body, "Cut variance")
    curve = _get_field(body, "pacing curve") or _get_field(body, "Pacing curve")

    cuts_per_min = _parse_pacing(pacing_raw)

    return RhythmDNA(
        cuts_per_minute=cuts_per_min,
        avg_cut_length=_parse_float(avg_cut, default=3.0),
        cut_length_variance=_parse_float(variance, default=1.5),
        pacing_curve=_validate_pacing_curve(curve),
    )


def _validate_pacing_curve(s: str | None) -> str:
    """Validate pacing curve against allowed values."""
    allowed = {"constant", "slow-fast-slow", "fast-slow", "slow-fast", "dynamic"}
    if s and s.strip().lower() in allowed:
        return s.strip().lower()
    return "constant"


def _parse_transitions(body: str) -> TransitionDNA:
    """Parse ## Transitions section."""
    return TransitionDNA(
        jump_cut_ratio=_parse_percentage(_get_field(body, "jump cut"), 0.8),
        fade_ratio=_parse_percentage(_get_field(body, "fade"), 0.1),
        dissolve_ratio=_parse_percentage(_get_field(body, "dissolve"), 0.05),
        wipe_ratio=_parse_percentage(_get_field(body, "wipe"), 0.05),
        avg_transition_duration=_parse_float(
            _get_field(body, "transition duration"), default=0.5
        ),
    )


def _parse_visual(body: str) -> VisualDNA:
    """Parse ## Visual section."""
    temp_raw = _get_field(body, "color temperature") or "neutral"
    temp = temp_raw.lower().strip()
    if temp not in ("neutral", "warm", "cool"):
        temp = "neutral"

    return VisualDNA(
        color_temperature=temp,  # type: ignore[arg-type]
        avg_saturation=_parse_float(_get_field(body, "saturation"), default=1.0),
        avg_contrast=_parse_float(_get_field(body, "contrast"), default=1.0),
        avg_brightness=_parse_float(_get_field(body, "brightness"), default=0.0),
    )


def _parse_audio(body: str) -> AudioDNA:
    """Parse ## Audio section."""
    bgm_raw = _get_field(body, "bgm") or ""
    has_bgm = bgm_raw.lower().startswith("yes") if bgm_raw else False

    # Extract volume from BGM line like "yes, lo-fi / upbeat, 20% volume"
    bgm_vol = 0.15
    vol_m = re.search(r"([\d.]+)\s*%\s*(?:volume)?", bgm_raw)
    if vol_m:
        bgm_vol = float(vol_m.group(1)) / 100.0

    speech_raw = _get_field(body, "speech ratio")
    speech = _parse_percentage(speech_raw, 0.6)

    return AudioDNA(
        has_bgm=has_bgm,
        bgm_volume_ratio=bgm_vol,
        speech_ratio=speech,
        silence_tolerance=1.0,  # may be overridden by rhythm section
    )


def _parse_subtitles(body: str) -> SubtitleDNA:
    """Parse ## Subtitles section."""
    enabled = (_get_field(body, "enabled") or "no").lower().startswith("yes")
    position_raw = (_get_field(body, "position") or "bottom").lower().strip()
    if position_raw not in ("bottom", "center", "top"):
        position_raw = "bottom"
    size_raw = (_get_field(body, "size") or "medium").lower().strip()
    if size_raw not in ("small", "medium", "large"):
        size_raw = "medium"

    return SubtitleDNA(
        has_subtitles=enabled,
        position=position_raw,  # type: ignore[arg-type]
        font_size_category=size_raw,  # type: ignore[arg-type]
    )


def _parse_list_section(body: str) -> list[str]:
    """Parse a section with bullet-point list items."""
    items: list[str] = []
    for line in body.strip().splitlines():
        line = line.strip()
        if line.startswith("- "):
            item = line[2:].strip()
            # Strip bold markers for clean storage
            item = re.sub(r"\*\*(.+?)\*\*\s*:\s*", r"\1: ", item)
            items.append(item)
    return items
