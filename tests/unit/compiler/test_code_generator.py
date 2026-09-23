"""Unit tests for deterministic Protocol and Mock code generation."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from contract_agent.compiler.code_generator import (
    generate_interface_code,
    generate_mocks_code,
)
from contract_agent.core.parser import ContractParser


def test_generate_interface_billing_dispute() -> None:
    """Assert generated interface protocol contains typed signatures from contract AST."""
    fixture_path = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")
    ast = ContractParser.from_file(fixture_path)

    code = generate_interface_code(ast)
    assert "class AgentToolsProtocol(Protocol):" in code
    assert "def fetch_invoice(self, invoice_id: str) -> dict[str, Any]:" in code
    assert (
        "def execute_refund(self, invoice_id: str, amount: float, reason: str) -> dict[str, Any]:"
        in code
    )


def test_generate_mocks_billing_dispute() -> None:
    """Assert generated mock doubles track calls and satisfy interface."""
    fixture_path = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")
    ast = ContractParser.from_file(fixture_path)

    code = generate_mocks_code(ast)
    assert "class MockAgentTools(AgentToolsProtocol):" in code
    assert "def fetch_invoice(" in code
    assert "def execute_refund(" in code
    assert "self.calls.append(" in code


def test_generated_code_executability() -> None:
    """Assert generated code compiles cleanly under Python AST exec."""
    fixture_path = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")
    ast = ContractParser.from_file(fixture_path)

    interface_code = generate_interface_code(ast)
    mocks_code = generate_mocks_code(ast)

    # Compile interface
    interface_ns: dict[str, object] = {}
    exec(interface_code, interface_ns)
    agent_tools_proto = interface_ns["AgentToolsProtocol"]

    # Register mock module so import dist.interface succeeds
    fake_dist = types.ModuleType("dist")
    fake_interface = types.ModuleType("dist.interface")
    setattr(fake_interface, "AgentToolsProtocol", agent_tools_proto)
    sys.modules["dist"] = fake_dist
    sys.modules["dist.interface"] = fake_interface

    try:
        mocks_ns: dict[str, object] = {}
        exec(mocks_code, mocks_ns)
        mock_cls = mocks_ns.get("MockAgentTools")
        assert mock_cls is not None

        mock_instance = mock_cls()  # type: ignore[operator]
        res = mock_instance.fetch_invoice(invoice_id="INV-999")
        assert res == {"status": "mocked_ok"}
        assert len(mock_instance.calls) == 1
        assert mock_instance.calls[0]["args"] == {"invoice_id": "INV-999"}
    finally:
        sys.modules.pop("dist.interface", None)
        sys.modules.pop("dist", None)
