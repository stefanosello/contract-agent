"""Integration tests for User Story 1: De-correlated Dual-Synthesis Compilation."""

from __future__ import annotations

from pathlib import Path

from contract_agent.compiler.orchestrator import ContractCompiler
from contract_agent.compiler.providers import MockLLMProvider


def test_dual_synthesis_generates_all_artifacts(tmp_path: Path) -> None:
    """Assert dual-synthesis compiles contract into all 4 staged artifacts with 0 service touch."""
    contract_file = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")
    out_dir = tmp_path / "dist"
    staging_dir = tmp_path / "dist" / ".staging"

    compiler = ContractCompiler(provider=MockLLMProvider())
    result = compiler.compile(
        contract_path=contract_file,
        output_dir=out_dir,
        staging_dir=staging_dir,
        workspace_root=tmp_path,
    )

    assert result.success is True
    assert (staging_dir / "interface.py").exists()
    assert (staging_dir / "mocks.py").exists()
    assert (staging_dir / "agent.py").exists()
    assert (staging_dir / "test_contract.py").exists()

    # Verify telemetry
    assert result.telemetry.call_count == 2
    assert "AgentImplementer" in result.telemetry.by_persona
    assert "AdversarialTester" in result.telemetry.by_persona

    # Assert services/ was not touched
    assert not (tmp_path / "services").exists()


def test_dual_synthesis_artifact_contents(tmp_path: Path) -> None:
    """Assert generated artifacts contain expected classes and protocols."""
    contract_file = Path("tests/fixtures/benchmarks/02_sql_read_only_agent.contract.yaml")
    out_dir = tmp_path / "dist"
    staging_dir = tmp_path / "dist" / ".staging"

    compiler = ContractCompiler(provider=MockLLMProvider())
    result = compiler.compile(
        contract_path=contract_file,
        output_dir=out_dir,
        staging_dir=staging_dir,
        workspace_root=tmp_path,
    )

    assert result.success is True
    interface_content = (staging_dir / "interface.py").read_text()
    assert "AgentToolsProtocol" in interface_content
    assert "execute_sql" in interface_content

    agent_content = (staging_dir / "agent.py").read_text()
    assert "SqlReadOnlyAgent" in agent_content
    assert "AgentState" in agent_content
    assert "GuardInterceptor" in agent_content

    test_content = (staging_dir / "test_contract.py").read_text()
    assert "test_scenario_scen_001" in test_content
    assert "test_adversarial_probe_invariant_enforcement" in test_content
