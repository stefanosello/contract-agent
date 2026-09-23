"""Unit tests for SandboxedVerificationRunner."""

from __future__ import annotations

from pathlib import Path

from contract_agent.compiler.verification import SandboxedVerificationRunner


def test_runner_passing_suite(tmp_path: Path) -> None:
    """Assert passing test file returns passed=True."""
    test_file = tmp_path / "test_ok.py"
    test_file.write_text(
        "def test_success():\n    assert 1 + 1 == 2\n"
    )

    runner = SandboxedVerificationRunner()
    report = runner.run_verification(test_file=test_file, working_dir=tmp_path)
    assert report.passed is True
    assert report.failed_tests == 0
    assert report.passed_tests == 1


def test_runner_failing_suite_captures_diagnostics(tmp_path: Path) -> None:
    """Assert failing test captures assertion error and stack trace."""
    test_file = tmp_path / "test_fail.py"
    test_file.write_text(
        "def test_boom():\n    assert False, 'Expected value was 42'\n"
    )

    runner = SandboxedVerificationRunner()
    report = runner.run_verification(test_file=test_file, working_dir=tmp_path)
    assert report.passed is False
    assert report.failed_tests == 1
    assert len(report.failures) == 1
    assert "Expected value was 42" in report.failures[0].assertion_error
    assert report.failures[0].test_name == "test_boom"


def test_runner_cel_invariant_parsing(tmp_path: Path) -> None:
    """Assert CEL invariant violation IDs are extracted into structured diagnostic."""
    test_file = tmp_path / "test_cel.py"
    test_file.write_text(
        "from contract_agent.core.exceptions import InvariantViolationError\n"
        "def test_invariant_breach():\n"
        "    raise InvariantViolationError('INV-999', 'Limit exceeded', 'refund', {'amount': 500})\n"
    )

    runner = SandboxedVerificationRunner()
    report = runner.run_verification(test_file=test_file, working_dir=tmp_path)
    assert report.passed is False
    assert len(report.failures) == 1
    assert report.failures[0].cel_invariant_id == "INV-999"


def test_runner_timeout_containment(tmp_path: Path) -> None:
    """Assert runaway code is terminated by per-test timeout."""
    test_file = tmp_path / "test_hang.py"
    test_file.write_text(
        "import time\n"
        "def test_infinite():\n"
        "    time.sleep(5)\n"
    )

    runner = SandboxedVerificationRunner(total_timeout=0.5)
    report = runner.run_verification(test_file=test_file, working_dir=tmp_path)
    assert report.passed is False
    assert report.failures[0].test_name == "execution_timeout"
