"""Focused CLI regression tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cutai.cli import app
from cutai.models.types import EditDNA, EditPlan, SubtitleOperation


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
            "--sidecar-subtitles",
        ],
    )

    assert result.exit_code == 0
    assert "Subtitles:" in result.output
    assert ass_path.name in result.output




def test_edit_burns_subtitles_by_default(
    monkeypatch,
    sample_analysis,
    tmp_path: Path,
):
    video_path = tmp_path / "input.mp4"
    output_path = tmp_path / "input_edited.mp4"
    video_path.write_bytes(b"video")

    calls = {}

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

    def fake_render(_video_path, _plan, _analysis, _output, *, burn_subtitles=True, **_kwargs):
        calls["burn_subtitles"] = burn_subtitles
        return str(output_path)

    monkeypatch.setattr("cutai.editor.renderer.render", fake_render)

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
    assert calls == {"burn_subtitles": True}
    assert "Subtitles:" not in result.output

def test_preview_accepts_style_without_instruction(
    monkeypatch,
    sample_analysis,
    tmp_path: Path,
):
    video_path = tmp_path / "input.mp4"
    preview_path = tmp_path / "input_preview.mp4"
    video_path.write_bytes(b"video")

    applied = {}

    monkeypatch.setattr("cutai.analyzer.analyze_video", lambda *_args, **_kwargs: sample_analysis)
    monkeypatch.setattr("cutai.style.load_style", lambda *_args, **_kwargs: EditDNA(name="cinematic"))

    def fake_apply_style(analysis, style_dna, instruction=""):
        applied["analysis"] = analysis
        applied["style_name"] = style_dna.name
        applied["instruction"] = instruction
        return EditPlan(
            instruction="style preview",
            operations=[],
            estimated_duration=analysis.duration,
            summary="Preview style only",
        )

    monkeypatch.setattr("cutai.style.apply_style", fake_apply_style)
    monkeypatch.setattr(
        "cutai.preview.render_preview",
        lambda *_args, **_kwargs: str(preview_path),
    )

    result = runner.invoke(
        app,
        [
            "preview",
            str(video_path),
            "--style",
            "cinematic.yaml",
        ],
    )

    assert result.exit_code == 0
    assert "Preview ready!" in result.output
    assert applied == {
        "analysis": sample_analysis,
        "style_name": "cinematic",
        "instruction": "",
    }


def test_preview_requires_instruction_or_style(tmp_path: Path):
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")

    result = runner.invoke(app, ["preview", str(video_path)])

    assert result.exit_code == 1
    assert "Provide --instruction or --style (or both)." in result.output
