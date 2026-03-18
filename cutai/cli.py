"""CutAI CLI — beautiful terminal interface using Typer + Rich.

Commands:
  cutai analyze <video>  — Analyze video (scenes, transcript, quality)
  cutai plan <video>     — Analyze + generate edit plan (no render)
  cutai edit <video>     — Full pipeline: analyze → plan → edit → render
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="cutai",
    help="🎬 CutAI — AI video editor with natural language instructions.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _validate_video(path: str) -> Path:
    """Validate that the video file exists."""
    p = Path(path)
    if not p.exists():
        console.print(f"[red]Error:[/red] Video file not found: {path}")
        raise typer.Exit(1)
    return p


def _handle_error(exc: Exception) -> None:
    """Handle exceptions with user-friendly Rich error panels."""
    import subprocess as _sp
    import traceback

    if isinstance(exc, FileNotFoundError):
        console.print(Panel(
            f"[red bold]File Not Found[/red bold]\n\n{exc}",
            style="red",
            title="❌ Error",
        ))
        raise typer.Exit(1)
    elif isinstance(exc, (_sp.CalledProcessError, _sp.TimeoutExpired)):
        detail = str(exc)
        if hasattr(exc, 'stderr') and exc.stderr:
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else str(exc.stderr)
            detail += f"\n\n[dim]stderr:[/dim] {stderr[:500]}"
        console.print(Panel(
            f"[red bold]FFmpeg / Subprocess Error[/red bold]\n\n{detail}",
            style="red",
            title="❌ Error",
        ))
        raise typer.Exit(1)
    elif isinstance(exc, RuntimeError):
        console.print(Panel(
            f"[red bold]Runtime Error[/red bold]\n\n{exc}",
            style="red",
            title="❌ Error",
        ))
        raise typer.Exit(1)
    elif isinstance(exc, ValueError):
        console.print(Panel(
            f"[red bold]Invalid Input[/red bold]\n\n{exc}",
            style="red",
            title="❌ Error",
        ))
        raise typer.Exit(1)
    else:
        tb = traceback.format_exc()
        console.print(Panel(
            f"[red bold]Unexpected Error[/red bold]\n\n{exc}\n\n"
            f"[dim]{tb}[/dim]\n\n"
            "[yellow]Please report this bug at https://github.com/minseo/cutai/issues[/yellow]",
            style="red",
            title="🐛 Bug",
        ))
        raise typer.Exit(1)


@app.command()
def analyze(
    video: str = typer.Argument(help="Path to the video file"),
    output: str | None = typer.Option(None, "--output", "-o", help="Save analysis JSON to file"),
    model: str = typer.Option("base", "--model", "-m", help="Whisper model size (tiny/base/small/medium/large)"),
    skip_transcription: bool = typer.Option(False, "--no-transcript", help="Skip Whisper transcription"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Analyze a video file — detect scenes, transcribe audio, check quality."""
    _setup_logging(verbose)
    video_path = _validate_video(video)

    try:
        console.print(
            Panel(f"🎬 Analyzing [bold]{video_path.name}[/bold]", style="blue")
        )

        from cutai.analyzer import analyze_video

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing video...", total=None)
            analysis = analyze_video(
                str(video_path),
                whisper_model=model,
                skip_transcription=skip_transcription,
            )
            progress.update(task, completed=True)

        # Display results
        _display_analysis(analysis)

        # Save to file if requested
        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(analysis.model_dump(), f, indent=2, ensure_ascii=False)
            console.print(f"\n📄 Analysis saved to [bold]{output}[/bold]")
    except typer.Exit:
        raise
    except Exception as exc:
        _handle_error(exc)


