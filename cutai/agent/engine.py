"""CutAI Agent Engine — goal-driven multi-step autonomous video editing.

Instead of a single analyze → plan → render pipeline, the Agent takes a
high-level goal (e.g. "make a 15-minute cafe vlog, warm and casual") and
autonomously:

1. Analyzes all input videos
2. Selects relevant scenes based on the goal
3. Decides style (from EDITSTYLE.md or infers from goal)
4. Plans and renders
5. Self-evaluates the result against the goal
6. Iterates if needed

Usage:
    engine = AgentEngine(
        inputs=["footage1.mp4", "footage2.mp4"],
        goal="15분짜리 카페 브이로그. 따뜻하고 캐주얼하게.",
        max_iterations=3,
    )
    result = engine.run()
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from cutai.config import load_config
from cutai.models.types import (
    EditDNA,
    EditPlan,
    EngagementReport,
    VideoAnalysis,
)

logger = logging.getLogger(__name__)


# ── Result types ─────────────────────────────────────────────────────────────


@dataclass
class EvaluationResult:
    """Self-evaluation of an agent iteration."""

    score: float  # 0-100
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    meets_goal: bool = False


@dataclass
class AgentIteration:
    """A single iteration of the agent loop."""

    iteration: int
    plan: EditPlan
    output_path: str
    evaluation: EvaluationResult | None = None


@dataclass
class AgentResult:
    """Final result of the agent run."""

    goal: str
    iterations: list[AgentIteration]
    final_output: str
    final_score: float
    total_iterations: int


# ── Agent Engine ─────────────────────────────────────────────────────────────


class AgentEngine:
    """Goal-driven autonomous video editing agent.

    Args:
        inputs: List of input video file paths.
        goal: High-level editing goal in natural language.
        output: Output file path.
        max_iterations: Maximum number of edit-evaluate iterations.
        min_score: Stop iterating when evaluation score reaches this threshold.
        editstyle: Optional path to an EDITSTYLE.md file.
        style: Optional path to an EditDNA YAML file.
        whisper_model: Whisper model size for transcription.
        llm_model: LLM model for planning.
        use_llm: Whether to use LLM for planning.
        burn_subtitles: Whether to burn subtitles into the video.
        verbose: Enable debug logging.
    """

    def __init__(
        self,
        inputs: list[str],
        goal: str,
        output: str = "agent_output.mp4",
        max_iterations: int = 3,
        min_score: float = 80.0,
        editstyle: str | None = None,
        style: str | None = None,
        whisper_model: str = "base",
        llm_model: str = "gpt-4o",
        use_llm: bool = True,
        burn_subtitles: bool = True,
        verbose: bool = False,
    ) -> None:
        self.inputs = [str(Path(p).resolve()) for p in inputs]
        self.goal = goal
        self.output = output
        self.max_iterations = max_iterations
        self.min_score = min_score
        self.editstyle = editstyle
        self.style = style
        self.whisper_model = whisper_model
        self.llm_model = llm_model
        self.use_llm = use_llm
        self.burn_subtitles = burn_subtitles
        self.verbose = verbose

        self._analyses: list[VideoAnalysis] = []
        self._merged_analysis: VideoAnalysis | None = None
        self._style_dna: EditDNA | None = None
        self._iterations: list[AgentIteration] = []
        self._config = load_config()

    # ── Public API ───────────────────────────────────────────────────────

    def run(self, on_progress: callable | None = None) -> AgentResult:
        """Execute the full agent loop.

        Args:
            on_progress: Optional callback(step: str, detail: str) for progress updates.

        Returns:
            AgentResult with final output and all iteration details.
        """
        self._emit(on_progress, "init", f"Agent starting with goal: {self.goal}")

        # Step 1: Analyze all inputs
        self._emit(on_progress, "analyze", f"Analyzing {len(self.inputs)} video(s)...")
        self._analyze_all()

        # Step 2: Resolve style
        self._emit(on_progress, "style", "Resolving editing style...")
        self._resolve_style()

        # Step 3: Iterative edit loop
        best_output = self.output
        best_score = 0.0

        for i in range(1, self.max_iterations + 1):
            self._emit(on_progress, "iteration", f"Iteration {i}/{self.max_iterations}")

            # Build instruction with context from previous iterations
            instruction = self._build_instruction(i)

            # Plan
            self._emit(on_progress, "plan", f"[{i}] Generating edit plan...")
            plan = self._create_plan(instruction)

            # Render
            iter_output = self._iter_output_path(i)
            self._emit(on_progress, "render", f"[{i}] Rendering to {iter_output}...")
            self._render(plan, iter_output)

            # Self-evaluate
            self._emit(on_progress, "evaluate", f"[{i}] Evaluating result...")
            evaluation = self._evaluate(plan, iter_output)

            iteration = AgentIteration(
                iteration=i,
                plan=plan,
                output_path=iter_output,
                evaluation=evaluation,
            )
            self._iterations.append(iteration)

            if evaluation.score > best_score:
                best_score = evaluation.score
                best_output = iter_output

            self._emit(
                on_progress,
                "score",
                f"[{i}] Score: {evaluation.score:.0f}/100 "
                f"({'✅ meets goal' if evaluation.meets_goal else '🔄 needs improvement'})",
            )

            if evaluation.meets_goal or evaluation.score >= self.min_score:
                self._emit(on_progress, "done", f"Goal met at iteration {i}!")
                break

        # Copy best result to final output path
        if best_output != self.output:
            import shutil
            shutil.copy2(best_output, self.output)

        result = AgentResult(
            goal=self.goal,
            iterations=self._iterations,
            final_output=self.output,
            final_score=best_score,
            total_iterations=len(self._iterations),
        )

        self._emit(
            on_progress,
            "complete",
            f"Agent complete. {result.total_iterations} iterations, "
            f"score: {result.final_score:.0f}/100",
        )

        return result

    # ── Step implementations ─────────────────────────────────────────────

    def _analyze_all(self) -> None:
        """Analyze all input videos."""
        from cutai.analyzer import analyze_video

        for path in self.inputs:
            logger.info("Analyzing %s", path)
            analysis = analyze_video(
                path,
                whisper_model=self.whisper_model,
                skip_transcription=False,
            )
            self._analyses.append(analysis)

        # Merge analyses if multiple inputs
        if len(self._analyses) == 1:
            self._merged_analysis = self._analyses[0]
        else:
            self._merged_analysis = self._merge_analyses()

    def _merge_analyses(self) -> VideoAnalysis:
        """Merge multiple video analyses into a combined analysis."""
        from cutai.multi import merge_analyses
        return merge_analyses(self._analyses)

    def _resolve_style(self) -> None:
        """Resolve the editing style from EDITSTYLE.md, YAML, or goal inference."""
        # Priority: explicit EDITSTYLE.md > YAML style > auto-detect > None
        if self.editstyle:
            from cutai.style.editstyle_parser import parse_editstyle
            result = parse_editstyle(self.editstyle)
            self._style_dna = result.dna
            logger.info("Using EDITSTYLE.md: %s", result.dna.name)
            return

        if self.style:
            from cutai.style.io import load_style
            self._style_dna = load_style(self.style)
            logger.info("Using style preset: %s", self._style_dna.name)
            return

        # Auto-detect EDITSTYLE.md in CWD or next to first input
        from cutai.style.editstyle_parser import parse_editstyle
        candidates = [
            Path.cwd() / "EDITSTYLE.md",
            Path(self.inputs[0]).parent / "EDITSTYLE.md",
            Path.home() / ".config" / "cutai" / "default-editstyle.md",
        ]
        for candidate in candidates:
            if candidate.is_file():
                try:
                    result = parse_editstyle(str(candidate))
                    self._style_dna = result.dna
                    logger.info("Auto-detected EDITSTYLE.md: %s", candidate)
                    return
                except Exception:
                    continue

        logger.info("No style found. Agent will infer from goal.")

    def _build_instruction(self, iteration: int) -> str:
        """Build the instruction for this iteration, incorporating feedback from previous ones."""
        parts = [self.goal]

        if self._style_dna:
            parts.append(f"\n[Style: {self._style_dna.name}]")

        # Add feedback from previous iterations
        if iteration > 1 and self._iterations:
            prev = self._iterations[-1]
            if prev.evaluation:
                ev = prev.evaluation
                if ev.weaknesses:
                    parts.append(f"\n[Previous issues to fix: {'; '.join(ev.weaknesses)}]")
                if ev.suggestions:
                    parts.append(f"\n[Suggestions: {'; '.join(ev.suggestions)}]")

        return "\n".join(parts)

    def _create_plan(self, instruction: str) -> EditPlan:
        """Create an edit plan using style or instruction-based planning."""
        assert self._merged_analysis is not None

        if self._style_dna:
            from cutai.style.applier import apply_style
            return apply_style(self._merged_analysis, self._style_dna, instruction=instruction)
        else:
            from cutai.planner import create_edit_plan
            return create_edit_plan(
                self._merged_analysis,
                instruction,
                llm_model=self.llm_model,
                use_llm=self.use_llm,
            )

    def _render(self, plan: EditPlan, output_path: str) -> str:
        """Render the edit plan to a video file."""
        from cutai.editor.renderer import render

        assert self._merged_analysis is not None

        # Use the first input video as source for rendering
        source = self.inputs[0] if len(self.inputs) == 1 else self._get_concat_path()
        return render(
            source,
            plan,
            self._merged_analysis,
            output_path,
            burn_subtitles=self.burn_subtitles,
        )

    def _evaluate(self, plan: EditPlan, output_path: str) -> EvaluationResult:
        """Self-evaluate the rendered output against the goal.

        Uses a combination of heuristic checks and optional LLM evaluation.
        """
        strengths: list[str] = []
        weaknesses: list[str] = []
        suggestions: list[str] = []
        score = 50.0  # Base score

        # Heuristic evaluation
        assert self._merged_analysis is not None
        source_duration = self._merged_analysis.duration
        estimated_output = plan.estimated_duration

        # 1. Duration check
        if estimated_output > 0:
            keep_ratio = estimated_output / source_duration if source_duration > 0 else 1.0
            if 0.2 <= keep_ratio <= 0.85:
                strengths.append(f"Good trim ratio ({keep_ratio:.0%} kept)")
                score += 10
            elif keep_ratio > 0.95:
                weaknesses.append("Almost nothing was cut — edit may be too conservative")
                suggestions.append("Try removing more low-energy or silent sections")
                score -= 10
            elif keep_ratio < 0.15:
                weaknesses.append("Too much was cut — result may feel rushed")
                suggestions.append("Keep more scenes to maintain narrative flow")
                score -= 10

        # 2. Operation variety check
        op_types = {type(op).__name__ for op in plan.operations}
        if len(op_types) >= 3:
            strengths.append(f"Diverse operations ({len(op_types)} types)")
            score += 10
        elif len(op_types) == 1:
            weaknesses.append("Only one type of operation applied")
            suggestions.append("Consider adding subtitles, color grading, or transitions")

        # 3. Subtitle check (most vlogs need them)
        has_subs = any(
            type(op).__name__ == "SubtitleOperation" for op in plan.operations
        )
        if has_subs:
            strengths.append("Subtitles included")
            score += 5
        else:
            suggestions.append("Consider adding subtitles for accessibility")

        # 4. Style consistency (if style was applied)
        if self._style_dna:
            strengths.append(f"Style '{self._style_dna.name}' applied")
            score += 10

        # 5. Goal keyword matching (simple heuristic)
        goal_lower = self.goal.lower()
        goal_keywords = {
            "자막": has_subs,
            "subtitle": has_subs,
            "bgm": any(type(op).__name__ == "BGMOperation" for op in plan.operations),
            "music": any(type(op).__name__ == "BGMOperation" for op in plan.operations),
            "warm": any(
                getattr(op, "preset", "") == "warm"
                for op in plan.operations
                if type(op).__name__ == "ColorGradeOperation"
            ),
            "cinematic": any(
                getattr(op, "preset", "") == "cinematic"
                for op in plan.operations
                if type(op).__name__ == "ColorGradeOperation"
            ),
        }
        matched = sum(1 for kw, present in goal_keywords.items() if kw in goal_lower and present)
        mentioned = sum(1 for kw in goal_keywords if kw in goal_lower)
        if mentioned > 0:
            match_ratio = matched / mentioned
            if match_ratio >= 0.8:
                strengths.append("Goal keywords well-addressed")
                score += 15
            elif match_ratio >= 0.5:
                score += 5
            else:
                unmatched = [kw for kw, present in goal_keywords.items() if kw in goal_lower and not present]
                if unmatched:
                    weaknesses.append(f"Missing requested features: {', '.join(unmatched)}")
                    suggestions.append(f"Add {', '.join(unmatched)} as requested")
                    score -= 5

        # Clamp score
        score = max(0.0, min(100.0, score))
        meets_goal = score >= self.min_score

        return EvaluationResult(
            score=score,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            meets_goal=meets_goal,
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    def _iter_output_path(self, iteration: int) -> str:
        """Generate output path for a specific iteration."""
        base = Path(self.output)
        return str(base.parent / f"{base.stem}_iter{iteration}{base.suffix}")

    def _get_concat_path(self) -> str:
        """Get path to concatenated video for multi-input editing."""
        # Use temp dir for concat intermediates
        import tempfile
        return str(Path(tempfile.gettempdir()) / "cutai_agent_concat.mp4")

    @staticmethod
    def _emit(callback: callable | None, step: str, detail: str) -> None:
        """Emit a progress update."""
        logger.info("[Agent/%s] %s", step, detail)
        if callback:
            callback(step, detail)
