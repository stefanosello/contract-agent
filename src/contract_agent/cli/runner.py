"""CLI runner for interactive chat and one-shot script execution."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from contract_agent.cli.review import ReviewGate
from contract_agent.compiler.orchestrator import ContractCompiler
from contract_agent.compiler.providers import get_provider
from contract_agent.core.parser import ContractParser
from contract_agent.runtime.context import WorkflowContext
from contract_agent.runtime.conversational import BaseConversationalAgent
from contract_agent.runtime.guards import GuardInterceptor


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[name] = mod
    return mod


def load_agent(
    contract_path: Path,
    dist_dir: Path,
    provider: str = "mock",
    recompile: bool = False,
) -> BaseConversationalAgent:
    """Loads a compiled conversational agent, compiling if necessary."""
    agent_file = dist_dir / "agent.py"
    if recompile or not agent_file.exists():
        llm = get_provider(provider_name=provider)
        compiler = ContractCompiler(provider=llm)
        staging_dir = dist_dir / ".staging"
        result = compiler.compile(
            contract_path=contract_path,
            output_dir=dist_dir,
            staging_dir=staging_dir,
            headless_ci=True,
        )
        if not result.success:
            raise RuntimeError(f"Failed to compile contract: {result.error_message}")
        gate = ReviewGate(output_dir=dist_dir, staging_dir=staging_dir)
        gate.prompt_and_promote(headless_ci=True)

    mod_iface = _load_module("dist.interface", dist_dir / "interface.py")
    sys.modules["interface"] = mod_iface
    mod_mocks = _load_module("dist.mocks", dist_dir / "mocks.py")
    mod_agent = _load_module("dist.agent", agent_file)

    agent_cls: type[BaseConversationalAgent] | None = None
    for attr in dir(mod_agent):
        obj = getattr(mod_agent, attr)
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseConversationalAgent)
            and obj is not BaseConversationalAgent
        ):
            agent_cls = obj
            break

    if agent_cls is None:
        raise ValueError(f"No BaseConversationalAgent subclass found in {agent_file}")

    tools_cls: Any = getattr(mod_mocks, "MockAgentTools", None)
    if tools_cls is None:
        for attr in dir(mod_mocks):
            if attr.startswith("Mock") and attr.endswith("Tools"):
                tools_cls = getattr(mod_mocks, attr)
                break
    if tools_cls is None:
        tools_cls = object

    contract = ContractParser.from_file(contract_path)
    context = WorkflowContext()
    interceptor = GuardInterceptor(contract=contract, context=context)

    return agent_cls(tools=tools_cls(), interceptor=interceptor)


def run_command_action(
    message: str,
    contract_path: Path,
    dist_dir: Path,
    as_json: bool = False,
    provider: str = "mock",
    console: Console | None = None,
) -> int:
    """Executes a single conversational turn from bash/scripts."""
    out = console or Console()
    agent = load_agent(contract_path, dist_dir, provider=provider)
    result = agent.step(message)

    if as_json:
        payload = {
            "state": result.state.value,
            "reply": result.reply,
            "tools_executed": result.tools_executed,
            "requires_approval": result.requires_approval,
            "approval_token": result.approval_token,
        }
        out.print(json.dumps(payload, indent=2))
    else:
        out.print(f"[bold cyan]Agent [{result.state.value}]:[/bold cyan] {result.reply}")
        if result.requires_approval:
            out.print(
                f"[bold yellow]⚠️ Escalation Required![/bold yellow] Token: [bold]{result.approval_token}[/bold]"
            )
            return 3

    return 0


def chat_command_action(
    contract_path: Path,
    dist_dir: Path,
    provider: str = "mock",
    console: Console | None = None,
) -> None:
    """Runs a live interactive chat session in the terminal."""
    out = console or Console()
    contract = ContractParser.from_file(contract_path)
    agent = load_agent(contract_path, dist_dir, provider=provider)

    banner = (
        f"[bold cyan]🤖 ContractAgent Interactive Chat[/bold cyan]\n"
        f"Contract: [green]{contract.metadata.name}[/green] (v{contract.metadata.version})\n"
        f"Invariants: [yellow]{len(contract.invariants)} active guardrails[/yellow]\n\n"
        f"[dim]Special commands:[/dim]\n"
        f"  [dim]• /approve <token>[/dim]  Approve a paused escalation\n"
        f"  [dim]• /history[/dim]          View conversation message history\n"
        f"  [dim]• /reset[/dim]            Reset conversation session\n"
        f"  [dim]• /exit[/dim]             Quit session"
    )
    out.print(Panel(banner, border_style="cyan"))

    while True:
        try:
            user_input = out.input("\n[bold blue]You:[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            out.print("\n[dim]Session ended.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/exit", "exit", "quit", ":q"):
            out.print("[dim]Goodbye![/dim]")
            break
        if user_input.lower() == "/reset":
            agent.reset()
            out.print("[green]✔ Conversation session reset.[/green]")
            continue
        if user_input.lower() == "/history":
            table = Table(title="Conversation History", show_header=True)
            table.add_column("Role", style="bold")
            table.add_column("Content")
            for msg in agent.session.messages:
                table.add_row(msg.role.value, msg.content)
            out.print(table)
            continue
        if user_input.startswith("/approve"):
            parts = user_input.split()
            if len(parts) < 2:
                out.print("[red]Usage: /approve <token>[/red]")
                continue
            token = parts[1]
            res = agent.approve(token)
            out.print(f"[bold green]Agent [{agent.state.value}]:[/bold green] {res.reply}")
            continue

        result = agent.step(user_input)
        out.print(f"[bold cyan]Agent [{agent.state.value}]:[/bold cyan] {result.reply}")
        if result.requires_approval:
            out.print(
                f"[bold yellow]⚠️ Action paused requiring approval.[/bold yellow]\n"
                f"   Token: [bold]{result.approval_token}[/bold]\n"
                f"   Type:  [dim]/approve {result.approval_token}[/dim] to resume."
            )
