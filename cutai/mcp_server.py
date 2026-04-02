"""CutAI MCP Server — expose CutAI tools via the Model Context Protocol.

Enables AI coding agents (Claude Code, Cursor, etc.) to call CutAI
functions as MCP tools.

Usage:
    cutai mcp-server                     # stdio transport (default)
    cutai mcp-server --port 8765         # HTTP/SSE transport

MCP config example (for Claude Code / Cursor):
    {
      "mcpServers": {
        "cutai": {
          "command": "cutai",
          "args": ["mcp-server"]
        }
      }
    }
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "cutai_analyze",
        "description": "Analyze a video file — detect scenes, transcribe speech, assess quality, and score engagement.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video": {"type": "string", "description": "Path to the video file"},
                "whisper_model": {"type": "string", "default": "base", "description": "Whisper model size (tiny/base/small/medium/large)"},
                "skip_transcription": {"type": "boolean", "default": False, "description": "Skip Whisper transcription"},
            },
            "required": ["video"],
        },
    },
    {
        "name": "cutai_plan",
        "description": "Generate an edit plan from a video analysis and natural language instruction, without rendering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video": {"type": "string", "description": "Path to the video file"},
                "instruction": {"type": "string", "description": "Natural language editing instruction"},
                "style": {"type": "string", "description": "Path to EditDNA YAML or EDITSTYLE.md file"},
                "no_llm": {"type": "boolean", "default": False, "description": "Use rule-based planning only"},
            },
            "required": ["video", "instruction"],
        },
    },
    {
        "name": "cutai_edit",
        "description": "Full edit pipeline: analyze a video, generate a plan from natural language, and render the result.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video": {"type": "string", "description": "Path to the video file"},
                "instruction": {"type": "string", "description": "Natural language editing instruction"},
                "output": {"type": "string", "description": "Output file path"},
                "style": {"type": "string", "description": "Path to EditDNA YAML or EDITSTYLE.md file"},
                "no_llm": {"type": "boolean", "default": False, "description": "Use rule-based planning only"},
                "burn_subtitles": {"type": "boolean", "default": True, "description": "Burn subtitles into video"},
            },
            "required": ["video", "instruction"],
        },
    },
    {
        "name": "cutai_agent",
        "description": "Goal-driven autonomous video editing. Analyzes, plans, renders, self-evaluates, and iterates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inputs": {"type": "array", "items": {"type": "string"}, "description": "List of input video paths"},
                "goal": {"type": "string", "description": "High-level editing goal"},
                "output": {"type": "string", "default": "agent_output.mp4", "description": "Output file path"},
                "max_iterations": {"type": "integer", "default": 3, "description": "Max edit-evaluate iterations"},
                "editstyle": {"type": "string", "description": "Path to EDITSTYLE.md file"},
            },
            "required": ["inputs", "goal"],
        },
    },
    {
        "name": "cutai_style_extract",
        "description": "Extract Edit DNA (editing style fingerprint) from a reference video.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video": {"type": "string", "description": "Path to the reference video"},
                "output": {"type": "string", "description": "Output YAML/MD file path"},
                "format": {"type": "string", "enum": ["yaml", "md"], "default": "yaml", "description": "Output format"},
            },
            "required": ["video"],
        },
    },
    {
        "name": "cutai_highlights",
        "description": "Generate a highlight reel from the most engaging scenes of a video.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video": {"type": "string", "description": "Path to the video file"},
                "duration": {"type": "number", "description": "Target highlight duration in seconds"},
                "style": {"type": "string", "enum": ["best-moments", "narrative", "shorts"], "default": "best-moments"},
                "output": {"type": "string", "description": "Output file path"},
            },
            "required": ["video"],
        },
    },
    {
        "name": "cutai_engagement",
        "description": "Analyze per-scene engagement scores for a video.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video": {"type": "string", "description": "Path to the video file"},
            },
            "required": ["video"],
        },
    },
    {
        "name": "cutai_editstyle_parse",
        "description": "Parse an EDITSTYLE.md file and return its structured content (EditDNA + patterns + rules).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Path to the EDITSTYLE.md file"},
            },
            "required": ["file"],
        },
    },
]


# ── Tool handlers ────────────────────────────────────────────────────────────


def _handle_analyze(params: dict) -> dict:
    from cutai.analyzer import analyze_video
    analysis = analyze_video(
        params["video"],
        whisper_model=params.get("whisper_model", "base"),
        skip_transcription=params.get("skip_transcription", False),
    )
    return {
        "duration": analysis.duration,
        "fps": analysis.fps,
        "resolution": f"{analysis.width}x{analysis.height}",
        "scenes": len(analysis.scenes),
        "transcript_segments": len(analysis.transcript),
        "silent_segments": len(analysis.quality.silent_segments),
        "silence_ratio": round(analysis.quality.overall_silence_ratio, 3),
    }


def _handle_plan(params: dict) -> dict:
    from cutai.analyzer import analyze_video
    from cutai.planner import create_edit_plan

    analysis = analyze_video(params["video"])

    style_path = params.get("style")
    if style_path:
        if style_path.endswith(".md"):
            from cutai.style.editstyle_parser import parse_editstyle
            from cutai.style.applier import apply_style
            es = parse_editstyle(style_path)
            plan = apply_style(analysis, es.dna, instruction=params["instruction"])
        else:
            from cutai.style.io import load_style
            from cutai.style.applier import apply_style
            dna = load_style(style_path)
            plan = apply_style(analysis, dna, instruction=params["instruction"])
    else:
        plan = create_edit_plan(
            analysis,
            params["instruction"],
            use_llm=not params.get("no_llm", False),
        )

    return {
        "instruction": plan.instruction,
        "operations": len(plan.operations),
        "estimated_duration": round(plan.estimated_duration, 2),
        "summary": plan.summary,
    }


def _handle_edit(params: dict) -> dict:
    from cutai.analyzer import analyze_video
    from cutai.planner import create_edit_plan
    from cutai.editor.renderer import render

    analysis = analyze_video(params["video"])

    style_path = params.get("style")
    if style_path:
        if style_path.endswith(".md"):
            from cutai.style.editstyle_parser import parse_editstyle
            from cutai.style.applier import apply_style
            es = parse_editstyle(style_path)
            plan = apply_style(analysis, es.dna, instruction=params["instruction"])
        else:
            from cutai.style.io import load_style
            from cutai.style.applier import apply_style
            dna = load_style(style_path)
            plan = apply_style(analysis, dna, instruction=params["instruction"])
    else:
        plan = create_edit_plan(
            analysis,
            params["instruction"],
            use_llm=not params.get("no_llm", False),
        )

    output = params.get("output") or str(
        Path(params["video"]).parent / f"{Path(params['video']).stem}_edited.mp4"
    )
    result_path = render(
        params["video"],
        plan,
        analysis,
        output,
        burn_subtitles=params.get("burn_subtitles", True),
    )

    return {
        "output": result_path,
        "operations": len(plan.operations),
        "estimated_duration": round(plan.estimated_duration, 2),
        "summary": plan.summary,
    }


def _handle_agent(params: dict) -> dict:
    from cutai.agent.engine import AgentEngine

    engine = AgentEngine(
        inputs=params["inputs"],
        goal=params["goal"],
        output=params.get("output", "agent_output.mp4"),
        max_iterations=params.get("max_iterations", 3),
        editstyle=params.get("editstyle"),
    )
    result = engine.run()
    return {
        "output": result.final_output,
        "score": result.final_score,
        "iterations": result.total_iterations,
        "goal": result.goal,
    }


def _handle_style_extract(params: dict) -> dict:
    from cutai.analyzer import analyze_video
    from cutai.style.extractor import extract_style

    analysis = analyze_video(params["video"])
    dna = extract_style(analysis)

    fmt = params.get("format", "yaml")
    output = params.get("output")

    if fmt == "md":
        from cutai.style.editstyle_converter import editdna_to_markdown
        text = editdna_to_markdown(dna)
        if output:
            Path(output).write_text(text, encoding="utf-8")
    else:
        from cutai.style.io import save_style
        output = output or "style.yaml"
        save_style(dna, output)

    return {
        "name": dna.name,
        "output": output or "(returned inline)",
        "format": fmt,
    }


def _handle_highlights(params: dict) -> dict:
    from cutai.analyzer import analyze_video
    from cutai.analyzer.engagement import analyze_engagement
    from cutai.highlight import generate_highlights
    from cutai.editor.renderer import render

    analysis = analyze_video(params["video"])
    engagement = analyze_engagement(analysis)

    target = params.get("duration")
    plan = generate_highlights(
        params["video"],
        analysis,
        engagement,
        target_duration=target,
        style=params.get("style", "best-moments"),
    )

    output = params.get("output") or str(
        Path(params["video"]).parent / f"{Path(params['video']).stem}_highlights.mp4"
    )
    result_path = render(params["video"], plan, analysis, output)

    return {
        "output": result_path,
        "scenes_kept": len([
            op for op in plan.operations
            if hasattr(op, "action") and op.action == "keep"
        ]),
        "estimated_duration": round(plan.estimated_duration, 2),
    }


def _handle_engagement(params: dict) -> dict:
    from cutai.analyzer import analyze_video
    from cutai.analyzer.engagement import analyze_engagement

    analysis = analyze_video(params["video"])
    report = analyze_engagement(analysis)

    return {
        "avg_score": round(report.avg_score, 1),
        "high_count": report.high_count,
        "low_count": report.low_count,
        "scenes": [
            {
                "id": s.scene_id,
                "score": round(s.score, 1),
                "label": s.label,
            }
            for s in report.scenes
        ],
    }


def _handle_editstyle_parse(params: dict) -> dict:
    from cutai.style.editstyle_parser import parse_editstyle

    result = parse_editstyle(params["file"])
    dna = result.dna

    return {
        "name": dna.name,
        "source": dna.source,
        "rhythm": {
            "cuts_per_minute": dna.rhythm.cuts_per_minute,
            "avg_cut_length": dna.rhythm.avg_cut_length,
            "pacing_curve": dna.rhythm.pacing_curve,
        },
        "visual": {
            "color_temperature": dna.visual.color_temperature,
            "saturation": dna.visual.avg_saturation,
        },
        "audio": {
            "has_bgm": dna.audio.has_bgm,
            "speech_ratio": dna.audio.speech_ratio,
        },
        "subtitle": {
            "enabled": dna.subtitle.has_subtitles,
            "position": dna.subtitle.position,
        },
        "patterns": result.patterns,
        "rules": result.rules,
    }


HANDLERS = {
    "cutai_analyze": _handle_analyze,
    "cutai_plan": _handle_plan,
    "cutai_edit": _handle_edit,
    "cutai_agent": _handle_agent,
    "cutai_style_extract": _handle_style_extract,
    "cutai_highlights": _handle_highlights,
    "cutai_engagement": _handle_engagement,
    "cutai_editstyle_parse": _handle_editstyle_parse,
}


# ── MCP Protocol (stdio JSON-RPC) ───────────────────────────────────────────


def _make_response(id: Any, result: Any = None, error: dict | None = None) -> dict:
    resp: dict = {"jsonrpc": "2.0", "id": id}
    if error:
        resp["error"] = error
    else:
        resp["result"] = result
    return resp


def run_stdio_server() -> None:
    """Run the MCP server over stdio using JSON-RPC 2.0."""
    logger.info("CutAI MCP Server starting (stdio transport)...")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            resp = _make_response(None, error={"code": -32700, "message": "Parse error"})
            _send(resp)
            continue

        req_id = request.get("id")
        method = request.get("method", "")

        try:
            if method == "initialize":
                _send(_make_response(req_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "cutai",
                        "version": "0.2.0",
                    },
                }))
            elif method == "notifications/initialized":
                # Client ack — no response needed
                pass
            elif method == "tools/list":
                _send(_make_response(req_id, {"tools": TOOLS}))
            elif method == "tools/call":
                tool_name = request["params"]["name"]
                tool_args = request["params"].get("arguments", {})

                handler = HANDLERS.get(tool_name)
                if not handler:
                    _send(_make_response(req_id, error={
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}",
                    }))
                    continue

                try:
                    result = handler(tool_args)
                    _send(_make_response(req_id, {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}],
                    }))
                except Exception as exc:
                    _send(_make_response(req_id, {
                        "content": [{"type": "text", "text": f"Error: {exc}"}],
                        "isError": True,
                    }))
            else:
                _send(_make_response(req_id, error={
                    "code": -32601,
                    "message": f"Method not found: {method}",
                }))
        except Exception as exc:
            _send(_make_response(req_id, error={
                "code": -32603,
                "message": str(exc),
            }))


def _send(response: dict) -> None:
    """Send a JSON-RPC response to stdout."""
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()
