"""Compiler orchestrator coordinating AST parsing, dual-synthesis, verification, and promotion."""

from __future__ import annotations

from pathlib import Path

from contract_agent.compiler.code_generator import (
    generate_interface_code,
    generate_mocks_code,
)
from contract_agent.compiler.isolation import (
    ensure_clean_staging_dir,
    validate_output_path,
)
from contract_agent.compiler.models import (
    CompilationResult,
    CostTelemetry,
)
from contract_agent.compiler.personas import (
    ADVERSARIAL_TESTER_SYSTEM_PROMPT,
    AGENT_IMPLEMENTER_SYSTEM_PROMPT,
    build_implementer_prompt,
    build_tester_prompt,
    extract_code_block,
)
from contract_agent.compiler.providers import LLMProvider, get_provider
from contract_agent.compiler.self_healing import SelfHealingEngine
from contract_agent.compiler.telemetry import check_budget_ceiling
from contract_agent.compiler.templates import (
    generate_default_conversational_agent,
    generate_default_test_suite,
)
from contract_agent.compiler.verification import SandboxedVerificationRunner
from contract_agent.core.parser import ContractParser


class ContractCompiler:
    """Orchestrates dual-synthesis, sandboxed verification, self-healing, and review gate promotion."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        budget_ceiling: float = 0.05,
        per_test_timeout: float = 10.0,
        runner: SandboxedVerificationRunner | None = None,
        self_healing_engine: SelfHealingEngine | None = None,
    ) -> None:
        self.provider = provider or get_provider("mock")
        self.budget_ceiling = budget_ceiling
        self.per_test_timeout = per_test_timeout
        self.runner = runner or SandboxedVerificationRunner(per_test_timeout=per_test_timeout)
        self.self_healing_engine = self_healing_engine or SelfHealingEngine(
            provider=self.provider,
            runner=self.runner,
            budget_ceiling=budget_ceiling,
        )

    def compile(
        self,
        contract_path: Path | str,
        output_dir: Path | str = Path("dist"),
        staging_dir: Path | str = Path("dist/.staging"),
        max_retries: int = 3,
        headless_ci: bool = False,
        workspace_root: Path | None = None,
        skip_verification: bool = False,
    ) -> CompilationResult:
        """Executes full dual-synthesis compilation pipeline."""
        contract_file = Path(contract_path)
        ast = ContractParser.from_file(contract_file)

        # 1. Path isolation validations
        validate_output_path(output_dir, workspace_root=workspace_root)
        stage_path = ensure_clean_staging_dir(staging_dir, workspace_root=workspace_root)

        telemetry = CostTelemetry()

        # 2. Deterministically generate Protocols and Mocks
        interface_code = generate_interface_code(ast)
        mocks_code = generate_mocks_code(ast)

        (stage_path / "interface.py").write_text(interface_code, encoding="utf-8")
        (stage_path / "mocks.py").write_text(mocks_code, encoding="utf-8")

        # 3. Dual-synthesis
        # 3a. Agent implementer persona
        imp_prompt = build_implementer_prompt(ast)
        imp_resp = self.provider.generate(
            prompt=imp_prompt,
            system_prompt=AGENT_IMPLEMENTER_SYSTEM_PROMPT,
            temperature=0.0,
        )
        telemetry.record_call(imp_resp, persona="AgentImplementer")
        check_budget_ceiling(telemetry.total_cost_usd, self.budget_ceiling)

        if self.provider.name == "mock" and (
            imp_resp.content.startswith("# Mock") or not imp_resp.content.strip()
        ):
            agent_code = generate_default_conversational_agent(ast)
        else:
            agent_code = extract_code_block(imp_resp.content)

        (stage_path / "agent.py").write_text(agent_code, encoding="utf-8")

        # 3b. Adversarial test persona
        test_prompt = build_tester_prompt(ast)
        test_resp = self.provider.generate(
            prompt=test_prompt,
            system_prompt=ADVERSARIAL_TESTER_SYSTEM_PROMPT,
            temperature=0.0,
        )
        telemetry.record_call(test_resp, persona="AdversarialTester")
        check_budget_ceiling(telemetry.total_cost_usd, self.budget_ceiling)

        if self.provider.name == "mock" and (
            test_resp.content.startswith("# Mock") or not test_resp.content.strip()
        ):
            test_code = generate_default_test_suite(ast)
        else:
            test_code = extract_code_block(test_resp.content)

        (stage_path / "test_contract.py").write_text(test_code, encoding="utf-8")

        generated_files = [
            stage_path / "interface.py",
            stage_path / "mocks.py",
            stage_path / "agent.py",
            stage_path / "test_contract.py",
        ]

        if skip_verification:
            return CompilationResult(
                success=True,
                promoted=False,
                iterations_used=0,
                telemetry=telemetry,
                generated_files=generated_files,
            )

        # 4. Self-healing verification loop
        converged, _final_code, verification_report = self.self_healing_engine.run_loop(
            contract=ast,
            staging_dir=stage_path,
            initial_agent_code=agent_code,
            test_file=stage_path / "test_contract.py",
            telemetry=telemetry,
        )

        if not converged:
            return CompilationResult(
                success=False,
                promoted=False,
                iterations_used=max_retries,
                telemetry=telemetry,
                verification_report=verification_report,
                generated_files=generated_files,
                error_message="Verification failed: Self-healing retries exhausted.",
            )

        return CompilationResult(
            success=True,
            promoted=False,
            iterations_used=1,
            telemetry=telemetry,
            verification_report=verification_report,
            generated_files=generated_files,
        )
