"""Unit tests for compiler telemetry, cost calculation, and budget enforcement."""

from __future__ import annotations

import pytest

from contract_agent.compiler.models import CostTelemetry, LLMResponse
from contract_agent.compiler.providers_live import DeepSeekProvider, GeminiFlashProvider
from contract_agent.compiler.telemetry import (
    calculate_cost,
    check_budget_ceiling,
    estimate_tokens,
    format_telemetry_summary,
)
from contract_agent.core.exceptions import BudgetExceededError


def test_estimate_tokens() -> None:
    """Assert token estimation handles empty and typical text."""
    assert estimate_tokens("") == 0
    tokens = estimate_tokens("def hello_world(): return True")
    assert tokens > 0


def test_calculate_cost_deepseek() -> None:
    """Assert DeepSeek-V3 pricing matches rates."""
    # 1M prompt ($0.14) + 1M completion ($0.28) = $0.42
    cost = calculate_cost(1_000_000, 1_000_000, "deepseek-chat")
    assert pytest.approx(cost, rel=1e-4) == 0.42

    # Typical small call
    small_cost = calculate_cost(1000, 500, "deepseek-v3")
    assert small_cost < 0.001


def test_calculate_cost_gemini_flash() -> None:
    """Assert Gemini Flash pricing matches rates."""
    # 1M prompt ($0.075) + 1M completion ($0.30) = $0.375
    cost = calculate_cost(1_000_000, 1_000_000, "gemini-1.5-flash")
    assert pytest.approx(cost, rel=1e-4) == 0.375


def test_calculate_cost_mock() -> None:
    """Assert mock model is zero cost."""
    cost = calculate_cost(5000, 2000, "mock-model")
    assert cost == 0.0


def test_budget_ceiling_enforcement() -> None:
    """Assert budget ceiling passes under limit and raises when breached."""
    check_budget_ceiling(current_cost=0.01, budget_ceiling=0.05)

    with pytest.raises(BudgetExceededError, match="Budget ceiling exceeded"):
        check_budget_ceiling(current_cost=0.055, budget_ceiling=0.05)


def test_cost_telemetry_accumulation() -> None:
    """Assert CostTelemetry aggregates usage across multiple calls and personas."""
    telemetry = CostTelemetry()
    resp1 = LLMResponse(
        content="code", prompt_tokens=100, completion_tokens=50, cost_usd=0.001
    )
    resp2 = LLMResponse(
        content="test", prompt_tokens=200, completion_tokens=80, cost_usd=0.002
    )

    telemetry.record_call(resp1, persona="AgentImplementer")
    telemetry.record_call(resp2, persona="AdversarialTester")

    assert telemetry.call_count == 2
    assert telemetry.total_prompt_tokens == 300
    assert telemetry.total_completion_tokens == 130
    assert pytest.approx(telemetry.total_cost_usd, rel=1e-4) == 0.003
    assert telemetry.by_persona["AgentImplementer"] == 0.001
    assert telemetry.by_persona["AdversarialTester"] == 0.002

    summary = format_telemetry_summary(telemetry)
    assert "Calls: 2" in summary
    assert "Prompt Tokens: 300" in summary


def test_live_providers_require_api_key() -> None:
    """Assert live adapters raise ValueError if API key is not present."""
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        DeepSeekProvider(api_key="").generate("test")

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiFlashProvider(api_key="").generate("test")
