"""ContractAgent CLI entrypoint defining contract-agent compile and review gate."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from contract_agent.cli.review import ReviewGate
from contract_agent.compiler.orchestrator import ContractCompiler
from contract_agent.compiler.providers import get_provider
from contract_agent.core.exceptions import (
    BudgetExceededError,
    ContractValidationError,
    IsolationSecurityError,
)

app = typer.Typer(
    name="contract-agent",
    help="ContractAgent: Spec-Driven Behavioral Contract & Verification Engine",
    no_args_is_help=True,
)
console = Console()


@app.command()
def compile(
    contract_path: Path = typer.Argument(..., help="Path to input agent.contract.yaml"),
    output_dir: Path = typer.Option(Path("dist"), "--output-dir", help="Directory for verified artifacts"),
    staging_dir: Path = typer.Option(Path("dist/.staging"), "--staging-dir", help="Ephemeral build directory"),
    provider: str = typer.Option("mock", "--provider", help="LLM provider: mock, gemini-flash, deepseek"),
    model: str | None = typer.Option(None, "--model", help="Model identifier override"),
    max_retries: int = typer.Option(3, "--max-retries", help="Max self-healing retry iterations"),
    budget_ceiling: float = typer.Option(0.05, "--budget-ceiling", help="Maximum budget in USD"),
    headless_ci: bool = typer.Option(False, "--headless-ci", help="Run non-interactively in CI mode"),
) -> None:
    """Compiles behavioral contract into typed protocols, mocks, FSM agent, and tests."""
    console.print(f"[bold cyan]🔨 Compiling contract:[/bold cyan] {contract_path}")

    try:
        llm = get_provider(provider_name=provider, model_name=model)
    except ValueError as exc:
        console.print(f"[bold red]Configuration Error:[/bold red] {exc}")
        sys.exit(1)

    compiler = ContractCompiler(provider=llm, budget_ceiling=budget_ceiling)

    try:
        result = compiler.compile(
            contract_path=contract_path,
            output_dir=output_dir,
            staging_dir=staging_dir,
            max_retries=max_retries,
            headless_ci=headless_ci,
        )
    except ContractValidationError as exc:
        console.print(f"[bold red]Contract Validation Error:[/bold red] {exc}")
        sys.exit(1)
    except IsolationSecurityError as exc:
        console.print(f"[bold red]Security Error:[/bold red] {exc}")
        sys.exit(5)
    except BudgetExceededError as exc:
        console.print(f"[bold red]Budget Exceeded:[/bold red] {exc}")
        sys.exit(3)

    if not result.success:
        console.print(f"[bold red]❌ Compilation failed:[/bold red] {result.error_message}")
        sys.exit(2)

    console.print("[bold green]✔ Invariant verification passed 100%.[/bold green]")
    console.print(
        f"[dim]Telemetry: {result.telemetry.total_prompt_tokens} prompt tokens, "
        f"{result.telemetry.total_completion_tokens} completion tokens, "
        f"${result.telemetry.total_cost_usd:.4f}[/dim]"
    )

    # Review Gate promotion
    gate = ReviewGate(output_dir=output_dir, staging_dir=staging_dir, console=console)
    promoted = gate.prompt_and_promote(headless_ci=headless_ci)

    if not promoted:
        sys.exit(4)

    sys.exit(0)


if __name__ == "__main__":
    app()
