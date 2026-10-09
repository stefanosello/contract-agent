"""Contract-specific, fail-closed property and mutation checks (C2)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from contract_agent.compiler.zero_llm_verification import ZeroLLMVerificationRunner
from contract_agent.core.parser import ContractParser
from contract_agent.testing.verification_probes import boundary_probes


def guarded_contract(rule: str = "args.amount <= 50"):
    return ContractParser.from_dict({
        "metadata": {"name": "boundary_agent"},
        "tools": [{"name": "credit", "description": "Credit account", "parameters": {
            "type": "object", "properties": {
                "amount": {"type": "integer"}, "resource_id": {"type": "string"}
            }
        }}],
        "invariants": [{"id": "INV-1", "target": "tool:credit", "description": "Limit",
                        "rule": rule, "on_violation": "block_tool_call"}],
    })


def test_exact_numeric_boundary_and_adjacent_probes() -> None:
    ast = guarded_contract()
    probes = boundary_probes(ast, ast.tools[0], ast.invariants[0])
    assert {49, 50, 51}.issubset({args["amount"] for args in probes})


@pytest.mark.parametrize("action", ["block_tool_call", "raise_invariant_violation", "require_escalation"])
def test_gate_checks_all_violation_actions(action: str) -> None:
    ast = guarded_contract()
    ast.invariants[0].on_violation = action
    report = ZeroLLMVerificationRunner(max_examples=10).run_verification(ast)
    assert report.passed, report.raw_output
    assert report.total_tests > 0
    assert "mutation" in report.raw_output.lower()


def test_bypassed_guard_is_detected() -> None:
    with patch("contract_agent.runtime.guards.GuardInterceptor.wrap_tool",
               side_effect=lambda name, handler: handler):
        report = ZeroLLMVerificationRunner(max_examples=5).run_verification(guarded_contract())
    assert not report.passed
    assert report.failed_tests > 0


def test_malformed_cel_fails_closed() -> None:
    ast = guarded_contract()
    ast.invariants[0].rule = "args.amount <= ("
    report = ZeroLLMVerificationRunner().run_verification(ast)
    assert not report.passed
    assert report.failures


def test_unbound_invariant_is_not_silently_skipped() -> None:
    ast = guarded_contract()
    ast.invariants[0].target = "tool:missing"
    report = ZeroLLMVerificationRunner().run_verification(ast)
    assert not report.passed
    assert "target" in report.raw_output.lower()


def test_erroring_rule_is_fail_closed_without_backend_execution() -> None:
    ast = guarded_contract()
    ast.invariants[0].rule = "args.missing_field > 0"
    report = ZeroLLMVerificationRunner(max_examples=5).run_verification(ast)
    assert not report.passed


@pytest.mark.parametrize("filename", [
    "01_billing_dispute", "02_sql_read_only_agent", "03_api_sync_agent", "04_conversational_service"
])
def test_contract_specific_gate_passes_benchmarks(filename: str) -> None:
    ast = ContractParser.from_file(Path("tests/fixtures/benchmarks") / f"{filename}.contract.yaml")
    report = ZeroLLMVerificationRunner(max_examples=10).run_verification(ast)
    assert report.passed, report.raw_output
    assert report.total_tests > 0


def test_mutation_escape_fails_even_when_property_checks_succeed() -> None:
    from contract_agent.testing.mutants import MutationReport

    with patch("contract_agent.compiler.zero_llm_verification.run_mutation_safety_suite",
               return_value=MutationReport(1, 0, 1, 1.0)):
        report = ZeroLLMVerificationRunner(max_examples=5).run_verification(guarded_contract())
    assert not report.passed
    assert "mutation" in report.raw_output.lower()
