"""Edit planner — converts VideoAnalysis + natural language → EditPlan.

Supports:
- LLM-based planning (OpenAI API)
- Rule-based fallback for common instructions
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from cutai.config import load_config
from cutai.models.types import (
    CutOperation,
    EditPlan,
    SubtitleOperation,
    VideoAnalysis,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


def create_edit_plan(
    analysis: VideoAnalysis,
    instruction: str,
    llm_model: str = "gpt-4o",
    use_llm: bool = True,
) -> EditPlan:
    """Create an edit plan from a video analysis and instruction.

    First tries rule-based fallback for common instructions.
    Falls back to LLM if no rule matches or if use_llm is True and
    the rule-based plan seems insufficient.

    Args:
        analysis: Complete video analysis.
        instruction: Natural language editing instruction.
        llm_model: LLM model to use for planning.
        use_llm: Whether to use LLM for planning (requires API key).

    Returns:
        EditPlan with ordered operations.
    """
    # Try rule-based fallback first
    rule_plan = _try_rule_based(analysis, instruction)
    if rule_plan and not use_llm:
        return rule_plan

    # Try LLM-based planning
    config = load_config()
    if config.openai_api_key and use_llm:
        try:
            llm_plan = _plan_with_llm(analysis, instruction, llm_model, config.openai_api_key)
            return llm_plan
        except Exception as exc:
            logger.warning("LLM planning failed: %s. Using rule-based fallback.", exc)

    # If LLM failed or no API key, use rule-based
    if rule_plan:
        return rule_plan

    # Last resort: return a minimal plan
    logger.warning("No LLM API key and no matching rules. Returning minimal plan.")
    return EditPlan(
        instruction=instruction,
        operations=[],
        estimated_duration=analysis.duration,
        summary="No edit operations could be determined. Please provide an OpenAI API key for LLM-based planning.",
    )


def _try_rule_based(analysis: VideoAnalysis, instruction: str) -> EditPlan | None:
    """Try to create an edit plan using simple rule matching.

    Handles common instructions without needing an LLM.
    """
    lower = instruction.lower()
    operations: list = []
    summary_parts: list[str] = []

    # Rule: Remove silence
    if _matches_any(lower, ["remove silence", "무음 제거", "cut silence", "무음 삭제", "delete silence"]):
        for seg in analysis.quality.silent_segments:
            operations.append(
                CutOperation(
                    action="remove",
                    start_time=seg.start,
                    end_time=seg.end,
                    reason=f"Silent segment ({seg.duration:.1f}s)",
                )
            )
        summary_parts.append(f"Remove {len(analysis.quality.silent_segments)} silent segments")

    # Rule: Add subtitles
    if _matches_any(lower, ["add subtitles", "자막", "subtitle", "subtitles", "자막 넣어", "자막 추가"]):
        style = "default"
        position = "bottom"
        if _matches_any(lower, ["center", "중앙"]):
            position = "center"
        if _matches_any(lower, ["top", "상단"]):
            position = "top"

        operations.append(
            SubtitleOperation(
                style=style,
                language="auto",
                font_size=24,
                position=position,
            )
        )
        summary_parts.append("Add subtitles")

    # Rule: Remove boring/uninteresting parts
    if _matches_any(lower, [
        "재미없는 부분 잘라", "재미없는 부분 제거", "boring", "remove boring",
        "지루한 부분", "필요없는 부분",
    ]):
        for scene in analysis.scenes:
            if scene.is_silent or (scene.avg_energy < -45 and not scene.has_speech):
                operations.append(CutOperation(
                    action="remove",
                    start_time=scene.start_time,
                    end_time=scene.end_time,
                    reason=f"Low engagement scene (silent={scene.is_silent}, energy={scene.avg_energy:.1f}dB)",
                ))
        summary_parts.append("Remove boring/low-engagement scenes")

    # Rule: Keep only speech parts
    if _matches_any(lower, [
        "말하는 부분만", "speech only", "talking only", "대화만",
    ]):
        for scene in analysis.scenes:
            if not scene.has_speech:
                operations.append(CutOperation(
                    action="remove",
                    start_time=scene.start_time,
                    end_time=scene.end_time,
                    reason="No speech detected",
                ))
        summary_parts.append("Keep only scenes with speech")

    # Rule: Trim to X minutes
    trim_match = re.search(r"(?:trim|cut|줄여|줄이)\s*(?:to\s*)?(\d+)\s*(?:min|분|minutes?)", lower)
    if trim_match:
        target_minutes = int(trim_match.group(1))
        target_seconds = target_minutes * 60.0
        trim_ops = _trim_to_duration(analysis, target_seconds)
        operations.extend(trim_ops)
        summary_parts.append(f"Trim to {target_minutes} minutes")

    if not operations:
        return None

    # Calculate estimated duration
    estimated = _estimate_duration(analysis, operations)

    return EditPlan(
        instruction=instruction,
        operations=operations,
        estimated_duration=round(estimated, 2),
        summary="; ".join(summary_parts),
    )


def _plan_with_llm(
    analysis: VideoAnalysis,
    instruction: str,
    model: str,
    api_key: str,
) -> EditPlan:
    """Create an edit plan using OpenAI's API."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    # Load system prompt
    system_prompt = "You are a professional video editor AI."
    if SYSTEM_PROMPT_PATH.exists():
        system_prompt = SYSTEM_PROMPT_PATH.read_text()

    # Prepare analysis summary (keep it concise for token efficiency)
    analysis_summary = {
        "file": analysis.file_path,
        "duration": analysis.duration,
        "fps": analysis.fps,
        "resolution": f"{analysis.width}x{analysis.height}",
        "scenes": [
            {
                "id": s.id,
                "start": s.start_time,
                "end": s.end_time,
                "duration": s.duration,
                "has_speech": s.has_speech,
                "is_silent": s.is_silent,
                "transcript": s.transcript[:200] if s.transcript else None,
                "avg_energy": s.avg_energy,
            }
            for s in analysis.scenes
        ],
        "silent_segments": [
            {"start": seg.start, "end": seg.end}
            for seg in analysis.quality.silent_segments
        ],
        "silence_ratio": analysis.quality.overall_silence_ratio,
    }

    user_message = (
        f"## Video Analysis\n```json\n{json.dumps(analysis_summary, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## Editing Instruction\n{instruction}"
    )

    logger.info("Calling %s for edit planning...", model)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = response.choices[0].message.content
    if not raw:
        raise ValueError("LLM returned empty response")

    logger.debug("LLM raw response: %s", raw[:500])
    data = json.loads(raw)

    return _parse_llm_response(data, instruction)


