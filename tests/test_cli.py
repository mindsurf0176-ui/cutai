"""Focused CLI regression tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cutai.cli import app
from cutai.models.types import EditPlan, SubtitleOperation


runner = CliRunner()


def test_edit_does_not_report_stale_subtitle_sidecar(
    monkeypatch,
    sample_analysis,
    tmp_path: Path,
):
    video_path = tmp_path / "input.mp4"
    output_path = tmp_path / "input_edited.mp4"
    stale_ass_path = output_path.with_suffix(".ass")
    video_path.write_bytes(b"video")
    stale_ass_path.write_text("stale subtitle file")

    monkeypatch.setattr("cutai.analyzer.analyze_video", lambda *_args, **_kwargs: sample_analysis)
    monkeypatch.setattr(
        "cutai.planner.create_edit_plan",
        lambda *_args, **_kwargs: EditPlan(
            instruction="remove silence",
            operations=[],
            estimated_duration=sample_analysis.duration,
            summary="No-op",
        ),
    )
    monkeypatch.setattr(
        "cutai.editor.renderer.render",
        lambda *_args, **_kwargs: str(output_path),
    )

    result = runner.invoke(
        app,
        [
            "edit",
            str(video_path),
            "-i",
            "remove silence",
            "--no-llm",
        ],
    )

    assert result.exit_code == 0
    assert "Subtitles:" not in result.output


def test_edit_reports_subtitle_sidecar_when_plan_has_subtitles(
    monkeypatch,
    sample_analysis,
    tmp_path: Path,
):
    video_path = tmp_path / "input.mp4"
    output_path = tmp_path / "input_edited.mp4"
    ass_path = output_path.with_suffix(".ass")
    video_path.write_bytes(b"video")
    ass_path.write_text("subtitle file")

    monkeypatch.setattr("cutai.analyzer.analyze_video", lambda *_args, **_kwargs: sample_analysis)
    monkeypatch.setattr(
        "cutai.planner.create_edit_plan",
        lambda *_args, **_kwargs: EditPlan(
            instruction="add subtitles",
            operations=[SubtitleOperation()],
            estimated_duration=sample_analysis.duration,
            summary="Add subtitles",
        ),
    )
    monkeypatch.setattr(
        "cutai.editor.renderer.render",
        lambda *_args, **_kwargs: str(output_path),
    )

    result = runner.invoke(
        app,
        [
            "edit",
            str(video_path),
            "-i",
            "add subtitles",
            "--no-llm",
        ],
    )

    assert result.exit_code == 0
    assert "Subtitles:" in result.output
    assert ass_path.name in result.output
