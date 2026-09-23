"""Interactive unified git diff review gate and artifact promotion."""

from __future__ import annotations

import difflib
import shutil
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm
from rich.syntax import Syntax

from contract_agent.compiler.isolation import validate_output_path


class ReviewGate:
    """Generates unified diffs and coordinates human or headless promotion."""

    def __init__(
        self,
        output_dir: Path,
        staging_dir: Path,
        console: Console | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.staging_dir = staging_dir
        self.console = console or Console()

    def generate_diff(self) -> str:
        """Generates unified git diff comparing staged files against target output."""
        if not self.staging_dir.exists():
            return ""

        diff_chunks: list[str] = []
        for stage_file in sorted(self.staging_dir.glob("*.py")):
            rel_name = stage_file.name
            out_file = self.output_dir / rel_name

            stage_lines = stage_file.read_text(encoding="utf-8").splitlines(keepends=True)
            if out_file.exists():
                out_lines = out_file.read_text(encoding="utf-8").splitlines(keepends=True)
                from_file = f"a/{self.output_dir.name}/{rel_name}"
            else:
                out_lines: list[str] = []
                from_file = "/dev/null"

            to_file = f"b/{self.output_dir.name}/{rel_name}"

            diff = list(
                difflib.unified_diff(
                    out_lines,
                    stage_lines,
                    fromfile=from_file,
                    tofile=to_file,
                )
            )
            if diff:
                diff_chunks.extend(diff)

        return "".join(diff_chunks)

    def display_diff(self, diff_text: str) -> None:
        """Renders colorized unified diff in terminal using Rich."""
        if not diff_text.strip():
            self.console.print("[dim]No changes detected between staging and output.[/dim]")
            return

        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
        self.console.print("\n[bold cyan]=== Proposed Candidate Unified Diff ===[/bold cyan]\n")
        self.console.print(syntax)
        self.console.print("\n[bold cyan]========================================[/bold cyan]\n")

    def promote_artifacts(self, workspace_root: Path | None = None) -> list[Path]:
        """Atomically copies verified candidate files from staging to output directory."""
        validate_output_path(self.output_dir, workspace_root=workspace_root)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        promoted: list[Path] = []
        for stage_file in self.staging_dir.glob("*.py"):
            dest = self.output_dir / stage_file.name
            validate_output_path(dest, workspace_root=workspace_root)
            shutil.copy2(stage_file, dest)
            promoted.append(dest)

        return promoted

    def prompt_and_promote(
        self,
        headless_ci: bool = False,
        confirm_callback: Callable[[], bool] | None = None,
        workspace_root: Path | None = None,
    ) -> bool:
        """Reviews and promotes candidate artifacts."""
        diff_text = self.generate_diff()

        if headless_ci:
            self.promote_artifacts(workspace_root=workspace_root)
            return True

        self.display_diff(diff_text)

        if confirm_callback is not None:
            approved = confirm_callback()
        else:
            approved = Confirm.ask(
                f"Promote verified artifacts to {self.output_dir}/?",
                default=False,
                console=self.console,
            )

        if approved:
            self.promote_artifacts(workspace_root=workspace_root)
            self.console.print(f"[bold green]✔ Successfully promoted artifacts to {self.output_dir}/[/bold green]")
            return True

        self.console.print("[yellow]Promotion aborted by developer. Staged artifacts discarded.[/yellow]")
        return False