def _parse_llm_response(data: dict, instruction: str) -> EditPlan:
    """Parse LLM JSON response into an EditPlan."""
    operations = []

    for op_data in data.get("operations", []):
        op_type = op_data.get("type")

        if op_type == "cut":
            operations.append(
                CutOperation(
                    action=op_data.get("action", "remove"),
                    start_time=float(op_data.get("start_time", 0)),
                    end_time=float(op_data.get("end_time", 0)),
                    reason=op_data.get("reason", ""),
                )
            )
        elif op_type == "subtitle":
            operations.append(
                SubtitleOperation(
                    style=op_data.get("style", "default"),
                    language=op_data.get("language", "auto"),
                    font_size=int(op_data.get("font_size", 24)),
                    position=op_data.get("position", "bottom"),
                )
            )
        # Phase 2 types — just skip them for now
        else:
            logger.debug("Skipping unsupported operation type: %s", op_type)

    return EditPlan(
        instruction=instruction,
        operations=operations,
        estimated_duration=float(data.get("estimated_duration", 0)),
        summary=data.get("summary", ""),
    )


def _trim_to_duration(analysis: VideoAnalysis, target_seconds: float) -> list[CutOperation]:
    """Create cut operations to trim a video to a target duration.

    Strategy: remove silent/low-energy scenes first, then lowest-energy scenes
    until target duration is reached.
    """
    if analysis.duration <= target_seconds:
        return []

    # Score scenes: higher = more worth keeping
    scored = []
    for scene in analysis.scenes:
        score = 0.0
        if scene.has_speech:
            score += 50.0
        if not scene.is_silent:
            score += 30.0
        # Energy scoring: dB is negative, closer to 0 = louder = more interesting
        if scene.avg_energy < 0:
            # -60dB → 0 points, -10dB → 50 points
            score += max(0, (60 + scene.avg_energy))
        elif scene.avg_energy == 0:
            score += 10  # No data — give neutral score, don't penalize
        scored.append((scene, score))

    # Sort by score (lowest first — candidates for removal)
    scored.sort(key=lambda x: x[1])

    excess = analysis.duration - target_seconds
    removed = 0.0
    ops: list[CutOperation] = []

    for scene, score in scored:
        if removed >= excess:
            break
        ops.append(
            CutOperation(
                action="remove",
                start_time=scene.start_time,
                end_time=scene.end_time,
                reason=f"Low priority scene (score={score:.1f}) — trimming to target duration",
            )
        )
        removed += scene.duration

    return ops


def _estimate_duration(analysis: VideoAnalysis, operations: list) -> float:
    """Estimate the output duration after applying operations."""
    removed = 0.0
    for op in operations:
        if isinstance(op, CutOperation) and op.action == "remove":
            removed += op.end_time - op.start_time

    return max(0, analysis.duration - removed)


def _matches_any(text: str, patterns: list[str]) -> bool:
    """Check if text contains any of the given patterns."""
    return any(p in text for p in patterns)
