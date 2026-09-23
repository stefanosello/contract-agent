"""Integration tests for User Story 2: Autonomous Self-Healing Verification Loop."""

from __future__ import annotations

from pathlib import Path

from contract_agent.compiler.orchestrator import ContractCompiler
from contract_agent.compiler.providers import MockLLMProvider
from contract_agent.compiler.templates import generate_default_fsm_agent
from contract_agent.core.parser import ContractParser


def test_self_healing_converges_after_fault_injection(tmp_path: Path) -> None:
    """Assert compiler catches defect on turn 0, repairs on turn 1, and converges."""
    contract_file = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")
    ast = ContractParser.from_file(contract_file)
    valid_agent_code = generate_default_fsm_agent(ast)

    # Buggy agent that crashes on execute_action
    buggy_agent_code = (
        'from dist.interface import AgentToolsProtocol\n'
        'from contract_agent.runtime.guards import GuardInterceptor\n'
        'class BillingDisputeAgent:\n'
        '    def __init__(self, tools, interceptor):\n'
        '        self.tools = tools\n'
        '        self.interceptor = interceptor\n'
        '        self.state = "IDLE"\n'
        '    def execute_action(self, action, **kwargs):\n'
        '        raise AssertionError("Simulated initial defect")\n'
    )

    # Fault schedule:
    # Call 0: AgentImplementer (returns buggy agent)
    # Call 1: AdversarialTester (returns default test suite)
    # Call 2: RepairSynthesizer (returns valid working agent)
    provider = MockLLMProvider(
        fault_schedule={
            0: buggy_agent_code,
            1: "# Mock test suite\n",
            2: valid_agent_code,
        }
    )

    compiler = ContractCompiler(provider=provider)
    result = compiler.compile(
        contract_path=contract_file,
        output_dir=tmp_path / "dist",
        staging_dir=tmp_path / "dist" / ".staging",
        workspace_root=tmp_path,
        max_retries=2,
    )

    assert result.success is True
    assert result.verification_report is not None
    assert result.verification_report.passed is True
    assert "RepairSynthesizer" in result.telemetry.by_persona


def test_self_healing_exhaustion_terminates_gracefully(tmp_path: Path) -> None:
    """Assert compiler terminates with failure when repair attempts exhaust retries."""
    contract_file = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")

    persistent_bad_agent = (
        'from dist.interface import AgentToolsProtocol\n'
        'from contract_agent.runtime.guards import GuardInterceptor\n'
        'class BillingDisputeAgent:\n'
        '    def __init__(self, tools, interceptor):\n'
        '        self.state = "FAILED"\n'
        '    def execute_action(self, action, **kwargs):\n'
        '        raise RuntimeError("Unfixable bug")\n'
    )

    provider = MockLLMProvider(
        default_response=persistent_bad_agent,
    )

    compiler = ContractCompiler(provider=provider)
    result = compiler.compile(
        contract_path=contract_file,
        output_dir=tmp_path / "dist",
        staging_dir=tmp_path / "dist" / ".staging",
        workspace_root=tmp_path,
        max_retries=2,
    )

    assert result.success is False
    assert "retries exhausted" in (result.error_message or "").lower()
