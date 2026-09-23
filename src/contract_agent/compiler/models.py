"""Data models and telemetry schemas for the ContractAgent compiler."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CompilationConfig(BaseModel):
    """Configuration options for a compiler execution run."""

    contract_path: Path
    output_dir: Path = Field(default_factory=lambda: Path("dist"))
    staging_dir: Path = Field(default_factory=lambda: Path("dist/.staging"))
    provider_name: str = "mock"
    model_name: str | None = None
    max_retries: int = 3
    budget_ceiling: float = 0.05
    per_test_timeout: float = 10.0
    headless_ci: bool = False

    model_config = ConfigDict(extra="forbid")


class LLMResponse(BaseModel):
    """Output from an LLM synthesis turn."""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    model_name: str = "mock"

    model_config = ConfigDict(extra="forbid")


class CostTelemetry(BaseModel):
    """Cumulative usage and financial telemetry across compilation turns."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
    by_persona: dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    def record_call(self, response: LLMResponse, persona: str | None = None) -> None:
        """Accumulates token counts and dollar expenses."""
        self.total_prompt_tokens += response.prompt_tokens
        self.total_completion_tokens += response.completion_tokens
        self.total_cost_usd += response.cost_usd
        self.call_count += 1
        if persona:
            self.by_persona[persona] = (
                self.by_persona.get(persona, 0.0) + response.cost_usd
            )


class TestFailureDetail(BaseModel):
    """Detailed diagnosis for a single test assertion or CEL failure."""

    test_name: str
    assertion_error: str
    traceback: str = ""
    cel_invariant_id: str | None = None
    cel_violation_rule: str | None = None
    cel_args: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class VerificationReport(BaseModel):
    """Structured report produced by the sandboxed test runner."""

    passed: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    failures: list[TestFailureDetail] = Field(default_factory=list)
    execution_time_seconds: float = 0.0
    raw_output: str = ""

    model_config = ConfigDict(extra="forbid")


class CompilationResult(BaseModel):
    """Final output and promotion status from a contract compilation run."""

    success: bool
    promoted: bool
    iterations_used: int = 0
    telemetry: CostTelemetry = Field(default_factory=CostTelemetry)
    verification_report: VerificationReport | None = None
    generated_files: list[Path] = Field(default_factory=list)
    diff_summary: str | None = None
    error_message: str | None = None

    model_config = ConfigDict(extra="forbid")
