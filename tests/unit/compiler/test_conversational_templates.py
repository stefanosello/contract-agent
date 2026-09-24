"""Unit tests for conversational agent template code generation (T007)."""

from __future__ import annotations

from pathlib import Path

from contract_agent.compiler.templates import (
    generate_default_conversational_agent,
    generate_default_fsm_agent,
)
from contract_agent.core.parser import ContractParser


def test_generate_conversational_agent_syntax() -> None:
    """Verify that generated conversational agent code compiles without syntax errors."""
    fixture_path = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")
    ast = ContractParser.from_file(fixture_path)

    code = generate_default_conversational_agent(ast)
    compiled = compile(code, "<string>", "exec")
    assert compiled is not None
    assert "class BillingDisputeAgent:" in code


def test_conversational_agent_has_required_methods() -> None:
    """Assert all required conversational methods exist in generated code."""
    fixture_path = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")
    ast = ContractParser.from_file(fixture_path)

    code = generate_default_conversational_agent(ast)
    assert "async def stream(" in code
    assert "def step(" in code
    assert "def chat(" in code
    assert "def approve(" in code
    assert "def reset(" in code
    assert "def export_session(" in code
    assert "def from_session(" in code
    assert "def execute_action(" in code


def test_fsm_agent_compatibility_alias() -> None:
    """Verify generate_default_fsm_agent also provides conversational capabilities."""
    fixture_path = Path("tests/fixtures/benchmarks/02_sql_read_only_agent.contract.yaml")
    ast = ContractParser.from_file(fixture_path)

    code = generate_default_fsm_agent(ast)
    compiled = compile(code, "<string>", "exec")
    assert compiled is not None
    assert "class SqlReadOnlyAgent:" in code
    assert "async def stream(" in code
    assert "def execute_action(" in code
