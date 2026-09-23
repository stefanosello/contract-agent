"""Sandboxed test verification runner executing test suites with timeouts."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from contract_agent.compiler.models import TestFailureDetail, VerificationReport


class SandboxedVerificationRunner:
    """Runs test suites in isolated subprocesses with timeouts and parses tracebacks."""

    def __init__(self, per_test_timeout: float = 10.0, total_timeout: float | None = None) -> None:
        self.per_test_timeout = per_test_timeout
        self.total_timeout = total_timeout

    def run_verification(
        self,
        test_file: Path,
        working_dir: Path,
    ) -> VerificationReport:
        """Executes pytest in a sandboxed subprocess and extracts structured diagnostics."""
        start_time = time.time()
        test_path = test_file.resolve()
        work_path = working_dir.resolve()

        # Build clean environment with PYTHONPATH pointing to working_dir and src
        env = os.environ.copy()
        current_pythonpath = env.get("PYTHONPATH", "")
        repo_root = str(Path.cwd().resolve())
        src_root = str((Path.cwd() / "src").resolve())
        env["PYTHONPATH"] = f"{work_path}:{src_root}:{repo_root}:{current_pythonpath}"

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_path),
            "-v",
            "--tb=short",
        ]

        timeout_limit = self.total_timeout or max(5.0, self.per_test_timeout * 3)

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(work_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_limit,
                check=False,
            )
            elapsed = time.time() - start_time
            raw_output = proc.stdout + "\n" + proc.stderr

            if proc.returncode == 0:
                total, passed = self._parse_pass_counts(raw_output)
                return VerificationReport(
                    passed=True,
                    total_tests=total,
                    passed_tests=passed,
                    failed_tests=0,
                    failures=[],
                    execution_time_seconds=elapsed,
                    raw_output=raw_output,
                )
            else:
                failures = self._parse_failures(raw_output)
                total, passed = self._parse_pass_counts(raw_output)
                return VerificationReport(
                    passed=False,
                    total_tests=total or len(failures),
                    passed_tests=passed,
                    failed_tests=len(failures) or 1,
                    failures=failures,
                    execution_time_seconds=elapsed,
                    raw_output=raw_output,
                )

        except subprocess.TimeoutExpired as exc:
            elapsed = time.time() - start_time
            timeout_detail = TestFailureDetail(
                test_name="execution_timeout",
                assertion_error=f"Verification exceeded timeout ceiling of {timeout_limit:.1f}s",
                traceback=str(exc),
            )
            return VerificationReport(
                passed=False,
                total_tests=1,
                passed_tests=0,
                failed_tests=1,
                failures=[timeout_detail],
                execution_time_seconds=elapsed,
                raw_output=f"TimeoutExpired: {exc}",
            )

    def _parse_pass_counts(self, output: str) -> tuple[int, int]:
        """Extracts passed and total test counts from pytest terminal output."""
        passed = 0
        failed = 0
        match_passed = re.search(r"(\d+)\s+passed", output)
        if match_passed:
            passed = int(match_passed.group(1))
        match_failed = re.search(r"(\d+)\s+failed", output)
        if match_failed:
            failed = int(match_failed.group(1))
        return passed + failed, passed

    def _parse_failures(self, output: str) -> list[TestFailureDetail]:
        """Parses failure blocks, stack traces, and CEL invariant violation markers."""
        failures: list[TestFailureDetail] = []
        # Pattern matching pytest FAILURES block like: _____ test_name _____
        fail_blocks = re.split(r"_{3,}\s+([\w\.\:\-\[\]]+)\s+_{3,}", output)
        if len(fail_blocks) > 1:
            for i in range(1, len(fail_blocks), 2):
                test_name = fail_blocks[i]
                trace = fail_blocks[i + 1] if i + 1 < len(fail_blocks) else ""

                # Extract assertion error
                assert_match = re.search(r"(?:E\s+)(.+)", trace)
                assertion_msg = assert_match.group(1) if assert_match else "Assertion failed"

                # Check for CEL invariant violations
                inv_id = None
                rule = None
                cel_match = re.search(r"Invariant\s+([A-Z0-9_-]+)\s+violated", trace)
                if cel_match:
                    inv_id = cel_match.group(1)

                failures.append(
                    TestFailureDetail(
                        test_name=test_name,
                        assertion_error=assertion_msg.strip(),
                        traceback=trace.strip(),
                        cel_invariant_id=inv_id,
                        cel_violation_rule=rule,
                    )
                )

        if not failures:
            failures.append(
                TestFailureDetail(
                    test_name="pytest_execution_failure",
                    assertion_error="Pytest exited with non-zero status",
                    traceback=output[-1000:],
                )
            )

        return failures
