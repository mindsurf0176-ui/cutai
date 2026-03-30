"""CutAI Chat — Interactive REPL-based video editing session.

Users can iteratively refine edits through natural language conversation,
with full undo/redo support and live preview generation.

Example:
    $ cutai chat ./vlog.mp4

    > 카페 가는 부분만 뽑아줘
    ✅ Applied: Keep 3 cafe scenes (4:32)

    > /preview
    🎬 Generating preview (360p)...

    > /render
    🎬 Rendering final video...
"""

from __future__ import annotations

import logging
from contextlib import suppress
from pathlib import Path

with suppress(ImportError):
    import readline  # noqa: F401 — enables input history

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cutai.models.types import (
    BGMOperation,
    ColorGradeOperation,
    CutOperation,
    EditPlan,
    SpeedOperation,
    SubtitleOperation,
    TransitionOperation,
    UserPreferences,
    VideoAnalysis,
)

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency at module level
def _load_learning():
    """Lazy import of learning module."""
    from cutai.learning import (
        load_preferences,
        record_feedback,
        record_instruction,
        save_preferences,
        suggest_defaults,
    )
    return load_preferences, save_preferences, record_instruction, record_feedback, suggest_defaults


class ChatSession:
    """Interactive editing session with undo support.

    Each natural language instruction adds operations to the current plan.
    Slash commands control the session (undo, preview, render, etc.).
    """

    def __init__(
        self,
        video_path: str,
        analysis: VideoAnalysis,
        whisper_model: str = "base",
        llm_model: str = "gpt-4o",
        use_llm: bool = True,
        default_output: str | None = None,
    ) -> None:
        self.video_path = video_path
        self.analysis = analysis
        self.whisper_model = whisper_model
        self.llm_model = llm_model
        self.use_llm = use_llm
        self.default_output = default_output

        self.plan_history: list[EditPlan] = []  # stack for undo
        self.current_plan = EditPlan(
            instruction="interactive",
            operations=[],
            estimated_duration=analysis.duration,
            summary="",
        )
        self.console = Console()

        # Track what was last applied for undo display
        self._last_action_desc: str = ""

        # Load personal learning preferences
        self._preferences: UserPreferences | None = None
        try:
            load_prefs, _, _, _, _ = _load_learning()
            self._preferences = load_prefs()
            if self._preferences.instruction_history:
                logger.debug(
                    "Loaded %d instruction memories",
                    len(self._preferences.instruction_history),
                )
        except Exception as exc:
            logger.debug("Could not load learning preferences: %s", exc)
            self._preferences = None

    def run(self) -> None:
        """Main REPL loop."""
        self._show_welcome()

        while True:
            try:
                user_input = input("\n\033[1;36m>\033[0m ")
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[dim]Goodbye! 👋[/dim]")
                break

            if not user_input.strip():
                continue

            stripped = user_input.strip()
            if stripped.startswith("/"):
                try:
                    self._handle_command(stripped)
                except SystemExit:
                    break
            else:
                self._handle_instruction(stripped)

    # ── Welcome & Help ───────────────────────────────────────────────────

    def _show_welcome(self) -> None:
        """Display welcome banner with video info."""
        duration_str = _format_time(self.analysis.duration)
        resolution = f"{self.analysis.width}×{self.analysis.height}"
        fps = f"{self.analysis.fps:.0f}fps"
        scenes = len(self.analysis.scenes)
        segments = len(self.analysis.transcript)

        self.console.print()
        self.console.print(Panel(
            f"[bold]🎬 CutAI Chat — Interactive Editor[/bold]\n"
            f"📁 Video: [cyan]{Path(self.video_path).name}[/cyan] "
            f"({duration_str}, {resolution}, {fps})\n"
            f"📊 {scenes} scenes detected, {segments} transcript segments\n\n"
            f"[dim]Type editing instructions. "
            f"Commands: /undo, /plan, /preview, /render, /style, /reset, /help, /quit[/dim]",
            style="blue",
        ))

    def _cmd_help(self, arg: str) -> None:
        """Show help message."""
        help_table = Table(
            title="📖 Commands",
            show_header=True,
            header_style="bold",
        )
        help_table.add_column("Command", style="cyan", width=18)
        help_table.add_column("Description")

        help_table.add_row("/undo", "Undo the last instruction")
        help_table.add_row("/plan", "Show the current edit plan")
        help_table.add_row("/preview [res]", "Generate low-res preview (default 360p)")
        help_table.add_row("/render [path]", "Render the final full-quality video")
        help_table.add_row("/style load <file>", "Load and apply an Edit DNA style file")
        help_table.add_row("/style show", "Show the current style (if loaded)")
        help_table.add_row("/highlights [duration] [style]", "Generate highlights (best-moments/narrative/shorts)")
        help_table.add_row("/feedback good|bad|adjusted [note]", "Rate the current edit result")
        help_table.add_row("/prefs", "Show learned editing preferences")
        help_table.add_row("/reset", "Clear all operations and start over")
        help_table.add_row("/help", "Show this help message")
        help_table.add_row("/quit, /exit", "Exit the chat session")

        self.console.print()
        self.console.print(help_table)
        self.console.print()
        self.console.print("[dim]Or just type a natural language instruction, e.g.:[/dim]")
        self.console.print("[dim]  > 무음 부분 제거하고 자막 넣어줘[/dim]")
        self.console.print("[dim]  > 시네마틱하게 바꿔줘[/dim]")

    # ── Command dispatch ─────────────────────────────────────────────────

    def _handle_command(self, cmd: str) -> None:
        """Handle slash commands."""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        commands = {
            "/undo": self._cmd_undo,
            "/plan": self._cmd_show_plan,
            "/preview": self._cmd_preview,
            "/render": self._cmd_render,
            "/style": self._cmd_style,
            "/highlights": self._cmd_highlights,
            "/feedback": self._cmd_feedback,
            "/prefs": self._cmd_prefs,
            "/reset": self._cmd_reset,
            "/help": self._cmd_help,
            "/quit": self._cmd_quit,
            "/exit": self._cmd_quit,
        }

        handler = commands.get(command)
        if handler:
            handler(arg)
        else:
            self.console.print(
                f"[red]Unknown command: {command}[/red]. Type /help for available commands."
            )

    # ── Natural language instruction handling ────────────────────────────

    def _handle_instruction(self, instruction: str) -> None:
        """Process a natural language editing instruction.

        Uses the planner to generate operations from the instruction,
        then merges them into the current plan with smart replacement logic.
        Records the instruction in learning history.
        """
        from cutai.planner import create_edit_plan

        try:
            new_plan = create_edit_plan(
                self.analysis,
                instruction,
                llm_model=self.llm_model,
                use_llm=self.use_llm,
                preferences=self._preferences,
            )
        except Exception as exc:
            self.console.print(f"[red]❌ Planning failed:[/red] {exc}")
            logger.exception("Planning failed for instruction: %s", instruction)
            return

        if not new_plan.operations:
            self.console.print(
                "[yellow]⚠️  Couldn't determine edit operations from that instruction.[/yellow]\n"
                "[dim]Try rephrasing, or use --llm for smarter planning.[/dim]"
            )
            return

        # Save current state for undo
        self.plan_history.append(self.current_plan.model_copy(deep=True))

        # Merge new operations into current plan
        merged_ops = self._merge_operations(
            self.current_plan.operations,
            new_plan.operations,
        )

        # Re-estimate duration
        estimated = self._estimate_duration(merged_ops)

        self.current_plan = EditPlan(
            instruction="interactive",
            operations=merged_ops,
            estimated_duration=estimated,
            summary=self._build_summary(merged_ops),
        )

        # Build feedback message
        self._last_action_desc = new_plan.summary or instruction
        duration_str = _format_time(estimated)
        original_str = _format_time(self.analysis.duration)

        self.console.print(f"[green]✅ Applied:[/green] {self._last_action_desc}")
        self.console.print(
            f"   [dim]Current timeline: {duration_str} (was {original_str})[/dim]"
        )

        # Record instruction in learning history (accepted=True initially;
        # undo will mark it as not accepted)
        self._record_learning(instruction, new_plan, accepted=True)

    def _merge_operations(
        self,
        existing: list,
        new: list,
    ) -> list:
        """Merge new operations into existing ones with smart replacement.

        Rules:
        - CutOperation and SpeedOperation: additive (append)
        - ColorGradeOperation: replace existing (don't stack)
        - BGMOperation: replace existing
        - SubtitleOperation: replace existing
        - TransitionOperation: additive
        """
        # Start with a copy of existing ops
        result = list(existing)

        for op in new:
            if isinstance(op, (ColorGradeOperation, BGMOperation, SubtitleOperation)):
                # Replace: remove existing ops of the same type, then add new
                result = [
                    r for r in result if not isinstance(r, type(op))
                ]
                result.append(op)
            else:
                # Additive: cuts, speed, transitions
                result.append(op)

        return result

    def _estimate_duration(self, operations: list) -> float:
        """Estimate output duration after all operations."""
        removed = 0.0
        speed_factor = 1.0

        for op in operations:
            if isinstance(op, CutOperation) and op.action == "remove":
                removed += op.end_time - op.start_time
            elif isinstance(op, SpeedOperation) and op.start_time <= 0.05:
                speed_factor = op.factor

        base = max(0.0, self.analysis.duration - removed)
        return base / speed_factor if speed_factor > 0 else base

    def _build_summary(self, operations: list) -> str:
        """Build a human-readable summary from operations."""
        parts: list[str] = []
        cuts = [op for op in operations if isinstance(op, CutOperation)]
        subs = [op for op in operations if isinstance(op, SubtitleOperation)]
        bgms = [op for op in operations if isinstance(op, BGMOperation)]
        colors = [op for op in operations if isinstance(op, ColorGradeOperation)]
        speeds = [op for op in operations if isinstance(op, SpeedOperation)]
        transitions = [op for op in operations if isinstance(op, TransitionOperation)]

        if cuts:
            keeps = [c for c in cuts if c.action == "keep"]
            removes = [c for c in cuts if c.action == "remove"]
            if keeps:
                parts.append(f"Keep {len(keeps)} segments")
            if removes:
                parts.append(f"Remove {len(removes)} segments")
        if subs:
            parts.append(f"Subtitles ({subs[0].position})")
        if bgms:
            parts.append(f"BGM ({bgms[0].mood})")
        if colors:
            parts.append(f"Color grade ({colors[0].preset})")
        if speeds:
            parts.append(f"Speed ×{speeds[0].factor}")
        if transitions:
            parts.append(f"{len(transitions)} transitions")

        return "; ".join(parts) if parts else "No operations"

    # ── Slash command implementations ────────────────────────────────────

    def _cmd_undo(self, arg: str) -> None:
        """Undo the last instruction."""
        if not self.plan_history:
            self.console.print("[yellow]Nothing to undo[/yellow]")
            return

        undone_desc = self._last_action_desc or "last action"
        self.current_plan = self.plan_history.pop()

        # Mark the last instruction as not accepted in learning
        if self._preferences and self._preferences.instruction_history:
            self._preferences.instruction_history[-1].was_accepted = False
            self._save_learning()

        # Update last action desc from remaining history
        self._last_action_desc = ""

        duration_str = _format_time(self.current_plan.estimated_duration)
        self.console.print(f"[cyan]↩️  Undone:[/cyan] {undone_desc}")
        self.console.print(f"   [dim]Current timeline: {duration_str}[/dim]")

    def _cmd_show_plan(self, arg: str) -> None:
        """Display the current edit plan as a rich table."""
        ops = self.current_plan.operations

        if not ops:
            self.console.print("[yellow]📋 No operations in the current plan.[/yellow]")
            return

        self.console.print()
        table = Table(
            title="📋 Current Edit Plan",
            show_header=True,
            header_style="bold",
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Type", width=12)
        table.add_column("Details")

        for i, op in enumerate(ops, 1):
            op_type = op.type
            details = _format_operation(op)
            table.add_row(str(i), f"[{op_type}]", details)

        self.console.print(table)

        duration_str = _format_time(self.current_plan.estimated_duration)
        original_str = _format_time(self.analysis.duration)
        self.console.print(
            f"\n[dim]Estimated duration: {duration_str} (original: {original_str})[/dim]"
        )

    def _cmd_preview(self, arg: str) -> None:
        """Generate a low-resolution preview."""
        from cutai.preview import render_preview

        resolution = 360
        if arg.strip():
            try:
                resolution = int(arg.strip().rstrip("p"))
            except ValueError:
                self.console.print(
                    f"[red]Invalid resolution: {arg}[/red]. Use a number like 360 or 480."
                )
                return

        self.console.print(f"[blue]🎬 Generating preview ({resolution}p)...[/blue]")

        try:
            preview_path = render_preview(
                self.video_path,
                self.current_plan,
                self.analysis,
                resolution=resolution,
            )
            self.console.print(f"[green]📁 Preview saved:[/green] {preview_path}")
        except Exception as exc:
            self.console.print(f"[red]❌ Preview failed:[/red] {exc}")
            logger.exception("Preview generation failed")

    def _cmd_render(self, arg: str) -> None:
        """Render the final full-quality video."""
        from cutai.editor.renderer import render

        output_path = arg.strip() or self.default_output
        if not output_path:
            stem = Path(self.video_path).stem
            output_path = str(Path(self.video_path).parent / f"{stem}_edited.mp4")

        if not self.current_plan.operations:
            self.console.print(
                "[yellow]⚠️  No operations to render. Add some instructions first.[/yellow]"
            )
            return

        self.console.print("[blue]🎬 Rendering final video...[/blue]")

        try:
            result = render(
                self.video_path,
                self.current_plan,
                self.analysis,
                output_path,
            )
            self.console.print(f"[green]📁 Output:[/green] {result}")

            # Check for sidecar subtitle file
            ass_path = Path(output_path).with_suffix(".ass")
            if ass_path.exists():
                self.console.print(f"[dim]📝 Subtitles: {ass_path}[/dim]")

            # Mark all instructions as accepted on successful render
            if self._preferences:
                for mem in self._preferences.instruction_history:
                    mem.was_accepted = True
                self._save_learning()
        except Exception as exc:
            self.console.print(f"[red]❌ Render failed:[/red] {exc}")
            logger.exception("Render failed")

    def _cmd_style(self, arg: str) -> None:
        """Handle style commands: /style load <file> or /style show."""
        parts = arg.strip().split(maxsplit=1)
        subcmd = parts[0].lower() if parts else ""

        if subcmd == "load" and len(parts) > 1:
            self._style_load(parts[1])
        elif subcmd == "show":
            self._style_show()
        else:
            self.console.print(
                "[dim]Usage: /style load <file.yaml> or /style show[/dim]"
            )

    def _style_load(self, style_path: str) -> None:
        """Load and apply an Edit DNA style file."""
        from cutai.style import apply_style, load_style

        path = Path(style_path)
        if not path.exists():
            self.console.print(f"[red]Style file not found: {style_path}[/red]")
            return

        try:
            style_dna = load_style(style_path)
            new_plan = apply_style(self.analysis, style_dna, instruction="")
        except Exception as exc:
            self.console.print(f"[red]❌ Failed to load style:[/red] {exc}")
            return

        # Save current for undo
        self.plan_history.append(self.current_plan.model_copy(deep=True))
        self.current_plan = new_plan
        self._last_action_desc = f"Apply style: {style_dna.name}"

        duration_str = _format_time(self.current_plan.estimated_duration)
        self.console.print(
            f"[green]✅ Applied style:[/green] {style_dna.name} — {style_dna.description}"
        )
        self.console.print(f"   [dim]Current timeline: {duration_str}[/dim]")

    def _style_show(self) -> None:
        """Show summary of current plan operations as pseudo-style."""
        if not self.current_plan.operations:
            self.console.print("[yellow]No style applied (no operations).[/yellow]")
            return

        self.console.print("\n[bold]Current style summary:[/bold]")
        self.console.print(f"  {self.current_plan.summary or 'No summary'}")

    def _cmd_highlights(self, arg: str) -> None:
        """Generate highlights from the current video.

        Usage: /highlights [duration_seconds] [style]
        Styles: best-moments (default), narrative, shorts
        """
        from cutai.analyzer.engagement import compute_engagement_scores
        from cutai.highlight import auto_highlight_duration, generate_highlights

        parts = arg.strip().split()
        target_duration: float | None = None
        hl_style = "best-moments"

        for part in parts:
            try:
                target_duration = float(part)
            except ValueError:
                if part in ("best-moments", "narrative", "shorts"):
                    hl_style = part

        self.console.print("[blue]📊 Computing engagement scores...[/blue]")

        try:
            report = compute_engagement_scores(self.analysis, self.video_path)
        except Exception as exc:
            self.console.print(f"[red]❌ Engagement analysis failed:[/red] {exc}")
            return

        if target_duration is None:
            target_duration = auto_highlight_duration(self.analysis.duration)

        self.console.print(
            f"[blue]🎬 Generating {hl_style} highlights "
            f"(target: {target_duration:.0f}s)...[/blue]"
        )

        try:
            new_plan = generate_highlights(
                self.video_path,
                self.analysis,
                report,
                target_duration=target_duration,
                style=hl_style,
            )
        except Exception as exc:
            self.console.print(f"[red]❌ Highlight generation failed:[/red] {exc}")
            return

        # Save current state for undo
        self.plan_history.append(self.current_plan.model_copy(deep=True))
        self.current_plan = new_plan
        self._last_action_desc = f"Highlights ({hl_style}, {target_duration:.0f}s)"

        duration_str = _format_time(new_plan.estimated_duration)
        original_str = _format_time(self.analysis.duration)

        self.console.print(
            f"[green]✅ Highlights generated:[/green] {len(new_plan.operations)} scenes, "
            f"{duration_str} (was {original_str})"
        )
        self.console.print(
            f"   [dim]Avg engagement: {report.avg_score:.1f} | "
            f"🟢 High: {report.high_count} | 🔴 Low: {report.low_count}[/dim]"
        )

    def _cmd_feedback(self, arg: str) -> None:
        """Record user feedback on the current edit.

        Usage: /feedback good|bad|adjusted [note]
        """
        parts = arg.strip().split(maxsplit=1)
        if not parts:
            self.console.print(
                "[dim]Usage: /feedback good|bad|adjusted [optional note][/dim]"
            )
            return

        feedback_type = parts[0].lower()
        if feedback_type not in ("good", "bad", "adjusted"):
            self.console.print(
                f"[red]Invalid feedback type: {feedback_type}[/red]. "
                "Use: good, bad, or adjusted"
            )
            return

        adjustment = parts[1] if len(parts) > 1 else None

        if self._preferences is None:
            self.console.print("[yellow]Learning system not available.[/yellow]")
            return

        try:
            _, save_prefs, _, rec_feedback, _ = _load_learning()
            instruction_desc = self._last_action_desc or "current edit"
            rec_feedback(self._preferences, instruction_desc, feedback_type, adjustment)
            save_prefs(self._preferences)
            self.console.print(f"[green]📝 Feedback recorded:[/green] {feedback_type}")
            if adjustment:
                self.console.print(f"   [dim]Note: {adjustment}[/dim]")
        except Exception as exc:
            self.console.print(f"[red]Failed to record feedback:[/red] {exc}")

    def _cmd_prefs(self, arg: str) -> None:
        """Show learned editing preferences."""
        if self._preferences is None:
            self.console.print("[yellow]Learning system not available.[/yellow]")
            return

        try:
            _, _, _, _, suggest_def = _load_learning()
            defaults = suggest_def(self._preferences)
        except Exception:
            defaults = {}

        prefs_table = Table(
            title="🧠 Learned Preferences",
            show_header=True,
            header_style="bold",
        )
        prefs_table.add_column("Property", style="dim")
        prefs_table.add_column("Value")

        prefs_table.add_row("Preferred style", self._preferences.preferred_style or "(none)")
        prefs_table.add_row("Subtitle position", self._preferences.preferred_subtitle_position)
        prefs_table.add_row("Color preset", self._preferences.preferred_color_preset or "(none)")
        prefs_table.add_row("BGM mood", self._preferences.preferred_bgm_mood or "(none)")
        prefs_table.add_row("Avg keep ratio", f"{self._preferences.avg_keep_ratio:.0%}")
        prefs_table.add_row("Instruction history", str(len(self._preferences.instruction_history)))
        prefs_table.add_row("Feedback entries", str(len(self._preferences.feedback_history)))

        self.console.print()
        self.console.print(prefs_table)

        if defaults:
            self.console.print(f"\n[dim]Suggested defaults: {defaults}[/dim]")

    def _record_learning(
        self,
        instruction: str,
        plan: EditPlan,
        accepted: bool,
    ) -> None:
        """Record an instruction in learning history (safe — never crashes)."""
        if self._preferences is None:
            return
        try:
            _, _, rec_instr, _, _ = _load_learning()
            rec_instr(self._preferences, instruction, plan, accepted)
            self._save_learning()
        except Exception as exc:
            logger.debug("Failed to record learning: %s", exc)

    def _save_learning(self) -> None:
        """Persist learning preferences to disk (safe — never crashes)."""
        if self._preferences is None:
            return
        try:
            _, save_prefs, _, _, _ = _load_learning()
            save_prefs(self._preferences)
        except Exception as exc:
            logger.debug("Failed to save learning: %s", exc)

    def _cmd_reset(self, arg: str) -> None:
        """Reset all operations."""
        if not self.current_plan.operations:
            self.console.print("[yellow]Already empty — nothing to reset.[/yellow]")
            return

        self.plan_history.append(self.current_plan.model_copy(deep=True))
        self.current_plan = EditPlan(
            instruction="interactive",
            operations=[],
            estimated_duration=self.analysis.duration,
            summary="",
        )
        self._last_action_desc = "Reset all operations"

        duration_str = _format_time(self.analysis.duration)
        self.console.print("[cyan]🔄 Reset — all operations cleared.[/cyan]")
        self.console.print(f"   [dim]Timeline restored to {duration_str}[/dim]")

    def _cmd_quit(self, arg: str) -> None:
        """Exit the chat session."""
        if self.current_plan.operations:
            self.console.print(
                f"[yellow]⚠️  You have {len(self.current_plan.operations)} pending operations. "
                f"Use /render first if you want to save.[/yellow]"
            )
        self.console.print("[dim]Goodbye! 👋[/dim]")
        raise SystemExit(0)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _format_time(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    if seconds < 0:
        return "0:00"
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_operation(op: object) -> str:
    """Format a single operation for display."""
    if isinstance(op, CutOperation):
        start_str = _format_time(op.start_time)
        end_str = _format_time(op.end_time)
        return f"{op.action} {start_str}–{end_str} — {op.reason}"
    elif isinstance(op, SubtitleOperation):
        return f"style={op.style}, position={op.position}, lang={op.language}"
    elif isinstance(op, BGMOperation):
        return f"mood={op.mood}, volume={op.volume}%"
    elif isinstance(op, ColorGradeOperation):
        return f"preset={op.preset}, intensity={op.intensity}"
    elif isinstance(op, SpeedOperation):
        start_str = _format_time(op.start_time)
        end_str = _format_time(op.end_time)
        return f"×{op.factor} ({start_str}–{end_str})"
    elif isinstance(op, TransitionOperation):
        return f"{op.style}, duration={op.duration}s, between scenes {op.between}"
    else:
        return str(op)
