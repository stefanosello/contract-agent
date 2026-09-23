"""Token usage calculation, model pricing tables, and budget discipline enforcement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from contract_agent.core.exceptions import BudgetExceededError

if TYPE_CHECKING:
    from contract_agent.compiler.models import CostTelemetry

# Model pricing in USD per 1,000,000 tokens
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_name: (prompt_rate_per_1M, completion_rate_per_1M)
    "deepseek-chat": (0.14, 0.28),
    "deepseek-v3": (0.14, 0.28),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.075, 0.30),
    "mock-model": (0.0, 0.0),
    "mock": (0.0, 0.0),
}


def estimate_tokens(text: str) -> int:
    """Estimates token count from text using standard whitespace and character heuristics."""
    if not text:
        return 0
    words = len(text.split())
    char_est = len(text) // 4
    return max(words, char_est)


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model_name: str = "mock-model",
) -> float:
    """Calculates dollar expenditure for an LLM call based on model pricing."""
    norm_model = model_name.strip().lower()
    rates = MODEL_PRICING.get(norm_model)
    if rates is None:
        # Fallback to DeepSeek-V3 pricing as baseline
        rates = (0.14, 0.28)

    prompt_rate, completion_rate = rates
    cost = (prompt_tokens * (prompt_rate / 1_000_000.0)) + (
        completion_tokens * (completion_rate / 1_000_000.0)
    )
    return round(cost, 6)


def check_budget_ceiling(
    current_cost: float,
    budget_ceiling: float = 0.05,
) -> None:
    """Enforces budget discipline; raises BudgetExceededError if limit is reached."""
    if current_cost >= budget_ceiling:
        raise BudgetExceededError(
            f"Budget ceiling exceeded: Current expenditure ${current_cost:.5f} >= ceiling ${budget_ceiling:.5f}"
        )


def format_telemetry_summary(telemetry: CostTelemetry) -> str:
    """Formats cost and token telemetry into a readable console summary."""
    lines = [
        f"Calls: {telemetry.call_count}",
        f"Prompt Tokens: {telemetry.total_prompt_tokens:,}",
        f"Completion Tokens: {telemetry.total_completion_tokens:,}",
        f"Total Cost: ${telemetry.total_cost_usd:.5f}",
    ]
    if telemetry.by_persona:
        lines.append("By Persona:")
        for persona, cost in telemetry.by_persona.items():
            lines.append(f"  - {persona}: ${cost:.5f}")
    return "\n".join(lines)
