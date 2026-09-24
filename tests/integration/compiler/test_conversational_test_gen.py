"""Integration test for conversational test suite generation and simulation (T020)."""

from __future__ import annotations

from pathlib import Path

from contract_agent.compiler.orchestrator import ContractCompiler
from contract_agent.compiler.providers import MockLLMProvider


def test_conversational_test_suite_compilation_and_execution(tmp_path: Path) -> None:
    """Assert compiler synthesizes runnable conversational test suite that passes 100%."""
    contract_file = Path("tests/fixtures/benchmarks/04_conversational_service.contract.yaml")
    out_dir = tmp_path / "dist"
    staging_dir = tmp_path / "dist" / ".staging"

    compiler = ContractCompiler(provider=MockLLMProvider(), budget_ceiling=0.05)
    result = compiler.compile(
        contract_path=contract_file,
        output_dir=out_dir,
        staging_dir=staging_dir,
        workspace_root=tmp_path,
        headless_ci=True,
    )

    assert result.success is True
    assert result.verification_report is not None
    assert result.verification_report.passed is True
    assert result.verification_report.failed_tests == 0

    # Verify generated test_contract.py contains conversational scenarios and step()
    test_content = (staging_dir / "test_contract.py").read_text()
    assert "agent.step(" in test_content
    assert "agent.complete_session()" in test_content
    assert "test_adversarial_probe_invariant_enforcement" in test_content
