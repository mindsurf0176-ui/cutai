from __future__ import annotations

import asyncio
import time
from pathlib import Path

from fastapi.testclient import TestClient

import cutai.server as server
from cutai.models.types import EditPlan


def _wait_for_job(job_id: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = server.jobs[job_id]
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


def test_render_job_uses_selected_preset(monkeypatch, sample_analysis, tmp_path: Path):
    server.videos.clear()
    server.jobs.clear()
    monkeypatch.setattr(server, "OUTPUT_DIR", tmp_path)

    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"source")

    video_id = "video-render"
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

    preset_calls: list[tuple[str, str, server.RenderPresetSpec, int]] = []

    def fake_export_render_with_settings(
        input_path: str,
        output_path: str,
        preset: server.RenderPresetSpec,
        input_height: int,
    ) -> None:
        preset_calls.append((input_path, output_path, preset, input_height))
        Path(output_path).write_bytes(f"render-{preset.key}".encode())

    monkeypatch.setattr(server, "_export_render_with_settings", fake_export_render_with_settings)
    scheduled: list[object] = []
    monkeypatch.setattr(server.asyncio, "create_task", lambda coro: scheduled.append(coro))

    client = TestClient(server.app)
    plan = EditPlan(
        instruction="render",
        operations=[],
        estimated_duration=sample_analysis.duration,
        summary="Render only",
    )

    start_response = client.post(
        "/api/render",
        json={
            "video_id": video_id,
            "plan": plan.model_dump(),
            "render_preset": "draft",
        },
    )

    assert start_response.status_code == 200
    job_id = start_response.json()["job_id"]
    assert len(scheduled) == 1
    asyncio.run(scheduled.pop())

    job = _wait_for_job(job_id)
    assert job["type"] == "render"
    assert job["status"] == "completed"
    assert job["result"]["render_preset"] == "draft"
    assert job["result"]["resolution"] == 720
    assert preset_calls[0][2].key == "draft"
    assert preset_calls[0][3] == sample_analysis.height

    video_response = client.get(f"/api/render/{job_id}/video")
    assert video_response.status_code == 200
    assert video_response.content == b"render-draft"


def test_render_job_persists_sidecar_subtitle_metadata(monkeypatch, sample_analysis, tmp_path: Path):
    server.videos.clear()
    server.jobs.clear()
    monkeypatch.setattr(server, "OUTPUT_DIR", tmp_path)

    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"source")

    video_id = "video-render-sidecar"
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

    sample_analysis.transcript = [
        {
            "start_time": 0.0,
            "end_time": 1.0,
            "text": "hello",
        }
    ]

    def fake_export_render_with_settings(
        input_path: str,
        output_path: str,
        preset: server.RenderPresetSpec,
        input_height: int,
    ) -> None:
        Path(output_path).write_bytes(f"render-{preset.key}".encode())

    def fake_generate_ass(transcript, output_path, operation) -> None:
        Path(output_path).write_text("sidecar subtitle")

    monkeypatch.setattr(server, "_export_render_with_settings", fake_export_render_with_settings)
    scheduled: list[object] = []
    monkeypatch.setattr(server.asyncio, "create_task", lambda coro: scheduled.append(coro))

    import types
    import sys

    subtitle_module = types.SimpleNamespace(
        generate_ass=fake_generate_ass,
        burn_subtitles=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "cutai.editor.subtitle", subtitle_module)

    client = TestClient(server.app)
    plan = {
        "instruction": "add subtitles",
        "operations": [
            {
                "type": "subtitle",
                "position": "bottom",
                "font_size": 24,
                "language": "en",
            }
        ],
        "estimated_duration": sample_analysis.duration,
        "summary": "Add subtitles",
    }

    start_response = client.post(
        "/api/render",
        json={
            "video_id": video_id,
            "plan": plan,
            "render_preset": "balanced",
            "subtitle_export_mode": "sidecar",
        },
    )

    assert start_response.status_code == 200
    job_id = start_response.json()["job_id"]
    assert len(scheduled) == 1
    asyncio.run(scheduled.pop())

    job = _wait_for_job(job_id)
    assert job["status"] == "completed"
    assert job["result"]["subtitle_export_mode"] == "sidecar"
    assert job["result"]["subtitle_path"].endswith(".ass")
    assert Path(job["result"]["subtitle_path"]).read_text() == "sidecar subtitle"


def test_render_request_accepts_legacy_burn_subtitles_flag(
    monkeypatch, sample_analysis, tmp_path: Path
):
    server.videos.clear()
    server.jobs.clear()
    monkeypatch.setattr(server, "OUTPUT_DIR", tmp_path)

    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"source")

    video_id = "video-render-legacy-subtitles"
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

    sample_analysis.transcript = [
        {
            "start_time": 0.0,
            "end_time": 1.0,
            "text": "legacy",
        }
    ]

    def fake_export_render_with_settings(
        input_path: str,
        output_path: str,
        preset: server.RenderPresetSpec,
        input_height: int,
    ) -> None:
        Path(output_path).write_bytes(f"render-{preset.key}".encode())

    def fake_generate_ass(transcript, output_path, operation) -> None:
        Path(output_path).write_text("legacy subtitle")

    monkeypatch.setattr(server, "_export_render_with_settings", fake_export_render_with_settings)
    scheduled: list[object] = []
    monkeypatch.setattr(server.asyncio, "create_task", lambda coro: scheduled.append(coro))

    import types
    import sys

    subtitle_module = types.SimpleNamespace(
        generate_ass=fake_generate_ass,
        burn_subtitles=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "cutai.editor.subtitle", subtitle_module)

    client = TestClient(server.app)
    response = client.post(
        "/api/render",
        json={
            "video_id": video_id,
            "plan": {
                "instruction": "add subtitles",
                "operations": [
                    {
                        "type": "subtitle",
                        "position": "bottom",
                        "font_size": 24,
                        "language": "en",
                    }
                ],
                "estimated_duration": sample_analysis.duration,
                "summary": "Add subtitles",
            },
            "burn_subtitles": False,
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert len(scheduled) == 1
    asyncio.run(scheduled.pop())

    job = _wait_for_job(job_id)
    assert job["status"] == "completed"
    assert job["result"]["subtitle_export_mode"] == "sidecar"


def test_render_request_rejects_unknown_preset(sample_analysis, tmp_path: Path):
    server.videos.clear()
    server.jobs.clear()

    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"source")

    video_id = "video-render-invalid"
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

    client = TestClient(server.app)
    response = client.post(
        "/api/render",
        json={
            "video_id": video_id,
            "plan": {
                "instruction": "render",
                "operations": [],
                "estimated_duration": sample_analysis.duration,
                "summary": "Render only",
            },
            "render_preset": "ultra",
        },
    )

    assert response.status_code == 422
