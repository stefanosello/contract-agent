"""Self-healing repair engine coordinating diagnostic-enriched repair turns."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contract_agent.compiler.models import CostTelemetry, VerificationReport
    from contract_agent.compiler.providers import LLMProvider
    from contract_agent.compiler.verification import SandboxedVerificationRunner
    from contract_agent.core.ast import ContractAST


class SelfHealingEngine:
    """Manages iterative repair of failing synthesized candidate agents."""

    def __init__(
        self,
        provider: LLMProvider,
        runner: SandboxedVerificationRunner,
        max_retries: int = 3,
        budget_ceiling: float = 0.05,
    ) -> None:
        self.provider = provider
        self.runner = runner
        self.max_retries = max_retries
        self.budget_ceiling = budget_ceiling

    def run_loop(
        self,
        contract: ContractAST,
        staging_dir: Path,
        initial_agent_code: str,
        test_file: Path,
        telemetry: CostTelemetry,
    ) -> tuple[bool, str, VerificationReport]:
        raise NotImplementedError("Fleshed out in US2")
