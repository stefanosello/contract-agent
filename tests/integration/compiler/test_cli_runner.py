"""Integration tests for contract-agent run and chat CLI commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from contract_agent.cli.main import app

runner = CliRunner()


def test_cli_run_text_output() -> None:
    """Assert contract-agent run executes a turn and outputs text."""
    contract = "tests/fixtures/benchmarks/01_billing_dispute.contract.yaml"
    res = runner.invoke(app, ["run", "Hello there!", "-c", contract])
    assert res.exit_code == 0
    assert "Agent [" in res.output
    assert "assist you" in res.output


def test_cli_run_json_output() -> None:
    """Assert contract-agent run with --json outputs valid JSON payload."""
    contract = "tests/fixtures/benchmarks/01_billing_dispute.contract.yaml"
    res = runner.invoke(app, ["run", "Please fetch invoice INV-101", "-c", contract, "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["state"] == "AWAITING_INPUT"
    assert "fetch_invoice" in data["tools_executed"]
    assert data["requires_approval"] is False


def test_cli_chat_interactive_session() -> None:
    """Assert contract-agent chat processes conversation and built-in slash commands."""
    contract = "tests/fixtures/benchmarks/01_billing_dispute.contract.yaml"
    simulated_inputs = "Hello\n/history\n/reset\n/exit\n"
    res = runner.invoke(app, ["chat", contract], input=simulated_inputs)
    assert res.exit_code == 0
    assert "ContractAgent Interactive Chat" in res.output
    assert "Conversation History" in res.output
    assert "Conversation session reset." in res.output
    assert "Goodbye!" in res.output
