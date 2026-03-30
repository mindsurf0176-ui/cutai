"""Style learner — combine EditDNA from multiple reference videos."""

from __future__ import annotations

import logging
from collections import Counter
from statistics import mean

from cutai.models.types import (
    AudioDNA,
    EditDNA,
    RhythmDNA,
    SubtitleDNA,
    TransitionDNA,
    VisualDNA,
)
from cutai.style.extractor import extract_style

logger = logging.getLogger(__name__)


def learn_style(
    video_paths: list[str],
    name: str = "learned",
    whisper_model: str = "base",
) -> EditDNA:
    """Extract EditDNA from multiple videos and average them.

    For each video, runs ``extract_style()``.  Numeric fields are averaged;
    categorical / boolean fields use the mode (most common value).

    Args:
        video_paths: List of video file paths.
        name: Name for the resulting EditDNA.
        whisper_model: Whisper model size for transcription.

    Returns:
        Averaged EditDNA.

    Raises:
        ValueError: If no videos could be analysed.
    """
    if not video_paths:
        raise ValueError("At least one video path is required")

    dnas: list[EditDNA] = []
    for vp in video_paths:
        try:
            logger.info("Extracting style from %s …", vp)
            dna = extract_style(vp, whisper_model=whisper_model)
            dnas.append(dna)
        except Exception as exc:
            logger.warning("Skipping %s: %s", vp, exc)

    if not dnas:
        raise ValueError("Could not extract style from any of the provided videos")

    rhythm = _average_sub(
        [d.rhythm for d in dnas],
        RhythmDNA,
        categorical={"pacing_curve"},
    )
    transitions = _average_sub(
        [d.transitions for d in dnas],
        TransitionDNA,
        categorical=set(),
    )
    visual = _average_sub(
        [d.visual for d in dnas],
        VisualDNA,
        categorical={"color_temperature"},
    )
    audio = _average_sub(
        [d.audio for d in dnas],
        AudioDNA,
        categorical={"has_bgm"},
    )
    subtitle = _average_sub(
        [d.subtitle for d in dnas],
        SubtitleDNA,
        categorical={"has_subtitles", "position", "font_size_category"},
    )

    sources = ", ".join(d.source for d in dnas if d.source)

    return EditDNA(
        name=name,
        description=f"Learned from {len(dnas)} video(s)",
        source=sources,
        rhythm=rhythm,
        transitions=transitions,
        visual=visual,
        audio=audio,
        subtitle=subtitle,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _average_sub(instances: list, model_cls: type, categorical: set[str]):
    """Average numeric fields and pick mode for categorical/bool fields."""
    if not instances:
        return model_cls()

    data: dict = {}

    # Get field names from the first instance
    field_names = list(instances[0].model_fields.keys())

    for field_name in field_names:
        values = [getattr(inst, field_name) for inst in instances]

        if field_name in categorical:
            # Mode
            counter = Counter(values)
            data[field_name] = counter.most_common(1)[0][0]
        elif isinstance(values[0], bool):
            # Bool → majority vote
            data[field_name] = sum(values) > len(values) / 2
        elif isinstance(values[0], (int, float)):
            data[field_name] = round(mean(values), 3)
        else:
            # Fallback — keep first value
            data[field_name] = values[0]

    return model_cls(**data)
