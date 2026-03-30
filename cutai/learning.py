"""CutAI Personal Learning — remember user preferences and editing patterns.

Stores learned preferences in ~/.cutai/learning.json.
All functions are safe to call even when the learning file doesn't exist.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from cutai.config import CONFIG_DIR
from cutai.models.types import (
    BGMOperation,
    ColorGradeOperation,
    CutOperation,
    EditPlan,
    FeedbackEntry,
    InstructionMemory,
    SpeedOperation,
    SubtitleOperation,
    TransitionOperation,
    UserPreferences,
)

logger = logging.getLogger(__name__)

DEFAULT_LEARNING_PATH = CONFIG_DIR / "learning.json"
MAX_INSTRUCTION_HISTORY = 50


# Re-export types for convenience (import from cutai.learning)
__all__ = [
    "UserPreferences",
    "InstructionMemory",
    "FeedbackEntry",
    "load_preferences",
    "save_preferences",
    "record_instruction",
    "record_feedback",
    "get_few_shot_examples",
    "suggest_defaults",
]


def load_preferences(path: str | Path | None = None) -> UserPreferences:
    """Load user preferences from a JSON file.

    Args:
        path: Path to the learning JSON file.
              Defaults to ~/.cutai/learning.json.

    Returns:
        UserPreferences instance (empty defaults if file missing/corrupt).
    """
    file_path = Path(path) if path else DEFAULT_LEARNING_PATH

    if not file_path.exists():
        logger.debug("Learning file not found at %s, returning defaults", file_path)
        return UserPreferences()

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return UserPreferences.model_validate(data)
    except Exception as exc:
        logger.warning("Failed to load learning file %s: %s", file_path, exc)
        return UserPreferences()


def save_preferences(
    prefs: UserPreferences,
    path: str | Path | None = None,
) -> None:
    """Save user preferences to a JSON file.

    Args:
        prefs: The preferences to save.
        path: Path to the learning JSON file.
              Defaults to ~/.cutai/learning.json.
    """
    file_path = Path(path) if path else DEFAULT_LEARNING_PATH

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            prefs.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.debug("Saved learning data to %s", file_path)
    except Exception as exc:
        logger.warning("Failed to save learning file %s: %s", file_path, exc)


def record_instruction(
    prefs: UserPreferences,
    instruction: str,
    plan: EditPlan,
    accepted: bool = True,
) -> None:
    """Record an instruction-result pair for learning.

    Keeps last MAX_INSTRUCTION_HISTORY entries (FIFO).

    Args:
        prefs: UserPreferences to update (mutated in place).
        instruction: The natural language instruction.
        plan: The resulting EditPlan.
        accepted: Whether the user accepted (rendered) the result.
    """
    # Build operations summary
    ops_summary = _summarize_operations(plan)

    entry = InstructionMemory(
        instruction=instruction,
        operations_summary=ops_summary,
        was_accepted=accepted,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    prefs.instruction_history.append(entry)

    # FIFO: keep only last N entries
    if len(prefs.instruction_history) > MAX_INSTRUCTION_HISTORY:
        prefs.instruction_history = prefs.instruction_history[-MAX_INSTRUCTION_HISTORY:]

    # Update aggregate stats
    _update_aggregates(prefs)


def record_feedback(
    prefs: UserPreferences,
    instruction: str,
    feedback: str,
    adjustment: str | None = None,
) -> None:
    """Record user feedback on edit quality.

    Args:
        prefs: UserPreferences to update (mutated in place).
        instruction: The instruction that was evaluated.
        feedback: One of "good", "bad", "adjusted".
        adjustment: What was changed (for "adjusted" feedback).
    """
    # Validate feedback value
    if feedback not in ("good", "bad", "adjusted"):
        logger.warning("Invalid feedback value: %s (expected good/bad/adjusted)", feedback)
        feedback = "good"

    entry = FeedbackEntry(
        instruction=instruction,
        feedback=feedback,  # type: ignore[arg-type]
        adjustment=adjustment,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    prefs.feedback_history.append(entry)

    # Keep feedback history bounded too
    if len(prefs.feedback_history) > MAX_INSTRUCTION_HISTORY:
        prefs.feedback_history = prefs.feedback_history[-MAX_INSTRUCTION_HISTORY:]


def get_few_shot_examples(
    prefs: UserPreferences,
    instruction: str,
    max_examples: int = 3,
) -> list[InstructionMemory]:
    """Get relevant few-shot examples for the current instruction.

    Uses simple keyword overlap scoring to find the most relevant
    past instructions. Only returns accepted instructions.

    Args:
        prefs: UserPreferences with instruction history.
        instruction: The current instruction to match against.
        max_examples: Maximum number of examples to return.

    Returns:
        List of InstructionMemory sorted by relevance (most relevant first).
    """
    if not prefs.instruction_history:
        return []

    current_words = set(instruction.lower().split())
    if not current_words:
        return []

    scored: list[tuple[InstructionMemory, float]] = []
    for memory in prefs.instruction_history:
        if not memory.was_accepted:
            continue
        past_words = set(memory.instruction.lower().split())
        if not past_words:
            continue
        overlap = len(current_words & past_words)
        # Normalize by the size of the smaller set for better matching
        score = overlap / min(len(current_words), len(past_words)) if past_words else 0
        if score > 0:
            scored.append((memory, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    return [mem for mem, _ in scored[:max_examples]]


def suggest_defaults(prefs: UserPreferences) -> dict:
    """Suggest default operation parameters based on learning history.

    Analyzes instruction history to find the most commonly used parameters.

    Args:
        prefs: UserPreferences with history data.

    Returns:
        Dict with suggested defaults like:
        {
            "color_preset": "warm",
            "subtitle_position": "bottom",
            "bgm_mood": "calm",
            "keep_ratio": 0.65,
        }
    """
    defaults: dict = {}

    # Collect from preferences
    if prefs.preferred_color_preset:
        defaults["color_preset"] = prefs.preferred_color_preset
    if prefs.preferred_bgm_mood:
        defaults["bgm_mood"] = prefs.preferred_bgm_mood
    defaults["subtitle_position"] = prefs.preferred_subtitle_position
    defaults["keep_ratio"] = prefs.avg_keep_ratio

    # If we have instruction history, analyze it for common patterns
    if prefs.instruction_history:
        color_presets: list[str] = []
        bgm_moods: list[str] = []
        subtitle_positions: list[str] = []

        for mem in prefs.instruction_history:
            if not mem.was_accepted:
                continue
            for summary in mem.operations_summary:
                lower = summary.lower()
                if lower.startswith("colorgrade:"):
                    preset = summary.split(":", 1)[1].strip()
                    color_presets.append(preset)
                elif lower.startswith("bgm:"):
                    mood = summary.split(":", 1)[1].strip()
                    bgm_moods.append(mood)
                elif lower.startswith("subtitle:"):
                    pos = summary.split(":", 1)[1].strip()
                    subtitle_positions.append(pos)

        if color_presets:
            defaults["color_preset"] = Counter(color_presets).most_common(1)[0][0]
        if bgm_moods:
            defaults["bgm_mood"] = Counter(bgm_moods).most_common(1)[0][0]
        if subtitle_positions:
            defaults["subtitle_position"] = Counter(subtitle_positions).most_common(1)[0][0]

    return defaults


# ── Internal helpers ─────────────────────────────────────────────────────────


def _summarize_operations(plan: EditPlan) -> list[str]:
    """Create a concise summary of operations in a plan.

    Returns list of strings like:
        ["cut:remove 3 scenes", "colorgrade:warm", "subtitle:bottom"]
    """
    summaries: list[str] = []

    cuts = [op for op in plan.operations if isinstance(op, CutOperation)]
    if cuts:
        keeps = [c for c in cuts if c.action == "keep"]
        removes = [c for c in cuts if c.action == "remove"]
        if keeps:
            summaries.append(f"cut:keep {len(keeps)} scenes")
        if removes:
            summaries.append(f"cut:remove {len(removes)} scenes")

    for op in plan.operations:
        if isinstance(op, ColorGradeOperation):
            summaries.append(f"colorgrade:{op.preset}")
        elif isinstance(op, BGMOperation):
            summaries.append(f"bgm:{op.mood}")
        elif isinstance(op, SubtitleOperation):
            summaries.append(f"subtitle:{op.position}")
        elif isinstance(op, SpeedOperation):
            summaries.append(f"speed:{op.factor}x")
        elif isinstance(op, TransitionOperation):
            summaries.append(f"transition:{op.style}")

    return summaries


def _update_aggregates(prefs: UserPreferences) -> None:
    """Update aggregate preference fields from instruction history."""
    accepted = [m for m in prefs.instruction_history if m.was_accepted]
    if not accepted:
        return

    # Count color presets, bgm moods, subtitle positions
    color_presets: list[str] = []
    bgm_moods: list[str] = []
    subtitle_positions: list[str] = []

    for mem in accepted:
        for summary in mem.operations_summary:
            lower = summary.lower()
            if lower.startswith("colorgrade:"):
                color_presets.append(summary.split(":", 1)[1].strip())
            elif lower.startswith("bgm:"):
                bgm_moods.append(summary.split(":", 1)[1].strip())
            elif lower.startswith("subtitle:"):
                subtitle_positions.append(summary.split(":", 1)[1].strip())

    if color_presets:
        prefs.preferred_color_preset = Counter(color_presets).most_common(1)[0][0]
    if bgm_moods:
        prefs.preferred_bgm_mood = Counter(bgm_moods).most_common(1)[0][0]
    if subtitle_positions:
        prefs.preferred_subtitle_position = Counter(subtitle_positions).most_common(1)[0][0]