@app.command()
def plan(
    video: str = typer.Argument(help="Path to the video file"),
    instruction: str = typer.Option(..., "--instruction", "-i", help="Natural language editing instruction"),
    output: str | None = typer.Option(None, "--output", "-o", help="Save edit plan JSON to file"),
    model: str = typer.Option("base", "--model", "-m", help="Whisper model size"),
    llm: str = typer.Option("gpt-4o", "--llm", help="LLM model for planning"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Use rule-based planning only (no API key needed)"),
    skip_transcription: bool = typer.Option(False, "--no-transcript", help="Skip Whisper transcription"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Analyze a video and generate an edit plan (without rendering)."""
    _setup_logging(verbose)
    video_path = _validate_video(video)

    try:
        console.print(
            Panel(
                f"🎬 Planning edit for [bold]{video_path.name}[/bold]\n"
                f"📝 Instruction: [italic]{instruction}[/italic]",
                style="blue",
            )
        )

        from cutai.analyzer import analyze_video
        from cutai.planner import create_edit_plan

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            t1 = progress.add_task("Analyzing video...", total=None)
            analysis = analyze_video(
                str(video_path),
                whisper_model=model,
                skip_transcription=skip_transcription,
            )
            progress.update(t1, completed=True)

            t2 = progress.add_task("Generating edit plan...", total=None)
            edit_plan = create_edit_plan(
                analysis,
                instruction,
                llm_model=llm,
                use_llm=not no_llm,
            )
            progress.update(t2, completed=True)

        _display_analysis(analysis)
        _display_plan(edit_plan)

        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(edit_plan.model_dump(), f, indent=2, ensure_ascii=False)
            console.print(f"\n📄 Edit plan saved to [bold]{output}[/bold]")
    except typer.Exit:
        raise
    except Exception as exc:
        _handle_error(exc)


@app.command()
def edit(
    video: str = typer.Argument(help="Path to the video file"),
    instruction: str = typer.Option(..., "--instruction", "-i", help="Natural language editing instruction"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output video file path"),
    model: str = typer.Option("base", "--model", "-m", help="Whisper model size"),
    llm: str = typer.Option("gpt-4o", "--llm", help="LLM model for planning"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Use rule-based planning only"),
    skip_transcription: bool = typer.Option(False, "--no-transcript", help="Skip Whisper transcription"),
    burn_subtitles: bool = typer.Option(False, "--burn-subtitles", help="Burn subtitles into video (slow, re-encodes). Default: save as .ass sidecar file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Full pipeline: analyze → plan → edit → render.

    Example:
        cutai edit video.mp4 -i "remove silence and add subtitles"
    """
    _setup_logging(verbose)
    video_path = _validate_video(video)

    # Default output path
    if not output:
        stem = video_path.stem
        output = str(video_path.parent / f"{stem}_edited.mp4")

    try:
        console.print(
            Panel(
                f"🎬 Editing [bold]{video_path.name}[/bold]\n"
                f"📝 Instruction: [italic]{instruction}[/italic]\n"
                f"📁 Output: [dim]{output}[/dim]",
                style="blue",
            )
        )

        from cutai.analyzer import analyze_video
        from cutai.editor.renderer import render
        from cutai.planner import create_edit_plan

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Analyze
            t1 = progress.add_task("Step 1/3: Analyzing video...", total=None)
            analysis = analyze_video(
                str(video_path),
                whisper_model=model,
                skip_transcription=skip_transcription,
            )
            progress.update(t1, completed=True)

            # Step 2: Plan
            t2 = progress.add_task("Step 2/3: Generating edit plan...", total=None)
            edit_plan = create_edit_plan(
                analysis,
                instruction,
                llm_model=llm,
                use_llm=not no_llm,
            )
            progress.update(t2, completed=True)

            # Step 3: Render
            t3 = progress.add_task("Step 3/3: Rendering video...", total=None)
            result = render(str(video_path), edit_plan, analysis, output, burn_subtitles=burn_subtitles)
            progress.update(t3, completed=True)

        _display_analysis(analysis)
        _display_plan(edit_plan)

        # Build success message
        success_lines = [
            "✅ [bold green]Done![/bold green]",
            f"📁 Output: [bold]{result}[/bold]",
        ]
        ass_path = Path(output).with_suffix(".ass")
        if ass_path.exists():
            success_lines.append(f"📝 Subtitles: {ass_path}")

        console.print()
        console.print(
            Panel(
                "\n".join(success_lines),
                style="green",
            )
        )
    except typer.Exit:
        raise
    except Exception as exc:
        _handle_error(exc)


# ── Display helpers ──────────────────────────────────────────────────────────


def _display_analysis(analysis) -> None:
    """Display video analysis in a rich table."""
    from cutai.models.types import VideoAnalysis

    table = Table(title="📊 Video Analysis", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    table.add_row("File", Path(analysis.file_path).name)
    table.add_row("Duration", f"{analysis.duration:.1f}s ({analysis.duration/60:.1f}min)")
    table.add_row("Resolution", f"{analysis.width}×{analysis.height}")
    table.add_row("FPS", f"{analysis.fps:.1f}")
    table.add_row("Scenes", str(len(analysis.scenes)))
    table.add_row("Transcript segments", str(len(analysis.transcript)))
    table.add_row("Silent segments", str(len(analysis.quality.silent_segments)))
    table.add_row(
        "Silence ratio",
        f"{analysis.quality.overall_silence_ratio * 100:.1f}%",
    )

    console.print()
    console.print(table)

    # Show scenes summary
    if analysis.scenes:
        scene_table = Table(title="🎬 Scenes", show_header=True, header_style="bold")
        scene_table.add_column("#", style="dim", width=4)
        scene_table.add_column("Time", width=16)
        scene_table.add_column("Duration", width=10)
        scene_table.add_column("Speech", width=8)
        scene_table.add_column("Silent", width=8)

        for scene in analysis.scenes[:20]:  # Limit display
            scene_table.add_row(
                str(scene.id),
                f"{scene.start_time:.1f}–{scene.end_time:.1f}",
                f"{scene.duration:.1f}s",
                "✅" if scene.has_speech else "❌",
                "🔇" if scene.is_silent else "🔊",
            )

        if len(analysis.scenes) > 20:
            scene_table.add_row("...", f"+{len(analysis.scenes)-20} more", "", "", "")

        console.print(scene_table)


def _display_plan(plan) -> None:
    """Display edit plan in a rich format."""
    from cutai.models.types import CutOperation, EditPlan, SubtitleOperation

    console.print()
    console.print(
        Panel(
            f"📋 [bold]Edit Plan[/bold]\n"
            f"Instruction: [italic]{plan.instruction}[/italic]\n"
            f"Summary: {plan.summary}\n"
            f"Estimated duration: {plan.estimated_duration:.1f}s ({plan.estimated_duration/60:.1f}min)\n"
            f"Operations: {len(plan.operations)}",
            style="yellow",
        )
    )

    if plan.operations:
        ops_table = Table(title="✂️  Operations", show_header=True, header_style="bold")
        ops_table.add_column("#", style="dim", width=4)
        ops_table.add_column("Type", width=10)
        ops_table.add_column("Details")

        for i, op in enumerate(plan.operations[:30]):
            if isinstance(op, CutOperation):
                details = f"{op.action} [{op.start_time:.1f}–{op.end_time:.1f}s] — {op.reason}"
            elif isinstance(op, SubtitleOperation):
                details = f"style={op.style}, position={op.position}, lang={op.language}"
            else:
                details = str(op.model_dump())

            ops_table.add_row(str(i), op.type, details)

        console.print(ops_table)


def app_entry() -> None:
    """Entry point for the CLI (used by pyproject.toml)."""
    app()


if __name__ == "__main__":
    app_entry()
