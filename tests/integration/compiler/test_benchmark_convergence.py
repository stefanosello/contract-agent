"""Convergence benchmark integration test verifying all 3 benchmark contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from contract_agent.compiler.orchestrator import ContractCompiler
from contract_agent.compiler.providers import MockLLMProvider


@pytest.mark.parametrize(
    "benchmark_filename",
    [
        "01_billing_dispute.contract.yaml",
        "02_sql_read_only_agent.contract.yaml",
        "03_api_sync_agent.contract.yaml",
    ],
)
def test_benchmark_contracts_compile_and_converge(
    tmp_path: Path, benchmark_filename: str
) -> None:
    """Assert all 3 benchmark contracts compile, verify 100%, and cost < $0.05."""
    contract_file = Path("tests/fixtures/benchmarks") / benchmark_filename
    assert contract_file.exists(), f"Benchmark fixture missing: {contract_file}"

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
    assert result.telemetry.total_cost_usd < 0.05

    # Verify all 4 required artifacts exist in staging
    assert (staging_dir / "interface.py").exists()
    assert (staging_dir / "mocks.py").exists()
    assert (staging_dir / "agent.py").exists()
    assert (staging_dir / "test_contract.py").exists()

    # Isolation check: human services directory must never be created or written
    assert not (tmp_path / "services").exists()
