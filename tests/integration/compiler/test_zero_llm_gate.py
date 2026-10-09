"""Compiler ordering and fail-closed Zero-LLM gate integration (C2)."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from contract_agent.compiler.models import VerificationReport
from contract_agent.compiler.orchestrator import ContractCompiler
from contract_agent.compiler.providers import MockLLMProvider
from contract_agent.compiler.verification import SandboxedVerificationRunner
from contract_agent.compiler.zero_llm_verification import ZeroLLMVerificationRunner

CONTRACT = Path("tests/fixtures/benchmarks/01_billing_dispute.contract.yaml")


@pytest.mark.parametrize("skip", [False, True])
@pytest.mark.parametrize("headless", [False, True])
def test_failing_gate_prevents_synthesis_and_testing(
    tmp_path: Path, skip: bool, headless: bool
) -> None:
    gate = ZeroLLMVerificationRunner()
    gate.run_verification = Mock(return_value=VerificationReport(passed=False, failed_tests=1))
    provider = MockLLMProvider()
    provider.generate = Mock(side_effect=AssertionError("Synthesis must not run"))
    runner = SandboxedVerificationRunner()
    runner.run_verification = Mock(side_effect=AssertionError("Synthesized tests must not run"))
    compiler = ContractCompiler(provider=provider, runner=runner, zero_llm_runner=gate)
    result = compiler.compile(
        CONTRACT, tmp_path / "dist", tmp_path / "dist/.staging",
        workspace_root=tmp_path, skip_verification=skip, headless_ci=headless,
    )
    assert not result.success
    assert not result.promoted
    assert result.zero_llm_report is not None and not result.zero_llm_report.passed
    assert result.telemetry.call_count == 0
    assert result.generated_files == []
    provider.generate.assert_not_called()
    runner.run_verification.assert_not_called()
    gate.run_verification.assert_called_once()


def test_zero_llm_gate_precedes_both_personas_and_generated_tests(tmp_path: Path) -> None:
    events: list[str] = []
    gate = ZeroLLMVerificationRunner()
    original_gate = gate.run_verification

    def verify_contract(contract):
        events.append("zero_llm")
        return original_gate(contract)

    gate.run_verification = Mock(side_effect=verify_contract)
    provider = MockLLMProvider()
    original_generate = provider.generate

    def synthesize(**kwargs):
        events.append("synthesis")
        return original_generate(**kwargs)

    provider.generate = Mock(side_effect=synthesize)
    runner = SandboxedVerificationRunner()

    def verify_generated(*args, **kwargs):
        events.append("generated_tests")
        return VerificationReport(passed=True, total_tests=1, passed_tests=1)

    runner.run_verification = Mock(side_effect=verify_generated)
    result = ContractCompiler(provider=provider, runner=runner, zero_llm_runner=gate).compile(
        CONTRACT, tmp_path / "dist", tmp_path / "dist/.staging", workspace_root=tmp_path
    )
    assert result.success
    assert events == ["zero_llm", "synthesis", "synthesis", "generated_tests"]
    assert result.zero_llm_report is not None and result.zero_llm_report.passed


def test_skip_generated_tests_still_runs_real_zero_llm_gate(tmp_path: Path) -> None:
    result = ContractCompiler(provider=MockLLMProvider()).compile(
        CONTRACT, tmp_path / "dist", tmp_path / "dist/.staging",
        workspace_root=tmp_path, skip_verification=True,
    )
    assert result.success
    assert result.zero_llm_report is not None
    assert result.zero_llm_report.passed
    assert result.zero_llm_report.total_tests > 0
    assert result.verification_report is None
