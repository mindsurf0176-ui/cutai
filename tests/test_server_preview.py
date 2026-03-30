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


def test_preview_job_start_and_download(monkeypatch, sample_analysis, tmp_path: Path):
    server.videos.clear()
    server.jobs.clear()
    monkeypatch.setattr(server, "OUTPUT_DIR", tmp_path)

    source_path = tmp_path / "input.mp4"
    source_path.write_bytes(b"source")

    video_id = "video-preview"
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

    def fake_render_preview(_video_path, _plan, _analysis, output_path=None, resolution=360):
        preview_path = Path(output_path or tmp_path / "generated_preview.mp4")
        preview_path.write_bytes(f"preview-{resolution}".encode())
        return str(preview_path)

    monkeypatch.setattr("cutai.preview.render_preview", fake_render_preview)
    scheduled: list[object] = []
    monkeypatch.setattr(server.asyncio, "create_task", lambda coro: scheduled.append(coro))

    client = TestClient(server.app)
    plan = EditPlan(
        instruction="preview",
        operations=[],
        estimated_duration=sample_analysis.duration,
        summary="Preview only",
    )

    start_response = client.post(
        "/api/preview",
        json={
            "video_id": video_id,
            "plan": plan.model_dump(),
            "resolution": 480,
        },
    )

    assert start_response.status_code == 200
    job_id = start_response.json()["job_id"]
    assert len(scheduled) == 1
    asyncio.run(scheduled.pop())

    job = _wait_for_job(job_id)
    assert job["type"] == "preview"
    assert job["status"] == "completed"
    assert job["result"]["resolution"] == 480

    job_response = client.get(f"/api/jobs/{job_id}")
    assert job_response.status_code == 200
    assert job_response.json()["type"] == "preview"

    video_response = client.get(f"/api/preview/{job_id}/video")
    assert video_response.status_code == 200
    assert video_response.headers["content-type"] == "video/mp4"

    download_response = client.get(f"/api/preview/{job_id}/download")
    assert download_response.status_code == 200
    assert download_response.content == b"preview-480"


def test_render_download_rejects_preview_job(tmp_path: Path):
    server.videos.clear()
    server.jobs.clear()

    preview_path = tmp_path / "preview.mp4"
    preview_path.write_bytes(b"preview")
    server.jobs["preview-job"] = {
        "type": "preview",
        "status": "completed",
        "progress": 100.0,
        "result": {"output_path": str(preview_path), "resolution": 360},
        "error": None,
    }

    client = TestClient(server.app)
    response = client.get("/api/render/preview-job/download")

    assert response.status_code == 400
    assert "expected render" in response.text
