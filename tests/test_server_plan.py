from __future__ import annotations

import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient

import cutai.server as server


def _register_video(video_id: str, sample_analysis, tmp_path: Path) -> None:
    source_path = tmp_path / f"{video_id}.mp4"
    source_path.write_bytes(b"source")

    server.videos[video_id] = {
        "path": str(source_path),
        "original_name": "input.mp4",
        "file_size": source_path.stat().st_size,
        "duration": sample_analysis.duration,
        "width": sample_analysis.width,
        "height": sample_analysis.height,
        "fps": sample_analysis.fps,
        "analysis": sample_analysis.model_dump(),
    }


def test_resolve_style_source_accepts_bare_name_and_explicit_extension():
    bare = server._resolve_style_source(style_preset="cinematic")
    explicit = server._resolve_style_source(style_preset="cinematic.yaml")

    assert bare.endswith("cutai/style/presets/cinematic.yaml")
    assert explicit == bare


def test_plan_request_uses_style_preset_when_present(monkeypatch, sample_analysis, tmp_path: Path):
    server.videos.clear()
    server.jobs.clear()
    _register_video("video-plan-style", sample_analysis, tmp_path)

    load_calls: list[str] = []
    apply_calls: list[tuple[str, str]] = []

    def fake_load_style(path: str):
        load_calls.append(path)
        return {"name": "cinematic"}

    def fake_apply_style(analysis, style_dna, instruction: str = ""):
        apply_calls.append((style_dna["name"], instruction))
        return types.SimpleNamespace(
            model_dump=lambda: {
                "instruction": instruction,
                "operations": [],
                "estimated_duration": analysis.duration,
                "summary": "Styled plan",
            }
        )

    monkeypatch.setitem(
        sys.modules,
        "cutai.style",
        types.SimpleNamespace(load_style=fake_load_style, apply_style=fake_apply_style),
    )

    client = TestClient(server.app)
    response = client.post(
        "/api/plan",
        json={
            "video_id": "video-plan-style",
            "instruction": "make it cinematic",
            "style_preset": "cinematic",
        },
    )

    assert response.status_code == 200
    assert load_calls == [server._resolve_style_source(style_preset="cinematic")]
    assert apply_calls == [("cinematic", "make it cinematic")]
    assert response.json()["summary"] == "Styled plan"


def test_plan_request_prefers_explicit_style_path_over_style_preset(
    monkeypatch, sample_analysis, tmp_path: Path
):
    server.videos.clear()
    server.jobs.clear()
    _register_video("video-plan-style-path", sample_analysis, tmp_path)

    custom_style = tmp_path / "custom-style.yaml"
    custom_style.write_text("name: custom-style\n")
    load_calls: list[str] = []

    def fake_load_style(path: str):
        load_calls.append(path)
        return {"name": "custom"}

    def fake_apply_style(analysis, style_dna, instruction: str = ""):
        return types.SimpleNamespace(
            model_dump=lambda: {
                "instruction": instruction,
                "operations": [],
                "estimated_duration": analysis.duration,
                "summary": style_dna["name"],
            }
        )

    monkeypatch.setitem(
        sys.modules,
        "cutai.style",
        types.SimpleNamespace(load_style=fake_load_style, apply_style=fake_apply_style),
    )

    client = TestClient(server.app)
    response = client.post(
        "/api/plan",
        json={
            "video_id": "video-plan-style-path",
            "instruction": "use my local style",
            "style_path": str(custom_style),
            "style_preset": "cinematic",
        },
    )

    assert response.status_code == 200
    assert load_calls == [str(custom_style)]
    assert response.json()["summary"] == "custom"


def test_plan_request_without_style_uses_instruction_planner(
    monkeypatch, sample_analysis, tmp_path: Path
):
    server.videos.clear()
    server.jobs.clear()
    _register_video("video-plan-instruction", sample_analysis, tmp_path)

    planner_calls: list[tuple[str, str, bool]] = []

    def fake_create_edit_plan(analysis, instruction: str, llm_model: str, use_llm: bool):
        planner_calls.append((instruction, llm_model, use_llm))
        return types.SimpleNamespace(
            model_dump=lambda: {
                "instruction": instruction,
                "operations": [],
                "estimated_duration": analysis.duration,
                "summary": "Instruction plan",
            }
        )

    monkeypatch.setitem(
        sys.modules,
        "cutai.planner",
        types.SimpleNamespace(create_edit_plan=fake_create_edit_plan),
    )

    client = TestClient(server.app)
    response = client.post(
        "/api/plan",
        json={
            "video_id": "video-plan-instruction",
            "instruction": "trim silent parts",
            "use_llm": False,
            "llm_model": "gpt-4.1-mini",
        },
    )

    assert response.status_code == 200
    assert planner_calls == [("trim silent parts", "gpt-4.1-mini", False)]
    assert response.json()["summary"] == "Instruction plan"
