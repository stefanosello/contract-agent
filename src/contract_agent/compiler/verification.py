"""Sandboxed test verification runner executing test suites with timeouts."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contract_agent.compiler.models import VerificationReport


class SandboxedVerificationRunner:
    """Runs test suites in isolated subprocesses with timeouts."""

    def __init__(self, per_test_timeout: float = 10.0) -> None:
        self.per_test_timeout = per_test_timeout

    def run_verification(
        self,
        test_file: Path,
        working_dir: Path,
    ) -> VerificationReport:
        raise NotImplementedError("Fleshed out in US2")
