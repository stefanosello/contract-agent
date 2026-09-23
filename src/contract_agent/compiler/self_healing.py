"""Autonomous self-healing engine coordinating iterative candidate repair."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from contract_agent.compiler.personas import (
    REPAIR_SYNTHESIZER_SYSTEM_PROMPT,
    build_repair_prompt,
    extract_code_block,
)
from contract_agent.core.exceptions import BudgetExceededError

if TYPE_CHECKING:
    from contract_agent.compiler.models import CostTelemetry, VerificationReport
    from contract_agent.compiler.providers import LLMProvider
    from contract_agent.compiler.verification import SandboxedVerificationRunner
    from contract_agent.core.ast import ContractAST


class SelfHealingEngine:
    """Coordinates iterative repair of failing synthesized candidate agents."""

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
        """Executes the diagnostic-enriched self-healing repair cycle.

        Returns:
            tuple[bool, str, VerificationReport]: (converged, final_code, last_report)
        """
        current_code = initial_agent_code
        last_report: VerificationReport | None = None

        for iteration in range(self.max_retries + 1):
            # 1. Execute verification in sandboxed runner
            report = self.runner.run_verification(
                test_file=test_file,
                working_dir=staging_dir,
            )
            last_report = report

            # 2. Check for convergence (100% tests passed)
            if report.passed:
                return True, current_code, report

            # 3. If tests failed and retries remain, attempt repair
            if iteration < self.max_retries:
                # Check budget constraint before making synthesis call
                if telemetry.total_cost_usd >= self.budget_ceiling:
                    raise BudgetExceededError(
                        f"Compilation aborted: Budget ceiling of ${self.budget_ceiling:.4f} exceeded (${telemetry.total_cost_usd:.4f})."
                    )

                # Formulate diagnostic repair prompt
                repair_prompt = build_repair_prompt(
                    ast=contract,
                    current_agent_code=current_code,
                    report=report,
                )

                repair_response = self.provider.generate(
                    prompt=repair_prompt,
                    system_prompt=REPAIR_SYNTHESIZER_SYSTEM_PROMPT,
                    temperature=0.0,
                )
                telemetry.record_call(repair_response, persona="RepairSynthesizer")

                # Extract and overwrite candidate agent.py
                new_code = extract_code_block(repair_response.content)
                if new_code.strip() and not new_code.startswith("# Mock"):
                    current_code = new_code
                    (staging_dir / "agent.py").write_text(current_code, encoding="utf-8")

        # Retries exhausted
        assert last_report is not None
        return False, current_code, last_report
