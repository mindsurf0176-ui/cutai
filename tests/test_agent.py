"""Tests for the Agent Engine and MCP Server modules."""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from cutai.agent.engine import AgentEngine, AgentResult, EvaluationResult
from cutai.models.types import (
    EditDNA,
    EditPlan,
    QualityReport,
    SceneInfo,
    VideoAnalysis,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_analysis(duration: float = 120.0, scenes: int = 5) -> VideoAnalysis:
    """Create a minimal VideoAnalysis for testing."""
    return VideoAnalysis(
        file_path="/tmp/test.mp4",
        duration=duration,
        fps=30.0,
        width=1920,
        height=1080,
        scenes=[
            SceneInfo(
                id=i,
                start_time=i * (duration / scenes),
                end_time=(i + 1) * (duration / scenes),
                duration=duration / scenes,
                has_speech=i % 2 == 0,
                is_silent=i % 3 == 0,
                avg_energy=-20.0 + i * 5,
            )
            for i in range(scenes)
        ],
        transcript=[],
        quality=QualityReport(silent_segments=[], audio_energy=[], overall_silence_ratio=0.1),
    )


def _make_plan(ops: int = 5) -> EditPlan:
    from cutai.models.types import CutOperation, SubtitleOperation
    operations = [
        CutOperation(action="remove", start_time=0, end_time=5, reason="silent"),
        SubtitleOperation(style="default", language="ko"),
    ]
    return EditPlan(
        instruction="test",
        operations=operations,
        estimated_duration=90.0,
        summary="test plan",
    )


# ── Agent Engine Tests ───────────────────────────────────────────────────────


class TestAgentEngine:
    def test_init(self):
        engine = AgentEngine(
            inputs=["/tmp/test.mp4"],
            goal="make it short and fun",
        )
        assert engine.goal == "make it short and fun"
        assert engine.max_iterations == 3

    def test_build_instruction_first_iteration(self):
        engine = AgentEngine(
            inputs=["/tmp/test.mp4"],
            goal="카페 브이로그",
        )
        instruction = engine._build_instruction(1)
        assert "카페 브이로그" in instruction

    def test_build_instruction_with_feedback(self):
        engine = AgentEngine(
            inputs=["/tmp/test.mp4"],
            goal="카페 브이로그",
        )
        from cutai.agent.engine import AgentIteration
        engine._iterations.append(
            AgentIteration(
                iteration=1,
                plan=_make_plan(),
                output_path="/tmp/out.mp4",
                evaluation=EvaluationResult(
                    score=50,
                    weaknesses=["too long"],
                    suggestions=["cut more"],
                ),
            )
        )
        instruction = engine._build_instruction(2)
        assert "too long" in instruction
        assert "cut more" in instruction

    def test_evaluate_good_plan(self):
        engine = AgentEngine(
            inputs=["/tmp/test.mp4"],
            goal="자막 넣어줘",
        )
        engine._merged_analysis = _make_analysis()
        engine._style_dna = None

        plan = _make_plan()
        ev = engine._evaluate(plan, "/tmp/out.mp4")

        assert ev.score > 0
        assert isinstance(ev.strengths, list)
        assert isinstance(ev.weaknesses, list)

    def test_evaluate_with_style(self):
        engine = AgentEngine(
            inputs=["/tmp/test.mp4"],
            goal="warm vlog",
        )
        engine._merged_analysis = _make_analysis()
        engine._style_dna = EditDNA(name="test-style")

        plan = _make_plan()
        ev = engine._evaluate(plan, "/tmp/out.mp4")

        assert any("Style" in s for s in ev.strengths)

    def test_iter_output_path(self):
        engine = AgentEngine(
            inputs=["/tmp/test.mp4"],
            goal="test",
            output="/tmp/output/final.mp4",
        )
        assert engine._iter_output_path(1) == "/tmp/output/final_iter1.mp4"
        assert engine._iter_output_path(3) == "/tmp/output/final_iter3.mp4"


# ── MCP Server Tests ────────────────────────────────────────────────────────


class TestMCPTools:
    def test_tool_definitions(self):
        from cutai.mcp_server import TOOLS
        assert len(TOOLS) == 8
        names = {t["name"] for t in TOOLS}
        assert "cutai_analyze" in names
        assert "cutai_agent" in names
        assert "cutai_editstyle_parse" in names

    def test_handlers_registered(self):
        from cutai.mcp_server import HANDLERS
        assert len(HANDLERS) == 8
        assert "cutai_analyze" in HANDLERS
        assert "cutai_agent" in HANDLERS

    def test_editstyle_parse_handler(self, tmp_path):
        from cutai.mcp_server import _handle_editstyle_parse

        md = tmp_path / "EDITSTYLE.md"
        md.write_text("""\
# Test Style

> Source: test
> CutAI EDITSTYLE v1

## Rhythm
- **Pacing**: fast (14 cuts/min)

## Visual
- **Color temperature**: warm
""")

        result = _handle_editstyle_parse({"file": str(md)})
        assert result["name"] == "Test Style"
        assert result["rhythm"]["cuts_per_minute"] == 14.0
        assert result["visual"]["color_temperature"] == "warm"

    def test_make_response(self):
        from cutai.mcp_server import _make_response
        resp = _make_response(1, {"ok": True})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert resp["result"] == {"ok": True}

    def test_make_error_response(self):
        from cutai.mcp_server import _make_response
        resp = _make_response(2, error={"code": -32601, "message": "Not found"})
        assert "error" in resp
        assert resp["error"]["code"] == -32601
